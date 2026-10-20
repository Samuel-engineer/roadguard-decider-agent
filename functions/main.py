import logging
import os
import uuid
from typing import Any

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Frozen 19-name re-export contract (design section 1). Tests patch these
# attributes on this module, so the list is preserved and extended, never shrunk.
__all__ = [
    "_SAGEMAKER_RUNTIME",
    "_build_decider_questions",
    "_build_situation_questions",
    "_create_upload_request",
    "_get_media_key",
    "_invoke_decider",
    "_invoke_decider_with_client",
    "_media_metadata",
    "_parse_request",
    "_response",
    "_retrieve_knowledge",
    "_retrieve_knowledge_exam",
    "_retrieve_knowledge_situation",
    "_select_decider_options",
    "build_response",
    "decide",
    "extract_facts_from_media",
    "lambda_handler",
    "logger",
]

if __package__:
    from .core import aws
    from .core.circuits.present import build_response
    from .core.circuits.situation import (
        SITUATION_SYSTEM_VLM_PROMPT,
        SITUATION_TOOL_CONFIG,
        _build_situation_questions,
    )
    from .core.decider import (
        _build_decider_questions,
        _invoke_decider_with_client,
        _select_decider_options,
        decide,
    )
    from .core.errors import RequestError, UpstreamError
    from .core.http import _parse_request, _response
    from .core.knowledge import (
        _retrieve_knowledge,
        _retrieve_knowledge_exam,
        _retrieve_knowledge_situation,
    )
    from .core.media import (
        _get_media_key,
        _media_metadata,
        extract_facts_from_media,
    )
    from .core.uploads import _create_upload_request
else:
    from core import aws
    from core.circuits.present import build_response
    from core.circuits.situation import (
        SITUATION_SYSTEM_VLM_PROMPT,
        SITUATION_TOOL_CONFIG,
        _build_situation_questions,
    )
    from core.decider import (
        _build_decider_questions,
        _invoke_decider_with_client,
        _select_decider_options,
        decide,
    )
    from core.errors import RequestError, UpstreamError
    from core.http import _parse_request, _response
    from core.knowledge import (
        _retrieve_knowledge,
        _retrieve_knowledge_exam,
        _retrieve_knowledge_situation,
    )
    from core.media import (
        _get_media_key,
        _media_metadata,
        extract_facts_from_media,
    )
    from core.uploads import _create_upload_request

_SAGEMAKER_RUNTIME = aws._SAGEMAKER_RUNTIME


def _invoke_decider(
    facts: dict[str, Any],
    references: list[dict[str, Any]],
    request_id: str | None = None,
    **kwargs: Any,
) -> Any:
    decision, _elapsed_ms = decide(
        facts,
        references,
        _SAGEMAKER_RUNTIME,
        request_id=request_id,
        **kwargs,
    )
    return decision


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    request_context = event.get("requestContext", {})
    request_id = (
        (
            request_context.get("requestId")
            if isinstance(request_context, dict)
            else None
        )
        or getattr(context, "aws_request_id", None)
        or str(uuid.uuid4())
    )
    route = event.get("rawPath") or event.get("routeKey", "unknown")
    stage = "parse_request"
    logger.info("request_started request_id=%s route=%s", request_id, route)

    try:
        request = _parse_request(event)
        if route.rstrip("/").endswith("/uploads"):
            stage = "create_upload"
            media_type, _, content_type = _media_metadata(request)
            logger.info(
                "upload_authorization_started request_id=%s media_type=%s content_type=%s",
                request_id,
                media_type,
                content_type,
            )
            upload_request = _create_upload_request(request)
            logger.info("upload_authorization_created request_id=%s", request_id)
            return _response(200, upload_request)

        stage = "validate_media_request"
        mode = request.get("mode", "exam")
        if mode not in {"exam", "situation"}:
            raise RequestError("Mode inconnu. Utilisez exam ou situation.")
        media_type, _, content_type = _media_metadata(request)
        media_key = _get_media_key(request)
        logger.info(
            "media_analysis_started request_id=%s mode=%s media_type=%s "
            "content_type=%s s3_key=%s",
            request_id,
            mode,
            media_type,
            content_type,
            media_key,
        )
        stage = "extract_visual_facts"
        if mode == "situation":
            facts = extract_facts_from_media(
                os.environ["MEDIA_BUCKET"],
                media_key,
                media_type,
                content_type,
                "le json :",
                tool_config=SITUATION_TOOL_CONFIG,
                system_prompt=SITUATION_SYSTEM_VLM_PROMPT,
            )
        else:
            facts = extract_facts_from_media(
                os.environ["MEDIA_BUCKET"],
                media_key,
                media_type,
                content_type,
                "le json :",
            )
        logger.info("visual_facts_extracted request_id=%s", request_id)
        stage = "retrieve_knowledge"
        references = _retrieve_knowledge(facts, mode=mode)
        logger.info(
            "knowledge_retrieved request_id=%s reference_count=%d "
            "decider_state_context_chars=%d",
            request_id,
            len(references),
            sum(len(reference.get("text", "")) for reference in references),
        )
        stage = "invoke_decider"
        remaining_time = getattr(context, "get_remaining_time_in_millis", None)
        remaining_ms = remaining_time() if callable(remaining_time) else None
        logger.info(
            "decider_stage_started request_id=%s remaining_lambda_ms=%s",
            request_id,
            remaining_ms if remaining_ms is not None else "unknown",
        )
        decision, elapsed_ms = decide(
            facts,
            references,
            _SAGEMAKER_RUNTIME,
            request_id=request_id,
            mode=mode,
        )
        logger.info("media_analysis_completed request_id=%s", request_id)

        return _response(
            200,
            build_response(mode, facts, references, decision, media_key, elapsed_ms),
        )
    except RequestError as error:
        logger.warning(
            "request_rejected request_id=%s route=%s stage=%s status_code=%d reason=%s",
            request_id,
            route,
            stage,
            error.status_code,
            error,
        )
        return _response(
            error.status_code,
            {
                "error": str(error),
                "code": "request_error",
                "request_id": request_id,
            },
        )
    except UpstreamError as error:
        logger.exception(
            "upstream_failure request_id=%s route=%s stage=%s",
            request_id,
            route,
            stage,
        )
        return _response(
            502,
            {
                "error": str(error),
                "code": "upstream_error",
                "request_id": request_id,
            },
        )
    except Exception:
        logger.exception(
            "request_failed request_id=%s route=%s stage=%s",
            request_id,
            route,
            stage,
        )
        return _response(
            500,
            {
                "error": (
                    "Échec interne du traitement. Consultez les logs avec "
                    "l’identifiant de requête."
                ),
                "code": "internal_error",
                "request_id": request_id,
            },
        )

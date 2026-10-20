import json
import logging
import os
import time
from typing import Any

from .errors import UpstreamError

logger = logging.getLogger()


def _build_decider_questions(
    facts: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    question_type = facts.get("question_type")
    if question_type not in {"single_choice", "multiple_choice"}:
        raise UpstreamError(
            f"Le modèle visuel a renvoyé un question_type non pris en charge : "
            f"{question_type!r}."
        )

    sub_questions = facts.get("sub_questions")
    if not isinstance(sub_questions, list) or not sub_questions:
        raise UpstreamError("Le modèle visuel n'a renvoyé aucune sous-question.")

    questions: dict[str, dict[str, Any]] = {}
    question_metadata: dict[str, dict[str, Any]] = {}
    for index, sub_question in enumerate(sub_questions, start=1):
        if not isinstance(sub_question, dict):
            raise UpstreamError(
                f"La sous-question {index} renvoyée par le modèle visuel est invalide."
            )
        text = sub_question.get("text")
        candidates = sub_question.get("candidates")
        if not isinstance(text, str) or not text.strip():
            raise UpstreamError(
                f"La sous-question {index} renvoyée par le modèle visuel n'a pas de texte."
            )
        if not isinstance(candidates, list) or not candidates:
            raise UpstreamError(
                f"La sous-question {index} renvoyée par le modèle visuel n'a pas d'options."
            )

        candidates_by_label: dict[str, dict[str, str | None]] = {}
        for candidate in candidates:
            if not isinstance(candidate, dict):
                raise UpstreamError(
                    f"La sous-question {index} contient une option invalide."
                )
            label = candidate.get("label")
            candidate_id = candidate.get("id")
            if not isinstance(label, str) or not label.strip():
                raise UpstreamError(
                    f"La sous-question {index} contient une option sans libellé."
                )
            label = label.strip()
            normalized_id = (
                candidate_id.strip().upper()
                if isinstance(candidate_id, str) and candidate_id.strip()
                else None
            )
            candidates_by_label[label] = {
                "id": normalized_id,
                "label": label,
            }

        if len(candidates_by_label) != len(candidates):
            raise UpstreamError(
                f"La sous-question {index} contient des libellés d'options dupliqués."
            )
        if len(candidates_by_label) < 2:
            raise UpstreamError(
                f"La sous-question {index} doit avoir au moins deux options."
            )

        question_key = str(index)
        labels = list(candidates_by_label)
        yes_label = next(
            (label for label in labels if label.casefold() == "oui"),
            None,
        )
        no_label = next(
            (label for label in labels if label.casefold() == "non"),
            None,
        )
        if len(labels) == 2 and yes_label is not None and no_label is not None:
            wire_question = {
                "type": "noul",
                "instructions": text.strip(),
                "criteria": {
                    "true": f"La réponse « {yes_label} » est correcte.",
                    "false": f"La réponse « {no_label} » est correcte.",
                },
            }
            mode = "binary"
        else:
            wire_question = {
                "type": "choice",
                "instructions": text.strip(),
                "criteria": {
                    label: (f"Candidat {candidate['id']}" if candidate["id"] else label)
                    for label, candidate in candidates_by_label.items()
                },
            }
            mode = question_type

        questions[question_key] = wire_question
        question_metadata[question_key] = {
            "mode": mode,
            "candidates": candidates_by_label,
        }
    return questions, question_metadata


def _select_decider_options(
    decision: Any,
    question_metadata: dict[str, dict[str, Any]],
) -> Any:
    if not isinstance(decision, dict):
        raise UpstreamError("Le Decider a renvoyé une réponse invalide.")
    answers = decision.get("answers")
    if not isinstance(answers, dict):
        raise UpstreamError("Le Decider n'a pas renvoyé d'objet « answers » valide.")

    for question_key, metadata in question_metadata.items():
        answer = answers.get(question_key)
        if not isinstance(answer, dict):
            raise UpstreamError(
                f"Le Decider n'a pas renvoyé la réponse à la question {question_key}."
            )

        candidates = metadata["candidates"]
        labels = list(candidates)
        mode = metadata["mode"]
        if mode == "binary":
            probability = answer.get("noul")
            if (
                answer.get("type") != "noul"
                or isinstance(probability, bool)
                or not isinstance(probability, (int, float))
                or not 0 <= probability <= 1
            ):
                raise UpstreamError(
                    f"Le Decider a renvoyé une probabilité binaire invalide "
                    f"pour la question {question_key}."
                )
            selected_label = (
                next(label for label in labels if label.casefold() == "oui")
                if probability >= 0.5
                else next(label for label in labels if label.casefold() == "non")
            )
            answer["threshold"] = 0.5
            answer["selected_options"] = [selected_label]
        else:
            probabilities = answer.get("probabilities")
            if (
                answer.get("type") != "choice"
                or not isinstance(probabilities, dict)
                or set(probabilities) != set(labels)
            ):
                raise UpstreamError(
                    f"Le Decider a renvoyé des probabilités option-réponse "
                    f"invalides pour la question {question_key}."
                )
            for label, probability in probabilities.items():
                if (
                    isinstance(probability, bool)
                    or not isinstance(probability, (int, float))
                    or not 0 <= probability <= 1
                ):
                    raise UpstreamError(
                        f"Le Decider a renvoyé une probabilité invalide pour "
                        f"l'option {label!r} de la question {question_key}."
                    )

            if mode == "multiple_choice":
                threshold = 1 / len(labels)
                selected_options = [
                    label for label in labels if probabilities[label] >= threshold
                ]
                answer["threshold"] = threshold
            else:
                selected_label = answer.get("choice")
                if selected_label not in candidates:
                    raise UpstreamError(
                        f"Le Decider a sélectionné une option inconnue pour "
                        f"la question {question_key}."
                    )
                selected_options = [selected_label]
            answer["selected_options"] = selected_options
    return decision


def _invoke_decider_with_client(
    facts: dict[str, Any],
    references: list[dict[str, Any]],
    runtime_client: Any,
    *,
    request_id: str | None = None,
) -> Any:
    rag_context = "\n".join(reference.get("text", "") for reference in references)
    state_content = (
        f"Observations : {json.dumps(facts, ensure_ascii=False)}\n"
        f"Documentation : {rag_context}"
    )

    questions, question_metadata = _build_decider_questions(facts)
    payload = {
        "state": state_content,
        "questions": questions,
    }
    request_body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    endpoint_name = os.environ["DECIDER_ENDPOINT"]
    logger.info(
        "decider_invoke_started request_id=%s endpoint=%s payload_bytes=%d "
        "question_count=%d state_chars=%d",
        request_id or "unknown",
        endpoint_name,
        len(request_body),
        len(questions),
        len(state_content),
    )
    started_at = time.monotonic()
    try:
        response = runtime_client.invoke_endpoint(
            EndpointName=endpoint_name,
            ContentType="application/json",
            Accept="application/json",
            Body=request_body,
        )

        logger.info(response)
    except Exception:
        logger.exception(
            "decider_invoke_failed request_id=%s endpoint=%s elapsed_ms=%d",
            request_id or "unknown",
            endpoint_name,
            round((time.monotonic() - started_at) * 1000),
        )
        raise
    logger.info(
        "decider_invoke_completed request_id=%s endpoint=%s elapsed_ms=%d",
        request_id or "unknown",
        endpoint_name,
        round((time.monotonic() - started_at) * 1000),
    )
    raw_body = response["Body"].read()
    logger.info(
        "decider_response_received request_id=%s response_bytes=%d",
        request_id or "unknown",
        len(raw_body),
    )
    try:
        decision = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise UpstreamError(
            "Le Decider a renvoyé une réponse qui n'est pas un JSON valide."
        ) from error
    return _select_decider_options(decision, question_metadata)

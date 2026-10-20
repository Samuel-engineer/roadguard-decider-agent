import os
import re
from typing import Any

from botocore.exceptions import ClientError

from .aws import _BEDROCK_RUNTIME, _S3
from .circuits.exam import (
    EXAM_JSON_SCHEMA,
    EXAM_SYSTEM_VLM_PROMPT,
    EXAM_TOOL_CONFIG,
)
from .errors import RequestError

_MAX_MEDIA_BYTES = 4 * 1024 * 1024
_SUPPORTED_MEDIA = {
    "image/jpeg": ("image", "jpg"),
    "image/png": ("image", "png"),
    "image/gif": ("image", "gif"),
    "image/webp": ("image", "webp"),
    "video/mp4": ("video", "mp4"),
    "video/mpeg": ("video", "mpeg"),
    "video/quicktime": ("video", "mov"),
    "video/webm": ("video", "webm"),
    "video/x-matroska": ("video", "mkv"),
}
_S3_KEY_PATTERN = re.compile(r"^[^\x00]+$")

# Back-compat re-exports (existing importers expect these names on media).
json_schema = EXAM_JSON_SCHEMA
tool_config = EXAM_TOOL_CONFIG
SYSTEM_VLM_PROMPT = EXAM_SYSTEM_VLM_PROMPT


def _media_metadata(request: dict[str, Any]) -> tuple[str, str, str]:
    content_type = request.get("content_type")
    if not isinstance(content_type, str):
        raise RequestError("Le champ 'content_type' est requis.")
    content_type = content_type.split(";", 1)[0].strip().lower()

    supported = _SUPPORTED_MEDIA.get(content_type)
    if supported is None:
        raise RequestError(
            "Format non pris en charge. Utilisez une image JPEG, PNG, GIF ou WebP "
            "ou une vidéo MP4, MPEG, MOV, WebM ou MKV."
        )

    media_type, extension = supported
    requested_type = request.get("media_type")
    if requested_type is not None and requested_type != media_type:
        raise RequestError("'media_type' ne correspond pas à 'content_type'.")
    return media_type, extension, content_type


def _get_media_key(request: dict[str, Any]) -> str:
    s3_key = request.get("s3_key")
    if (
        not isinstance(s3_key, str)
        or not s3_key
        or len(s3_key) > 1024
        or _S3_KEY_PATTERN.fullmatch(s3_key) is None
        or not s3_key.startswith("requests/")
    ):
        raise RequestError(
            "'s3_key' doit être une clé valide retournée par POST /uploads."
        )
    return s3_key


def _read_image(bucket: str, key: str) -> bytes:
    try:
        response = _S3.get_object(Bucket=bucket, Key=key)
    except ClientError as error:
        error_code = error.response.get("Error", {}).get("Code")
        if error_code in {"NoSuchKey", "NotFound"}:
            raise RequestError(
                "Fichier introuvable dans le bucket média. Vérifiez la clé S3 "
                "et confirmez que le téléversement a réussi.",
                status_code=404,
            ) from error
        raise
    body = response["Body"]
    try:
        image_bytes = body.read(_MAX_MEDIA_BYTES + 1)
    finally:
        body.close()
    if len(image_bytes) > _MAX_MEDIA_BYTES:
        raise RequestError("L'image dépasse la limite de 4 Mio.", status_code=413)
    return image_bytes


def extract_facts_from_media(
    bucket: str,
    media_key: str,
    media_type: str = "image",
    content_type: str = "image/jpeg",
    prompt: str | None = None,
    model_id: str | None = None,
    *,
    tool_config: dict[str, Any] = EXAM_TOOL_CONFIG,
    system_prompt: str = EXAM_SYSTEM_VLM_PROMPT,
) -> dict[str, Any]:
    """Analyse un média S3 avec Bedrock et renvoie les faits structurés."""
    model_id = model_id or os.environ.get("VISION_MODEL_ID", "us.amazon.nova-lite-v1:0")
    normalized_format = content_type.split("/", 1)[-1].lower()
    if normalized_format in ("jpg", "pjpeg"):
        normalized_format = "jpeg"

    prompt_text = system_prompt
    if prompt:
        prompt_text += f"\n{prompt}"

    content: list[dict[str, Any]] = [{"text": prompt_text}]
    if media_type == "video":
        content.append(
            {
                "video": {
                    "format": normalized_format,
                    "source": {"s3Location": {"uri": f"s3://{bucket}/{media_key}"}},
                }
            }
        )
    else:
        image_bytes = _read_image(bucket, media_key)
        content.append(
            {
                "image": {
                    "format": normalized_format,
                    "source": {"bytes": image_bytes},
                }
            }
        )

    response = _BEDROCK_RUNTIME.converse(
        modelId=model_id,
        messages=[{"role": "user", "content": content}],
        inferenceConfig={
            "maxTokens": 1000,
            "temperature": 0.0,
            "topP": 0.9,
        },
        toolConfig=tool_config,
    )

    message_content = response.get("output", {}).get("message", {}).get("content", [])
    tool_use = next(
        (block["toolUse"] for block in message_content if "toolUse" in block), None
    )
    if not tool_use:
        raise RuntimeError("Le modèle n'a pas retourné de structure via toolUse.")
    return tool_use["input"]

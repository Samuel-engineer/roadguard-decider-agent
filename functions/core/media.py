import os
import re
from typing import Any

from botocore.exceptions import ClientError

from .aws import _BEDROCK_RUNTIME, _S3
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

json_schema = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
        "question_type": {
            "type": "string",
            "enum": ["single_choice", "multiple_choice", "unknown"],
        },
        "scene_summary": {
            "type": "string",
            "maxLength": 500,
            "description": "Décris la situation physique visible sur la route sans interprétation",
        },
        "keywords": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
            "maxItems": 10,
        },
        "sub_questions": {
            "type": "array",
            "description": "Liste des questions ou assertions posées sur l'image.",
            "minItems": 1,
            "maxItems": 4,
            "items": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Énoncé complet de la question ou de l'assertion.",
                    },
                    "candidates": {
                        "type": "array",
                        "minItems": 2,
                        "maxItems": 4,
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {
                                    "type": "string",
                                    "description": "Lettre identifiant le choix (ex: A, B, C, D).",
                                },
                                "label": {
                                    "type": "string",
                                    "description": "Texte brut de l'option d'une assertion (ex: OUI, NON, Je dois m'arreter au feu rouge).",
                                },
                            },
                            "required": ["id", "label"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["text", "candidates"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["question_type", "scene_summary", "keywords", "sub_questions"],
    "additionalProperties": False,
}

tool_config = {
    "tools": [
        {
            "toolSpec": {
                "name": "extract_road_data",
                "description": "Enregistre l'analyse structurée de la scène routière.",
                "inputSchema": {"json": json_schema},
            }
        }
    ],
    "toolChoice": {"tool": {"name": "extract_road_data"}},
}

SYSTEM_VLM_PROMPT = """Tu es le Moteur de Perception Visuelle de RoadGuard-Decider, un agent d'assistance à la conduite et d'évaluation réglementaire du Code de la route.

TON OBJECTIF :
Analyser l'image de conduite fournie et renseigner rigoureusement l'outil structuré `extract_road_data`.

- RÈGLE FONDAMENTALE :
  * Chaque lettre visible à l'écran (A, B, C, D) correspond à UN UNIQUE candidat dans le JSON.
  * Si l'image comporte 4 lettres au total (A, B, C, D), la somme des candidats de toutes les `sub_questions` doit faire EXACTEMENT 4.
  * Détermine le `label` en lisant le texte relié à la lettre :
    - Si la ligne contient du texte suivi de la lettre (ex: "les roues risquent de se bloquer.... A"), le label de A est "les roues risquent de se bloquer".
    - Si la ligne contient un mot binaire suivi de la lettre (ex: "OUI.... C"), le label de C est "OUI".
  * Ne colle JAMAIS le texte de l'option A ou de l'option B à l'intérieur de `text`. Le texte de la proposition va exclusivement dans `candidates[].label`.

  RÈGLE D'OBJECTIVITÉ DU RÉSUMÉ (scene_summary) :
  - Décris UNIQUEMENT la situation physique visible sur la route (panneaux réels et couleurs, signes, marquages, usagers, environnement) sans interprétation.
  - N'UTILISE PAS le texte de la question du QCM pour composer `scene_summary`.
  - Langue obligatoire : l'ensemble des champs (`scene_summary`, `keywords`, `text`, `label`) doit être rédigé STRICTEMENT en français en respectant la nomenclature officielle.
"""


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
) -> dict[str, Any]:
    """Analyse un média S3 avec Bedrock et renvoie les faits structurés."""
    model_id = model_id or os.environ.get("VISION_MODEL_ID", "us.amazon.nova-lite-v1:0")
    normalized_format = content_type.split("/", 1)[-1].lower()
    if normalized_format in ("jpg", "pjpeg"):
        normalized_format = "jpeg"

    prompt_text = SYSTEM_VLM_PROMPT
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

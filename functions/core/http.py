import base64
import binascii
import json
from typing import Any

from .errors import RequestError


def _response(status_code: int, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {
            "content-type": "application/json",
            "cache-control": "no-store",
        },
        "body": json.dumps(payload, ensure_ascii=False),
    }


def _parse_request(event: dict[str, Any]) -> dict[str, Any]:
    body = event.get("body")
    if not isinstance(body, str):
        raise RequestError("Le corps de la requête doit être un objet JSON.")

    if event.get("isBase64Encoded"):
        try:
            body = base64.b64decode(body, validate=True).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError) as error:
            raise RequestError("Le corps encodé en base64 n'est pas valide.") from error

    try:
        request = json.loads(body)
    except json.JSONDecodeError as error:
        raise RequestError(
            "Le corps de la requête doit être un JSON valide."
        ) from error

    if not isinstance(request, dict):
        raise RequestError("Le corps JSON doit être un objet.")
    return request

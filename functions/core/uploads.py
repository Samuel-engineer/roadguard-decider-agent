import os
import uuid
from typing import Any

from .aws import _S3
from .media import _media_metadata

_MAX_PRESIGNED_UPLOAD_BYTES = 100 * 1024 * 1024


def _create_upload_request(request: dict[str, Any]) -> dict[str, Any]:
    media_type, extension, content_type = _media_metadata(request)
    key = f"requests/{uuid.uuid4().hex}.{extension}"
    presigned_post = _S3.generate_presigned_post(
        Bucket=os.environ["MEDIA_BUCKET"],
        Key=key,
        Fields={"Content-Type": content_type},
        Conditions=[
            {"Content-Type": content_type},
            ["content-length-range", 1, _MAX_PRESIGNED_UPLOAD_BYTES],
        ],
        ExpiresIn=300,
    )
    return {
        "upload_method": "POST",
        "upload_url": presigned_post["url"],
        "fields": presigned_post["fields"],
        "s3_key": key,
        "content_type": content_type,
        "media_type": media_type,
        "max_size_bytes": _MAX_PRESIGNED_UPLOAD_BYTES,
        "expires_in_seconds": 300,
    }

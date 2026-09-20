import hashlib
import json
from datetime import UTC

from .contracts import HandoverSubmissionRequest


def submission_fingerprint(
    request: HandoverSubmissionRequest,
) -> str:
    canonical_request = {
        "operation": "handover.submit.v1",
        "resident_id": str(request.resident_id),
        "shift_start": request.shift_start.astimezone(UTC).isoformat(),
        "shift_end": request.shift_end.astimezone(UTC).isoformat(),
    }

    encoded = json.dumps(
        canonical_request,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()


"""Run both synthetic agents against a separately started local API."""

import json
from urllib.request import Request, urlopen

from intelligence.config import Settings

settings = Settings()
for agent_id in ("resident_history", "handover_draft"):
    request = Request(
        "http://127.0.0.1:8100/v1/runs",
        data=json.dumps(
            {
                "agent_id": agent_id,
                "resident_id": "30000000-0000-0000-0000-000000000001",
                "period": {"start": "2026-09-08T00:00:00+01:00", "end": "2026-09-09T00:00:00+01:00"},
            }
        ).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + settings.demo_token.get_secret_value(),
        },
    )
    with urlopen(request, timeout=10) as response:
        print(json.dumps(json.load(response), indent=2))

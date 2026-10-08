# OpenAI runtime provider

The worker and legacy `/v1/runs` endpoint now use OpenAI. Deterministic providers
live in `tests/support` only; there is no runtime fake selection or fallback.
The legacy endpoint still retrieves synthetic fluid fixtures, not live history.

Set these in the intelligence-service environment (never commit the actual key):

```dotenv
INTELLIGENCE_PROVIDER=openai
INTELLIGENCE_HANDOVER_PROVIDER=openai
OPENAI_API_KEY=<local secret>
OPENAI_MODEL=gpt-6.1-sol
OPENAI_TIMEOUT_SECONDS=25
OPENAI_MAX_OUTPUT_TOKENS=4096
```

Replace any existing `fake` setting; restart API and workers after configuration
changes. Existing `.env` secrets are not modified by this implementation.
`OPENAI_MODEL` can override the default. Availability must be verified for the
account. Missing credentials or unsupported provider settings fail generation;
they do not fall back to synthetic output. Readiness probes test the database,
not external model availability.

## Flow and extension point

Worker → `providers/runtime.py` → handover provider protocol → OpenAI adapter.
The gateway still prepares and validates every payload and validates all returned
claims. The client is created/closed inside the execution event loop, including
on failure. Worker model and prompt metadata come from that same runtime selection.
SDK retries are disabled to avoid stacking retries with future job retry policies.
Requests use `store=False`; this alone does not establish zero provider retention.

For hybrid routing, extend `open_provider_runtime` with a trusted use-case policy
and another adapter implementing the existing protocol. Route before generation,
record the chosen provider/model, and preserve the gateway on every route. Hybrid
routing and automatic fallback are not implemented yet.

## Current limits

Handover claims now use supported-prose-v2: trusted code supplies readable,
evidence-backed sentences and the model must preserve their text and citations.
All evidence and sourced metrics remain represented. Unrestricted paraphrasing is
still rejected. See [readable prose](handover-readable-prose.md). Free-text privacy
policy remains fail-closed; wiring OpenAI does not
approve raw care notes for external transmission. A live synthetic smoke test and
clinical evaluation remain necessary. No paid calls were made during this change.

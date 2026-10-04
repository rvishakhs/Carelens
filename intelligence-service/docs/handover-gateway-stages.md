# Handover gateway: stages 8.3–8.8

These components are called by the `HandoverGateway.generate` orchestration (8.9). No external provider, database, worker or scheduler is invoked by
the stage tests.

## Data flow

1. `prepare_handover(input=..., text_policy=...)` detaches the input from mutable
   caller dictionaries and validates tenant/resident scope, time grouping and metrics.
2. It renders allowlisted fields, assigns request-local aliases, and applies the
   text policy to every source string. Numbers and booleans retain their types.
3. It builds metric aliases with source references, controlled outbound warnings,
   and a bounded `HandoverPayload`. Outbound validation checks schema, identities,
   metric references, temporal compatibility and byte/output budgets.
4. A provider receives **only** `prepared.payload`, never the PreparedHandover wrapper,
   execution context, original evidence or alias mappings.
5. `validate_inbound_output` validates resident, citations, category/context, limits,
   omissions and deterministic support.
6. `resolve_handover(prepared=..., output=...)` revalidates internal consistency,
   checks alias bindings and resolves citations to authorised SourceRefs. It returns
   sectioned `ValidatedHandoverContent` and independently preserved warnings.

## Intentional initial restrictions

`ReviewedTextPolicy` rejects every source string unless it has an exact, trusted,
reviewed minimised replacement. The empty default blocks unreviewed free text. This
is a fail-closed manual privacy boundary, **not automatic PII detection**. Identifier
regex checks are defence in depth, not a guarantee of anonymity. Do not construct
replacement approvals from client-supplied maps or model output. Never enable an
identity/passthrough policy for unreviewed real data. Examples using unchanged text
are for reviewed synthetic fixtures only.

The initial output support policy is extractive. Every source must receive a claim
with its supplied time qualifier and exact prepared content; supported metrics use
fixed wording. All supplied evidence and supported metrics must be retained. This
blocks arbitrary paraphrases, inferred diagnoses, fabricated times and misleading
metric totals. It is intentionally not a polished narrative summariser. Clinical
accuracy of original records and appropriateness of reviewed replacements still
need human evaluation. Glenrose's narrative evaluations have not been run here.

Date/unknown-time context and quality warnings survive independently of provider
output. Raw retrieval warnings remain internal; controlled notices are sent instead.
Resident identity stays in trusted draft metadata. Source aliases are resolved, but
no global string replacement inserts names into generated prose.

## Next step: 8.9

Implement orchestration around these functions with explicit provider injection,
bounded invocation time, sanitised error translation, cancellation handling and no
raw-data fallback. Validate output and resolve it before returning anything to the
caller. Keep request state local. Real-provider integration, automatic text privacy,
persistence and review/finalisation are separate acceptance gates.

Step 8.9 now lives in `gateway/handover.py`. Provider implementations have moved to
`providers/`. API startup uses fake adapters while external-provider configuration
is incomplete; no credentials are required by the offline test suite.

## Verification

From intelligence-service:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest --noconftest -p no:cacheprovider \
  tests/unit/gateway tests/unit/handover tests/unit/connectors -q
```

Result at implementation: 204 passed. New cases cover stage composition, private
warnings, blocked source text, reviewed replacements, fabricated/duplicate citations,
metric references, temporal/category errors, unsupported claims, omissions, mapping
changes, independent concurrent requests, size limits and empty evidence. Database
and external-provider tests were not run.

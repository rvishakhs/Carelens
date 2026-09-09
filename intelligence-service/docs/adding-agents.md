# Adding agents and future features

## What an agent means here

An agent is a bounded capability with a typed input/output, explicit permission, controlled dependencies and evaluation cases. It does not own a database connection to CareLens, mint its own authority, choose arbitrary external tools or call a model SDK directly.

The shared platform supplies identity, scoped evidence, gateway, durable execution (later), telemetry and budgets. Care-specific semantics live in care-domain logic. As more domains appear, move care workflows under `domains/care/` while keeping generic contracts in `core/`; do not make core depend on CareLens tables.

## Add one capability

1. Write its purpose, source allowlist, permitted recipients, read/write behaviour and human-review requirement. Add synthetic success, missing-data, access-denial and failure cases first.
2. Introduce a versioned typed request/result if the existing `RunRequest` is insufficient. Add an allowlisted `AgentId`; unknown IDs must fail validation.
3. Implement the `Agent` protocol in `agents/`, with a unique ID and required permission. Use `AgentContext.reader` and `.gateway`; do not import `app`, provider SDKs or secret settings.
4. Register it in `default_registry()`. The API catalogue derives from that registry. Add permission checks at the agent boundary and current result reads; extend production identity grants explicitly when that adapter exists.
5. Extend the gateway's typed operation contract for new model tasks; keep raw identity/mapping control inside the gateway. Do not force new data into the fluid-only demo payload.
6. Add a workflow only when durable retries, multiple activities, scheduling or human wait states are needed. Keep non-deterministic model calls in activities, not workflow replay logic.
7. Add typed action proposals for writes. CareLens commands enforce authority and nurse-in-charge sign-off; an agent response cannot mark a clinical record final.
8. Run the isolated tests, role/scope/gateway cases and affected pilot evaluations; record agent/prompt/model versions before rollout.

The enum/registry changes are deliberate review points, not dynamic loading of arbitrary user code. Once there are many agents, use a declarative manifest validated on startup, not runtime `eval` or unreviewed plugin imports.

## Example implementation shape

```python
class ActivitySummaryAgent:
    agent_id = AgentId.ACTIVITY_SUMMARY  # add this allowlisted enum member
    permission = "activities:analyse"

    async def run(self, scope, request, context):
        require_access(scope, request.resident_id, self.permission)
        evidence = await context.reader.retrieve(scope, request.resident_id, request.period)
        # Filter allowed activity sources; check coverage and scope.
        # Calculate counts in trusted code; never ask a model to invent totals.
        # Call the gateway's new typed activity-summary operation.
        # Return typed cited results with source versions and coverage warnings.
```

This sketch is not a drop-in implementation: add the enum, gateway operation, source semantics and result contract together. The existing `CareAgent` is the runnable reference for dependency injection and scoped evidence checks.

## Feature expansion map

| Feature | Reuses | Additional capability required before enabling |
|---|---|---|
| Resident enquiry | Scope, evidence reader, gateway, results | Complete CareLens history, question parsing, hybrid retrieval, citations and free-text protection |
| Handover | Evidence, metrics, gateway, versions | Shift roster, original/final storage, nurse-in-charge review API and amendment tracking |
| Nutrition/hydration/activity/mood/sleep analytics | Structured projections, evidence, permissions | Clinically agreed metric definitions, offer/consumption linkage, time buckets and coverage; charts should use deterministic values |
| Deterioration/behaviour-change detection | Longitudinal evidence, metrics | Approved intended use, validated baselines/thresholds, false-positive/negative assessment, clinical oversight and escalation workflow |
| Remember commitments/appointments | Extraction, proposals, gateway | Authoritative task/appointment APIs, staff confirmation, identity/owner resolution, durable timers and cancellation |
| Family summaries | Cited drafts, review | Consent/relationship enforcement, per-recipient disclosure policy and reviewed sending |
| Clinician email sync/drafts | Connector ports, gateway, proposals | Scoped mailbox access, attachment policy, incremental sync, recipient validation and explicit send permission |
| Voice recording | Gateway, proposals, care commands | Speech provider/region assessment, audio retention, transcript review, field validation and idempotent recording |
| Wound vision | Evidence lineage and later media adapters | Governed images, quality/measurement protocol, intended-use assessment and image-specific validation; outside first pilot |

Add one feature track at a time. A larger agent count is not a substitute for complete evidence, explicit authority and tested workflows.

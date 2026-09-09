# CareLens intelligence implementation plan

Status: roadmap in progress. The independently packaged [intelligence-service skeleton](../intelligence-service/README.md) now implements a synthetic-only API/agent/gateway path. Live integration, durable storage/workflows and real-data activation remain future milestones.

Created: 8 September 2026.

## 1. Target outcome

Build an independently deployable intelligence platform that connects to CareLens through versioned APIs and durable events. CareLens remains the source of truth for resident records, permissions, accepted care entries, appointments and assigned tasks. Intelligence owns derived evidence, search, analysis, generation and workflow execution.

The first release is **authorised resident-history search and draft handover summaries with source links**. Broader autonomy follows only after the evidence and execution foundations are demonstrated.

### Working assumptions

- Start with CareLens as the first client and a limited pilot population.
- Use synthetic data for engineering; representative care data requires appropriate governance and access arrangements.
- Build one modular intelligence service with separately runnable workers, rather than a service per agent.
- Keep model, speech, email and workflow integrations behind interfaces.
- Agreed 9 September 2026: the separate intelligence layer includes a mandatory AI gateway for minimisation, pseudonymisation, LLM dispatch and authorised re-identification. See the [gateway design](../governance/intelligence-ai-gateway-design.md). CareLens currently runs locally; future AWS/Azure hosting and regions remain undecided.
- Core recording, structured handover and existing clinical escalation must work during intelligence outages.
- Initial communications, extracted appointments and voice entries require staff review before external delivery or authoritative recording.
- No production deployment, external messaging or clinical automation is authorised by this planning document.

### Decisions to resolve during Phase 0

| Decision | Proposed starting position | Accountable role |
|---|---|---|
| Pilot scope | One home, staff-only search and handover | Product owner and care lead |
| Hosting and model processing | Choose after data handling, regional availability and quality assessment | Technical lead and privacy lead |
| Repository | Independent intelligence repository; create location and access arrangements during setup | Technical lead |
| Deployment | Separate API, worker processes and intelligence database | Technical lead |
| Workflow engine | Durable workflow adapter; evaluate Temporal with a restart/retry proof | Technical lead |
| Search storage | PostgreSQL full-text search and pgvector, benchmarked on pilot data | Technical lead |
| Identity | Trusted service identity plus delegated actor/tenant scope; explicit scope for background jobs | Security lead |
| Handover format | Agree required fields, evidence and review requirements | Care lead |
| Clinical purpose | Document exact intended use and assess applicable clinical/regulatory obligations | Clinical safety lead |
| Email provider | Defer connector selection until the organisation's provider is known | Product owner |

One person may fulfil multiple roles in a small team. Clinical and privacy decisions still need suitably qualified input.

## 2. Architecture boundaries

```text
CareLens UI -> CareLens API -> authorised intelligence requests
                     |
                 care database + transactional outbox
                                      |
                                event dispatcher
                                      |
                      Intelligence ingestion and reconciliation
                                      |
                      evidence store / search / metric projections
                                      |
                        workflows -> model and tool adapters
                                      |
                           results / proposed actions
                                      |
                    CareLens review and validated command APIs
```

### Suggested intelligence code organisation

```text
intelligence-platform/
  api/                       # requests, job status, results, cancellation
  contracts/                 # versioned inputs, outputs and events
  core/
    identity/                # trusted execution context and policy checks
    evidence/                # source records, lineage and freshness
    retrieval/               # lexical, semantic and structured retrieval
    workflows/               # durable execution interfaces and state
    actions/                 # proposals, approvals and execution ledger
    model_gateway/           # model adapters, budgets and output validation
    observability/           # traces, audit metadata, costs and health
  domains/care/
    schemas/
    metrics/
    rules/
    workflows/
    prompts/
  connectors/carelens/        # CareLens-specific mapping and API client
  connectors/email/           # added after provider selection
  workers/
  evaluations/
  tests/
  deployment/
```

Framework-specific objects stay behind adapters. The platform must not import CareLens ORM models or write directly into its database.

### Reusable contracts to establish

- **Execution context:** tenant, actor/service identity, allowed resident scope, purpose and correlation ID. Derive scope from trusted identity; do not trust model-supplied scope.
- **Source record:** source system, record ID/version, tenant/resident, type, effective time, recorded time, ingestion time, access restrictions and correction/deletion state.
- **Event envelope:** event ID/type/schema version, source record ID/version, tenant, timestamps and correlation ID. Carry identifiers and metadata; fetch clinical content through an authorised API.
- **Evidence-backed result:** result ID/type, resident, covered period, source versions, claim-level references, data cutoff, warnings, generation version and review state.
- **Action proposal:** action type, target, proposed payload, evidence, expected record version, review state, expiry and idempotency key.
- **Job state:** queued, running, awaiting review, completed, failed, cancelled or expired. Document permissible transitions.

## 3. Delivery sequence and gates

| Phase | Outcome | Dependency |
|---|---|---|
| 0 | Agreed scope and a known CareLens baseline | None |
| 1 | Separate service and secure integration contracts | Phase 0 |
| 2 | Reliable resident evidence ingestion | Phase 1 |
| 3 | Authorised evidence-backed search | Phase 2 |
| 4 | Draft handover and first staff pilot | Phases 2–3 |
| 5 | Reproducible analytics and daily/weekly reports | Phase 2 and agreed metric definitions |
| 6 | Confirmed commitments, reminders and follow-through | Phase 4 and authoritative task APIs |
| 7A | Reviewed voice recording | Phase 1, recording APIs and voice evaluation set |
| 7B | Family drafts and clinician email workflows | Phase 4, disclosure policies and connector approval |
| 8 | Validated deterioration and behaviour-change detection | Phase 5 and clinical validation |

Clinical intended-use work starts in Phase 0, even though detection is delivered later. Voice can be brought forward after the first pilot if recording speed is the higher priority. Start only one new feature track at a time for a small team.

## 4. Phase 0 — establish the baseline and pilot specification

P0-01 progress: source review completed on 8 September 2026. See the [baseline review](phase-0/baseline-review.md) and [file manifest](phase-0/baseline-manifest.json). Current working tree is the recommended candidate baseline; acceptance, runtime verification and physical implementation isolation remain outstanding. No application code was changed by the review.

- [ ] **P0-01:** Review the existing uncommitted work and agree which changes form the baseline. Preserve current work; isolate intelligence implementation changes.
- [x] **P0-02:** Run existing backend tests and frontend checks; record failures and infrastructure prerequisites separately from new work. Completed 8 September 2026: [verification report](phase-0/verification-report.md). Backend: 25 passed, 1 skipped; frontend build passed; static-check failures and coverage gaps recorded.
- [x] **P0-03:** Address the readiness endpoint's unawaited dependency checks before relying on it for service health. Completed 8 September 2026: concurrent awaited probes, two-second timeouts and HTTP contract tests; full suite 35 passed, 1 skipped. See [verification](phase-0/readiness-verification.md).
- [x] **P0-04:** Inventory actual API coverage for care events, observations, medications, appointments, tasks and permission checks. Completed 8 September 2026: [API coverage matrix and minimum integration backlog](phase-0/api-inventory.md), cross-checked with 43 registered OpenAPI operations. Generic observation storage, complete history retrieval, service authorisation and change tracking require work.
- P0-04 follow-up: [historical clinical mapping resolved](phase-0/clinical-feed-resolution.md), including native observation storage, 14 source projections, period/type filters, source detail, and summary/gateway schema alignment. Apply migrations 0030–0031 before using against the application database. Service authorisation, durable export and other inventory gaps remain separate work.
- [x] **P0-05:** Agree two pilot stories: resident-history enquiry and end-of-shift handover review. [Pilot specification](phase-0/pilot-specification.md): care events plus 14 connected clinical sources; authorised carers, nurses and care managers edit drafts. After review the user confirmed only the designated nurse in charge can finalise, including drafts they edited, superseding the earlier broader policy. Preserve the original AI draft separately from the signed final handover; corrections require reviewed amendments. Workflow implementation and pilot operating details remain outstanding.
- [ ] **P0-06:** Define allowed data, recipients, retention, processing locations and intended clinical use. [Data-policy/DPIA addendum](../governance/intelligence-pilot-data-policy.md): UK/local-only baseline and separate intelligence gateway direction recorded; conversation (24-hour maximum), inactive draft (30-day) and operational audit (90-day) defaults agreed on 9 September 2026, alongside temporary mapping cleanup and source-aligned derived-data retention. Hosting regions, accountable owners, eligibility and remaining retention details are still open; deletion controls are not implemented.
- [x] **P0-07:** Draft at least 20 representative search questions and 10 handover scenarios, including missing data, corrections, late records and permission denials. Completed 9 September 2026: [synthetic case pack](phase-0/pilot-evaluation-cases.md) and [Glenrose's review sheet](phase-0/pilot-evaluation-review.md). All 14 clinical sources plus care events covered, with expected outcomes and workflow/gateway cases. Drafting is complete; nurse review, executable fixtures and output evaluation remain outstanding. This is a starter set, not sufficient clinical validation.
- [x] **P0-08:** Agree latency, freshness, cost and quality targets and named reviewers before choosing models or accepting output. [Headline acceptance targets agreed](phase-0/pilot-acceptance-targets.md): evidence-supported accuracy and no unauthorised disclosures in tests; p95 search ≤10 seconds, handover ≤60 seconds and source freshness ≤60 seconds; average model cost ≤£0.05/search and ≤£0.50/floor handover. Reviewers assigned: Glenrose for care accuracy/usefulness and the user (project developer) for technical evaluation. Operational incident ownership and detailed runtime settings remain implementation decisions. No benchmark results or paid runs are implied.
- P0-07 review follow-up: [feedback incorporated](phase-0/pilot-review-feedback.md) into case-pack revision 2: offered/consumed and partial drinks, optional BMI, mobility issues, post-fall evidence window, recorded-time fallback and separate original/final handovers. S15 execution deferred to retrieval work; completeness remains a gate. Wound vision is a future request. All AI output tests remain unrun.
- Pilot representative recorded on 9 September 2026: **Glenrose (nurse)**, for workflow input and search/handover evaluation. The user is the technical developer/reviewer. Organisational/privacy ownership and formal clinical safety responsibility remain unassigned; P0-06 remains open, while P0-08 planning is complete.

**Deliverables:** baseline report, short architecture decision record, pilot specification, data-access matrix and initial evaluation cases.

**Exit gate:** pilot scope and data access are agreed; baseline failures are understood; the first two workflows have reviewable examples and acceptance criteria.

## 5. Phase 1 — build the independent service skeleton

- [ ] **P1-01:** Create the agreed repository with its own dependencies, migrations, CI and deployment configuration.
- [ ] **P1-02:** Implement health/readiness, configuration, structured logging and correlation IDs without logging clinical payloads by default.
- [ ] **P1-03:** Define versioned execution-context, evidence, result and event contracts.
- [ ] **P1-04:** Implement service authentication and tenant/resident scope checks, including explicit background-job identities.
- [ ] **P1-05:** Add narrowly scoped CareLens integration endpoints for the minimum pilot evidence.
- [ ] **P1-06:** Implement the CareLens connector using those endpoints; prohibit direct CareLens database access.
- [ ] **P1-07:** Add model interfaces, a deterministic fake provider and structured response validation.
- [ ] **P1-08:** Prove durable workflow restart, retry, cancellation and timeout behaviour using a fake workflow. Keep model and network calls outside deterministic replay logic if the chosen engine requires it.
- [ ] **P1-09:** Create automated contract and cross-tenant denial tests.

**Deliverables:** runnable intelligence API/worker, connector, contracts and CI.

**Exit gate:** a request travels from CareLens to intelligence and returns a fake result with correct scope and trace ID; unauthorised requests fail; restarting a worker does not lose the test job.

## 6. Phase 2 — make evidence ingestion trustworthy

- [ ] **P2-01:** Add a transactional outbox in CareLens, written in the same transaction as the associated care-record change.
- [ ] **P2-02:** Implement dispatch acknowledgement, retries, backoff and a failed-event queue with controlled replay.
- [ ] **P2-03:** Add an intelligence inbox/deduplication ledger; define handling for out-of-order record versions.
- [ ] **P2-04:** Build paginated backfill and incremental synchronisation. Capture a cursor/watermark so changes during backfill are reconciled.
- [ ] **P2-05:** Store only approved evidence fields with separate occurrence, recording and ingestion timestamps.
- [ ] **P2-06:** Process amendments, deletions, resident transfers and access changes. Invalidate affected search entries, memory and generated results.
- [ ] **P2-07:** Add tenant-scoped lexical and vector indexes with source lineage. Check permissions before content reaches a model.
- [ ] **P2-08:** Expose last successful sync, coverage and ingestion lag. Run periodic source reconciliation.
- [ ] **P2-09:** Test duplicates, unavailable consumers, late offline care entries, corrections and interruption during backfill.

**Deliverables:** rebuildable evidence store, reliable sync pipeline, freshness status and recovery runbook.

**Exit gate:** a committed test record reaches the index after recovery from an outage; duplicates do not duplicate evidence; corrections/deletions propagate; reconciliation finds deliberately omitted events; isolation tests pass.

## 7. Phase 3 — deliver resident-history search

- [ ] **P3-01:** Start with a selected resident and explicit date range; defer open-ended searches across all residents.
- [ ] **P3-02:** Combine exact filters, full-text retrieval and semantic retrieval; use structured queries for counts, quantities and dates.
- [ ] **P3-03:** Implement a bounded enquiry workflow with allowlisted tools, call limits, timeouts and budgets.
- [ ] **P3-04:** Require source-linked answers; distinguish reported facts, interpretation and insufficient evidence.
- [ ] **P3-05:** Show source passages, timestamps and index freshness in the CareLens enquiry panel.
- [ ] **P3-06:** Enforce access on result reads, source navigation and caches, including after a user's permissions change.
- [ ] **P3-07:** Test adversarial instructions in notes, ambiguous resident references, conflicting facts and absence of data.
- [ ] **P3-08:** Evaluate retrieval independently of generation; compare candidate models on the same evidence and questions.

**Deliverables:** resident enquiry panel, search API and quality/cost report.

**Exit gate:** agreed pilot questions meet the pre-agreed evidence and usefulness targets; citations resolve; no unauthorised evidence is returned in the isolation suite; missing data produces an explicit limitation.

## 8. Phase 4 — deliver handover and run the first pilot

- [ ] **P4-01:** Agree a handover schema: significant changes, relevant observations, outstanding actions, appointments, unresolved concerns and missing information.
- [ ] **P4-02:** Assemble evidence across care events, observations and other confirmed available domains. Explicitly label unavailable domains.
- [ ] **P4-03:** Define shift boundaries and care-home timezones; handle daylight-saving transitions and late entries.
- [ ] **P4-04:** Generate a structured draft with claim-level sources, data cutoff and workflow/model/prompt versions.
- [ ] **P4-05:** Add validation for source existence, dates, measurements, unsupported claims and required sections. Treat these checks as partial safeguards, not proof of factual correctness.
- [ ] **P4-06:** Add draft/reviewed/superseded states, staff editing and attributed approval. Preserve approved versions; flag later corrections rather than silently rewriting history.
- [ ] **P4-07:** Integrate with the existing CareLens handover surface through an adapter; retain structured fallback.
- [ ] **P4-08:** Implement the actual active-home registry for scheduled jobs; the current scheduler returns an empty list.
- [ ] **P4-09:** Run a staff-reviewed pilot, measure omissions and corrections, and record issues before expansion.

**Deliverables:** shift handover workflow, review interface, scheduled generation and pilot report.

**Exit gate:** care staff accept the agreed pilot quality; evidence and review history are visible; failed generation leaves a useful structured handover; late records and reruns do not silently replace approved output.

**Release A:** resident-history search and reviewed handovers. Complete this release before broadening the feature portfolio.

## 9. Phase 5 — add deterministic analytics

- [ ] **P5-01:** Create a metric catalogue with source fields, units, denominators, time windows, completeness rules and calculation version.
- [ ] **P5-02:** Start with recorded hydration, meal intake and care-record completeness; add activity, mood/behaviour, mobility, continence and sleep after verifying source coverage.
- [ ] **P5-03:** Build calculations in SQL/tested code and test against manually checked fixtures.
- [ ] **P5-04:** Distinguish absent records from zero intake or no symptoms; avoid inferring sleep duration from sparse checks without an agreed method.
- [ ] **P5-05:** Support documented individual targets where available; do not invent universal clinical targets.
- [ ] **P5-06:** Build charts and daily/weekly reporting from the same metric outputs.
- [ ] **P5-07:** Add generated explanations that cite the metric period and relevant source records without claiming causation.
- [ ] **P5-08:** Recalculate affected periods after source amendments and label superseded reports.

**Exit gate:** reported numbers match independently checked calculations; completeness is visible; report and chart values agree; corrections update the correct periods.

## 10. Phase 6 — add commitment memory and reminders

- [ ] **P6-01:** Confirm or implement CareLens task/appointment APIs, ownership, statuses and audit trails.
- [ ] **P6-02:** Extract candidate commitments with source text, proposed owner, due date, timezone and ambiguity flags.
- [ ] **P6-03:** Add a review inbox to accept, edit or reject proposals. Resolve phrases such as 'next Tuesday' against the source timestamp and confirm ambiguity.
- [ ] **P6-04:** Deduplicate against existing appointments/tasks; persist accepted proposals through CareLens commands with idempotency keys.
- [ ] **P6-05:** Schedule durable reminders, acknowledgements, escalation and expiry according to agreed policy.
- [ ] **P6-06:** Handle appointment changes, cancellations, reassignment and revoked access before execution.
- [ ] **P6-07:** Keep approved resident preferences separately from unreviewed extracted statements; support correction and expiry.
- [ ] **P6-08:** Test worker restarts, overdue tasks, notification failures and duplicate source notes.

**Exit gate:** an accepted commitment survives restarts and produces the expected reminder; cancellation suppresses it; duplicate input produces one task; unresolved ambiguity does not become a confirmed appointment.

## 11. Phase 7A — add voice-assisted recording

- [ ] **P7A-01:** Agree permitted audio processing, retention and deletion rules.
- [ ] **P7A-02:** Add push-to-talk with a clearly selected resident and visible recording state.
- [ ] **P7A-03:** Map transcription into existing care templates and schemas; retain uncertainty for staff review.
- [ ] **P7A-04:** Show transcript and structured preview, highlighting resident identity, amounts, units, negation and event time.
- [ ] **P7A-05:** Save confirmed entries through normal CareLens validation and idempotency behaviour; preserve typed entry when speech is unavailable.
- [ ] **P7A-06:** Evaluate representative accents, background noise and clinically consequential field errors.

**Exit gate:** staff can correct and confirm before save; agreed critical-field accuracy targets are met; ambiguous speech never silently becomes a committed record.

## 12. Phase 7B — add communication workflows

- [ ] **P7B-01:** Define audience templates and recipient-specific disclosure rules, including consent or other applicable authority.
- [ ] **P7B-02:** Generate family and clinician drafts using evidence that the recipient is authorised to receive.
- [ ] **P7B-03:** Add staff review, recipient verification, approval expiry and an immutable record of approved content.
- [ ] **P7B-04:** Select and connect the actual email provider with minimum required permissions.
- [ ] **P7B-05:** Implement incremental sync, missed-notification reconciliation, deduplication and token/credential handling.
- [ ] **P7B-06:** Match emails to residents with a review queue for uncertain matches; handle attachments and untrusted instructions safely.
- [ ] **P7B-07:** Keep draft creation separate from sending. Recheck recipient, content approval and access at send time.
- [ ] **P7B-08:** Track delivery results; reconcile uncertain provider responses rather than blindly resending.

**Exit gate:** drafts respect the recipient access matrix; sending requires valid approval; ambiguous resident matches remain unresolved; outage recovery avoids duplicate messages in tested scenarios.

## 13. Phase 8 — validate deterioration and behaviour-change detection

- [ ] **P8-01:** Finalise intended use, hazard analysis, clinical ownership and applicable assurance/regulatory route before operational deployment.
- [ ] **P8-02:** Define data requirements, clinically approved rules, baseline windows and escalation pathways.
- [ ] **P8-03:** Implement data-quality gates and deterministic detection first; use a model to explain evidence, not to silently set clinical thresholds.
- [ ] **P8-04:** Add personal baselines only when sufficient comparable data exists. Separate missing recording from possible change in health.
- [ ] **P8-05:** Create alert states, ownership, deduplication, suppression, acknowledgement and resolution tracking.
- [ ] **P8-06:** Evaluate against appropriately governed, representative clinician-labelled cases, including false negatives and subgroup performance.
- [ ] **P8-07:** Run in shadow mode and measure alert burden and missed events before staff rely on it.
- [ ] **P8-08:** Obtain the required clinical release decision, train staff and retain ordinary escalation during outages.
- [ ] **P8-09:** Introduce statistical prediction only as a separately evaluated extension with a defined outcome and monitoring plan.

**Exit gate:** clinically agreed performance and alert-burden targets are met; assurance obligations are addressed; each operational alert has an owner and response pathway. Passing software tests alone does not satisfy this gate.

## 14. Cross-cutting acceptance requirements

Apply these throughout delivery, not as an end-of-project checklist.

| Requirement | Evidence to retain |
|---|---|
| Tenant and resident isolation | Automated denial tests across API, retrieval, caches and result reads |
| Source fidelity | Claim citations, record versions, data cutoff and correction tests |
| Durable execution | Restart, duplicate event, partial failure and replay tests |
| Controlled actions | Approval history, idempotency and commit-time permission checks |
| Privacy | Data inventory, retention/deletion propagation and restricted telemetry |
| Prompt-injection resistance | Adversarial notes/emails cannot change scope or authorise tools |
| Model release discipline | Versioned prompts/models, evaluation results and rollback route |
| Operational visibility | Event lag, job failures, overdue reviews, budgets and notification status |
| Cost control | Per-workflow budgets, bounded retries and evaluation of cheaper task-specific models |
| Graceful degradation | Recording and structured care views remain usable when AI is unavailable |

Track retrieval recall, citation correctness, unsupported claims, important omissions, staff edit rates, workflow latency and cost. Define thresholds per use case before each pilot; do not use model-generated confidence percentages as a substitute for validation.

## 15. First implementation sprint

Skeleton delivered: see the standalone [architecture and stack](../intelligence-service/docs/architecture.md), [agent extension guide](../intelligence-service/docs/adding-agents.md), [delivery plan](../intelligence-service/docs/delivery-plan.md) and [verification](../intelligence-service/docs/verification.md). The project sits in `intelligence-service/` with its own package, lockfile and environment; it has not yet been moved into a separate Git repository. This does not mark production Phase 1 identity or durability gates complete.

Treat this as the first roughly two-week planning box, subject to baseline findings and team capacity. It is not a promised completion date.

| Order | Work item | Concrete result |
|---|---|---|
| 1 | P0-01 through P0-04 | Agreed baseline, health fix and integration inventory |
| 2 | P0-05 through P0-08 | Pilot examples, access matrix and evaluation targets |
| 3 | P1-01 through P1-04 | Independent service, contracts and authenticated scoped request |
| 4 | Minimum of P1-05 through P1-09 | One authorised connector call and a restartable fake job |
| 5 | First vertical slice of P2 | One committed synthetic care event reaches intelligence durably |
| 6 | Demonstrate and review | Evidence record can be inspected with tenant, source version and timestamps |

**Sprint demonstration:** record synthetic care in CareLens, stop and restart the intelligence worker, and show that the committed event arrives once in the derived evidence view without exposing it to another tenant.

If the baseline or access design takes longer, reduce sprint scope. Do not bypass those tasks to demonstrate an LLM response.

## 16. Working method and progress tracking

1. Select the next unchecked task whose dependencies are complete.
2. State its acceptance criteria before editing code.
3. Implement a small, reviewable change with appropriate tests.
4. Demonstrate the behaviour, including the relevant failure case.
5. Record evidence, limitations and any architecture decision.
6. Mark the task complete only when its result is verified.
7. Review the phase gate before starting dependent feature work.

Use task IDs from this document in issues and PRs. Keep implementation branches and review scope separate from the existing uncommitted work. Update this plan when scope changes rather than silently bypassing gates.

| Milestone | Status | Evidence / decision |
|---|---|---|
| M0: scope and baseline agreed | Not started | |
| M1: secure independent service | Not started | |
| M2: trustworthy evidence sync | Not started | |
| M3: resident search | Not started | |
| M4: reviewed handover pilot | Not started | |
| M5: reproducible analytics | Not started | |
| M6: commitments and reminders | Not started | |
| M7A: reviewed voice recording | Not started | |
| M7B: approved communication workflows | Not started | |
| M8: clinically validated detection | Not started | |

Estimate subsequent sprints after M0, and re-estimate after M2 when integration and data-quality costs are known. Detection validation and provider/governance approvals may determine elapsed time independently of coding effort.

## 17. Architectural references

- [Transactional outbox pattern](https://docs.aws.amazon.com/en_en/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html)
- [pgvector and hybrid search](https://github.com/pgvector/pgvector)
- [Temporal durable workflows](https://docs.temporal.io/)
- [LangGraph overview — optional agent orchestration](https://docs.langchain.com/oss/python/langgraph/overview)
- [Microsoft Graph incremental message synchronisation](https://learn.microsoft.com/en-us/graph/delta-query-messages)
- [NHS clinical safety applicability guidance](https://digital.nhs.uk/services/clinical-safety/applicability-of-dcb-0129-and-dcb-0160/nhs-digital-recommendation)
- [MHRA software and AI guidance](https://www.gov.uk/government/publications/software-and-artificial-intelligence-ai-as-a-medical-device)

These are architectural references reviewed during the preceding design discussion. Recheck provider capabilities and applicable clinical requirements when implementation decisions are made.

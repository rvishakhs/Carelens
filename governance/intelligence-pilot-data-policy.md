# P0-06 — Intelligence pilot data policy

Date: 9 September 2026.
Status: draft; P0-06 remains open. Agreed P0-05 scope is carried forward; remaining policy proposals are not yet approved or implemented. On 9 September 2026 the user confirmed a UK pilot, CareLens running only on their computer, future AWS or Azure hosting (undecided), separate application/intelligence layers, and an AI gateway using pseudonymise → LLM → re-identify. Cloud regions, accountable people and UK nation remain unconfirmed.

## 1. Intended use and responsibility

Proposed intended-use statement: help authorised care-home staff find and summarise existing resident care records for a selected period, with source references and explicit coverage limitations. Handover drafts require human review and designated sign-off in CareLens. Intended users are participating care staff; the population is the home's explicitly enrolled residents.

The pilot covers care events and the 14 clinical sources in the [agreed specification](../docs/phase-0/pilot-specification.md). It does not provide diagnoses, treatment recommendations, predictive alerts, autonomous escalation or external communications. Staff continue established care and escalation procedures. Human review and this scope statement do not by themselves determine medical-device status; the accountable clinical lead must assess the actual functionality and claims for the applicable jurisdiction.

Review update confirmed by the user: finalisation is restricted to the designated nurse in charge, superseding the earlier nurse/manager/senior-carer reviewer policy. Preserve the original AI draft and nurse-finalised version as separate linked artefacts. Draft editing remains available to authorised staff; implementation is outstanding.

Proposed accountability, subject to contractual confirmation:

| Responsibility | Required owner / decision |
|---|---|
| Purpose, resident eligibility and authoritative record retention | Care-home operating organisation; name the controller and accountable representative |
| CareLens and intelligence hosting/operation | Name the supplier and determine its controller/processor role for each purpose |
| Model, embedding, hosting and monitoring vendors | Identify processors/subprocessors, contracts and access locations |
| Privacy review | Named privacy lead / DPO where applicable |
| Pilot care workflow and output evaluation | Glenrose — pilot nurse representative, named by the user on 9 September 2026; contributes workflow requirements and reviews search answers and handover drafts for usefulness and accuracy |
| Intended use and clinical review | Named care/clinical safety lead |
| Technical implementation and evaluation | The user (project developer), confirmed as technical developer/reviewer; covers integration, tests, gateway/access controls and performance/cost evidence |
| Operational incident handling | Operational/security incident owner and contact remain to be assigned |

Glenrose's recorded role is pilot nurse representation and evaluation. It does not
assign organisational data-processing approval, privacy/DPO responsibility or a
formal clinical safety officer appointment. Those owners remain unassigned. This
record also does not create an application account or grant shift-finalisation
permissions; operational reviewer designation follows the agreed P0-05 policy.

## 2. Proposed data and recipient matrix

“Allowed” below means allowed by the proposed design after resident eligibility, governance and access requirements are met; it is not permission to use real data today.

| Data | CareLens | Separate intelligence service | External model / embedding provider |
|---|---|---|---|
| Resident identity, name, contact details, identifiers | Authoritative identity and staff display | Minimum scoped internal reference; avoid duplicating identity fields | No direct identity fields by default; use scoped opaque aliases |
| Care events and 14 clinical sources | Authoritative records | Relevant fields/text for authorised resident, purpose and period | Only minimised evidence needed for the current request, after tested redaction and provider approval |
| Event time, units, source ID/version and precision | Preserve source meaning | Required for retrieval, calculations, freshness and citations | Preserve necessary clinical time/units; use reference aliases where possible |
| Staff and third-party information in notes | Retain under source policy | Process only where needed; minimise unnecessary personal details | Remove unnecessary staff/relative identities and contact details |
| User questions and follow-up conversation | Authenticated staff interface | Treat as sensitive; they can contain names and health information | Apply the same minimisation controls as source notes |
| Generated answers and handover drafts | Display under current resident permissions | Store only under the approved result lifecycle | No vendor reuse/training; vendor retention must be assessed |
| Final handover, edits and reviewer identity | Authoritative signed record and amendment history | Minimum linkage/status needed by workflow | Reviewer identity and audit trail are not model inputs |
| Embeddings, snippets, summaries and retrieval caches | Links where needed | Treat as sensitive derived resident data with tenant/resident access and deletion rules | External embeddings require the same assessment as generation |
| Audit/operational telemetry | Access and review evidence | IDs, timings, errors, versions and costs; exclude raw notes, prompts, responses and tokens by default | No clinical content in external telemetry by default |
| Photos, attachments, audio, medical/medication history, appointments, family/email contacts | Existing application policy | Outside pilot ingestion allowlist | Not sent by this pilot |

Free text can mention out-of-scope subjects; source inclusion does not establish complete medication or appointment history. A scoped alias is pseudonymisation, not proof of anonymity. Do not equate a redaction pass with permission to disclose health information.

Recipients: staff with current home/floor/resident access and the agreed reviewer capabilities. No new family, clinician-email, head-office or administrator access is introduced. Operational support receives metadata by default; exceptional access to content must be time-limited, authorised and audited. Cross-tenant reuse, provider training and fine-tuning on pilot resident data are excluded from this proposal.

## 3. Processing flow and location register

CareLens authenticates staff and determines scope → separate intelligence service retrieves allowed evidence through authorised APIs → AI gateway minimises and pseudonymises input → approved LLM → gateway validates and re-identifies output within the trusted boundary → CareLens displays the result under current permissions and owns review/finalisation.

The gateway is a required component of the separate intelligence layer, reusable across workflows. Model credentials and provider egress belong to the gateway; application routes and agents must not call providers directly. Generation and external embedding requests both pass through its applicable controls. The identity mapping stays in separately access-controlled trusted storage and is never sent to the model. See the [gateway design](intelligence-ai-gateway-design.md) for boundaries, failure handling and implementation acceptance criteria.

Background ingestion must use explicit purpose and resident scope. Permission or eligibility changes must prevent further retrieval and serving of affected derived data, cancel affected queued work and trigger retention handling. Recheck access when opening results and citations. Clinical source text must be treated as data, never as instructions granting tools, recipients or permissions.

Before selecting vendors, complete this register:

| Component | Provider / region / access locations | Status |
|---|---|---|
| CareLens API, database and backups | Currently local to the user's computer; backup arrangements not assessed | Future AWS or Azure hosting undecided; region not selected |
| Intelligence API, gateway, workers, queues, database and index | Separate deployment; future AWS or Azure option undecided | Independent identity/storage; approved region still to be selected |
| Generation and embedding inference | Undecided | Verify exact service/model deployment and retention settings |
| Vendor abuse logs, support, subprocessors and failover | Undecided | Hosting region alone does not resolve these locations |
| Monitoring, error reporting and disaster recovery | Undecided | Include backups and support access in assessment |

Do not infer processing location from a vendor's headquarters or a model name. Document subprocessors, retention exceptions, training terms, deletion capability, support access and any required transfer arrangements. An unapproved fallback provider/region must fail closed rather than receive data during an outage.

## 4. Retention schedule — agreed defaults and remaining decisions

On 9 September 2026 the user agreed the conversation, draft, derived-data, audit and temporary identity-mapping rules explained below, and that finalised handovers follow the care home's approved record policy. These are agreed product defaults, not statutory retention periods or implemented deletion controls. The controller and privacy lead must validate purposes, periods and exceptions before real-data activation. Backup periods, vendor retention and temporary payload expiry remain proposals where marked. Deleting intelligence copies must not delete authoritative care records.

| Data class | Rule and agreement status | Decision still needed |
|---|---|---|
| Raw request/response payloads in diagnostic logs | Do not persist by default | Any restricted diagnostic exception, access and expiry |
| Temporary processing payloads | Remove after job completion; failed-job payloads expire within 24 hours | Retry requirements and deletion verification |
| Search conversation history | Agreed: session-only, with a maximum 24-hour server-side lifetime | Specify expiry trigger in the implementation contract; no indefinite browser storage |
| Unfinalised drafts and revisions | Agreed: delete after 30 days without activity, unless needed for an ongoing review or incident hold | Maximum hold/review period and responsible owner |
| Derived evidence/index/embeddings | Agreed principle: keep only while needed for enrolled residents and the approved retrieval horizon; update/remove after source changes or loss of eligibility | Exact retrieval horizon and measurable removal deadline; 30-day search default is not a retention decision |
| Final handovers, linked review evidence and amendments | Agreed: follow the care-home approved care-record schedule; review feedback requires preserving the original AI draft separately as linked review evidence | Obtain applicable retention trigger/duration and custody; linked originals are not abandoned drafts subject to 30-day inactivity deletion; preserve necessary evidence without retaining the whole index |
| Security/access audit metadata | Agreed: 90 days for pilot operations, excluding signed-review history governed by the care-record schedule | Validate against security, incident and records obligations |
| Temporary gateway identity mappings | Agreed: delete when processing and permitted retries finish | Bound the retry lifetime and verify cleanup after failure/cancellation; existing stable application mappings are not automatically purged by this decision |
| Backups | Proposed maximum 35-day rolling retention for intelligence stores | Hosting feasibility, exceptions and restore reconciliation |
| Model/embedding vendor copies | Prefer no retained request content where supported; no training | Verify contractual and technical exceptions; otherwise assess explicit period |

Deletion must cover caches, indexes, queues, exports and vendor copies where applicable. Track requests and completion without retaining deleted content in logs. Restore procedures must reapply deletion/restriction records before serving data. Legal/incident holds need a reason, authorised owner and review date. Loss of current user access blocks display immediately even where records must be retained.

## 5. Resident eligibility, transparency and rights

Document the legal basis and, where applicable, the additional health-data processing condition. Do not assume the existing `data_processing_consent` boolean is sufficient or that consent is necessarily the correct basis. Decide what false/unknown flags, objections, withdrawal where relevant, capacity/representative arrangements and resident departure mean for this purpose.

Proposed implementation: an explicit pilot enrolment/processing eligibility check, backed by the approved policy, in addition to staff access checks. Unresolved eligibility means no intelligence processing for that resident; ordinary care processing continues under its own policy. Provide a clear notice explaining the purpose, sources, recipients, retention, human review and contact for questions or rights requests. Plan access, correction, restriction and applicable deletion handling across CareLens and derived stores.

## 6. Existing controls and remaining evidence

- Clinical source projection and native storage have PostgreSQL tenant/floor isolation tests; see the [mapping report](../docs/phase-0/clinical-feed-resolution.md). These tests do not validate a separate intelligence deployment or all endpoint/role combinations.
- Current redaction is regex-based and can miss names in free text. H-003 remains open. Adding NER alone would not prove completeness: test leakage and preservation of clinically meaningful dates/values using synthetic adversarial fixtures.
- The retention job at `app/workers/jobs/retention_job.py` is a no-op. No expiry, purge or vendor deletion guarantee is implemented by this document.
- Delegated service access, permission-cache invalidation, complete care-event retrieval, source version/change tracking and draft review permissions remain implementation work.
- Production checks must cover encrypted transport/storage, credential separation, audit delivery, restricted support access and incident response; statements here are requirements, not verified deployment claims.
- Continue synthetic-data engineering under the existing DPIA boundary while the real-data policy is unresolved. Do not copy resident records into development fixtures or evaluation files by default.

## 7. P0-06 completion and activation gates

P0-06 is complete when the policy decisions are recorded with accountable owners: jurisdiction/controller, intended use, allowed fields and recipients, legal basis/eligibility, location requirements, retention schedule and review of the extended DPIA/hazards. Provider choice can remain deferred to model evaluation, but its acceptance requirements must be explicit.

Real-data activation additionally requires those requirements to be implemented and evidenced, the selected provider/contract/transfer assessment to be completed, P0-07/P0-08 evaluation gates to pass and the responsible care/privacy owners to approve the deployment. P0-06 paperwork alone does not satisfy this gate.

Hosting baseline, retention defaults and Glenrose's pilot nurse representative role are recorded; AWS/Azure selection can remain deferred while location requirements are agreed. Organisational/privacy ownership and UK nation remain to be confirmed, alongside remaining eligibility, location and retention details. Synthetic evaluation preparation can continue with Glenrose's input while these decisions remain open.

## 8. Reference guidance

The pilot country is confirmed as the United Kingdom. These sources inform the policy; responsible reviewers must assess their application to the actual service and processing arrangements:

- UK special-category processing requires both a lawful basis and an additional condition: [ICO special category data](https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/lawful-basis/a-guide-to-lawful-basis/special-category-data/).
- Assess relevant international transfers and arrangements, including supplier chains: [ICO international transfers](https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/international-transfers/).
- Minimise retained data and delete unneeded intermediate files: [ICO security and data minimisation in AI](https://cy.ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/artificial-intelligence/guidance-on-ai-and-data-protection/how-should-we-assess-security-and-data-minimisation-in-ai/).
- Define and assess actual intended purpose: [MHRA intended-purpose guidance](https://www.gov.uk/government/publications/crafting-an-intended-purpose-in-the-context-of-software-as-a-medical-device-samd).
- Keep re-identification information separately protected; pseudonymisation is not anonymisation: [ICO pseudonymisation guidance](https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/data-sharing/anonymisation/pseudonymisation/).

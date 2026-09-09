# Intelligence AI gateway — design and implementation requirements

Date: 9 September 2026.
Status: architectural direction agreed by the user; detailed controls below are proposed requirements, not implemented guarantees.

## 1. Separate application and intelligence layers

CareLens remains the authoritative application for resident identity, care records, permissions and finalised handovers. The intelligence service is independently deployable, owns its derived stores and uses versioned CareLens APIs. It does not import CareLens ORM models or access the care database directly. Both services may use the same chosen cloud while retaining separate service identities, credentials and storage permissions. AWS versus Azure and exact regions are undecided; CareLens currently runs only on the user's computer.

```text
CareLens UI / API / care database
          |
          | authorised request + delegated resident scope
          v
Separate intelligence service
  retrieval / deterministic calculations / workflows
          |
          v
  AI gateway (trusted boundary)
    validate scope → minimise → pseudonymise → inspect outbound payload
                                   |
                            protected alias mapping
                                   | never leaves trusted boundary
    approved provider adapter ──────┼────→ LLM
          ^                        |       |
          └──── pseudonymous response ──────┘
    validate output → resolve authorised aliases → re-identify
          |
          v
CareLens authorised display / review / finalisation
```

The LLM receives selected pseudonymised evidence. It does not receive the identity mapping, application credentials or unfiltered source records. The trusted retrieval/gateway components necessarily handle confidential information and require protection. Pseudonymised care details can remain sensitive personal data; removing names does not make rare events or distinctive narratives anonymous. This is a controlled-disclosure design, not a guarantee that no confidential information reaches inference. See [ICO guidance](https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/data-sharing/anonymisation/pseudonymisation/).

## 2. Request and response controls

1. **Authorise:** validate service identity and delegated tenant/resident/purpose scope before fetching evidence. Recheck current access before returning a result. The model cannot supply or expand its own authority.
2. **Minimise:** retrieve only relevant source fields and periods. Calculate totals in trusted deterministic code. Send enough evidence to support the narrative without transmitting whole resident profiles.
3. **Pseudonymise all inputs:** cover source notes, user questions, conversation history, tool results and citation metadata. Replace resident/relative/staff names with typed opaque aliases when their relationship matters; omit unnecessary identifiers, addresses, phone/email details, full DOB and home/room labels. Detect identifiers embedded in free text using combined structured-field rules, known-entity matching and local entity detection. Do not send raw text to an external detector to prepare it for another external model.
4. **Preserve meaning:** retain necessary measurements, units, temporal order and date precision. Treat DOB differently from a clinical event timestamp. Exact dates and distinctive context require minimisation assessment; use relative time or age bands when sufficient. Do not indiscriminately remove all dates and lose shift boundaries or source meaning.
5. **Inspect before egress:** validate the complete serialised outbound request, including metadata, against the field policy and leakage checks. Unresolved detection or gateway failure blocks provider dispatch and offers a visible manual/retry path. There is no raw-input fallback. Passing a detector is evidence of a check, not proof of perfect anonymisation.
6. **Call an approved provider:** route through gateway-owned credentials and an explicit model/region allowlist. Confirm no training/reuse and the actual retention terms/settings separately. Provider or region failover cannot bypass the same policy. External embeddings use the same applicable input controls; embeddings themselves remain protected derived data.
7. **Validate output before re-identifying:** require a structured result and source references from the request's evidence manifest. Reject unknown or out-of-scope aliases and source IDs; never attempt a global mapping lookup. Check unsupported identifiers and malformed output. Model text never triggers arbitrary tool execution or external delivery.
8. **Re-identify locally:** resolve only exact recognised placeholders from this authorised request context. Prefer typed structured fields and deterministic rendering over broad substring replacement. Only restore identities necessary for the authorised CareLens display; do not restore every removed detail. Keep result versions and claim references intact for review.

## 3. Mapping isolation and lifecycle

- Separate mapping access from model-adapter access. Use encryption and narrowly scoped service permissions; provider-facing components cannot query mappings.
- Prefer fresh request-scoped model aliases. Bind mappings to tenant, resident scope, purpose and request; retain only for the permitted job/retry lifetime. A job with an expired mapping must fail or regenerate safely, never guess an identity.
- Use separate internal evidence IDs where stable indexing is needed; avoid globally stable aliases visible across tenants or unrelated model requests.
- Never include mappings, raw prompts/responses, personal names or credentials in routine logs/traces. Audit policy/version, request ID, action, result and timings as metadata.
- Browser code and LLM tools have no mapping-store access. Re-identification is not a public arbitrary-token lookup endpoint.
- Apply the approved retention schedule to temporary mappings and retries. Signed review evidence follows the authoritative record policy and does not require keeping every temporary alias mapping indefinitely.

## 4. Current implementation versus target

The application already has the basic orchestration in `app/modules/ai_gateway/service.py`: pseudonymise → provider → re-identify. It is inside CareLens today and is not the future independently deployed intelligence service.

Current `pseudonymiser.py` substitutes a known resident placeholder and regex-matches NHS numbers, UK phone numbers and date-like strings. It does not reliably detect arbitrary resident/relative names, emails, addresses or contextual identifiers. The current mapping is stable per resident and re-identification uses string replacement. These are starter mechanisms, not the complete controls above.

Reusing the existing provider abstraction and behavioural tests is useful; future extraction must replace application-specific imports with gateway contracts and scoped mapping interfaces. H-003 remains open. No application code or deployment is changed by this design.

## 5. Implementation sequence and acceptance evidence

1. Define provider-neutral request/result, evidence-manifest and mapping contracts; separately specify the permitted outbound fields.
2. Implement scoped mapping storage and minimisation/pseudonymisation with synthetic fixtures, including names in questions and narrative text.
3. Enforce the gateway as the only provider egress path; implement output validation and restricted re-identification.
4. Test correct identity restoration, unknown aliases, malicious notes, cross-tenant/resident collisions, revoked access, gateway errors, expired mappings and retries. Assert zero provider calls when policy validation fails.
5. Inspect synthetic outbound requests and logs for leakage; test that clinical units, chronology and citations survive transformation. Include indirect-identification cases in reviewer assessment; do not report regex coverage as a privacy guarantee.
6. Evaluate model usefulness on transformed evidence during P0-07/P0-08, and verify provider/region/retention requirements before real-data use.

The [P0-06 data policy](intelligence-pilot-data-policy.md) remains the place to agree owners, recipients, location and retention. Gateway engineering implements part of that policy; it does not replace those decisions.

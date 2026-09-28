# Deterministic handover metrics

`intelligence.handover.metrics.calculate_handover_metrics` is a pure function:
no LLM, HTTP, persistence or source mutations. It accepts your existing assembled
`ShiftEvidence` and returns typed `HandoverMetrics`.

```python
from intelligence.handover.metrics import calculate_handover_metrics

metrics = calculate_handover_metrics(
    shift_evidence,
    retrieval_complete=False,  # Explicitly set from your retrieval/coverage checks.
)
# Calculate before preparing the handover agent/gateway request.
# Preserve server-owned metrics and warnings in the resulting draft.
```

Do not set completeness merely because one HTTP request succeeded. Your current
observation-only retrieval does not prove full care-event coverage or snapshot
consistency. This change supplies the calculation boundary; it does not alter the
in-progress Celery workflow or declare live retrieval complete.

## Output semantics

- `consumed` and `offered` have independent totals, statuses and source references.
- `value` is populated only for a complete, unambiguous total of recorded amounts.
  It is not proof of all actual intake. Missing offered values are never inferred
  from consumption.
- `known_subtotal` includes only validated contributions. Label it as a subtotal;
  never present it as the complete period total. An ambiguous/incomplete linked
  group is conservatively excluded in full.
- `status`: `complete`, `partial`, `no_records`, or `ambiguous`. A recorded zero is
  a complete value of zero; an empty successful retrieval has `value=None` and
  `no_records`; failed/incomplete retrieval has `partial`.
- `fluids` are sorted by actual time and preserve their time basis, original
  amounts, source reference and validated contribution (`consumption_delta_ml`).
- `meals` preserve each recorded percentage and source; no daily summed percentage
  or inferred missed/refused meal is produced.
- `record_counts` count supplied in-shift source records by exact `kind`. They do
  not count inferred episodes, unique activities or events mentioned in prose.
  With partial retrieval these counts describe the available subset only.
- Date-only and unknown-time context is excluded from exact shift totals/counts.
  Uncertain-time fluid context prevents complete fluid totals.
- Decimal arithmetic preserves fractional millilitres. Pydantic JSON serializes
  Decimal values as strings; consumers must not assume integer output.

## Current source fields

Fluid consumption reads `clinical_data.volume_ml`, `ml`, or `consumed_ml`, and
legacy top-level `Evidence.consumed_ml`. Equivalent aliases count once;
contradictory aliases raise `MetricsInputError`. Offered amounts read explicit
`clinical_data.offered_ml` or top-level `offered_ml` only. The normalization layer
must map care-template options into explicit canonical amounts: this module does
not parse option labels or clinical narratives.

Meals read `percentage_eaten` and/or `fraction_eaten` (multiplied by 100). Both
must agree if supplied. Values must be within 0–100. Invalid numeric types,
booleans, negatives, non-finite values and conflicting aliases fail validation.
Errors do not repeat the original clinical payload.

Unlinked historical intake rows are treated as separately recorded portions, as
in the existing domain contract. No semantic cross-source deduplication is
attempted. A duplicate source identity (including a conflicting revision) raises
an error; retrieval must reconcile it first. Different source types with the same
UUID remain distinct. If your connector cannot establish that two records are
independent, resolve/flag that overlap before presenting a combined metric.

## Explicit linked-drink contract

These optional `clinical_data` keys are the metrics input contract. Their presence
in this documentation does not mean the CareLens API already supplies them:

| Key | Meaning |
|---|---|
| `offer_id` | Stable non-empty link to one offered drink within the resident's evidence; connector must namespace IDs across source systems |
| `offered_ml` | Original offered volume, counted once per linked offer; repeated equal values are allowed |
| `consumed_ml` | An additional portion or cumulative reading, as identified by the mode |
| `consumption_mode` | `incremental`, `cumulative`, or `unknown`; linked entries without a mode are ambiguous |
| `opening_consumed_ml` | For cumulative groups, explicit amount already consumed before this shift; zero for a confirmed new offer. Must be on the first reading; subsequent supplied baselines must agree |

Incremental example: one offer of 200 ml, followed by 100 ml and another 50 ml,
produces 200 ml offered and 150 ml consumed. It does not require a second offer.

Cumulative example: opening baseline 0, readings 100 then 150, produces deltas
100 and 50 and total 150, not 250. An opening baseline of 100 and current reading
150 contributes only 50 ml to this shift. A baseline must be supplied explicitly;
the calculator cannot infer the beginning of a drink from the first fetched row.
Only include `offered_ml` in shift evidence when the offer belongs to this shift;
for carried-over drinks, consumption can be calculated without counting the old
offer again. Cross-shift normalization is the connector's responsibility.

Unknown/mixed modes, missing cumulative linkage/baseline, decreasing cumulative
readings, tied cumulative timestamps and consumption exceeding the known linked
offer produce ambiguity warnings and no complete consumed total. Conflicting
volumes for the same offer withhold the offered total. Missing consumption is not
zero. Separate offer-only events must first be normalized with an unambiguous
consumption history; this module does not infer zero consumption from an offer.

## Tests

```sh
.venv/bin/python -m pytest -q --confcutdir=tests tests/test_handover_metrics.py
```

Tests cover the source normalization → shift assembly → metrics path, decimals,
aliases, partial/cumulative drinks, new offers, baseline boundaries, invalid data,
missing/zero/partial distinctions, per-meal percentages, counts, source collisions,
scope isolation, uncertain times and input immutability.

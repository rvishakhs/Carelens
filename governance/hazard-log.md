# Hazard Log

Living document. Add an entry in the same PR as any feature that creates or mitigates
a hazard -- this file should never lag the code by more than one commit.

Format per entry: **Cause -> Harm -> Mitigation -> Status**.

---

## H-001: Wrong-resident data displayed

- **Cause**: UI or query error shows resident A's observations/summary under resident B's card.
- **Harm**: Carer acts on wrong information; potential clinical error (wrong meds, wrong care plan).
- **Mitigation**: `resident_id` is always the join key end-to-end, never a positional/ordinal index; handover read-model (`app/modules/handover/service.py`) keys every card explicitly by resident. RLS provides a second layer (cross-tenant, not cross-resident-within-tenant, but still defence-in-depth). Provenance (`source_observation_ids`) lets a nurse verify a summary against the actual records it was built from.
- **Status**: Open -- needs an integration test asserting card->resident_id integrity under concurrent requests once the handover endpoint is exercised against real data.

## H-002: Summary omits a critical event

- **Cause**: LLM summarisation drops or under-weights a clinically significant note (e.g. a fall, a refusal) in favour of routine detail.
- **Harm**: Staff miss a follow-up action because it wasn't surfaced in the summary they read.
- **Mitigation**: Summaries are explicitly labelled "AI-generated -- verify against records" with a source-records expander (never presented as the sole record). `is_implausible` flagging on ingestion and the rule-based note structurer's `refusal_mentioned`/`fall_mentioned` fields are available to the handover attention ranker independent of the LLM output, so a dropped mention in prose doesn't remove the underlying flag from the grid ordering.
- **Status**: Open -- prompt template (`app/modules/ai_gateway/prompts/daily_summary/v1.md`) needs eval against synthetic `post_fall_recovery`/`uti_episode` trajectories once synthdata is generating them, to confirm incidents survive summarisation.

## H-003: Pseudonymisation leak

- **Cause**: Free text (notes) containing a resident's real name, a relative's name, or other identifiers reaches the LLM provider unredacted.
- **Harm**: PII sent to a third-party LLM provider without a DPA in place (Phase 1 uses dev keys against synthetic data only, but the code path is the same one Phase 2 uses against real data).
- **Mitigation**: `app/modules/ai_gateway/pseudonymiser.py` strips known PII patterns (NHS number, UK phone, dates) and the resident is referred to only via a stable token substituted for a placeholder, never the real name, in prompt construction. Explicitly flagged as incomplete: no NER pass yet, so a name spelled out in a note (e.g. "Mrs T. was visited by her daughter Susan") is NOT currently caught.
- **Status**: **Open, high priority** -- blocks moving `LLM_PROVIDER` off `fake`/`local` for anything beyond gateway-path testing. Needs the spaCy NER pass and the fixture suite in `tests/unit/test_pseudonymiser.py` filled out with real edge cases before Phase 2 provider selection.

## H-004: Over-reliance on AI summary

- **Cause**: Staff treat the AI-generated summary as authoritative and stop checking source records, especially under time pressure at shift handover.
- **Harm**: An AI summarisation error (H-002) goes uncaught because nobody looked at the underlying data.
- **Mitigation**: UI requirement (Week 9-11): summary always labelled AI-generated, source-records expander always visible, feedback (👍/👎 + comment) captured on every summary as both a safety signal and an evaluation dataset. Read-only in Phase 1 -- no workflow lets a summary directly trigger an action without a human in the loop.
- **Status**: Open -- needs a nurse walkthrough (Week 9-11 exit criterion) to observe actual behaviour, not just the intended design.

## H-005: Stale data at handover

- **Cause**: Handover view caches or shows data older than the actual last-24h window (e.g. summary generated before a late-shift incident was logged).
- **Harm**: Incoming shift starts with an outdated picture.
- **Mitigation**: Handover read-model queries live data on every request (no caching layer in Phase 1); summary generation timestamp (`generated_at`) and source-record provenance are shown alongside the summary so staff can see how current it is. Shift-end job (`workers/scheduler.py`, 19:00 cron) regenerates before the next shift starts.
- **Status**: Open -- needs the <500ms/40-resident perf target verified (Week 9-11 exit criterion) to confirm "always live" doesn't become "always slow."

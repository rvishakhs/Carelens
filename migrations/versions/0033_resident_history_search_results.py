"""Persist short-lived, cited resident-history search results.

Revision ID: 0033
Revises: 0032

Search output is derived health data.  The tables deliberately do not retain a raw
staff question: the saved, reproducible result is limited to the deterministic
answer, coverage limitations, and the evidence citations required to verify it.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0033"
down_revision: Union[str, None] = "0032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""\
CREATE TABLE resident_history_searches (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_home_id          UUID NOT NULL REFERENCES care_homes(id),
    floor_id              UUID NOT NULL REFERENCES floors(id),
    resident_id           UUID NOT NULL REFERENCES residents(id),
    requested_by          UUID NOT NULL REFERENCES users(id),
    mode                  TEXT NOT NULL CHECK (mode IN ('evidence', 'ai_answer')),
    answer                TEXT NOT NULL,
    answer_status         TEXT NOT NULL CHECK (answer_status IN ('supported', 'no_evidence', 'partial')),
    coverage_limitations  JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at            TIMESTAMPTZ NOT NULL,
    CHECK (jsonb_typeof(coverage_limitations) = 'array'),
    CHECK (expires_at > created_at),
    UNIQUE (id, care_home_id, floor_id, resident_id)
);

CREATE TABLE resident_history_search_citations (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    search_id             UUID NOT NULL,
    care_home_id          UUID NOT NULL REFERENCES care_homes(id),
    floor_id              UUID NOT NULL REFERENCES floors(id),
    resident_id           UUID NOT NULL REFERENCES residents(id),
    source_type           TEXT NOT NULL CHECK (
        source_type IN ('fall', 'incident', 'observation', 'care_event', 'appointment', 'care_plan')
    ),
    source_id             UUID NOT NULL,
    source_version        TIMESTAMPTZ,
    occurred_at           TIMESTAMPTZ NOT NULL,
    title                 TEXT NOT NULL,
    excerpt               TEXT,
    rank                  INTEGER NOT NULL CHECK (rank > 0),
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (search_id, care_home_id, floor_id, resident_id)
        REFERENCES resident_history_searches (id, care_home_id, floor_id, resident_id)
        ON DELETE CASCADE,
    UNIQUE (search_id, source_type, source_id)
);

-- The floor is always derived from the authoritative resident row.  A client cannot
-- choose a different floor to widen access to a saved search result or citation.
CREATE TRIGGER trg_sync_floor_id BEFORE INSERT OR UPDATE ON resident_history_searches
    FOR EACH ROW EXECUTE FUNCTION sync_floor_id_from_resident();
CREATE TRIGGER trg_sync_floor_id BEFORE INSERT OR UPDATE ON resident_history_search_citations
    FOR EACH ROW EXECUTE FUNCTION sync_floor_id_from_resident();

CREATE INDEX idx_resident_history_searches_resident_expires
    ON resident_history_searches (resident_id, expires_at DESC);
CREATE INDEX idx_resident_history_searches_expiry
    ON resident_history_searches (expires_at);
CREATE INDEX idx_resident_history_search_citations_search_rank
    ON resident_history_search_citations (search_id, rank);
CREATE INDEX idx_resident_history_search_citations_source
    ON resident_history_search_citations (resident_id, source_type, source_id);

ALTER TABLE resident_history_searches ENABLE ROW LEVEL SECURITY;
ALTER TABLE resident_history_searches FORCE ROW LEVEL SECURITY;
ALTER TABLE resident_history_search_citations ENABLE ROW LEVEL SECURITY;
ALTER TABLE resident_history_search_citations FORCE ROW LEVEL SECURITY;

-- Recheck the resident's CURRENT floor on every operation.  This prevents a saved
-- result from remaining visible to someone who loses access after a resident moves
-- floor, even though the result preserves its original floor for provenance.
CREATE POLICY tenant_and_current_floor_searches_select ON resident_history_searches
    FOR SELECT
    USING (
        care_home_id = NULLIF(current_setting('app.care_home_id', true), '')::uuid
        AND EXISTS (
            SELECT 1 FROM residents r
            WHERE r.id = resident_history_searches.resident_id
              AND r.care_home_id = resident_history_searches.care_home_id
              AND r.floor_id = ANY (
                  string_to_array(NULLIF(current_setting('app.floor_ids', true), ''), ',')::uuid[]
              )
              AND r.deleted_at IS NULL
        )
    );

CREATE POLICY tenant_and_current_floor_searches_insert ON resident_history_searches
    FOR INSERT
    WITH CHECK (
        care_home_id = NULLIF(current_setting('app.care_home_id', true), '')::uuid
        AND EXISTS (
            SELECT 1 FROM residents r
            WHERE r.id = resident_history_searches.resident_id
              AND r.care_home_id = resident_history_searches.care_home_id
              AND r.floor_id = resident_history_searches.floor_id
              AND r.floor_id = ANY (
                  string_to_array(NULLIF(current_setting('app.floor_ids', true), ''), ',')::uuid[]
              )
              AND r.deleted_at IS NULL
        )
    );

CREATE POLICY tenant_and_current_floor_searches_delete ON resident_history_searches
    FOR DELETE
    USING (
        care_home_id = NULLIF(current_setting('app.care_home_id', true), '')::uuid
        AND EXISTS (
            SELECT 1 FROM residents r
            WHERE r.id = resident_history_searches.resident_id
              AND r.care_home_id = resident_history_searches.care_home_id
              AND r.floor_id = ANY (
                  string_to_array(NULLIF(current_setting('app.floor_ids', true), ''), ',')::uuid[]
              )
              AND r.deleted_at IS NULL
        )
    );

CREATE POLICY tenant_and_current_floor_citations_select ON resident_history_search_citations
    FOR SELECT
    USING (
        care_home_id = NULLIF(current_setting('app.care_home_id', true), '')::uuid
        AND EXISTS (
            SELECT 1 FROM residents r
            WHERE r.id = resident_history_search_citations.resident_id
              AND r.care_home_id = resident_history_search_citations.care_home_id
              AND r.floor_id = ANY (
                  string_to_array(NULLIF(current_setting('app.floor_ids', true), ''), ',')::uuid[]
              )
              AND r.deleted_at IS NULL
        )
    );

CREATE POLICY tenant_and_current_floor_citations_insert ON resident_history_search_citations
    FOR INSERT
    WITH CHECK (
        care_home_id = NULLIF(current_setting('app.care_home_id', true), '')::uuid
        AND EXISTS (
            SELECT 1 FROM residents r
            WHERE r.id = resident_history_search_citations.resident_id
              AND r.care_home_id = resident_history_search_citations.care_home_id
              AND r.floor_id = resident_history_search_citations.floor_id
              AND r.floor_id = ANY (
                  string_to_array(NULLIF(current_setting('app.floor_ids', true), ''), ',')::uuid[]
              )
              AND r.deleted_at IS NULL
        )
    );

CREATE POLICY tenant_and_current_floor_citations_delete ON resident_history_search_citations
    FOR DELETE
    USING (
        care_home_id = NULLIF(current_setting('app.care_home_id', true), '')::uuid
        AND EXISTS (
            SELECT 1 FROM residents r
            WHERE r.id = resident_history_search_citations.resident_id
              AND r.care_home_id = resident_history_search_citations.care_home_id
              AND r.floor_id = ANY (
                  string_to_array(NULLIF(current_setting('app.floor_ids', true), ''), ',')::uuid[]
              )
              AND r.deleted_at IS NULL
        )
    );
""")


def downgrade() -> None:
    op.execute("""\
DROP TABLE IF EXISTS resident_history_search_citations CASCADE;
DROP TABLE IF EXISTS resident_history_searches CASCADE;
""")

-- Debug issue capture for task-level prompt inspection.

BEGIN;

CREATE TABLE IF NOT EXISTS debug_issues (
    id UUID PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    phase_id TEXT,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    issue_type TEXT NOT NULL DEFAULT 'other',
    severity TEXT NOT NULL DEFAULT 'medium',
    status TEXT NOT NULL DEFAULT 'open',
    source TEXT NOT NULL DEFAULT 'manual',
    prompt_artifact_path TEXT,
    related_artifact_path TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    fixed_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_debug_issues_task_id ON debug_issues (task_id);
CREATE INDEX IF NOT EXISTS idx_debug_issues_status_created
    ON debug_issues (status, created_at DESC);

COMMIT;

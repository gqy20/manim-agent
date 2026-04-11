-- ── Manim Agent: Initial Schema (Neon PostgreSQL) ──────────
-- Migration: 001_initial_schema
-- Created: 2026-04-11
-- Migrates from JSON-file TaskStore to relational PostgreSQL tables.

BEGIN;

-- ══════════════════════════════════════════════════════════
-- 1. tasks — 主任务表
-- ══════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS tasks (
    id              TEXT PRIMARY KEY,          -- short UUID (8 chars)
    user_text       TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at    TIMESTAMPTZ,
    video_path      TEXT,
    error           TEXT,

    -- Pipeline options (from TaskCreateRequest) stored as JSONB
    options         JSONB NOT NULL DEFAULT '{}',

    -- Structured pipeline output (from dispatcher.get_pipeline_output())
    pipeline_output JSONB,

    -- Metadata
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks (status);
CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tasks_status_created ON tasks (status, created_at DESC);

-- ══════════════════════════════════════════════════════════
-- 2. task_logs — 任务日志（每行一条，支持高效追加和查询）
-- ══════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS task_logs (
    id              BIGSERIAL PRIMARY KEY,
    task_id         TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    content         TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_task_logs_task_id ON task_logs (task_id, id);
CREATE INDEX IF NOT EXISTS idx_task_logs_task_id_created ON task_logs (task_id, created_at);

-- ══════════════════════════════════════════════════════════
-- 3. Helper: get task with latest N logs in one query
-- ══════════════════════════════════════════════════════════
CREATE OR REPLACE FUNCTION get_task_with_logs(p_task_id TEXT, p_limit INT DEFAULT 500)
RETURNS TABLE(
    id TEXT, user_text TEXT, status TEXT, created_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ, video_path TEXT, error TEXT,
    options JSONB, pipeline_output JSONB, updated_at TIMESTAMPTZ,
    logs TEXT[]
) AS $$
BEGIN
    RETURN QUERY
    SELECT t.id, t.user_text, t.status, t.created_at, t.completed_at,
           t.video_path, t.error, t.options, t.pipeline_output, t.updated_at,
           COALESCE(
               ARRAY(
                   SELECT l.content
                   FROM task_logs l
                   WHERE l.task_id = p_task_id
                   ORDER BY l.id ASC
                   LIMIT p_limit
               ),
               '{}'::TEXT[]
           ) AS logs
    FROM tasks t
    WHERE t.id = p_task_id;
END;
$$ LANGUAGE plpgsql STABLE;

COMMIT;

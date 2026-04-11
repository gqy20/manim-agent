# Claude Agent SDK Migration Plan

## Purpose

This document translates the target model in
[`claude-sdk-state-model.md`](./claude-sdk-state-model.md) into a practical
migration sequence.

It answers:

1. What should be fixed first?
2. What can be changed without a large architectural rewrite?
3. How should we validate each stage?

The plan is intentionally incremental. The goal is to improve correctness
before improving elegance.

## Current Failure Pattern

Based on the current implementation and runtime traces, the most expensive
failure pattern is:

1. Claude successfully completes useful work
2. SDK emits enough information to recover the result
3. project fails to resolve the final output
4. backend marks task as failed
5. frontend renders a misleading task narrative

Because of this, migration should start from output correctness, not UI polish.

## Guiding Priorities

Migration should follow this order:

1. Fix false negatives in task completion
2. Isolate task-local runtime state
3. Make backend state authoritative
4. Simplify frontend inference
5. Remove heuristic fallbacks from the hot path

## Phase Overview

Recommended phases:

1. Output Resolution Stabilization
2. Task-Local State Isolation
3. Backend State Normalization
4. Frontend Contract Cleanup
5. Heuristic Fallback Containment
6. Optional Hardening

Each phase should be independently shippable.

## Phase 1: Output Resolution Stabilization

### Goal

Stop marking successful Claude runs as failed when valid result information
already exists in SDK messages.

### Why This Comes First

This is the highest-value change because it directly affects whether the system
produces usable results.

### Required Changes

- include `ResultMessage.result` in final output resolution
- keep `ResultMessage.structured_output` as preferred when valid
- treat `TaskNotificationMessage.output_file` as a first-class output source
- clearly log which source won during final resolution

### Suggested Implementation Scope

Touch only:

- SDK message consumption
- output resolution logic
- final validation logic

Avoid in this phase:

- large frontend refactors
- event model redesign
- database schema changes

### Expected Behavioral Change

A task should succeed if:

- Claude produced a valid `output_file`, or
- Claude produced a valid structured output, or
- Claude produced a valid parseable final result text

The task should fail only when all supported protocol-level output channels are
exhausted and final output still cannot be resolved.

### Validation

Add or update tests for:

- valid `ResultMessage.result` with no `structured_output`
- valid `task_notification.output_file` with no text marker
- conflicting sources where stronger source wins
- invalid structured output falling back to valid result text

Manual verification:

- replay one or two known failed historical tasks whose logs show a valid final
  result in `result (preview)`

### Exit Criteria

- false-negative failures caused by missing `structured_output` are eliminated
- output resolution path is deterministic and logged

## Phase 2: Task-Local State Isolation

### Goal

Remove cross-task contamination from runtime state.

### Why This Comes Second

Once output resolution improves, task contamination becomes the next most
dangerous source of silent corruption.

### Required Changes

- remove or encapsulate process-global mutable hook state
- key hook-captured state by task ID, SDK session ID, or both
- ensure source-code capture is cleared at task end
- ensure event callbacks are task-scoped

### Suggested Refactor Direction

Preferred direction:

- move hook state into a task-scoped runtime context object

Acceptable transitional direction:

- keep hook registry global, but make stored payloads keyed by task/session

### Validation

Add or update tests for:

- two sequential tasks do not share captured source
- concurrent tasks do not overwrite each other's captured files
- task-local cleanup occurs on both success and failure

Manual verification:

- start multiple tasks close together and confirm `pipeline_output.source_code`
  belongs to the correct task

### Exit Criteria

- no global captured-source map remains unscoped
- task-local runtime facts are isolated

## Phase 3: Backend State Normalization

### Goal

Make backend-owned task state the only authoritative lifecycle state.

### Why This Comes Third

After correctness and isolation improve, the next step is making state
transitions explicit and durable.

### Required Changes

- formalize backend transition rules for `pending/running/completed/failed`
- freeze `pipeline_output` once final output is resolved
- ensure status updates happen in a single authoritative place
- ensure terminal status is based on resolved output + exception state, not log
  wording

### Optional Enhancement

Introduce a backend-owned non-persisted or lightly persisted phase field, such
as:

- `sdk_connecting`
- `agent_active`
- `render_output_resolved`
- `tts_running`
- `mux_running`

This can be sent over SSE without changing top-level database status values.

### Validation

Add or update tests for:

- status only transitions forward
- `pipeline_output` is persisted once and treated as final
- successful tasks with TTS disabled still resolve correctly
- terminal failure requires unresolved output or real execution failure

### Exit Criteria

- backend status transitions are explicit and centralized
- frontend no longer needs logs to determine core task truth

## Phase 4: Frontend Contract Cleanup

### Goal

Make the frontend render backend truth instead of recreating it.

### Why This Comes After Backend Normalization

Frontend cleanup is much easier once the backend emits a cleaner contract.

### Required Changes

- prefer backend-owned structured events over log keyword inference
- add a structured `phase` event or equivalent backend phase field
- keep logs as display artifacts, not truth carriers
- reduce keyword-based phase detection to a temporary fallback only

### Suggested UI Contract

The frontend should ideally receive:

- task status
- phase
- structured progress
- tool lifecycle events
- optional human-readable logs

### Validation

Add or update tests for:

- status badge changes on backend `status` events only
- phase bar advances from structured phase events
- log wording changes do not break phase rendering

Manual verification:

- change or localize some log strings and confirm UI still behaves correctly

### Exit Criteria

- frontend phase display no longer depends on free-form backend log text
- logs remain useful, but non-authoritative

## Phase 5: Heuristic Fallback Containment

### Goal

Push filesystem and text heuristics out of the normal success path.

### Why This Comes Late

Heuristics are useful while the protocol path is still weak. Once protocol-level
resolution is stable, heuristics should be clearly demoted.

### Required Changes

- mark directory scanning as explicit fallback mode
- log when heuristic recovery is used
- prevent heuristic results from silently replacing stronger signals
- treat assistant text marker parsing as compatibility fallback, not preferred
  protocol

### Validation

Add or update tests for:

- filesystem fallback runs only when stronger sources are absent
- heuristic recovery is surfaced in logs
- stronger source overrides weaker source in conflicts

### Exit Criteria

- hot path relies on SDK/runtime facts
- heuristics are visible, rare, and contained

## Phase 6: Optional Hardening

### Goal

Address structural risks that are not required for immediate correctness but
matter for long-term stability.

### Candidate Topics

- permission policy review for `bypassPermissions`
- sandbox strategy for public or multi-tenant usage
- richer event payloads with tool duration and normalized tool names
- transcript retention and replay tooling
- recovery workflows for interrupted runs

### When To Do This

Only after phases 1 through 5 are stable.

## Recommended Work Breakdown

If this migration is implemented in small PRs, a good breakdown is:

1. Output resolution only
2. Hook state isolation only
3. Backend task-state cleanup only
4. Structured phase event support
5. Frontend phase bar migration
6. Filesystem fallback demotion

This breakdown minimizes risk and makes regression sources easier to identify.

## Test Strategy

### Unit Tests

Focus areas:

- message-to-fact extraction
- output resolution precedence
- conflict handling
- task-local state isolation

### Integration Tests

Focus areas:

- end-to-end backend task lifecycle
- SSE event order and terminal state emission
- persisted `pipeline_output` correctness

### Regression Fixtures

Create fixtures for real historical failure modes:

- `structured_output=None` but valid result text
- task notification provides output file
- multiple rendered mp4 files exist under the task directory
- two overlapping tasks create Python files

## Observability Requirements

Each phase should improve observability, not reduce it.

Recommended structured logs:

- which result source was selected
- which lower-priority sources were ignored
- whether heuristic recovery was needed
- task/session identifiers for all hook-captured artifacts

This is especially important while both old and new behaviors coexist.

## Anti-Patterns To Avoid During Migration

Do not:

- fix false negatives by simply broadening filesystem scanning
- add more frontend keyword matching to hide backend ambiguity
- keep adding fallback branches without defining source precedence
- treat global mutable state as acceptable because tasks are "usually" isolated

These patterns increase complexity while delaying the real fix.

## Success Criteria

Migration should be considered successful when:

- valid Claude completions are no longer commonly marked failed
- task-local artifacts are correctly isolated
- backend task state is authoritative
- frontend renders structured backend truth
- filesystem heuristics are no longer part of the normal happy path

## Short Version

If implementation time is limited, do these first:

1. Read from `TaskNotificationMessage.output_file`
2. Read from `ResultMessage.result`
3. Isolate `_hook_state` by task/session
4. Freeze final `pipeline_output` in the backend
5. Stop using frontend log keywords as the primary phase model

That sequence gives the highest correctness return for the least architectural
risk.

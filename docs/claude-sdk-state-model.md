# Claude Agent SDK Pipeline State Model

## Purpose

This document defines the intended runtime model for the `claude-agent-sdk`
integration in this project.

It focuses on four questions:

1. What is the single source of truth for task state?
2. Which SDK messages should drive state transitions?
3. How should final pipeline output be resolved when multiple signals exist?
4. Which responsibilities belong to the SDK consumption layer, backend task
   layer, and frontend display layer?

This document is intentionally implementation-oriented. It is meant to guide
future refactors of the current pipeline.

## Problem Summary

The current project consumes Claude SDK messages, but it does not yet define a
single authoritative state model.

At runtime, the system currently mixes:

- SDK-native messages such as `TaskNotificationMessage`, `TaskProgressMessage`,
  `ResultMessage`, and `AssistantMessage`
- dispatcher-local derived state such as `pipeline_output` and `video_output`
- filesystem heuristics such as scanning for the latest `*.mp4`
- frontend phase inference based on log keywords

This causes three classes of problems:

1. Success can be missed even when Claude already returned a valid result.
2. Task-local data can leak across runs because some runtime state is global.
3. The frontend displays inferred phases rather than a backend-owned state
   machine.

## Design Principles

The pipeline should follow these principles:

- Prefer SDK facts over local heuristics.
- Prefer explicit task output over parsed free text.
- Prefer backend-owned state over frontend keyword inference.
- Treat the filesystem as a validation surface, not a primary source of truth.
- Keep task-local runtime state scoped to one task/session.

## Runtime Layers

The runtime should be understood as three separate layers.

### 1. SDK Consumption Layer

This layer reads Claude SDK messages and normalizes them into task-local facts.

It should do only these things:

- receive SDK messages
- classify them by type
- extract structured facts
- emit normalized domain events

It should not:

- decide UI phases from log wording
- guess final outputs by scanning directories unless in explicit fallback mode
- store cross-task state in globals

### 2. Backend Task Layer

This layer owns the authoritative task state machine.

It should:

- persist task status
- persist resolved pipeline output
- emit backend-defined progress events for the frontend
- decide terminal success or failure

It should not:

- depend on frontend parsing for correctness
- treat logs as a primary state channel

### 3. Frontend Display Layer

This layer renders the backend state.

It may:

- visualize logs
- render structured tool events
- show a derived phase progress UI

It should not:

- define business truth
- infer task success from arbitrary text
- infer core pipeline phases from log keywords when structured state exists

## Authoritative Sources

The system should define a strict priority order for runtime truth.

### Authoritative Task Status

Authoritative task status should live in the backend task record only.

Allowed persisted statuses:

- `pending`
- `running`
- `completed`
- `failed`

Only the backend task layer may transition these states.

### Authoritative Final Output

The final rendered video path should be resolved from SDK/runtime signals in
this priority order:

1. `TaskNotificationMessage.output_file`
2. `ResultMessage.structured_output.video_output`
3. compatibility fallback (legacy path): parsed `ResultMessage.result`
4. compatibility fallback (legacy path): parsed assistant text markers
5. filesystem fallback search under the task output directory

Important:

- Levels 1 and 2 are protocol-level signals.
- Levels 3 to 5 are compatibility/recovery fallbacks and must never silently
  override stronger protocol signals.
- A filesystem hit alone should not override a stronger protocol signal.

### Authoritative Narration / Metadata

Metadata should be resolved in this priority order:

1. `ResultMessage.structured_output`
2. (optional compatibility) parsed `ResultMessage.result`
3. (optional compatibility) parsed assistant text markers

Filesystem artifacts should not be used to invent narration or scene metadata.

## Ideal Backend State Machine

The backend should own a single task state machine.

### States

- `pending`
- `running`
- `completed`
- `failed`

### Internal Substates

These do not need to be stored as top-level task status values. They may be
stored as progress detail or emitted as structured events.

- `sdk_connecting`
- `agent_active`
- `render_output_resolved`
- `tts_running`
- `mux_running`
- `finalizing`

### Transition Rules

#### `pending -> running`

Trigger:

- backend successfully starts the pipeline thread or async pipeline body

Meaning:

- the task has begun execution
- Claude SDK may or may not be connected yet

#### `running -> completed`

Trigger:

- final output path is resolved
- if TTS is enabled, TTS and mux steps have completed
- backend has persisted final `video_path`

Required completion conditions:

- terminal output file or URL exists
- `pipeline_output` has been frozen
- no uncaught pipeline exception remains

#### `running -> failed`

Trigger:

- unrecoverable exception in SDK layer, pipeline layer, TTS layer, or mux layer
- or required final output cannot be resolved after all supported protocol
  sources and approved fallbacks are exhausted

Important:

- "missing `structured_output`" alone is not a failure
- "missing text marker" alone is not a failure
- failure should be based on inability to resolve final output, not absence of
  a single preferred field

## SDK Message Mapping

This section defines what each SDK message means to the backend.

### `AssistantMessage`

Use for:

- text accumulation
- tool lifecycle visualization
- optional extraction of plain-text markers

Do not use as the only success channel in hot path.

Notes:

- `AssistantMessage` content may contain useful fallback text
- tool blocks are useful for UI and debugging
- assistant text should be treated as soft protocol unless explicitly required

### `TaskProgressMessage`

Use for:

- backend progress snapshots
- frontend progress visualization

Do not use for:

- terminal success/failure

### `TaskNotificationMessage`

Use for:

- primary output path resolution
- task-level completion/failure facts from the SDK/CLI side

This is the strongest non-filesystem signal for the rendered output file.

If `status == "completed"` and `output_file` exists, the backend should treat
that as a first-class resolved render artifact.

### `ResultMessage`

Use for:

- terminal conversation summary
- structured output
- plain result text
- cost and usage metadata

`ResultMessage.result` is a real result channel and must not be treated as
debug-only output.

`ResultMessage.structured_output` is optional and must not be assumed present.

### `StreamEvent`

Use for:

- partial UI rendering only
- optional live debugging

Do not use for durable task truth.

## Output Resolution Algorithm

The backend should resolve output in a deterministic, single-pass manner.

### Step 1: Accumulate Task-Local Facts

During message consumption, store task-local facts such as:

- latest `task_notification.output_file`
- latest valid `structured_output`
- latest plain-text parse candidate from `ResultMessage.result`
- latest assistant marker parse candidate
- hook-captured source code for files created in this task only

All of this state must be task-scoped.

### Step 2: Resolve Final `PipelineOutput`

When the SDK message stream ends, resolve `PipelineOutput` using the priority
order defined earlier.

Rules:

- pick the highest-priority valid candidate
- do not merge unrelated task candidates
- if stronger and weaker sources disagree, keep the stronger one and log the
  discrepancy

### Step 3: Validate the Resolved Output

Validation should be lightweight and explicit.

Examples:

- local file path exists
- file extension matches expected media type
- path is under the task output root, unless external storage URL is expected

Validation failure should not automatically drop to a weaker source without
recording why.

### Step 4: Freeze `pipeline_output`

Once resolved, `pipeline_output` should be treated as immutable task result
data.

After freeze:

- TTS reads from frozen narration or falls back to original user prompt
- mux reads from frozen `video_output`
- frontend reads persisted `pipeline_output`

## Frontend Contract

The frontend should consume backend truth, not recreate it.

### What the Backend Should Send

Structured event types should ideally include:

- `status`
- `phase`
- `tool_start`
- `tool_result`
- `thinking`
- `progress`
- `error`

Where possible, these events should already be normalized for UI use.

### What the Frontend May Derive

The frontend may still derive:

- folding/expand behavior
- visual grouping
- local ordering summaries

The frontend should not derive:

- authoritative task phase from log text
- completion from keyword matches
- failure from absence of one log phrase

### Recommended Phase Model

If the UI needs a phase bar, phase should be a backend-owned structured field.

Suggested phases:

- `init`
- `scene`
- `render`
- `tts`
- `mux`
- `done`
- `error`

These phases should be emitted from backend logic, not inferred from free-form
log lines.

## Task-Local State Requirements

The following runtime data must be scoped per task:

- hook-captured source code
- temporary result candidates
- dispatcher state
- CLI stderr buffer
- resolved pipeline output

The following must not be process-global unless additionally keyed by task or
session:

- captured source code maps
- event callbacks
- result candidates

If hooks remain global at the process level, their stored state must be keyed by
at least one of:

- task ID
- SDK session ID
- agent ID when sub-agents are involved

## Filesystem Fallback Policy

Filesystem scanning should be treated as emergency recovery logic only.

Allowed use:

- validating a path that was already reported by SDK messages
- recovering the output when all protocol-level result channels are absent

Not allowed as normal primary behavior:

- always selecting the newest `*.mp4`
- silently replacing a protocol-level output path with a different file

If filesystem recovery is used, the backend should log:

- why protocol-level resolution failed
- which directory was scanned
- which file was selected
- that the result was recovered heuristically

## Recommended Refactor Boundaries

This section describes where future changes should land.

### SDK Consumption / Dispatcher

Should own:

- message parsing
- task-local fact extraction
- normalized event emission

Should stop owning:

- directory search as implicit success path
- UI-oriented phase wording
- global mutable state

### Backend Pipeline Runner

Should own:

- authoritative task state transitions
- final `PipelineOutput` resolution
- validation of output path
- persistence of frozen result

### Frontend

Should own:

- rendering
- user-facing formatting
- non-authoritative display transforms

Should stop owning:

- pipeline phase detection from keyword corpora
- hidden business logic around success/failure

## Immediate Adoption Checklist

Before larger refactors, future changes should aim to satisfy this checklist:

- `ResultMessage.result` is included only as legacy compatibility fallback.
- `structured_output` is treated as optional, not mandatory.
- `TaskNotificationMessage.output_file` is treated as a first-class output
  signal.
- task-local runtime state is isolated per task/session.
- `pipeline_output` is resolved once and then frozen.
- frontend phase UI is driven by backend events or backend-owned phase state.
- filesystem scanning is downgraded to explicit fallback only.

## Non-Goals

This document does not define:

- the exact code patch plan
- database schema changes beyond current `status` and `pipeline_output`
- detailed TTS or FFmpeg implementation behavior
- permission policy for public multi-tenant deployment

Those should be addressed in follow-up design notes if needed.

## Summary

The intended model is simple:

- SDK messages provide facts.
- backend state machine provides truth.
- frontend provides visualization.

As long as those three roles remain separate, the pipeline can be made stable.
When they are mixed, the system becomes dependent on heuristics, log wording,
and accidental state coupling.

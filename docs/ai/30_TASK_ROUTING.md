# Task Routing

Use the branch matching the current task. Combine branches only when the task genuinely spans them.

## Bug / regression

`reproduce -> trace -> root cause -> similar working pattern -> regression test -> smallest fix -> focused verification -> diff review`

Do not patch only the symptom.

## Feature

`desired behavior -> existing pattern -> integration points -> architecture/data/API/UI impact -> implement -> tests -> verify -> review`

Do not over-engineer future flexibility.

## Refactor

`capture current behavior -> identify coupling -> establish test safety -> small staged refactor -> preserve behavior -> verify`

Do not mix unrelated behavior changes into a refactor unless requested.

## UI / UX

`find similar existing UI -> reuse design/system patterns -> implement states -> permissions/errors -> responsive/accessibility -> verify`

Relevant states may include initial/loading/success/empty/validation/server-error/disabled/permission-denied.

## API

`contract -> callers -> validation -> auth/permissions -> business logic -> errors -> compatibility -> tests`

Avoid unnecessary contract changes.

## Database / schema

`current model -> existing records -> schema impact -> migration/backfill -> constraints/indexes -> compatibility -> tests`

Prefer safe incremental changes.

## Permission / security

`identify protected resource -> reproduce safely -> permission/auth path -> root cause -> least-privilege fix -> regression test -> adjacent path review`

## Performance

`measure/identify hot path -> find actual cause -> smallest optimization -> compare correctness/performance -> review regression risk`

No speculative rewrites.

## New module / major architecture

`requirements -> repository architecture -> existing reusable mechanisms -> smallest maintainable design -> boundaries/data/API -> staged implementation -> tests -> docs -> verify`

Document only meaningful architectural decisions.

## Long-running task

Use a progress file copied from `docs/ai/PROGRESS_TEMPLATE.md`.
Keep progress in repository artifacts rather than relying on a massive chat history.

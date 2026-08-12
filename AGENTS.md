# Frappe Repository Instructions

These are the always-on instructions for work in this repository. Keep this file intentionally small.

## Always-on rules

- Inspect the relevant existing implementation before editing.
- Use repository evidence instead of assumptions.
- Prefer existing Frappe/project patterns over new abstractions.
- Make the smallest correct change and do not modify unrelated code.
- Preserve backward compatibility unless the task explicitly requires a breaking change.
- For Frappe behavior that is version-sensitive or uncertain, verify the exact installed source/version or matching official Frappe/ERPNext source before deciding.
- Respect permissions, document lifecycle, transactions, and existing hooks when they are relevant to the task.
- Do not use `ignore_permissions=True`, direct SQL, or direct database updates merely because they are shorter.
- Do not run state-changing Bench/Frappe operations without explicit user permission. This includes `bench build`, `bench migrate`, `bench update`, `bench restart`, cache-clearing commands, app install/uninstall, patch execution, restore, site creation/deletion, and production process changes.
- Do not perform destructive Git, database, site, or production operations without explicit permission.
- Run only the smallest relevant verification available. Never claim a test/build/check passed unless it was actually run.
- Inspect the final diff for unintended changes before reporting completion.
- Keep the final response concise: result, files changed, verification, and only important risks/notes.

## Context budget

Do NOT read every file under `docs/ai/`.

For a normal small task, read no AI guidance document unless the task clearly matches one of the triggers below. Inspect the target code and nearby existing patterns first.

When extra guidance is needed, load the smallest relevant set, normally zero or one document. Load multiple documents only when the task genuinely spans multiple risk areas.

Never load `docs/ai/archive/` during normal work.

## Conditional guidance

Read only when the task matches:

- DocType lifecycle, controller hooks, server validation, permissions, whitelisted APIs, document-vs-database updates, configuration:
  `docs/ai/FRAPPE_DOCTYPE_SERVER.md`

- Query Report, Script Report, Query Builder, SQL, aggregation, joins, totals:
  `docs/ai/REPORTS_QUERIES.md`

- Scheduler, queues, background jobs, integrations, retries, unattended processing:
  `docs/ai/BACKGROUND_JOBS.md`

- Desk JS, form/list scripts, website, portal, web form, browser bundles:
  `docs/ai/FRONTEND_CONTEXTS.md`

- Migration, destructive/state-changing operation, security-sensitive change, permission bypass, production/Bench operation:
  `docs/ai/HIGH_RISK_OPERATIONS.md`

- Large cross-cutting feature/refactor, architecture change, or a task spanning several modules:
  `docs/ai/COMPLEX_SDLC.md`

## Task behavior

- Small fix/change: inspect -> edit -> focused verify -> review.
- Bug: reproduce/trace -> root cause -> minimal fix -> regression verification when practical.
- Feature: inspect existing pattern -> identify integration point -> implement -> focused tests -> review.
- Refactor: establish current behavior -> small staged change -> preserve behavior -> verify.
- Large/architectural task: use `docs/ai/COMPLEX_SDLC.md`.

Do not create a long plan for a tiny change.

## Context recovery

If conversation history appears incomplete, compacted, interrupted, or inconsistent with the working tree, do not guess from memory. Reconstruct state from the current repository: inspect `git status`, relevant diff, changed files, tests/results available in the session, and the user's current request before continuing.

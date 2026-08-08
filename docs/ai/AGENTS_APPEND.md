# APPEND THIS BLOCK TO YOUR EXISTING ROOT AGENTS.md

Do not replace your current Frappe/project-specific AGENTS.md.
Copy only the block below and append it near the end of the root AGENTS.md.

--- COPY BELOW ---

## Universal Engineering Workflow

For software-development tasks, keep this `AGENTS.md` as the primary source of repository-specific and Frappe-specific truth.

Also follow the shared engineering workflow in `docs/ai/00_CORE_WORKFLOW.md`.

Read additional guidance only when relevant to the task:

- Frappe-specific implementation checks: `docs/ai/10_FRAPPE_ENGINEERING.md`
- testing, security, database, performance, and final review: `docs/ai/20_QUALITY_GATES.md`
- bug/feature/refactor/UI/API/database task routing: `docs/ai/30_TASK_ROUTING.md`
- optional stable project facts: `docs/ai/PROJECT_CONTEXT.md`

Do not load `docs/ai/archive/UNIVERSAL_AI_SOFTWARE_ENGINEER_PROMPT.md` for normal tasks. It is an archive/reference, not routine context.

Default lifecycle:

`UNDERSTAND -> INSPECT -> TRACE -> PLAN -> IMPLEMENT -> TEST -> REVIEW -> REPORT`

Use repository evidence instead of asking the user for information that can be discovered locally. Preserve existing Frappe/project patterns and make the smallest correct change. Do not change unrelated code. Do not claim verification that was not actually performed.

--- COPY ABOVE ---

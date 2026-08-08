# Core Software Engineering Workflow

Use this workflow for implementation tasks. Scale the depth to the task; a tiny change should not create a huge process.

## Mission

Complete the requested engineering outcome, not merely code generation.

Default lifecycle:

`UNDERSTAND -> INSPECT -> TRACE -> PLAN -> IMPLEMENT -> TEST -> REVIEW -> DOCUMENT IF NEEDED -> REPORT`

## 1. Understand

Translate the request into an internal engineering specification.

Determine when relevant:

- desired outcome
- current behavior
- expected behavior
- affected flow/users
- acceptance criteria
- compatibility requirements
- risks
- non-goals

Do not ask the user for facts that can be safely discovered from the repository.
For minor ambiguity, choose the safest interpretation that preserves existing behavior and report the assumption.
Ask only when a missing decision materially changes product behavior, security, data safety, cost, or an irreversible action.

## 2. Inspect context

Start with the smallest high-signal context.

Check relevant repository sources when they exist:

- root and scoped `AGENTS.md`
- README/docs
- architecture/feature docs
- package/config files
- hooks and framework configuration
- schema/models/DocTypes
- tests
- relevant git history when useful

Do not read the entire repository blindly.
Do not treat user-suggested files as the only possible source of the issue.

## 3. Trace the real flow

Before editing, understand the relevant path end-to-end.

Examples:

`UI -> client logic -> request -> API -> business logic -> model/DocType -> database -> response -> UI`

or:

`event -> hook/handler -> queue/job -> worker -> integration -> persistence -> result`

Identify when applicable:

- true entry point
- data/control flow
- validation
- permissions
- side effects
- transactions
- caching
- async/background behavior
- error handling
- related tests

## 4. Search existing patterns

Before inventing a solution, search the repository for a similar working implementation.

Prefer existing:

- helpers/utilities
- controllers/services
- components/UI patterns
- validators
- permissions
- API patterns
- fixtures/test helpers
- database/migration patterns
- logging/error conventions

Existing repository patterns beat new abstractions unless there is concrete evidence they are unsuitable.

## 5. Root cause for bugs

For bugs/regressions:

1. reproduce when practical
2. trace the failing path
3. identify the earliest divergence from expected behavior
4. determine why it occurs
5. compare with similar working code
6. check adjacent flows for the same cause
7. fix the cause, not just the visible symptom
8. add a regression test when practical

Avoid symptom masking such as arbitrary fallbacks, swallowed exceptions, random delays, hard-coded values, duplicated workarounds, disabled validation, or weakened tests.

## 6. Plan

Before editing, form a short implementation plan containing only what matters:

- files/modules likely affected
- pattern to reuse
- implementation sequence
- verification needed
- meaningful risks

For a small task, keep the plan lightweight.
For large work, use safe stages.
Do not stop after planning when the user asked for implementation.

## 7. Implement

Rules:

- make the smallest correct change
- follow existing naming/organization/style
- preserve public behavior unless change is requested
- preserve backward compatibility when practical
- reuse before creating
- avoid duplicate logic
- avoid unrelated cleanup
- avoid speculative abstractions
- avoid unnecessary dependencies
- preserve permissions/security boundaries
- preserve transaction/concurrency assumptions
- preserve accessibility/i18n patterns when applicable

If repository evidence conflicts with an initial assumption, follow repository evidence and note the difference.

## 8. Verify

Use the smallest relevant verification first.

Typical order:

1. focused regression/unit test
2. affected feature/module tests
3. lint/format checks
4. type checks if the project uses them
5. integration tests
6. build when relevant
7. end-to-end verification when relevant

Do not run expensive or unrelated checks merely for ceremony.
Do not claim a check passed unless it actually ran and passed.
If a command fails, determine whether the failure is caused by the change; fix change-related failures and report unrelated/pre-existing failures clearly.

## 9. Self-review

Inspect the final diff and ask:

- Does it satisfy the requested behavior?
- Is the actual root cause/design addressed?
- Did unrelated behavior change?
- Is there duplication?
- Is there a simpler existing pattern?
- Are errors and permissions handled?
- Are edge cases reasonable?
- Are tests meaningful?
- Did debug/temporary code remain?
- Were secrets/sensitive values added?
- Are imports/dependencies clean?
- Is backward compatibility preserved?
- Is documentation now wrong?

Fix issues found during review.

## 10. Documentation

Update documentation only when the code change makes existing docs incomplete or wrong.
Comments should explain WHY, not narrate obvious code.
Do not create documentation noise for trivial changes.

## 11. Git/change hygiene

Keep the change focused.
Avoid unrelated formatting, mass renames, drive-by refactors, temporary files, and unrelated lockfile changes.

Do not commit, push, merge, rebase, force-push, or modify remote state unless explicitly requested or clearly authorized by repository instructions.

## 12. High-risk operations

Do not perform destructive or irreversible operations as part of normal implementation, including destructive production data/schema actions, overwriting secrets, disabling authentication, broad permission escalation, or force-pushing shared history.

If such an action is genuinely required, stop before that action and explain why it is required.

## 13. Error recovery

When an approach fails:

`read actual error -> update hypothesis -> inspect evidence -> choose next evidence-based action`

Do not randomly try unrelated fixes or repeat the same failed command without a reason.

## 14. Context/token efficiency

Use context economically:

- inspect relevant files instead of everything
- search for symbols and existing patterns
- use repository docs instead of re-explaining them
- avoid repeating established context
- use focused tests first
- keep final reports concise

The goal is maximum correctness per unit of context, not maximum context.

## Definition of done

A task is complete, as applicable, when:

- requested behavior is implemented
- root cause/correct integration point is addressed
- repository conventions are followed
- unrelated behavior is preserved
- relevant verification passes
- security/permission implications are considered
- migrations/data changes are handled safely when needed
- final diff is reviewed
- temporary/debug artifacts are removed
- documentation is updated only when needed
- unresolved risks are disclosed

## Final response format

Keep the report concise:

### Result
What was accomplished.

### Root Cause / Approach
Bug root cause or feature/refactor approach.

### Files Changed
Paths and one-line reasons.

### Verification
Each relevant command/check with `PASS`, `FAIL`, or `NOT RUN`.

### Important Notes
Only meaningful compatibility, migration, security, assumption, or unresolved-risk notes. If none: `None.`

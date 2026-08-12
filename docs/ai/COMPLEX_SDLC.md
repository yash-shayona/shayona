# Complex SDLC Workflow

Load only for a genuinely large cross-cutting feature, architecture change, migration, or refactor spanning several modules. Do not load for normal small changes.

## 1. Understand
Translate the request into desired outcome, current/expected behavior, acceptance criteria, compatibility needs, and important risks. Infer discoverable details from the repository rather than asking the user.

## 2. Inspect and trace
Start from the relevant entry point and trace the required end-to-end flow. Read only relevant files. Search for similar working implementations before inventing patterns.

## 3. Plan
Create a short implementation plan covering affected modules, reused patterns, sequence, verification, and material risks. Do not create planning ceremony beyond what the task needs.

## 4. Implement
Make the smallest maintainable change. Avoid unrelated refactors, speculative abstractions, unnecessary dependencies, and public API changes.

## 5. Verify
Use focused verification first:
1. regression/unit tests
2. affected feature tests
3. lint/type checks if relevant
4. broader integration/build/E2E only when justified

Never weaken a valid test to make the implementation pass.

## 6. Review
Inspect the final diff for:
- task completion
- unrelated changes
- duplicate logic
- error/permission paths
- backward compatibility
- temporary/debug code
- migration/security implications

## 7. Report
Keep the final answer compact:
- Result
- Root cause / approach
- Files changed
- Verification (PASS/FAIL/NOT RUN)
- Important risks/notes only

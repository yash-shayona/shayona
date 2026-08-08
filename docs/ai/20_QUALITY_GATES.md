# Quality Gates

Apply only the gates relevant to the changed surface. Do not create unnecessary work for a tiny change.

## Testing

For bugs:
- reproduce when practical
- prefer a regression test
- confirm the test targets the root cause/public behavior

For features:
- happy path
- important validation/edge cases
- permission failures when relevant
- error paths when relevant
- compatibility behavior when relevant

For refactors:
- preserve observable behavior
- rely on existing coverage when sufficient
- add tests for changed risk, not implementation trivia

Never weaken, delete, skip, or rewrite a valid test merely to make an implementation pass.

## Verification order

Use the smallest relevant checks first:

1. focused unit/regression test
2. affected feature/module tests
3. lint/format
4. type checking if used
5. integration tests
6. build if relevant
7. end-to-end/manual flow if relevant

Report what actually ran.

## Security

Check only relevant attack/permission surfaces, including when applicable:

- authentication/authorization
- permission bypass
- injection
- XSS/CSRF/SSRF
- insecure object access
- unsafe file/path handling
- secret leakage
- sensitive logging
- mass assignment
- unsafe redirects
- token/session handling
- privilege escalation

Do not add unrelated security machinery; do not weaken existing protections.

## Data/schema

When persistence changes, inspect:

- null/default behavior
- uniqueness
- indexes
- relations
- existing records
- backfill/migration behavior
- rollback implications
- transaction safety

Avoid destructive migrations unless explicitly required.

## Performance

Only optimize when relevant/evidenced.
Check obvious regressions such as:

- N+1 queries
- repeated network/database calls
- large unbounded loops
- missing pagination
- unnecessary renders
- expensive hot-path work
- blocking work in request/async paths

Do not prematurely optimize.

## Compatibility

Check relevant compatibility boundaries:

- public API response/request shape
- existing DocType/data behavior
- integrations
- frontend callers
- existing records
- supported Frappe/ERPNext versions

## Final diff review

Before completion verify:

- task is actually satisfied
- no unrelated changes
- no duplicate logic
- no leftover debug code
- no secrets
- no unintended permission changes
- no unnecessary dependency
- no accidental generated files
- tests/checks reflect the actual risk
- docs remain accurate

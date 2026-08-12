# High-Risk and State-Changing Operations

Load only when the task involves migrations, security-sensitive behavior, permission bypass, destructive operations, Bench state changes, production, or irreversible side effects.

## Security

When relevant check:
- authentication/authorization
- permission bypass and guest access
- input validation/injection
- XSS/CSRF/SSRF
- unsafe file/path handling
- secret/sensitive-data exposure
- token/session behavior
- privilege escalation

Do not add unrelated security complexity, but do not weaken existing protections.

## Database and migration safety

When schema/data changes are needed, inspect existing Frappe/project migration conventions and consider:
- existing records
- nullability/defaults
- indexes/uniqueness/relations
- backfill
- transaction/rollback implications
- compatibility during upgrade

Avoid destructive data changes unless explicitly required.

## Bench / operational commands

Do not run state-changing commands without explicit user permission, including:
- `bench build`
- `bench migrate`
- `bench update`
- `bench restart`
- cache-clearing commands
- app install/uninstall
- patch execution
- database restore
- site creation/deletion
- scheduler/production process changes

Before proposing such a command, explain what it changes and its scope when that information matters to the decision.

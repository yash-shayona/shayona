# Frappe Engineering Guidance

Use this file only when the task touches Frappe Framework, ERPNext, or a Frappe app.
Repository-specific `AGENTS.md` remains the primary source of truth.

## 1. Discover the actual Frappe context

Before changing code, identify what is relevant from the repository and bench environment:

- app/module
- Frappe/ERPNext version or branch when relevant
- DocType/controller involved
- hooks/events involved
- client vs server responsibility
- site-specific behavior when relevant
- existing tests and fixtures

Do not assume every Frappe version or app uses identical internals.

## 2. Work in the correct repository

A Frappe bench contains apps under `apps/`; custom app source is normally developed in its app repository.
Do not confuse app source with site data/config under `sites/`.

## 3. Prefer Frappe-native patterns already used by the project

Before adding custom infrastructure, inspect existing use of Frappe mechanisms such as:

- DocType controllers
- hooks
- document events
- permissions
- whitelisted methods/APIs
- database APIs
- background jobs
- patches/migrations
- fixtures
- client scripts / form scripts
- reports
- portal/website files

Reuse the local pattern rather than creating a parallel architecture.

## 4. DocType and business logic

When a DocType is involved, inspect:

- DocType definition/schema
- controller methods
- validation lifecycle
- linked DocTypes
- permissions
- hooks that affect the document
- client-side handlers only if they participate in the behavior
- existing tests

Keep business rules in the project's established server-side location rather than relying only on client-side validation when server enforcement is required.

## 5. Database access

Prefer the Frappe APIs and patterns already present in the app.

Before introducing raw SQL, verify that the existing ORM/database APIs cannot express the operation adequately.

For write behavior, consider:

- permissions
- document lifecycle hooks
- transactions
- side effects
- existing data
- migration/backfill needs

Do not bypass framework behavior accidentally for convenience.

## 6. API / whitelisted methods

When changing an API or whitelisted method, inspect:

- authentication expectations
- guest access if any
- authorization/permission checks
- input validation
- response contract
- error behavior
- callers in frontend/integrations
- backward compatibility

Do not expose internal or sensitive fields unnecessarily.

## 7. Hooks and events

Before adding a new hook:

- inspect `hooks.py`
- search for existing document/event handlers
- check whether a controller method or existing hook is the established pattern
- consider duplicate execution and side effects

Avoid multiple competing implementations of the same business rule.

## 8. Background jobs / scheduler

When asynchronous work is involved, inspect existing queue/scheduler patterns.
Consider:

- idempotency
- retries
- duplicate jobs
- transaction timing
- site context
- error logging
- user/permission context where applicable

## 9. Schema changes, patches, migrations

When data/schema behavior changes:

- follow the repository's existing Frappe migration/patch conventions
- consider existing records
- make backfills safe and repeatable where the project expects that
- avoid destructive data changes without explicit need
- verify upgrade behavior, not only fresh-install behavior, when relevant

## 10. Frontend / Desk / forms

When UI is involved, first find a similar existing Frappe UI in the same app/version.
Reuse project conventions for:

- form scripts
- dialogs
- list views
- pages
- components
- messages/errors
- permissions
- loading states
- translations

Do not move a server-enforced business rule exclusively into JavaScript.

## 11. Tests

Use the project's existing Frappe test conventions.
Frappe's official testing tooling supports tests named `test_*.py`, and app-scoped tests can be run through Bench when appropriate.

Prefer:

- focused test for the affected DocType/module
- regression test for a bug
- permission/validation edge cases where meaningful
- broader app tests only when the change warrants them

Discover the exact command from the repository/version before assuming it.

## 12. Bench commands

Treat commands as version/project-sensitive.
Use repository documentation and `bench --help`/relevant command help when needed.

Do not run destructive commands or broad production migrations merely to test a hypothesis.
Do not run a full build unless the change actually requires it or repository instructions require it.

## 13. Source hierarchy

When behavior is unclear, prefer evidence in this order:

1. current repository code and its `AGENTS.md`
2. official Frappe/ERPNext documentation for the relevant version
3. official Frappe organization GitHub implementation
4. clearly labeled inference only when the above are insufficient

Do not substitute generic Django/Python/JavaScript assumptions for Frappe-specific behavior when the framework implementation can be checked.

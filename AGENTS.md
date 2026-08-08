# Frappe and ERPNext Project Instructions

These instructions apply to Frappe Framework, ERPNext, and official Frappe application work in this repository.

They supplement the global coding-agent instructions.

## 1. Confirm the Exact Frappe Environment

Before giving a repository-specific solution, confirm where relevant:

* Current Git branch
* Frappe version
* ERPNext version
* Relevant official app version
* Custom app version
* Installed applications
* Site context
* Whether the code belongs to Frappe core, ERPNext, an official app, a custom app, a Server Script, Client Script, Report, Print Format, Web Page, or another Desk configuration
* Whether an override, hook, monkey patch, custom field, property setter, or custom DocType is involved

Do not assume that behaviour from another Frappe version applies to the current version.

When framework behaviour is uncertain, verify it from:

* The exact installed source code
* The matching official branch or tag
* Official Frappe or ERPNext documentation
* Existing project usage

---

## 2. Understand the Real DocType Lifecycle

Before suggesting validation or logic for a DocType, determine its actual business role.

Possible classifications include:

* Master or setup data
* Business transaction
* Configuration
* Child table
* Temporary or staging data
* System-generated record
* Imported or synchronized record
* Derived or calculated data
* Processing queue
* Integration record
* Log, audit, or tracking data

Confirm who or what creates and updates it:

* Desk user
* Website user
* API
* Import
* Scheduler
* Background job
* External device
* External integration
* Another DocType
* Document submission or cancellation
* Automated calculation
* Patch or migration

Confirm whether the flow is:

* Manual
* Automated
* Both manual and automated
* Interactive
* Unattended

Trace:

* What occurs before the DocType
* How it is created
* Which controller events run
* Which hooks run
* Which linked records are read or written
* What occurs after processing
* Whether failure blocks a user or an automated process

Do not treat every DocType as a manually entered Desk form.

---

## 3. Lifecycle-Aware Error Handling

Before using:

* `frappe.throw`
* Confirmation dialogs
* Popups
* Mandatory manual correction
* Desk-only interaction
* Client-side validation

Confirm whether a user is present during processing.

For interactive business transactions, blocking validation may be appropriate.

For schedulers, integrations, imports, devices, APIs, queues, and background jobs, consider safer unattended handling such as:

* Structured error logging
* Status fields
* Failure reason fields
* Retry handling
* Skipped-record reporting
* Processing summaries
* Idempotent retries
* Recoverable states
* Administrator notifications

Do not introduce an interactive dependency into an unattended workflow.

Explain how the DocType classification affects the proposed error handling.

---

## 4. Inspect All Relevant Frappe Extension Points

Before deciding where logic belongs, inspect where relevant:

* DocType controller
* `validate`
* `before_validate`
* `before_insert`
* `after_insert`
* `before_save`
* `on_update`
* `before_submit`
* `on_submit`
* `before_cancel`
* `on_cancel`
* `on_trash`
* `after_delete`
* `doc_events`
* `override_doctype_class`
* `override_whitelisted_methods`
* Scheduler hooks
* Background jobs
* Queues
* Server Scripts
* Client Scripts
* List view scripts
* Reports
* Workflows
* Notifications
* Web forms
* API endpoints
* Integrations
* Related DocTypes
* Existing patches
* Custom fields and property setters

Do not place logic in a client script when the rule must also protect API, import, background, or server-side flows.

Do not duplicate server-side business rules only in the frontend.

---

## 5. Prefer Standard Frappe Mechanisms

Before creating custom infrastructure, check whether the requirement can be handled safely through:

* Standard DocType fields
* Settings DocType
* Workflow
* Assignment Rule
* Notification
* Server Script
* Client Script
* Report
* Print Format
* Property Setter
* Custom Field
* Hook
* Background job
* Scheduler event
* Existing controller extension point
* Standard Frappe API
* Existing custom-app pattern

Prefer a Desk-level or built-in solution when it fully satisfies the requirement and remains maintainable.

Do not recommend a new custom app or complex architecture before checking existing standard options.

Also do not force a Desk-only solution when the requirement requires tested, version-controlled application code.

Explain why the selected implementation level is appropriate.

---

## 6. Desk, Website, and Bundle Boundaries

Confirm where the code executes:

* Frappe Desk
* Website page
* Web form
* Portal
* Print rendering
* Background worker
* Scheduler
* Server
* Browser
* Mobile or external client

Do not assume Desk-only JavaScript APIs are available in website or portal bundles.

Before recommending APIs such as dialogs, form controls, list views, or Desk utilities, verify that they are included in the target execution context.

Keep client-side convenience logic separate from server-side authoritative validation.

---

## 7. Permissions and Security

For every relevant Frappe operation, check:

* DocType permissions
* User permissions
* Role permissions
* Company restrictions
* Permission query conditions
* Shared documents
* Guest access
* Whitelisted method exposure
* `allow_guest`
* `ignore_permissions`
* `sudo`-like bypass behaviour
* Field-level sensitive data
* File access
* CSRF and request context

Do not use `ignore_permissions=True` without a verified business reason.

Do not expose an internal method through `@frappe.whitelist()` unless the caller, permission checks, input validation, and response exposure have been reviewed.

Do not assume a logged-in user exists in scheduler or worker execution.

---

## 8. Document API Versus Direct Database Updates

Before choosing an update method, consider whether controller hooks, validation, permissions, modified timestamps, versioning, notifications, and related logic must run.

Inspect whether the project uses:

* `doc.insert()`
* `doc.save()`
* `doc.submit()`
* `doc.cancel()`
* `frappe.db.set_value()`
* `frappe.db.bulk_update()`
* `frappe.get_all()`
* `frappe.get_list()`
* Frappe Query Builder
* Direct SQL

Do not replace a document API call with a direct database update without explaining which hooks and validations will be bypassed.

Do not use direct SQL merely because it is shorter.

When direct SQL is necessary:

* Parameterize values
* Confirm table and field names
* Respect tenant and permission requirements
* Explain bypassed framework behaviour
* Consider rollback
* Preview affected records
* Avoid broad updates

---

## 9. Query and Report Safety

For Frappe reports, Insights queries, Query Builder, and SQL:

* Confirm the intended data grain.
* Confirm join cardinality.
* Check whether joins multiply rows.
* Check grouping before aggregation.
* Check null and empty-string behaviour.
* Confirm date filters and timezone handling.
* Check submitted, cancelled, and draft document status.
* Verify company and permission filters.
* Check whether a target or measure is repeated once per joined transaction.
* Avoid N+1 queries.
* Parameterize report filters.
* Preserve numeric types until final formatting.

When totals are incorrect, inspect the dataset grain before changing the final formula.

Do not solve duplicate aggregation only by applying `DISTINCT` unless the underlying relationship justifies it.

---

## 10. Background Jobs and Automated Processing

For scheduler and background processing, inspect:

* Queue name
* Timeout
* Retry behaviour
* Idempotency
* Duplicate enqueue protection
* Concurrent workers
* Record locking
* Processing status
* Partial success
* Failure recovery
* Progress reporting
* Realtime events
* Transaction boundaries
* Whether a worker can safely resume

A retry must not create duplicate business records or repeat irreversible side effects.

Prefer explicit statuses such as Pending, Processing, Failed, Validated, or Processed when they match the existing project pattern.

Do not introduce new statuses without checking reports, filters, list indicators, workflows, and integrations that depend on current values.

---

## 11. Configuration-Driven Frappe Logic

Before creating constants, check whether the value belongs in:

* An existing Settings DocType
* `hooks.py`
* Site configuration
* Common site configuration
* A standard Frappe setting
* A custom field
* A shared project constant
* An existing mapping
* An integration configuration record

Use a Settings DocType when authorised users genuinely need to maintain the value through Desk.

Use code-level constants when the value is technical, version-controlled, and not intended for normal user configuration.

Do not move every fixed business rule into a Settings DocType.

Explain:

* Who should be allowed to change the value
* How often it may change
* Whether a code deployment should be required
* Why the selected configuration location is appropriate

---

## 12. Frappe Commands

Do not run Frappe or Bench commands that modify state without explicit permission.

This includes, where applicable:

* `bench build`
* `bench migrate`
* `bench update`
* `bench restart`
* `bench clear-cache`
* `bench clear-website-cache`
* App installation or uninstallation
* Patch execution
* Database restore
* Site creation or deletion
* Scheduler changes
* Production process changes

Before suggesting such a command, explain:

* What it changes
* Whether it affects one site or the full bench
* Whether downtime is possible
* Whether backup is required
* Whether the command belongs on local, staging, or production

Never imply that running a command locally automatically updates another server.

---

## 13. Required Frappe Answer Format

For answers involving a DocType, state:

### Classification

Whether the DocType is confirmed or likely to be master, transaction, configuration, generated, staging, child, or log data.

### Creator and Updater

Who or what creates and updates it.

### Execution Mode

Whether processing is manual, automated, or both.

### User Presence

Whether a user is expected to be present during processing.

### Lifecycle

What happens before, during, and after this DocType.

### Evidence

Which controller, hooks, scheduler, API, integration, or project files support the classification.

### Solution Impact

How the lifecycle affects validation, errors, permissions, transactions, retries, and UI behaviour.

Do not label the classification as confirmed unless it has been verified from actual project code, exact framework implementation, official documentation, hooks, integrations, or existing usage.

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
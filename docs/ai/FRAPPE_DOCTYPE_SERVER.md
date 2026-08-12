# Frappe DocType and Server Guidance

Load this file only for DocType lifecycle, controller/hook, server validation, permission/API, document update, or configuration tasks.

## Classify the flow before changing it

Determine only what is necessary:
- business role: master/setup, transaction, configuration, child, staging, generated, integration, queue/log
- creator/updater: Desk user, website/API, import, scheduler/job, integration/device, another DocType
- execution: interactive, unattended, or both
- relevant lifecycle and extension points

Inspect relevant controller methods and hooks such as validation/insert/save/submit/cancel/delete events, `doc_events`, controller overrides, whitelisted method overrides, scheduler hooks, Server Scripts, Client Scripts, workflows, integrations, and related DocTypes only when they can affect the task.

Do not assume every DocType is a manually entered Desk form.

## Error handling

Use blocking interaction such as `frappe.throw` only when blocking the current operation is correct.

For unattended processing, evaluate project patterns for:
- structured logging
- status/failure fields
- retry/idempotency
- partial-success handling
- administrator notification

Do not introduce a user-dialog dependency into scheduler, worker, import, integration, or other unattended execution.

## Standard Frappe mechanisms first

Before inventing infrastructure, check existing project usage and standard mechanisms such as:
- DocType fields / Settings DocType
- Workflow / Notification / Assignment Rule
- Server Script / Client Script
- hooks and controller extension points
- background jobs / scheduler
- Reports / Print Formats
- Custom Fields / Property Setters
- standard Frappe APIs

Choose version-controlled app code when the behavior needs tested, maintainable server-side logic.

## Permissions and APIs

When relevant, verify DocType/user/role/company restrictions, query conditions, guest access, field/file sensitivity, and request context.

Do not use `ignore_permissions=True` without a verified business reason.

Do not expose a method through `@frappe.whitelist()` without reviewing caller permissions, input validation, and response exposure.

## Document API versus DB update

Before choosing `doc.save()/insert()/submit()/cancel()`, `frappe.db.set_value`, Query Builder, or SQL, determine which hooks, validations, permissions, timestamps, versions, notifications, and side effects must run.

Do not replace a document API with a direct DB update without evidence that bypassing those behaviors is correct.

For SQL, parameterize values and verify scope, rollback/transaction behavior, and affected records.

## Configuration

Use an existing Settings DocType when authorized users genuinely need runtime configuration through Desk.

Use code-level constants when the value is technical/version-controlled and not intended for normal user changes.

Do not turn every business rule into configuration.

## Reporting

In the final answer, do not dump a lifecycle checklist. Mention classification/lifecycle evidence only when it materially explains the solution.

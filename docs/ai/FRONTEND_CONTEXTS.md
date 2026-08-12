# Frappe Frontend Execution Contexts

Load only for Desk JavaScript, form/list scripts, website, portal, web forms, browser bundles, or client/server validation boundaries.

First determine where the code runs:
- Desk
- website/portal/web form
- browser bundle
- server-rendered/print context
- external/mobile client

Do not assume Desk-only APIs exist in website or portal bundles.

Reuse existing project patterns for form events, dialogs, list behavior, requests, states, styling, and validation.

Keep client-side convenience validation separate from authoritative server-side business rules when API/import/background flows must also be protected.

For UI changes, verify only relevant states such as loading, success, empty, validation/error, disabled/permission state, responsive behavior, and keyboard/focus accessibility.

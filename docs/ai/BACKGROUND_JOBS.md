# Background Jobs and Unattended Processing

Load only for scheduler events, queues, background jobs, integrations, imports, devices, retries, or unattended processing.

Inspect only what is relevant:
- queue and timeout
- retry behavior
- idempotency
- duplicate enqueue protection
- concurrency / locking
- processing status
- partial success
- failure recovery
- transaction boundaries
- irreversible side effects
- safe resume behavior

A retry must not duplicate business records or repeat irreversible side effects.

Do not assume a logged-in user exists.

Do not introduce interactive dialogs or mandatory user correction into an unattended path.

Prefer existing project status/retry patterns. Do not add new statuses without checking reports, filters, workflows, list indicators, and integrations that depend on existing values.

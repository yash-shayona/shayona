# Daily Task Prompt

Normally, type only what you want.

## Minimal

```text
<what I want>
```

Example:

```text
Add a date filter to the customer dashboard.
```

## With useful evidence

```text
<what I want>

Observed:
<error/current behavior>

Expected:
<expected behavior>
```

Example:

```text
Fix Sales Invoice grand total when tax is inclusive.

Observed:
Grand total is incorrect after an item-wise discount.

Expected:
Existing tax-inclusive behavior should remain correct with or without discount.
```

## If you know a likely starting file

```text
<what I want>

Start investigation around:
<path>

Trace dependencies if needed; do not assume the cause is limited to this file.
```

## Planning only

Use this only when you explicitly do NOT want implementation yet:

```text
Investigate and produce an implementation plan for:
<what I want>

Do not modify files yet.
```

## Normal implementation

Do NOT add `plan first`, `test it`, `review the diff`, etc. every time. Those are already in the repository workflow.

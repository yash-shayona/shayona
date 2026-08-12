# Reports and Query Safety

Load only for reports, SQL, Query Builder, joins, aggregation, or incorrect totals.

Check the intended data grain before changing formulas.

When relevant verify:
- join cardinality and row multiplication
- grouping before aggregation
- null/empty behavior
- date/timezone filters
- draft/submitted/cancelled status
- company and permission filters
- repeated targets/measures caused by joins
- N+1 queries
- parameterized filters
- numeric types before formatting

Do not use `DISTINCT` merely to hide duplicate aggregation unless the underlying relationship proves it is correct.

Prefer existing Frappe Query Builder/report patterns when they fit. If direct SQL is necessary, parameterize values and explain any relevant framework/permission behavior being bypassed.

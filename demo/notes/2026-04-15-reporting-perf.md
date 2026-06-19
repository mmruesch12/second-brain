---
title: Reporting Pipeline Performance Log
date: 2026-04-15
tags: [performance, reporting]
---

# April Performance Observations

## Measurements

| Query | Latency (ms) | Notes |
|-------|--------------|-------|
| list recent | 1250 | slow after join |
| search by tag | 890 | table scan |

See code for the slow path.

```sql
-- example slow query
SELECT * FROM notes WHERE ...
```

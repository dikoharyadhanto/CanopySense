# CDC-WALK-003-v0.3 — Technical Walkthrough

> [!IMPORTANT]
> **Dependencies**: `ANT-WO-003-v0.3`. **Migrated from legacy** `CDC-WALK-003-v0.10`.

## 1. Scope

Generic Write Routing: Patcher-Cloud now returns `writes` array — each entry a self-contained instruction. Patcher-Local is a pure executor with zero domain knowledge.

**Contract:**

```json
{
  "status": "success",
  "api_version": "1.1",
  "writes": [
    {"table": "satellite_data", "columns": [...], "values": [...], "conflict_columns": [...]},
    {"table": "patcher_write_test", "columns": [...], "values": [...], "conflict_columns": [...]}
  ]
}
```

Patcher-Local loops, builds `INSERT INTO {table} (...) VALUES (...) ON CONFLICT DO NOTHING` per entry. Adding a new cloud-side table requires zero Patcher-Local changes.

---

*Migrated from legacy `CDC-WALK-003-v0.10`.*

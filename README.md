# Schema Registry

A small but critical service that turns "column names in code" into an auditable, versioned contract shared by every producer and consumer in your stack.

## Why You Need It

| Pain without a registry                                                                 | What the registry fixes                                                                                                                                |
| --------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Loader silently breaks when a data vendor adds a new column or renames an old one.      | Loader pulls the current schema before ingest; if the file doesn't conform, ingestion halts and you get a Slack alert before bad rows leak downstream. |
| Hard‑coded field lists scattered across ETL jobs, ML notebooks, and C++ back‑test code. | Single source‑of‑truth JSON; every client library (tickdb, C++ loader, Great Expectations suite) reads it at runtime.                                  |
| Nobody knows if changing volume from int32 → int64 will break dashboards.               | GitHub diff bot classifies the change (compatible / incompatible) and blocks the PR if risk is high.                                                   |

## Core Design

```
┌─────────────────────────────┐
│   Git Repo  (schemas/)      │  <-- truth
└────────┬────────────────────┘
         │ PR merged
         ▼
┌─────────────────────────────┐
│  GitHub Action:             │
│  schema‑diff + tests        │
└────────┬────────────────────┘        kubectl apply
         ▼
┌─────────────────────────────┐   k8s service
│  Schema‑Registry API        │◀─────────────┐
│  (FastAPI + Etcd backend)   │              │
└────────┬──────────┬────────┘              │
         │          │                       │
 GET /schema/ticks  │                       │
         │          │                       │
         ▼          ▼                       │
┌────────────┐  ┌──────────────┐            │
│ Dataset    │  │ Great Expect │            │
│ Cleaner    │  │ Validation   │            │
└────────────┘  └──────────────┘            │
         ▲          ▲                       │
         └──────────┴───────────────────────┘
            Arrow & jsonschema clients
```

## Quick Start

1. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

2. **Start the service:**

   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

3. **Register a schema:**

   ```bash
   curl -X POST "http://localhost:8000/schema/ticks_v1" \
        -H "Content-Type: application/json" \
        -d @schemas/ticks_v1.json
   ```

4. **Fetch a schema:**
   ```bash
   curl "http://localhost:8000/schema/ticks_v1"
   ```

## Schema Document Format

Uses JSON-Schema Draft-07, plus an optional Arrow type block for fast C++ mapping:

```json
{
  "$id": "ticks_v1",
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Level‑1 Tick Data",
  "type": "object",
  "properties": {
    "ts": { "type": "string", "format": "date-time" },
    "symbol": { "type": "string" },
    "price": { "type": "number" },
    "size": { "type": "integer" },
    "side": { "type": "string", "enum": ["B", "S"] }
  },
  "required": ["ts", "symbol", "price", "size"],
  "additionalProperties": false,
  "arrow": {
    "fields": [
      { "name": "ts", "type": { "name": "timestamp", "unit": "us" } },
      { "name": "symbol", "type": { "name": "utf8" } },
      { "name": "price", "type": { "name": "float64" } },
      { "name": "size", "type": { "name": "int32" } },
      { "name": "side", "type": { "name": "utf8" } }
    ]
  },
  "version": "1.0.0"
}
```

## API Reference

| Verb | Path                               | Description                                       |
| ---- | ---------------------------------- | ------------------------------------------------- |
| GET  | `/schema/{id}`                     | Returns latest version                            |
| GET  | `/schema/{id}/{ver}`               | Returns specific version                          |
| POST | `/schema/{id}`                     | Create new schema (CI bot only)                   |
| POST | `/schema/{id}/compat`              | Check if candidate JSON is compatible with latest |
| GET  | `/compat/{id}/{ver_from}/{ver_to}` | Returns "compatible" or "incompatible + message"  |

## Development

### Running Tests

```bash
pytest tests/
```

### Schema Validation

```bash
python scripts/validate_schema.py schemas/ticks_v1.json
```

### Schema Diff

```bash
python scripts/diff_schemas.py v1.0.0 v1.1.0 schemas/ticks_v1.json
```

## Deployment

The service is designed to run in Kubernetes with Etcd as the backend storage. See `k8s/` directory for deployment manifests.

## Security

- API protected by mTLS inside k8s
- GitHub OIDC token + short-lived Etcd JWT for CI bot
- Nightly Etcd snapshots to S3
- Schema files versioned in Git repo

# QueryForge

Natural-language to SQL agent. Upload a database file (SQLite, CSV, Excel), ask a question in plain English, and get a validated SQL query with executed results.

## Architecture

```
┌──────────────────┐      ┌───────────────────────────────────────┐
│  React Frontend  │─────▶│  FastAPI Backend (/api/v1/sql/...)    │
│  (Vite + TW)     │      │                                       │
└──────────────────┘      │  ┌─────────────┐  ┌────────────────┐  │
                          │  │ SQL Agent   │  │ Schema         │  │
                          │  │ Service     │  │ Extractor      │  │
                          │  │ (Mistral or │  │ (SQLite/CSV/   │  │
                          │  │  Ollama)    │  │  Excel)        │  │
                          │  └──────┬──────┘  └────────────────┘  │
                          │         │                              │
                          │  ┌──────▼──────┐  ┌────────────────┐  │
                          │  │ SQL Safety  │  │ Query Executor │  │
                          │  │ Validator   │  │ (read-only     │  │
                          │  │             │  │  SQLite)       │  │
                          │  └─────────────┘  └────────────────┘  │
                          └───────────────────────────────────────┘
```

**Backend** (Python/FastAPI):
- `sql_agent_service.py` — LLM abstraction supporting Mistral API and Ollama (sqlcoder)
- `sql_safety.py` — validates queries: blocks DROP/DELETE/ALTER/injection, enforces SELECT-only
- `schema_extractor.py` — extracts schema from SQLite, CSV, Excel, SQL dumps, JSON
- `sql_endpoints.py` — REST API: generate SQL, validate, upload+query+execute, health check

**Frontend** (React/Vite/Tailwind):
- File upload (drag & drop)
- Natural language question input
- Displays: generated SQL, validation status, result table with columns/rows/timing

## Setup

### Prerequisites

- Python 3.10+
- Node.js 18+

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env — set MISTRAL_API_KEY
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend runs at `http://localhost:3000` and proxies `/api` requests to the backend.

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `LLM_PROVIDER` | No | `mistral` | `mistral` or `ollama` |
| `MISTRAL_API_KEY` | Yes (if mistral) | — | Mistral API key |
| `MISTRAL_MODEL` | No | `codestral-latest` | Mistral model name |
| `OLLAMA_URL` | No | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | No | `sqlcoder` | Ollama model name |

## API Endpoints

### `POST /api/v1/sql/query`

Upload a file and ask a question. Returns generated SQL and executed results.

```bash
curl -X POST http://localhost:8000/api/v1/sql/query \
  -F "file=@data.csv" \
  -F "question=Show the top 5 rows by revenue" \
  -F "max_rows=10"
```

Response:
```json
{
  "schema": { "name": "data", "tables": ["..."] },
  "sql": "SELECT * FROM data ORDER BY revenue DESC LIMIT 5",
  "explanation": "This query filters data to answer: ...",
  "is_valid": true,
  "validation_errors": [],
  "confidence": 0.9,
  "result": {
    "columns": ["id", "name", "revenue"],
    "rows": [[1, "Acme", 50000]],
    "row_count": 5,
    "execution_time_ms": 1.2
  },
  "execution_error": null
}
```

### `POST /api/v1/sql/generate`

Generate SQL from a question and schema (no file upload or execution).

```bash
curl -X POST http://localhost:8000/api/v1/sql/generate \
  -H "Content-Type: application/json" \
  -d '{
    "question": "How many users are there?",
    "schema": {
      "name": "mydb",
      "tables": [{
        "name": "users",
        "columns": [
          {"name": "id", "type": "INTEGER", "primary_key": true, "nullable": false},
          {"name": "name", "type": "TEXT", "primary_key": false, "nullable": false}
        ],
        "foreign_keys": []
      }]
    }
  }'
```

### `POST /api/v1/sql/extract-schema`

Extract schema from an uploaded file without generating SQL.

### `GET /api/v1/sql/health`

Returns provider status and connectivity.

## Tests

```bash
cd backend
python -m pytest tests/ -v
```

## Supported File Types

| Format | Extensions |
|---|---|
| SQLite | `.db`, `.sqlite`, `.sqlite3` |
| CSV | `.csv` |
| Excel | `.xlsx`, `.xls` |

## Security

- All generated queries pass through the SQL safety validator
- Only `SELECT` statements are allowed (strict mode)
- `DROP`, `DELETE`, `TRUNCATE`, `ALTER`, `INSERT`, `UPDATE` are blocked
- SQL injection patterns (`;`, `--`, `/*`) are detected and rejected
- Uploaded files are executed in read-only SQLite mode (`PRAGMA query_only = ON`)
- Result sets are capped at a configurable `max_rows` (default 100)

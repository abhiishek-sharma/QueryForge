# QueryForge

Ask questions about your data in plain English and get safe, validated SQL back.

QueryForge is a natural-language-to-SQL agent. It reads your database schema, builds a schema-aware prompt, generates SQL with **SQLCoder** running locally on **Ollama**, and passes every query through a safety validator before anything can run.

```
"How many songs does each singer have?"
        │
        ▼
SELECT singer.name, COUNT(song.song_id) AS song_count
FROM singer
LEFT JOIN song ON singer.singer_id = song.singer_id
GROUP BY singer.singer_id, singer.name;
```

## Features

- **Natural language → SQL** with SQLCoder, a model fine-tuned for text-to-SQL, served locally through Ollama. No data leaves your machine.
- **Schema-aware prompting.** Tables, columns, types, primary keys and foreign keys are injected into the prompt, so joins use real relationships instead of guesses.
- **Multi-format schema extraction.** Load a schema from a SQLite database, Excel workbook, CSV files, a SQL dump or JSON. Column types are inferred from the data.
- **SQL safety guardrails.** Built on `sqlparse`:
  - SELECT-only whitelist in strict mode
  - blocks `DROP`, `TRUNCATE`, `ALTER`, `GRANT`/`REVOKE`, `EXEC`
  - blocks `DELETE` and `UPDATE` without a `WHERE` clause
  - blocks stacked-query and comment-injection patterns (`; DROP`, `--`, `/* */`)
- **Structured responses.** Each result returns the SQL, a validity flag, any validation errors, a confidence score and an explanation.
- **FastAPI backend and React frontend.**

## Architecture

```
React UI ──► FastAPI ──► SQLAgentService ──► Ollama (sqlcoder)
                │              │
                │              └──► SQLSafetyValidator (sqlparse)
                └──► SchemaExtractor (SQLite / Excel / CSV / SQL dump / JSON)
```

| Path | Purpose |
| --- | --- |
| `backend/app/services/sql_agent_service.py` | Prompt construction, Ollama call, SQL extraction |
| `backend/app/utils/sql_safety.py` | Safety validation and blocked-pattern rules |
| `backend/app/utils/schema_extractor.py` | Schema extraction and type inference |
| `backend/app/api/` | REST endpoints |
| `frontend/` | React client |

## Quick start

**Requirements:** Python 3.11+, Node.js 18+, [Ollama](https://ollama.com)

```bash
# 1. Pull the model
ollama pull sqlcoder

# 2. Backend
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload       # http://localhost:8000, docs at /docs

# 3. Frontend (new terminal)
cd frontend
npm install
npm run dev
```

## API

### `GET /api/v1/sql/health`

Checks that the service and Ollama are reachable.

### `POST /api/v1/sql/generate`

```json
{
  "question": "List all singers born after 1990",
  "schema": {
    "name": "music_database",
    "tables": [
      {
        "name": "singer",
        "columns": [
          {"name": "singer_id", "type": "INTEGER", "primary_key": true},
          {"name": "name", "type": "TEXT"},
          {"name": "birth_year", "type": "INTEGER"}
        ],
        "foreign_keys": []
      }
    ]
  },
  "execute": false
}
```

Response:

```json
{
  "sql": "SELECT name FROM singer WHERE birth_year > 1990",
  "is_valid": true,
  "validation_errors": [],
  "confidence": 0.9,
  "explanation": "..."
}
```

A query that fails validation comes back with `is_valid: false` and the reasons in `validation_errors`, and is never executed.

## Testing

```bash
cd backend
python test_sql_api.py     # runs sample questions against a running server
```

Sample schemas (music and e-commerce) with expected SQL are in `backend/test_examples.py`.

## License

MIT

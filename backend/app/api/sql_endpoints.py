import os
import sqlite3
import tempfile
import time
import logging
import shutil
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, HTTPException, File, UploadFile, Form

from app.schemas.sql_schemas import (
    SQLRequest,
    SQLResponse,
    QueryResult,
    DatabaseSchema,
)
from app.services.sql_agent_service import (
    SQLAgentService,
    LLM_PROVIDER,
    MISTRAL_API_KEY,
    OLLAMA_URL,
)
from app.utils.schema_extractor import SchemaExtractor
from app.utils.sql_safety import SQLSafetyValidator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sql", tags=["SQL Agent"])
sql_agent = SQLAgentService()
safety = SQLSafetyValidator()


def _file_to_sqlite(file_path: str, ext: str) -> str:
    if ext in (".db", ".sqlite", ".sqlite3"):
        return file_path
    db_path = file_path + ".sqlite"
    conn = sqlite3.connect(db_path)
    if ext == ".csv":
        df = pd.read_csv(file_path)
        table_name = Path(file_path).stem
        df.to_sql(table_name, conn, if_exists="replace", index=False)
    elif ext in (".xlsx", ".xls"):
        xls = pd.ExcelFile(file_path)
        for sheet in xls.sheet_names:
            df = pd.read_excel(file_path, sheet_name=sheet)
            df.to_sql(sheet, conn, if_exists="replace", index=False)
    conn.close()
    return db_path


def _execute_readonly(db_path: str, sql: str, max_rows: int = 100) -> QueryResult:
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.execute("PRAGMA query_only = ON")
    cursor = conn.cursor()
    start = time.time()
    cursor.execute(sql)
    columns = [desc[0] for desc in cursor.description] if cursor.description else []
    rows = cursor.fetchmany(max_rows)
    elapsed = (time.time() - start) * 1000
    conn.close()
    return QueryResult(
        columns=columns,
        rows=[list(r) for r in rows],
        row_count=len(rows),
        execution_time_ms=round(elapsed, 2),
    )


@router.post("/generate", response_model=SQLResponse)
async def generate_sql(request: SQLRequest):
    try:
        return await sql_agent.generate_sql(
            question=request.question,
            schema=request.db_schema,
        )
    except Exception as e:
        logger.error(f"generate_sql error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validate", response_model=SQLResponse)
async def validate_sql(request: SQLRequest):
    try:
        return await sql_agent.validate_sql(
            sql=request.question,
            schema=request.db_schema,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query")
async def query(
    file: UploadFile = File(...),
    question: str = Form(...),
    max_rows: int = Form(100),
):
    allowed = (".db", ".sqlite", ".sqlite3", ".csv", ".xlsx", ".xls")
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(allowed)}",
        )

    tmp_dir = tempfile.mkdtemp()
    file_path = os.path.join(tmp_dir, f"upload{ext}")
    try:
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        schema = SchemaExtractor.extract_schema_auto(file_path)
        schema.name = Path(file.filename).stem

        sql_response = await sql_agent.generate_sql(question=question, schema=schema)

        result = None
        execution_error = None
        if sql_response.is_valid:
            db_path = _file_to_sqlite(file_path, ext)
            try:
                sanitized = safety.sanitize_sql(sql_response.sql, max_rows=max_rows)
                result = _execute_readonly(db_path, sanitized, max_rows)
            except Exception as e:
                execution_error = str(e)

        return {
            "schema": schema.model_dump(),
            "sql": sql_response.sql,
            "explanation": sql_response.explanation,
            "is_valid": sql_response.is_valid,
            "validation_errors": [
                err.model_dump() for err in sql_response.validation_errors
            ],
            "confidence": sql_response.confidence,
            "result": result.model_dump() if result else None,
            "execution_error": execution_error,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@router.post("/extract-schema")
async def extract_schema_from_file(file: UploadFile = File(...)):
    allowed = (".db", ".sqlite", ".sqlite3", ".xlsx", ".xls", ".csv", ".sql", ".json")
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(allowed)}",
        )

    tmp_dir = tempfile.mkdtemp()
    file_path = os.path.join(tmp_dir, f"upload{ext}")
    try:
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        schema = SchemaExtractor.extract_schema_auto(file_path)
        schema.name = Path(file.filename).stem
        info = SchemaExtractor.get_schema_info(file_path)

        return {"schema": schema.model_dump(), "info": info, "filename": file.filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@router.get("/health")
async def health_check():
    provider = LLM_PROVIDER
    if provider == "ollama":
        try:
            import httpx

            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{OLLAMA_URL}/api/tags")
                models = (
                    resp.json().get("models", []) if resp.status_code == 200 else []
                )
                sqlcoder = any(
                    m.get("name", "").startswith("sqlcoder") for m in models
                )
                return {
                    "status": "healthy" if resp.status_code == 200 else "degraded",
                    "provider": "ollama",
                    "ollama_connected": resp.status_code == 200,
                    "sqlcoder_available": sqlcoder,
                }
        except Exception as e:
            return {"status": "unhealthy", "provider": "ollama", "error": str(e)}
    else:
        has_key = bool(MISTRAL_API_KEY)
        return {
            "status": "healthy" if has_key else "degraded",
            "provider": "mistral",
            "api_key_configured": has_key,
        }

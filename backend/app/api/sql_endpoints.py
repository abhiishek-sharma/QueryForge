import os
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.db.readonly import HARD_MAX_ROWS, QueryRejected, QueryTimeout, execute_readonly
from app.schemas.sql_schemas import QueryResponse, QueryResult
from app.services.sql_agent_service import SQLAgentService
from app.utils.schema_extractor import SUPPORTED_EXTS, extract_schema, to_sqlite

MAX_UPLOAD_MB = float(os.getenv("MAX_UPLOAD_MB", "25"))
MAX_QUESTION_CHARS = 1000
_CHUNK = 1024 * 1024

router = APIRouter(prefix="/sql", tags=["SQL"])
sql_agent = SQLAgentService()


async def _save_upload(file: UploadFile, dest: str) -> None:
    limit = int(MAX_UPLOAD_MB * 1024 * 1024)
    written = 0
    with open(dest, "wb") as out:
        while chunk := await file.read(_CHUNK):
            written += len(chunk)
            if written > limit:
                raise HTTPException(413, f"File exceeds the {MAX_UPLOAD_MB:g} MB upload limit")
            out.write(chunk)
    if written == 0:
        raise HTTPException(400, "Uploaded file is empty")


@router.post("/query", response_model=QueryResponse, response_model_by_alias=True)
async def query(
    file: UploadFile = File(...),
    question: str = Form(...),
    max_rows: int = Form(100),
):
    question = question.strip()
    if not question:
        raise HTTPException(400, "Question is empty")
    if len(question) > MAX_QUESTION_CHARS:
        raise HTTPException(400, f"Question is longer than {MAX_QUESTION_CHARS} characters")
    max_rows = max(1, min(max_rows, HARD_MAX_ROWS))
    ext = Path(file.filename or "").suffix.lower()
    if ext not in SUPPORTED_EXTS:
        raise HTTPException(400, f"Unsupported file type '{ext}'. Allowed: {', '.join(SUPPORTED_EXTS)}")

    tmp_dir = tempfile.mkdtemp(prefix="queryforge_")
    try:
        upload_path = os.path.join(tmp_dir, f"upload{ext}")
        await _save_upload(file, upload_path)
        try:
            db_path = to_sqlite(upload_path, ext, file.filename or "data")
            schema = extract_schema(db_path, name=Path(file.filename or "data").stem)
        except Exception as e:
            raise HTTPException(400, f"Could not read the uploaded file: {e}")
        if not schema.tables:
            raise HTTPException(400, "No tables found in the uploaded file")

        gen = await sql_agent.generate_sql(question, schema)
        result, execution_error = None, None
        if gen.is_valid:
            try:
                r = execute_readonly(db_path, gen.sql, max_rows=max_rows)
                result = QueryResult(**r.__dict__)
            except QueryTimeout as e:
                execution_error = str(e)
            except QueryRejected as e:
                execution_error = f"Blocked by the read-only database connection: {e}"
            except Exception as e:  # e.g. the model referenced a column that does not exist
                execution_error = f"SQLite error: {e}"
        return QueryResponse(schema=schema.model_dump(), generation=gen, result=result, execution_error=execution_error)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@router.get("/health")
async def health():
    info = await sql_agent.health()
    info["status"] = "ok" if info["model_pulled"] else "degraded"
    info["max_upload_mb"] = MAX_UPLOAD_MB
    return info

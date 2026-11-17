"""Natural-language -> SQL using a local Ollama model."""
import os
import re
import time
from typing import Optional, Tuple

import httpx

from app.schemas.sql_schemas import DatabaseSchema, GenerationResult, ValidationError
from app.utils import sql_safety

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")
OLLAMA_TIMEOUT_S = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "180"))

SYSTEM_PROMPT = """You translate questions into a single SQLite query.
Rules:
- Use only the tables and columns in the schema. Never invent columns or tables.
- Write exactly one read-only SELECT statement (WITH ... SELECT is fine).
- Reply with the SQL inside one ```sql code block and nothing else.
- If the question has more than one reasonable reading, choose one and put it on the first line of the code block as: -- Assumption: <what you assumed>
- If the schema does not contain the data needed to answer, do not write SQL. Reply with exactly one line: CANNOT_ANSWER: <short reason>"""

_CANNOT = re.compile(r"CANNOT_ANSWER\s*:?\s*(.*)", re.IGNORECASE)
_ASSUME = re.compile(r"--\s*Assumption\s*:\s*(.+)", re.IGNORECASE)
_START = re.compile(r"^\s*(WITH|SELECT)\b", re.IGNORECASE | re.MULTILINE)


def build_messages(question: str, schema: DatabaseSchema) -> list:
    user = f"Schema:\n{schema.to_prompt_format()}\n\nQuestion: {question}"
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]


def parse_model_output(text: str) -> Tuple[str, Optional[str], Optional[str]]:
    """Return (sql, assumption, cannot_answer_reason) from raw model text."""
    text = (text or "").replace("<s>", "").replace("</s>", "").strip()
    block = re.search(r"```(?:sql|sqlite)?\s*\n?(.*?)(?:```|$)", text, re.DOTALL | re.IGNORECASE)
    body = block.group(1).strip() if block else text
    m = _CANNOT.search(text)
    if m and not _START.search(body):
        return "", None, m.group(1).strip() or "The schema does not contain the needed data."
    a = _ASSUME.search(body)
    assumption = a.group(1).strip() if a else None
    start = _START.search(body)
    # Multiple statements are left in place so the validator rejects them.
    sql = body[start.start():].strip() if start else body
    return sql, assumption, None


class SQLAgentService:
    def __init__(self, url: str = OLLAMA_URL, model: str = OLLAMA_MODEL):
        self.url = url
        self.model = model

    async def _chat(self, messages: list) -> str:
        async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT_S) as client:
            r = await client.post(
                f"{self.url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": 0, "seed": 0, "num_predict": 400},
                },
            )
        if r.status_code != 200:
            raise RuntimeError(f"Ollama returned {r.status_code}: {r.text[:300]}")
        return r.json().get("message", {}).get("content", "")

    async def generate_sql(self, question: str, schema: DatabaseSchema) -> GenerationResult:
        start = time.monotonic()
        try:
            raw = await self._chat(build_messages(question, schema))
        except httpx.ConnectError:
            return GenerationResult(
                model=self.model,
                validation_errors=[ValidationError(
                    error_type="llm_unavailable",
                    message=f"Cannot reach Ollama at {self.url}. Is `ollama serve` running?",
                    severity="critical")],
            )
        except Exception as e:  # timeouts, HTTP errors
            return GenerationResult(
                model=self.model,
                validation_errors=[ValidationError(
                    error_type="generation_error", message=f"SQL generation failed: {e}", severity="critical")],
            )
        elapsed = round((time.monotonic() - start) * 1000, 1)
        sql, assumption, cannot = parse_model_output(raw)
        if cannot:
            return GenerationResult(raw_output=raw, cannot_answer=cannot, model=self.model, generation_time_ms=elapsed)
        ok, errors = sql_safety.validate(sql)
        return GenerationResult(
            sql=sql_safety.prepare(sql) if ok else sql,
            raw_output=raw,
            assumption=assumption,
            is_valid=ok,
            validation_errors=errors,
            model=self.model,
            generation_time_ms=elapsed,
        )

    async def health(self) -> dict:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"{self.url}/api/tags")
            names = [m.get("name", "") for m in r.json().get("models", [])]
            return {"ollama_reachable": True, "model": self.model, "model_pulled": self.model in names}
        except Exception as e:
            return {"ollama_reachable": False, "model": self.model, "model_pulled": False, "error": str(e)}

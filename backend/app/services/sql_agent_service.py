import os
import httpx
import logging
from typing import Optional

from app.schemas.sql_schemas import SQLResponse, DatabaseSchema, ValidationError
from app.utils.sql_safety import SQLSafetyValidator

logger = logging.getLogger(__name__)

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "mistral").lower()
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "sqlcoder")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "codestral-latest")


class SQLAgentService:
    def __init__(self):
        self.safety_validator = SQLSafetyValidator()

    async def generate_sql(
        self,
        question: str,
        schema: DatabaseSchema,
        conversation_history: Optional[list] = None,
    ) -> SQLResponse:
        try:
            prompt = self._build_prompt(question, schema)
            generated_sql = await self._call_llm(prompt)
            sql = self._extract_sql(generated_sql)
            is_valid, errors = self.safety_validator.validate(sql, strict_mode=True)
            if is_valid:
                sql = self.safety_validator.format_sql(sql)
                sql = self.safety_validator.sanitize_sql(sql, max_rows=100)
            explanation = self._generate_explanation(sql, question)
            return SQLResponse(
                sql=sql,
                explanation=explanation,
                is_valid=is_valid,
                validation_errors=errors,
                confidence=0.9 if is_valid else 0.5,
            )
        except Exception as e:
            logger.error(f"Error generating SQL: {e}")
            return SQLResponse(
                sql="",
                explanation=None,
                is_valid=False,
                validation_errors=[
                    ValidationError(
                        error_type="generation_error",
                        message=f"Failed to generate SQL: {e}",
                        severity="critical",
                    )
                ],
                confidence=0.0,
            )

    def _build_prompt(self, question: str, schema: DatabaseSchema) -> str:
        return (
            f"### Task\n"
            f"Generate a SQL query to answer the following question: `{question}`\n\n"
            f"### Database Schema\n"
            f"{schema.to_prompt_format()}\n\n"
            f"### Answer\n"
            f"Given the database schema, here is the SQL query that answers `{question}`:\n"
            f"```sql\n"
        )

    async def _call_llm(self, prompt: str) -> str:
        if LLM_PROVIDER == "ollama":
            return await self._call_ollama(prompt)
        return await self._call_mistral(prompt)

    async def _call_ollama(self, prompt: str) -> str:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.0,
                        "top_p": 0.95,
                        "num_predict": 200,
                        "stop": ["```", "\n\n\n"],
                    },
                },
            )
            if response.status_code != 200:
                raise Exception(f"Ollama API error: {response.text}")
            return response.json().get("response", "")

    async def _call_mistral(self, prompt: str) -> str:
        if not MISTRAL_API_KEY:
            raise Exception("MISTRAL_API_KEY is not set")
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.mistral.ai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {MISTRAL_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": MISTRAL_MODEL,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are a SQL expert. Given a database schema, "
                                "generate only the SQL query that answers the user's "
                                "question. Output only the SQL, no explanation."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.0,
                    "max_tokens": 500,
                },
            )
            if response.status_code != 200:
                raise Exception(f"Mistral API error: {response.text}")
            data = response.json()
            return data["choices"][0]["message"]["content"]

    def _extract_sql(self, generated_text: str) -> str:
        text = generated_text.strip()
        text = text.replace("<s>", "").replace("</s>", "").strip()
        if "```sql" in text:
            start = text.find("```sql") + 6
            end = text.find("```", start)
            if end > start:
                text = text[start:end].strip()
        elif text.startswith("```"):
            text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        for i, line in enumerate(lines):
            if line.upper().startswith("SELECT"):
                sql_lines = [line]
                for next_line in lines[i + 1 :]:
                    sql_lines.append(next_line)
                    if next_line.endswith(";"):
                        break
                return " ".join(sql_lines).strip()
        if lines:
            return lines[0]
        return text

    def _generate_explanation(self, sql: str, question: str) -> str:
        upper = sql.upper()
        if "JOIN" in upper:
            return f"This query joins multiple tables to answer: {question}"
        if "GROUP BY" in upper:
            return f"This query aggregates data to answer: {question}"
        if "WHERE" in upper:
            return f"This query filters data to answer: {question}"
        return f"This query retrieves data to answer: {question}"

    async def validate_sql(self, sql: str, schema: DatabaseSchema) -> SQLResponse:
        is_valid, errors = self.safety_validator.validate(sql, strict_mode=True)
        return SQLResponse(
            sql=sql,
            explanation=None,
            is_valid=is_valid,
            validation_errors=errors,
            confidence=1.0 if is_valid else 0.0,
        )

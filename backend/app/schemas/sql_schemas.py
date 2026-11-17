"""Pydantic models for QueryForge."""
import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

_PLAIN_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def quote_ident(name: str) -> str:
    """Quote an identifier for SQLite unless it is a plain word."""
    if _PLAIN_IDENT.match(name):
        return name
    return '"' + name.replace('"', '""') + '"'


class Column(BaseModel):
    name: str
    type: str
    primary_key: bool = False
    nullable: bool = True


class ForeignKey(BaseModel):
    column: str
    referenced_table: str
    referenced_column: str


class Table(BaseModel):
    name: str
    columns: List[Column]
    foreign_keys: List[ForeignKey] = Field(default_factory=list)
    row_count: Optional[int] = None
    sample_rows: List[List[Any]] = Field(default_factory=list)


class DatabaseSchema(BaseModel):
    name: str = "database"
    tables: List[Table]

    def to_prompt_format(self) -> str:
        """CREATE TABLE statements plus a few sample rows as SQL comments."""
        blocks = []
        for t in self.tables:
            defs = []
            for c in t.columns:
                d = f"  {quote_ident(c.name)} {c.type or 'TEXT'}"
                if c.primary_key:
                    d += " PRIMARY KEY"
                if not c.nullable:
                    d += " NOT NULL"
                defs.append(d)
            for fk in t.foreign_keys:
                defs.append(
                    f"  FOREIGN KEY ({quote_ident(fk.column)}) REFERENCES "
                    f"{quote_ident(fk.referenced_table)}({quote_ident(fk.referenced_column)})"
                )
            block = f"CREATE TABLE {quote_ident(t.name)} (\n" + ",\n".join(defs) + "\n);"
            if t.sample_rows:
                header = ", ".join(c.name for c in t.columns)
                rows = "\n".join("--   " + ", ".join(repr(v) for v in r) for r in t.sample_rows)
                block += f"\n-- {t.row_count} rows. Sample ({header}):\n{rows}"
            blocks.append(block)
        return "\n\n".join(blocks)


class ValidationError(BaseModel):
    error_type: str
    message: str
    severity: str  # "error" | "critical"


class GenerationResult(BaseModel):
    """What the model produced, before execution. No confidence score: the
    model gives none, and passing validation says nothing about correctness."""
    sql: str = ""
    raw_output: str = ""
    assumption: Optional[str] = None
    cannot_answer: Optional[str] = None
    is_valid: bool = False
    validation_errors: List[ValidationError] = Field(default_factory=list)
    model: str = ""
    generation_time_ms: float = 0.0


class QueryResult(BaseModel):
    columns: List[str]
    rows: List[List[Any]]
    row_count: int
    truncated: bool
    execution_time_ms: float


class QueryResponse(BaseModel):
    schema_: Dict[str, Any] = Field(alias="schema")
    generation: GenerationResult
    result: Optional[QueryResult] = None
    execution_error: Optional[str] = None

    model_config = {"populate_by_name": True}

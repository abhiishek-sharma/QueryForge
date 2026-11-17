"""First-pass validation of generated SQL.

This is a filter that gives clear error messages before execution. It is *not*
the security boundary; ``app.db.readonly`` enforces read-only execution inside
SQLite. The checks work on sqlparse tokens rather than raw text, so string
literals such as ``'a--b'`` or column names such as ``exec`` are not flagged.
"""
from typing import List, Tuple

import sqlparse
from sqlparse import tokens as T

from app.schemas.sql_schemas import ValidationError

FORBIDDEN_KEYWORDS = {
    "INSERT", "UPDATE", "DELETE", "REPLACE", "MERGE", "UPSERT",
    "CREATE", "DROP", "ALTER", "TRUNCATE", "RENAME",
    "ATTACH", "DETACH", "PRAGMA", "VACUUM", "REINDEX", "ANALYZE",
    "GRANT", "REVOKE", "BEGIN", "COMMIT", "ROLLBACK", "SAVEPOINT", "RELEASE",
}


def strip_comments(sql: str) -> str:
    return sqlparse.format(sql, strip_comments=True).strip()


def _err(kind: str, msg: str, severity: str = "error") -> ValidationError:
    return ValidationError(error_type=kind, message=msg, severity=severity)


def validate(sql: str) -> Tuple[bool, List[ValidationError]]:
    """Return (is_valid, errors) for a single read-only SELECT/WITH statement."""
    cleaned = strip_comments(sql or "").rstrip(";").strip()
    if not cleaned:
        return False, [_err("empty_query", "SQL query is empty")]

    statements = [s for s in sqlparse.parse(cleaned) if s.value.strip().strip(";")]
    if len(statements) != 1:
        return False, [_err("multiple_statements", "Only a single SQL statement is allowed", "critical")]

    stmt = statements[0]
    errors: List[ValidationError] = []
    first = stmt.token_first(skip_cm=True, skip_ws=True)
    first_kw = first.normalized.upper() if first is not None else ""
    if first_kw not in ("SELECT", "WITH"):
        errors.append(_err("forbidden_operation", f"Only SELECT queries are allowed (found {first_kw or 'nothing'})"))

    found = {
        tok.normalized.upper()
        for tok in stmt.flatten()
        if tok.ttype in T.Keyword or tok.ttype in (T.Keyword.DML, T.Keyword.DDL)
    } & FORBIDDEN_KEYWORDS
    for kw in sorted(found):
        errors.append(_err("dangerous_operation", f"Statement contains forbidden keyword {kw}", "critical"))

    return not errors, errors


def prepare(sql: str) -> str:
    """Normalise SQL for display and execution (comments removed, no trailing ';')."""
    return strip_comments(sql).rstrip(";").strip()

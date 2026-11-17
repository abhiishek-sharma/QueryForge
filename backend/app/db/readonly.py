"""Read-only SQLite execution.

The text validator in ``app.utils.sql_safety`` is a first filter only. The
guarantees that matter are enforced here, by SQLite itself:

* the file is opened with ``mode=ro`` (and ``immutable=1``) so the OS-level
  handle cannot write;
* ``PRAGMA query_only = ON`` makes SQLite reject any write statement;
* an authorizer callback denies every action except reading tables/columns,
  SELECT, recursive CTEs and ordinary function calls (no ATTACH, PRAGMA,
  DDL/DML, transactions, or ``load_extension``);
* a progress handler aborts statements that run past a wall-clock deadline;
* ``SQLITE_LIMIT_LENGTH`` caps the size of any single string/blob value;
* at most ``max_rows`` rows are fetched (one extra row is read only to tell the
  caller that the result was truncated).
"""
from __future__ import annotations

import os
import sqlite3
import time
from dataclasses import dataclass
from typing import Any, List
from urllib.parse import quote

DEFAULT_TIMEOUT_S = float(os.getenv("QUERY_TIMEOUT_SECONDS", "5"))
MAX_VALUE_BYTES = 1_000_000  # largest single string/blob a query may build
HARD_MAX_ROWS = 1000

_ALLOWED_ACTIONS = {
    sqlite3.SQLITE_SELECT,
    sqlite3.SQLITE_READ,
    sqlite3.SQLITE_FUNCTION,
    sqlite3.SQLITE_RECURSIVE,
}
_DENIED_FUNCTIONS = {"load_extension", "readfile", "writefile", "edit", "fts3_tokenizer"}


class QueryTimeout(Exception):
    pass


class QueryRejected(Exception):
    """SQLite refused the statement (authorizer, query_only, or read-only file)."""


@dataclass
class ExecutionResult:
    columns: List[str]
    rows: List[List[Any]]
    row_count: int
    truncated: bool
    execution_time_ms: float


def _authorizer(action, arg1, arg2, dbname, source):
    if action not in _ALLOWED_ACTIONS:
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_FUNCTION and (arg2 or "").lower() in _DENIED_FUNCTIONS:
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


def open_readonly(db_path: str) -> sqlite3.Connection:
    uri = f"file:{quote(os.path.abspath(db_path))}?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
    conn.execute("PRAGMA query_only = ON")
    conn.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, MAX_VALUE_BYTES)
    conn.setlimit(sqlite3.SQLITE_LIMIT_ATTACHED, 0)
    conn.set_authorizer(_authorizer)
    return conn


def _jsonable(v: Any) -> Any:
    if isinstance(v, bytes):
        return f"<{len(v)} bytes>"
    return v


def execute_readonly(
    db_path: str,
    sql: str,
    max_rows: int = 100,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> ExecutionResult:
    max_rows = max(1, min(int(max_rows), HARD_MAX_ROWS))
    conn = open_readonly(db_path)
    deadline = time.monotonic() + timeout_s
    timed_out = False

    def _progress():
        nonlocal timed_out
        if time.monotonic() > deadline:
            timed_out = True
            return 1  # non-zero aborts the running statement
        return 0

    conn.set_progress_handler(_progress, 1000)
    start = time.monotonic()
    try:
        cur = conn.execute(sql)
        columns = [d[0] for d in cur.description] if cur.description else []
        rows = cur.fetchmany(max_rows + 1)
    except sqlite3.DatabaseError as e:
        if timed_out:
            raise QueryTimeout(f"Query exceeded the {timeout_s:g}s time limit") from e
        msg = str(e)
        if any(k in msg for k in ("not authorized", "authorization denied", "readonly", "read-only", "one statement")):
            raise QueryRejected(msg) from e
        raise
    finally:
        conn.close()
    elapsed = (time.monotonic() - start) * 1000
    truncated = len(rows) > max_rows
    rows = rows[:max_rows]
    return ExecutionResult(
        columns=columns,
        rows=[[_jsonable(v) for v in r] for r in rows],
        row_count=len(rows),
        truncated=truncated,
        execution_time_ms=round(elapsed, 2),
    )


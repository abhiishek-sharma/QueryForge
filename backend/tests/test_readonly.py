"""The connection itself must refuse writes, even for SQL the validator never saw."""
import sqlite3
import time

import pytest

from app.db.readonly import QueryRejected, QueryTimeout, execute_readonly


def _count(db):
    return sqlite3.connect(db).execute("SELECT count(*) FROM orders").fetchone()[0]


@pytest.mark.parametrize("sql", [
    "DELETE FROM orders",
    "UPDATE orders SET total = 0",
    "INSERT INTO orders VALUES (9, 1, 1.0)",
    "DROP TABLE orders",
    "CREATE TABLE x (a)",
    "ATTACH DATABASE ':memory:' AS other",
    "PRAGMA journal_mode = DELETE",
    "VACUUM INTO 'copy.db'",
    "BEGIN",
    "SELECT load_extension('anything')",
])
def test_writes_and_escapes_rejected_by_connection(shop_db, sql):
    with pytest.raises(QueryRejected):
        execute_readonly(shop_db, sql)
    assert _count(shop_db) == 3


def test_multiple_statements_rejected(shop_db):
    with pytest.raises(QueryRejected):
        execute_readonly(shop_db, "SELECT 1; DELETE FROM orders")
    assert _count(shop_db) == 3


def test_runaway_query_times_out(shop_db):
    sql = "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM c) SELECT count(*) FROM c"
    start = time.monotonic()
    with pytest.raises(QueryTimeout):
        execute_readonly(shop_db, sql, timeout_s=0.5)
    assert time.monotonic() - start < 3


def test_huge_value_rejected(shop_db):
    with pytest.raises(sqlite3.DataError):
        execute_readonly(shop_db, "SELECT length(zeroblob(2000000000))")


def test_row_cap_and_truncation_flag(shop_db):
    r = execute_readonly(shop_db, "SELECT * FROM orders", max_rows=2)
    assert r.row_count == 2 and r.truncated
    r = execute_readonly(shop_db, "SELECT * FROM orders", max_rows=3)
    assert r.row_count == 3 and not r.truncated


def test_select_and_recursive_cte_allowed(shop_db):
    r = execute_readonly(shop_db, "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM c WHERE x < 5) SELECT sum(x) FROM c")
    assert r.rows == [[15]]
    r = execute_readonly(shop_db, "SELECT c.name, sum(o.total) FROM customers c JOIN orders o ON o.customer_id = c.id GROUP BY c.id ORDER BY 1")
    assert r.rows == [["Ava", 15.5], ["Leo", 7.0]]

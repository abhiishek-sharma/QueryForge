import pytest

from app.utils.sql_safety import prepare, validate

ALLOWED = [
    "SELECT * FROM users",
    "select name from users where id = 1;",
    "WITH t AS (SELECT 1 AS x) SELECT x FROM t",
    "SELECT * FROM t WHERE note = 'a--b'",          # '--' inside a string literal
    "SELECT * FROM t WHERE note = 'drop table x'",  # keyword inside a string literal
    "SELECT exec, \"update\" FROM t",                # column names that look like keywords
    "-- top customers\nSELECT * FROM t",           # LLM-style leading comment
    "SELECT replace(name, 'a', 'b') FROM t",       # replace() function, not REPLACE INTO
]
BLOCKED = [
    "",
    "DROP TABLE users",
    "DELETE FROM users",
    "UPDATE users SET name = 'x'",
    "INSERT INTO users VALUES (1)",
    "REPLACE INTO users VALUES (1)",
    "ALTER TABLE users ADD c TEXT",
    "ATTACH DATABASE '/tmp/x.db' AS x",
    "PRAGMA writable_schema = ON",
    "VACUUM INTO '/tmp/copy.db'",
    "SELECT 1; DROP TABLE users",
    "WITH t AS (SELECT 1) DELETE FROM users",
    "/* hi */ UPDATE users SET a = 1",
]


@pytest.mark.parametrize("sql", ALLOWED)
def test_allowed(sql):
    ok, errors = validate(sql)
    assert ok, errors


@pytest.mark.parametrize("sql", BLOCKED)
def test_blocked(sql):
    ok, _ = validate(sql)
    assert not ok


def test_prepare_strips_comments_and_semicolon():
    assert prepare("-- c\nSELECT 1;") == "SELECT 1"

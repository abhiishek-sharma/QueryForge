import io
import sqlite3
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api import sql_endpoints
from app.schemas.sql_schemas import GenerationResult
from app.utils.sql_safety import validate
from main import app

client = TestClient(app)


def _gen(sql="", cannot=None):
    ok, errs = validate(sql) if sql else (False, [])
    return GenerationResult(sql=sql, is_valid=ok, validation_errors=errs, cannot_answer=cannot, model="mock")


def _post(name, data, question="q", **extra):
    return client.post("/api/v1/sql/query", files={"file": (name, io.BytesIO(data))},
                       data={"question": question, **extra})


@pytest.fixture
def mock_llm():
    with patch.object(sql_endpoints.sql_agent, "generate_sql", new_callable=AsyncMock) as m:
        yield m


def test_csv_upload_query(mock_llm):
    mock_llm.return_value = _gen("SELECT name FROM people ORDER BY age")
    r = _post("people.csv", b"name,age\nAlice,30\nBob,25\n")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["schema"]["tables"][0]["name"] == "people"
    assert body["result"]["rows"] == [["Bob"], ["Alice"]]
    assert "confidence" not in body["generation"]


def test_sqlite_upload_query(mock_llm, shop_db):
    mock_llm.return_value = _gen("SELECT count(*) FROM orders")
    r = _post("shop.db", open(shop_db, "rb").read())
    assert r.json()["result"]["rows"] == [[3]]


def test_invalid_sql_not_executed(mock_llm, shop_db):
    mock_llm.return_value = _gen("DELETE FROM orders")
    body = _post("shop.db", open(shop_db, "rb").read()).json()
    assert body["result"] is None and not body["generation"]["is_valid"]


def test_validator_bypass_still_blocked_by_connection(mock_llm, shop_db):
    # Simulate a validator bug: a write marked valid must still fail at execution.
    mock_llm.return_value = GenerationResult(sql="DELETE FROM orders", is_valid=True, model="mock")
    body = _post("shop.db", open(shop_db, "rb").read()).json()
    assert body["result"] is None
    assert "read-only" in body["execution_error"]


def test_cannot_answer_passthrough(mock_llm, shop_db):
    mock_llm.return_value = _gen(cannot="no email column")
    body = _post("shop.db", open(shop_db, "rb").read()).json()
    assert body["generation"]["cannot_answer"] == "no email column" and body["result"] is None


def test_unknown_column_reports_execution_error(mock_llm, shop_db):
    mock_llm.return_value = _gen("SELECT email FROM customers")
    body = _post("shop.db", open(shop_db, "rb").read()).json()
    assert "no such column" in body["execution_error"]


def test_max_rows_clamped(mock_llm, tmp_path):
    mock_llm.return_value = _gen("WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM c WHERE x < 5000) SELECT x FROM c")
    body = _post("t.csv", b"a\n1\n", max_rows="999999").json()
    assert body["result"]["row_count"] == 1000 and body["result"]["truncated"]


def test_upload_size_limit(mock_llm, monkeypatch):
    monkeypatch.setattr(sql_endpoints, "MAX_UPLOAD_MB", 0.001)  # ~1 KB
    r = _post("big.csv", b"a\n" + b"1\n" * 2000)
    assert r.status_code == 413
    mock_llm.assert_not_called()


@pytest.mark.parametrize("name", ["script.py", "old.xls", "data.json"])
def test_rejects_unsupported_types(name):
    assert _post(name, b"x").status_code == 400


def test_rejects_fake_sqlite():
    assert _post("fake.db", b"hello").status_code == 400


def test_empty_question():
    assert _post("a.csv", b"a\n1\n", question="   ").status_code == 400


def test_health_without_ollama(monkeypatch):
    monkeypatch.setattr(sql_endpoints.sql_agent, "url", "http://127.0.0.1:9")
    body = client.get("/api/v1/sql/health").json()
    assert body["ollama_reachable"] is False and body["status"] == "degraded"

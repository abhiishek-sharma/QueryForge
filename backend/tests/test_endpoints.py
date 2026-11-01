import os
import sqlite3
import io
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ["LLM_PROVIDER"] = "mistral"
os.environ["MISTRAL_API_KEY"] = "test-key"

from main import app
from app.schemas.sql_schemas import SQLResponse, ValidationError

client = TestClient(app)


def test_root():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "QueryForge" in resp.json()["message"]


def test_health():
    resp = client.get("/api/v1/sql/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["provider"] == "mistral"


@patch("app.api.sql_endpoints.sql_agent.generate_sql", new_callable=AsyncMock)
def test_generate_endpoint(mock_gen):
    mock_gen.return_value = SQLResponse(
        sql="SELECT * FROM users",
        explanation="Gets all users",
        is_valid=True,
        validation_errors=[],
        confidence=0.9,
    )
    resp = client.post(
        "/api/v1/sql/generate",
        json={
            "question": "show all users",
            "schema": {
                "name": "test_db",
                "tables": [
                    {
                        "name": "users",
                        "columns": [
                            {"name": "id", "type": "INTEGER", "primary_key": True, "nullable": False},
                            {"name": "name", "type": "TEXT", "primary_key": False, "nullable": False},
                        ],
                        "foreign_keys": [],
                    }
                ],
            },
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["sql"] == "SELECT * FROM users"
    assert data["is_valid"] is True
    mock_gen.assert_called_once()


@patch("app.api.sql_endpoints.sql_agent.generate_sql", new_callable=AsyncMock)
def test_query_endpoint_csv(mock_gen, tmp_path):
    mock_gen.return_value = SQLResponse(
        sql="SELECT name FROM upload",
        explanation="Gets names",
        is_valid=True,
        validation_errors=[],
        confidence=0.9,
    )
    csv_content = b"id,name,age\n1,Alice,30\n2,Bob,25\n"
    resp = client.post(
        "/api/v1/sql/query",
        files={"file": ("data.csv", io.BytesIO(csv_content), "text/csv")},
        data={"question": "show all names", "max_rows": "10"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_valid"] is True
    assert data["result"] is not None
    assert "name" in data["result"]["columns"]
    assert len(data["result"]["rows"]) == 2


@patch("app.api.sql_endpoints.sql_agent.generate_sql", new_callable=AsyncMock)
def test_query_endpoint_sqlite(mock_gen, tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE products (id INTEGER, name TEXT, price REAL)")
    conn.execute("INSERT INTO products VALUES (1, 'Widget', 9.99)")
    conn.execute("INSERT INTO products VALUES (2, 'Gadget', 19.99)")
    conn.commit()
    conn.close()
    with open(db_path, "rb") as f:
        db_bytes = f.read()

    mock_gen.return_value = SQLResponse(
        sql="SELECT name, price FROM products",
        explanation="Gets products",
        is_valid=True,
        validation_errors=[],
        confidence=0.9,
    )
    resp = client.post(
        "/api/v1/sql/query",
        files={"file": ("test.db", io.BytesIO(db_bytes), "application/octet-stream")},
        data={"question": "list products"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["result"]["row_count"] == 2


def test_query_rejects_bad_filetype():
    resp = client.post(
        "/api/v1/sql/query",
        files={"file": ("script.py", io.BytesIO(b"print('hi')"), "text/plain")},
        data={"question": "anything"},
    )
    assert resp.status_code == 400


def test_extract_schema():
    csv_content = b"x,y,z\n1,2,3\n4,5,6\n"
    resp = client.post(
        "/api/v1/sql/extract-schema",
        files={"file": ("nums.csv", io.BytesIO(csv_content), "text/csv")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "schema" in data
    assert data["filename"] == "nums.csv"

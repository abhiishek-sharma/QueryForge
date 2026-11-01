import csv
import sqlite3
import tempfile
import os

from app.utils.schema_extractor import SchemaExtractor


class TestSchemaExtractorCSV:

    def test_extract_csv(self, tmp_path):
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("id,name,age\n1,Alice,30\n2,Bob,25\n")
        schema = SchemaExtractor.extract_schema_auto(str(csv_file))
        assert len(schema.tables) == 1
        col_names = {c.name for c in schema.tables[0].columns}
        assert "id" in col_names
        assert "name" in col_names
        assert "age" in col_names

    def test_csv_types_inferred(self, tmp_path):
        csv_file = tmp_path / "typed.csv"
        csv_file.write_text("count,price,label\n1,9.99,foo\n2,3.50,bar\n")
        schema = SchemaExtractor.extract_schema_auto(str(csv_file))
        cols = {c.name: c.type for c in schema.tables[0].columns}
        assert cols["count"] == "INTEGER"
        assert cols["label"] == "TEXT"


class TestSchemaExtractorSQLite:

    def _make_db(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL, age INTEGER)")
        conn.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER, total REAL, FOREIGN KEY(user_id) REFERENCES users(id))")
        conn.execute("INSERT INTO users VALUES (1, 'Alice', 30)")
        conn.commit()
        conn.close()
        return db_path

    def test_extract_sqlite(self, tmp_path):
        db_path = self._make_db(tmp_path)
        schema = SchemaExtractor.extract_schema_auto(db_path)
        table_names = {t.name for t in schema.tables}
        assert "users" in table_names
        assert "orders" in table_names

    def test_sqlite_columns(self, tmp_path):
        db_path = self._make_db(tmp_path)
        schema = SchemaExtractor.extract_schema_auto(db_path)
        users = next(t for t in schema.tables if t.name == "users")
        col_names = {c.name for c in users.columns}
        assert "id" in col_names
        assert "name" in col_names
        assert "age" in col_names

    def test_schema_info(self, tmp_path):
        db_path = self._make_db(tmp_path)
        info = SchemaExtractor.get_schema_info(db_path)
        assert info["table_count"] == 2
        assert info["total_columns"] >= 5

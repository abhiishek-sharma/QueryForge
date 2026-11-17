"""Upload conversion (CSV/XLSX -> SQLite) and schema extraction from SQLite."""
import re
import sqlite3
from pathlib import Path

import pandas as pd

from app.db.readonly import open_readonly
from app.schemas.sql_schemas import Column, DatabaseSchema, ForeignKey, Table, quote_ident

SQLITE_EXTS = (".db", ".sqlite", ".sqlite3")
TABULAR_EXTS = (".csv", ".xlsx")
SUPPORTED_EXTS = SQLITE_EXTS + TABULAR_EXTS
SQLITE_MAGIC = b"SQLite format 3\x00"


def table_name_from_filename(filename: str) -> str:
    stem = Path(filename or "data").stem
    name = re.sub(r"[^0-9A-Za-z_]+", "_", stem).strip("_").lower() or "data"
    if name[0].isdigit():
        name = "t_" + name
    return name


def to_sqlite(file_path: str, ext: str, original_filename: str) -> str:
    """Return a path to a SQLite database containing the uploaded data."""
    if ext in SQLITE_EXTS:
        with open(file_path, "rb") as f:
            if f.read(16) != SQLITE_MAGIC:
                raise ValueError("File is not a SQLite database")
        return file_path
    db_path = file_path + ".sqlite"
    conn = sqlite3.connect(db_path)
    try:
        if ext == ".csv":
            df = pd.read_csv(file_path)
            df.to_sql(table_name_from_filename(original_filename), conn, index=False)
        elif ext == ".xlsx":
            for sheet, df in pd.read_excel(file_path, sheet_name=None).items():
                if not df.empty:
                    df.to_sql(table_name_from_filename(str(sheet)), conn, index=False)
        else:
            raise ValueError(f"Unsupported file type: {ext}")
    finally:
        conn.close()
    return db_path


def extract_schema(db_path: str, name: str = "database", sample_n: int = 3) -> DatabaseSchema:
    conn = open_readonly(db_path)
    conn.set_authorizer(None)  # PRAGMA table_info needs it; connection is still mode=ro + query_only
    try:
        tables = []
        names = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )]
        for t in names:
            lit = "'" + t.replace("'", "''") + "'"
            cols = [
                Column(name=r[1], type=r[2] or "TEXT", primary_key=bool(r[5]), nullable=not r[3])
                for r in conn.execute(f"PRAGMA table_info({lit})")
            ]
            fks = [
                ForeignKey(column=r[3], referenced_table=r[2], referenced_column=r[4] or "rowid")
                for r in conn.execute(f"PRAGMA foreign_key_list({lit})")
            ]
            ident = '"' + t.replace('"', '""') + '"'
            count = conn.execute(f"SELECT count(*) FROM {ident}").fetchone()[0]
            sample = [list(r) for r in conn.execute(f"SELECT * FROM {ident} LIMIT {int(sample_n)}")]
            tables.append(Table(name=t, columns=cols, foreign_keys=fks, row_count=count, sample_rows=sample))
        return DatabaseSchema(name=name, tables=tables)
    finally:
        conn.close()

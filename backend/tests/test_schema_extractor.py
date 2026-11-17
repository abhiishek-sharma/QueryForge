import pytest

from app.utils.schema_extractor import extract_schema, table_name_from_filename, to_sqlite


def test_sqlite_schema_with_fk_and_samples(shop_db):
    s = extract_schema(shop_db)
    orders = next(t for t in s.tables if t.name == "orders")
    assert orders.row_count == 3
    assert orders.foreign_keys[0].referenced_table == "customers"
    assert len(orders.sample_rows) == 3
    assert "FOREIGN KEY (customer_id) REFERENCES customers(id)" in s.to_prompt_format()


def test_csv_table_named_after_file(tmp_path):
    p = tmp_path / "upload.csv"
    p.write_text("id,unit price\n1,9.5\n2,3.0\n")
    db = to_sqlite(str(p), ".csv", "Q3 Sales-Report.csv")
    s = extract_schema(db)
    assert s.tables[0].name == "q3_sales_report"
    assert '"unit price" REAL' in s.to_prompt_format()  # odd column names are quoted


def test_xlsx_sheets_become_tables(tmp_path):
    import pandas as pd
    p = tmp_path / "book.xlsx"
    with pd.ExcelWriter(p) as w:
        pd.DataFrame({"a": [1, 2]}).to_excel(w, sheet_name="First Sheet", index=False)
        pd.DataFrame({"b": ["x"]}).to_excel(w, sheet_name="2nd", index=False)
    s = extract_schema(to_sqlite(str(p), ".xlsx", "book.xlsx"))
    assert {t.name for t in s.tables} == {"first_sheet", "t_2nd"}


def test_rejects_non_sqlite_file_with_db_extension(tmp_path):
    p = tmp_path / "fake.db"
    p.write_text("not a database")
    with pytest.raises(ValueError):
        to_sqlite(str(p), ".db", "fake.db")


def test_table_name_sanitising():
    assert table_name_from_filename("../../etc/passwd.csv") == "passwd"
    assert table_name_from_filename("2025 data.csv") == "t_2025_data"

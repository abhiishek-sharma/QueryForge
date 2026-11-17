import sqlite3

import pytest


@pytest.fixture
def shop_db(tmp_path):
    p = tmp_path / "shop.db"
    con = sqlite3.connect(p)
    con.executescript("""
    CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT NOT NULL, note TEXT);
    CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER REFERENCES customers(id), total REAL);
    INSERT INTO customers VALUES (1, 'Ava', 'call 5--6pm'), (2, 'Leo', NULL);
    INSERT INTO orders VALUES (1, 1, 10.0), (2, 1, 5.5), (3, 2, 7.0);
    """)
    con.commit()
    con.close()
    return str(p)

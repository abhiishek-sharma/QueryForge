"""Generate the synthetic demo data (deterministic; all names are made up).

    python samples/make_samples.py

Writes samples/shop.db (4 related tables) and samples/sales.csv (one flat table).
"""
import csv
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).parent
rng = random.Random(42)

FIRST = ["Ava", "Liam", "Maya", "Noah", "Zara", "Omar", "Iris", "Leo", "Nina", "Ravi",
         "Sofia", "Kai", "Elena", "Theo", "Priya", "Jonas", "Lena", "Arjun", "Mila", "Hugo"]
LAST = ["Patel", "Garcia", "Kim", "Novak", "Okafor", "Silva", "Berg", "Rossi", "Tanaka", "Moreau"]
CITIES = [("Berlin", "Germany"), ("Munich", "Germany"), ("Paris", "France"), ("Lyon", "France"),
          ("Madrid", "Spain"), ("Toronto", "Canada"), ("Austin", "USA"), ("Seattle", "USA")]
PRODUCTS = [
    ("Trail Running Shoes", "Footwear", 89.00), ("Leather Boots", "Footwear", 140.00),
    ("Canvas Sneakers", "Footwear", 55.00), ("Rain Jacket", "Apparel", 120.00),
    ("Wool Sweater", "Apparel", 75.00), ("Cotton T-Shirt", "Apparel", 18.50),
    ("Hiking Socks", "Apparel", 12.00), ("Daypack 20L", "Bags", 65.00),
    ("Travel Duffel", "Bags", 95.00), ("Laptop Sleeve", "Bags", 32.00),
    ("Steel Water Bottle", "Accessories", 24.00), ("Sunglasses", "Accessories", 48.00),
    ("Headlamp", "Accessories", 29.00), ("Camping Mug", "Accessories", 9.50),
    ("Two-Person Tent", "Camping", 230.00), ("Sleeping Bag", "Camping", 160.00),
    ("Fleece Jacket", "Apparel", 100.00),  # exactly 100: separates "> 100" from ">= 100"
]
# Boundary dates so off-by-one date filters give different results in the eval.
BOUNDARY_SIGNUPS = {1: "2024-03-01", 2: "2024-03-31", 3: "2024-04-01"}
STATUSES = ["completed"] * 8 + ["cancelled", "refunded"]


def build():
    db = HERE / "shop.db"
    db.unlink(missing_ok=True)
    con = sqlite3.connect(db)
    con.executescript("""
    CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT NOT NULL, city TEXT NOT NULL,
                            country TEXT NOT NULL, signup_date TEXT NOT NULL);
    CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL,
                           price REAL NOT NULL);
    CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL REFERENCES customers(id),
                         order_date TEXT NOT NULL, status TEXT NOT NULL);
    CREATE TABLE order_items (id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL REFERENCES orders(id),
                              product_id INTEGER NOT NULL REFERENCES products(id),
                              quantity INTEGER NOT NULL, unit_price REAL NOT NULL);
    """)
    names = set()
    while len(names) < 30:
        names.add(f"{rng.choice(FIRST)} {rng.choice(LAST)}")
    for i, n in enumerate(sorted(names), 1):
        city, country = rng.choice(CITIES)
        signup = (date(2024, 1, 1) + timedelta(days=rng.randrange(0, 365))).isoformat()
        signup = BOUNDARY_SIGNUPS.get(i, signup)
        con.execute("INSERT INTO customers VALUES (?,?,?,?,?)", (i, n, city, country, signup))
    con.executemany("INSERT INTO products VALUES (?,?,?,?)", [(i, *p) for i, p in enumerate(PRODUCTS, 1)])
    item_id = 0
    for oid in range(1, 151):
        d = date(2025, 1, 1) + timedelta(days=rng.randrange(0, 365))
        con.execute("INSERT INTO orders VALUES (?,?,?,?)", (oid, rng.randint(1, 30), d.isoformat(), rng.choice(STATUSES)))
        for pid in rng.sample(range(1, len(PRODUCTS) + 1), rng.randint(1, 3)):
            item_id += 1
            con.execute("INSERT INTO order_items VALUES (?,?,?,?,?)",
                        (item_id, oid, pid, rng.randint(1, 4), PRODUCTS[pid - 1][2]))
    con.commit()

    rows = con.execute("""
        SELECT o.order_date, c.country, p.category, p.name, oi.quantity,
               ROUND(oi.quantity * oi.unit_price, 2), o.status
        FROM order_items oi JOIN orders o ON o.id = oi.order_id
        JOIN customers c ON c.id = o.customer_id JOIN products p ON p.id = oi.product_id
        ORDER BY o.order_date, oi.id""").fetchall()
    with open(HERE / "sales.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["order_date", "country", "category", "product", "quantity", "revenue", "status"])
        w.writerows(rows)
    con.close()
    print(f"wrote {db.name} and sales.csv ({len(rows)} rows)")


if __name__ == "__main__":
    build()

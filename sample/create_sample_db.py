"""Builds sample/sample.db (SQLite) with realistic imperfections:
   * customers has a column literally named "group" (reserved word) so the
     naive profiling SQL fails validation and the QueryFixerAgent must
     quote it -- demonstrating the S1 fix loop.
   * NULL emails / bad emails      -> completeness + validity findings
   * duplicate SKUs                -> uniqueness finding
   * a negative order amount       -> validity finding
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

HERE = Path(__file__).resolve().parent


def build() -> Path:
    path = HERE / "sample.db"
    if path.exists():
        path.unlink()
    con = sqlite3.connect(path)
    cur = con.cursor()
    cur.executescript('''
    CREATE TABLE customers(
        id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT,
        "group" TEXT, created_at TEXT);
    CREATE TABLE orders(
        id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL,
        amount NUMERIC, status TEXT, order_date TEXT);
    CREATE TABLE products(
        id INTEGER PRIMARY KEY, sku TEXT, price NUMERIC, category TEXT);
    ''')
    cur.executemany("INSERT INTO customers VALUES (?,?,?,?,?)", [
        (1, "Asha Rao", "asha@example.com", "retail", "2024-01-05"),
        (2, "Ben Ortiz", None, "retail", "2024-02-11"),
        (3, "Chen Wu", "chen.wu@example.com", "wholesale", "2024-03-19"),
        (4, "Dana Fox", "not-an-email", "retail", "2024-04-02"),
        (5, "Elif Kaya", None, "wholesale", "2024-05-23"),
        (6, "Femi Ade", "femi@example.com", "retail", "2024-06-30"),
    ])
    cur.executemany("INSERT INTO orders VALUES (?,?,?,?,?)", [
        (1, 1, 120.50, "paid", "2024-07-01"),
        (2, 1, 89.99, "paid", "2024-07-03"),
        (3, 2, -15.00, "refund_error", "2024-07-04"),
        (4, 3, 560.00, "paid", "2024-07-10"),
        (5, 4, 42.10, "pending", "2024-07-12"),
        (6, 5, 300.00, "paid", "2024-07-15"),
        (7, 6, 77.77, "paid", "2024-07-21"),
    ])
    cur.executemany("INSERT INTO products VALUES (?,?,?,?)", [
        (1, "SKU-001", 19.99, "widgets"),
        (2, "SKU-002", 5.49, "widgets"),
        (3, "SKU-002", 5.49, "widgets"),      # duplicate SKU
        (4, "SKU-004", 99.00, "gadgets"),
        (5, None, 12.00, "gadgets"),          # missing SKU
    ])
    con.commit()
    con.close()
    return path


if __name__ == "__main__":
    print(build())

"""SQLite connection and small query helpers. All queries are read-only except insert_refund."""

import importlib.util
import sqlite3
from datetime import datetime

from .config import PROJECT_ROOT

DB_PATH = PROJECT_ROOT / "data" / "store.db"
SEED_SCRIPT = PROJECT_ROOT / "data" / "seed_db.py"


def reset_db():
    """Drop and recreate the database using data/seed_db.py."""
    spec = importlib.util.spec_from_file_location("seed_db", SEED_SCRIPT)
    seed_db = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(seed_db)
    seed_db.seed(DB_PATH)


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _all(sql, params=()):
    conn = get_conn()
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def _one(sql, params=()):
    rows = _all(sql, params)
    return rows[0] if rows else None


def get_customer(customer_id):
    return _one("SELECT * FROM customers WHERE customer_id = ?", (customer_id,))


def get_orders(customer_id):
    return _all(
        "SELECT order_id, order_date, status, total_usd, payment_method, delivered_date"
        " FROM orders WHERE customer_id = ? ORDER BY order_id",
        (customer_id,),
    )


def get_order(customer_id, order_id):
    """One order, only if it belongs to customer_id. Otherwise None."""
    return _one(
        "SELECT * FROM orders WHERE order_id = ? AND customer_id = ?",
        (order_id.strip().upper(), customer_id),
    )


def get_order_items(order_id):
    return _all(
        "SELECT p.product_id, p.name, p.category, p.returnable, i.qty, i.unit_price_usd"
        " FROM order_items i JOIN products p ON p.product_id = i.product_id"
        " WHERE i.order_id = ?",
        (order_id,),
    )


def get_shipment(order_id):
    return _one("SELECT * FROM shipments WHERE order_id = ?", (order_id,))


def get_products():
    return _all("SELECT * FROM products ORDER BY product_id")


def get_processed_refund(order_id):
    return _one(
        "SELECT * FROM refunds WHERE order_id = ? AND status = 'processed'", (order_id,)
    )


def get_refund_by_key(idempotency_key):
    return _one("SELECT * FROM refunds WHERE idempotency_key = ?", (idempotency_key,))


def get_refunds(order_id=None):
    if order_id is None:
        return _all("SELECT * FROM refunds ORDER BY refund_id")
    return _all("SELECT * FROM refunds WHERE order_id = ? ORDER BY refund_id", (order_id,))


def insert_refund(order_id, amount_usd, refund_type, reason, status, approval, idempotency_key):
    """Insert a refund row. Duplicates (same key, or a second processed refund) are ignored.

    Returns True if a row was written.
    """
    now = datetime.now().isoformat(timespec="seconds")
    conn = get_conn()
    try:
        with conn:  # commit on success
            cur = conn.execute(
            "INSERT OR IGNORE INTO refunds (order_id, amount_usd, refund_type, reason, status,"
            " approval, idempotency_key, created_at, processed_at)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
                (order_id, amount_usd, refund_type, reason, status, approval, idempotency_key,
                 now, now if status == "processed" else None),
            )
        return cur.rowcount == 1
    finally:
        conn.close()

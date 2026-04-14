"""
database/sql_store.py
----------------------
SQLite operations untuk structured Olist data queries.
Semua hasil di-sanitize dari NaN/Inf sebelum dikembalikan ke API.
"""

import os
import math
import sqlite3
import pandas as pd
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("SQLITE_DB_PATH", "./database/olist.db")


def _clean_record(record: dict) -> dict:
    """Replace NaN/Inf values dengan None agar JSON serializable."""
    cleaned = {}
    for k, v in record.items():
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            cleaned[k] = None
        else:
            cleaned[k] = v
    return cleaned


def _df_to_records(df: pd.DataFrame) -> list[dict]:
    """Convert DataFrame ke list of dicts, bersihkan NaN/Inf."""
    return [_clean_record(r) for r in df.to_dict(orient="records")]


class SQLStore:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def execute_query(self, sql: str, params: tuple = ()) -> pd.DataFrame:
        with self._connect() as conn:
            df = pd.read_sql_query(sql, conn, params=params)
        # Replace NaN dengan None di level DataFrame
        return df.where(pd.notnull(df), other=None)

    def get_schema(self) -> str:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

        schema_lines = []
        for table in tables:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute(f"PRAGMA table_info({table})")
                cols = cursor.fetchall()
            col_names = [c[1] for c in cols]
            schema_lines.append(f"Table: {table}\n  Columns: {', '.join(col_names)}")

        return "\n\n".join(schema_lines)

    # ── Pre-built analytics queries ───────────────────────────────────────────

    def get_top_sellers(self, limit: int = 10, state: Optional[str] = None) -> list[dict]:
        sql = """
        SELECT seller_id, seller_city, seller_state,
               COUNT(DISTINCT order_id) as total_orders,
               ROUND(SUM(price), 2) as total_revenue,
               ROUND(AVG(review_score), 2) as avg_rating
        FROM orders_master
        WHERE order_status = 'delivered'
        {state_filter}
        GROUP BY seller_id, seller_city, seller_state
        ORDER BY total_revenue DESC
        LIMIT ?
        """.format(state_filter=f"AND seller_state = '{state}'" if state else "")
        df = self.execute_query(sql, (limit,))
        return _df_to_records(df)

    def get_category_stats(self) -> list[dict]:
        sql = """
        SELECT category_en,
               COUNT(DISTINCT order_id) as total_orders,
               ROUND(AVG(price), 2) as avg_price,
               ROUND(AVG(review_score), 2) as avg_rating,
               ROUND(SUM(CASE WHEN is_late=1 THEN 1.0 ELSE 0.0 END) * 100.0 / COUNT(*), 2) as late_pct
        FROM orders_master
        WHERE category_en IS NOT NULL AND category_en != ''
        GROUP BY category_en
        ORDER BY total_orders DESC
        LIMIT 30
        """
        return _df_to_records(self.execute_query(sql))

    def get_monthly_revenue(self) -> list[dict]:
        sql = """
        SELECT year_month,
               COUNT(DISTINCT order_id) as orders,
               ROUND(COALESCE(SUM(payment_value), 0), 2) as revenue
        FROM orders_master
        WHERE year_month IS NOT NULL
          AND year_month != ''
          AND order_status = 'delivered'
        GROUP BY year_month
        ORDER BY year_month
        """
        return _df_to_records(self.execute_query(sql))

    def get_delivery_performance(self) -> list[dict]:
        sql = """
        SELECT customer_state,
               COUNT(*) as total_orders,
               ROUND(AVG(CASE WHEN delivery_days IS NOT NULL THEN delivery_days END), 1) as avg_delivery_days,
               ROUND(SUM(CASE WHEN is_late=1 THEN 1.0 ELSE 0.0 END) * 100.0 / COUNT(*), 2) as late_pct
        FROM orders_master
        WHERE customer_state IS NOT NULL
        GROUP BY customer_state
        ORDER BY avg_delivery_days
        """
        return _df_to_records(self.execute_query(sql))

    def get_payment_distribution(self) -> list[dict]:
        sql = """
        SELECT payment_type,
               COUNT(*) as count,
               ROUND(AVG(payment_value), 2) as avg_value
        FROM orders_master
        WHERE payment_type IS NOT NULL AND payment_type != ''
        GROUP BY payment_type
        ORDER BY count DESC
        """
        return _df_to_records(self.execute_query(sql))

    def get_review_distribution(self) -> list[dict]:
        sql = """
        SELECT CAST(ROUND(review_score) AS INT) as score,
               COUNT(*) as count
        FROM orders_master
        WHERE review_score IS NOT NULL
        GROUP BY score
        ORDER BY score
        """
        return _df_to_records(self.execute_query(sql))

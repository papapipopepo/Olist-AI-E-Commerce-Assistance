"""
scripts/prepare_data.py
-----------------------
Converts Olist CSV files into:
1. SQLite database (structured queries)
2. Rich text documents for RAG ingestion

Usage:
    python scripts/prepare_data.py --data_dir ./data/raw --output_dir ./data/processed
"""

import os
import json
import sqlite3
import argparse
import pandas as pd
from pathlib import Path
from tqdm import tqdm


# ─── Configuration ────────────────────────────────────────────────────────────

SQLITE_PATH = "./database/olist.db"
PROCESSED_DIR = "./data/processed"
RAW_DIR = "./data/raw"

SENTIMENT_MAP = {5: "sangat positif", 4: "positif", 3: "netral", 2: "negatif", 1: "sangat negatif"}


# ─── Load CSVs ────────────────────────────────────────────────────────────────

def load_dataframes(data_dir: str) -> dict:
    print("📂 Loading CSV files...")
    dfs = {}
    files = {
        "customers":    "olist_customers_dataset.csv",
        "orders":       "olist_orders_dataset.csv",
        "order_items":  "olist_order_items_dataset.csv",
        "payments":     "olist_order_payments_dataset.csv",
        "reviews":      "olist_order_reviews_dataset.csv",
        "products":     "olist_products_dataset.csv",
        "sellers":      "olist_sellers_dataset.csv",
        "category":     "product_category_name_translation.csv",
        "geolocation":  "olist_geolocation_dataset.csv",
    }
    for key, fname in files.items():
        path = Path(data_dir) / fname
        if path.exists():
            dfs[key] = pd.read_csv(path)
            print(f"  ✓ {fname}: {len(dfs[key]):,} rows")
        else:
            print(f"  ✗ {fname} not found — skipping")
    return dfs


# ─── Build SQLite ─────────────────────────────────────────────────────────────

def build_sqlite(dfs: dict, db_path: str):
    print(f"\n🗄️  Building SQLite database at {db_path}...")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)

    # --- orders_master: big denormalized table for analytics ---
    orders = dfs.get("orders")
    items  = dfs.get("order_items")
    pays   = dfs.get("payments")
    custs  = dfs.get("customers")
    sellers = dfs.get("sellers")
    products = dfs.get("products")
    category = dfs.get("category")
    reviews = dfs.get("reviews")

    if all(x is not None for x in [orders, items, pays, custs, sellers, products]):
        # Merge category translations
        if category is not None:
            products = products.merge(category, on="product_category_name", how="left")
            products["category_en"] = products["product_category_name_english"].fillna(
                products["product_category_name"]
            )

        # Aggregate payments per order
        pay_agg = pays.groupby("order_id").agg(
            payment_value=("payment_value", "sum"),
            payment_type=("payment_type", lambda x: x.mode()[0] if len(x) > 0 else "unknown"),
            installments=("payment_installments", "max"),
        ).reset_index()

        # Aggregate reviews per order
        if reviews is not None:
            rev_agg = reviews.groupby("order_id").agg(
                review_score=("review_score", "mean"),
                review_comment=("review_comment_message", lambda x: " | ".join(x.dropna().astype(str))),
            ).reset_index()
        else:
            rev_agg = pd.DataFrame(columns=["order_id", "review_score", "review_comment"])

        master = (
            orders
            .merge(custs[["customer_id", "customer_unique_id", "customer_city", "customer_state"]], on="customer_id", how="left")
            .merge(items[["order_id", "product_id", "seller_id", "price", "freight_value"]], on="order_id", how="left")
            .merge(sellers[["seller_id", "seller_city", "seller_state"]], on="seller_id", how="left")
            .merge(products[["product_id", "category_en", "product_weight_g"]], on="product_id", how="left")
            .merge(pay_agg, on="order_id", how="left")
            .merge(rev_agg, on="order_id", how="left")
        )

        # Date parsing
        for col in ["order_purchase_timestamp", "order_delivered_customer_date", "order_estimated_delivery_date"]:
            if col in master.columns:
                master[col] = pd.to_datetime(master[col], errors="coerce")

        # Derived columns
        master["delivery_days"] = (
            master["order_delivered_customer_date"] - master["order_purchase_timestamp"]
        ).dt.days
        master["is_late"] = (
            master["order_delivered_customer_date"] > master["order_estimated_delivery_date"]
        ).astype(int)
        master["year_month"] = master["order_purchase_timestamp"].dt.to_period("M").astype(str)

        master.to_sql("orders_master", conn, if_exists="replace", index=False)
        print(f"  ✓ orders_master: {len(master):,} rows")

    # --- Save individual tables too ---
    for table_name, df in dfs.items():
        if table_name == "geolocation":
            # geolocation is huge; deduplicate by zip prefix
            df = df.groupby("geolocation_zip_code_prefix").first().reset_index()
        df.to_sql(table_name, conn, if_exists="replace", index=False)
        print(f"  ✓ table '{table_name}': {len(df):,} rows")

    # --- Create indexes for fast queries ---
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_orders_status ON orders_master(order_status)",
        "CREATE INDEX IF NOT EXISTS idx_orders_category ON orders_master(category_en)",
        "CREATE INDEX IF NOT EXISTS idx_orders_seller ON orders_master(seller_id)",
        "CREATE INDEX IF NOT EXISTS idx_orders_ym ON orders_master(year_month)",
        "CREATE INDEX IF NOT EXISTS idx_orders_state ON orders_master(customer_state)",
    ]
    for idx in indexes:
        conn.execute(idx)

    conn.commit()
    conn.close()
    print(f"\n  ✅ SQLite ready at: {db_path}")


# ─── Build RAG Documents ──────────────────────────────────────────────────────

def build_rag_documents(dfs: dict, output_dir: str):
    print(f"\n📄 Building RAG documents at {output_dir}...")
    os.makedirs(output_dir, exist_ok=True)

    products  = dfs.get("products")
    reviews   = dfs.get("reviews")
    sellers   = dfs.get("sellers")
    items     = dfs.get("order_items")
    category  = dfs.get("category")

    if products is None:
        print("  ✗ products dataset missing, skipping RAG prep")
        return

    # Merge category names
    if category is not None:
        products = products.merge(category, on="product_category_name", how="left")
        products["category_en"] = products["product_category_name_english"].fillna(
            products["product_category_name"]
        )
    else:
        products["category_en"] = products["product_category_name"]

    # Aggregate reviews per product
    if reviews is not None and items is not None:
        product_reviews = (
            items[["order_id", "product_id"]]
            .merge(reviews[["order_id", "review_score", "review_comment_message"]], on="order_id", how="left")
            .groupby("product_id")
            .agg(
                avg_score=("review_score", "mean"),
                review_count=("review_score", "count"),
                reviews_text=("review_comment_message", lambda x: " | ".join(x.dropna().astype(str)[:5])),
            )
            .reset_index()
        )
        products = products.merge(product_reviews, on="product_id", how="left")

    # Aggregate seller info per product
    if sellers is not None and items is not None:
        product_sellers = (
            items[["product_id", "seller_id", "price"]]
            .merge(sellers[["seller_id", "seller_city", "seller_state"]], on="seller_id", how="left")
        )
        seller_info = product_sellers.groupby("product_id").agg(
            seller_cities=("seller_city", lambda x: ", ".join(x.dropna().unique()[:3])),
            avg_price=("price", "mean"),
            min_price=("price", "min"),
            max_price=("price", "max"),
        ).reset_index()
        products = products.merge(seller_info, on="product_id", how="left")

    # Build rich document per product
    documents = []
    for _, row in tqdm(products.iterrows(), total=len(products), desc="  Building product docs"):
        avg_score = row.get("avg_score", None)
        sentiment = SENTIMENT_MAP.get(round(avg_score) if pd.notna(avg_score) else None, "tidak diketahui")

        avg_price = row.get("avg_price", None)
        price_str = f"Rp{avg_price:,.0f}" if pd.notna(avg_price) else "harga tidak tersedia"

        reviews_text = row.get("reviews_text", "")
        review_snippet = str(reviews_text)[:300] if pd.notna(reviews_text) and reviews_text else ""

        doc_text = f"""Produk ID: {row['product_id']}
Kategori: {row.get('category_en', 'tidak diketahui')}
Berat: {row.get('product_weight_g', 'tidak diketahui')} gram
Harga rata-rata: {price_str}
Harga minimum: Rp{row.get('min_price', 0):,.0f} — Harga maksimum: Rp{row.get('max_price', 0):,.0f}
Dijual di kota: {row.get('seller_cities', 'tidak diketahui')}
Rating rata-rata: {f"{avg_score:.1f}/5" if pd.notna(avg_score) else "belum ada rating"} ({row.get('review_count', 0):.0f} ulasan)
Sentimen ulasan: {sentiment}
Kutipan ulasan: {review_snippet}""".strip()

        documents.append({
            "id": str(row["product_id"]),
            "text": doc_text,
            "metadata": {
                "product_id":  str(row["product_id"]),
                "category_en": str(row.get("category_en", "")),
                "avg_score":   float(avg_score) if pd.notna(avg_score) else None,
                "avg_price":   float(avg_price) if pd.notna(avg_price) else None,
                "seller_cities": str(row.get("seller_cities", "")),
                "sentiment":   sentiment,
            }
        })

    out_path = Path(output_dir) / "product_docs.jsonl"
    with open(out_path, "w", encoding="utf-8") as f:
        for doc in documents:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")
    print(f"  ✓ Saved {len(documents):,} product documents → {out_path}")

    # Separate review documents for review-specific RAG
    if reviews is not None:
        review_docs = []
        for _, row in tqdm(reviews.iterrows(), total=len(reviews), desc="  Building review docs"):
            comment = str(row.get("review_comment_message", ""))
            if not comment or comment == "nan":
                continue
            score = row.get("review_score", 3)
            sentiment = SENTIMENT_MAP.get(int(score), "netral")
            doc_text = f"""Order ID: {row['order_id']}
Review Score: {score}/5
Sentimen: {sentiment}
Ulasan Pelanggan: {comment[:500]}""".strip()

            review_docs.append({
                "id": str(row["review_id"]),
                "text": doc_text,
                "metadata": {
                    "review_id": str(row["review_id"]),
                    "order_id": str(row["order_id"]),
                    "review_score": int(score),
                    "sentiment": sentiment,
                }
            })

        rev_path = Path(output_dir) / "review_docs.jsonl"
        with open(rev_path, "w", encoding="utf-8") as f:
            for doc in review_docs:
                f.write(json.dumps(doc, ensure_ascii=False) + "\n")
        print(f"  ✓ Saved {len(review_docs):,} review documents → {rev_path}")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Olist data preparation pipeline")
    parser.add_argument("--data_dir", default=RAW_DIR)
    parser.add_argument("--output_dir", default=PROCESSED_DIR)
    parser.add_argument("--db_path", default=SQLITE_PATH)
    args = parser.parse_args()

    dfs = load_dataframes(args.data_dir)
    build_sqlite(dfs, args.db_path)
    build_rag_documents(dfs, args.output_dir)
    print("\n🎉 Data preparation complete!")


if __name__ == "__main__":
    main()

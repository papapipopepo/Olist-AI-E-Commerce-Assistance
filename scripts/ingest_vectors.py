"""
scripts/ingest_vectors.py
--------------------------
Embed product & review documents menggunakan OpenAI text-embedding-3-small,
lalu upload ke Qdrant Cloud.

Fitur:
- Resume otomatis jika proses sebelumnya terputus (via checkpoint file)
- Retry dengan exponential backoff saat Qdrant timeout
- Embed batch lebih besar (OpenAI), upsert batch lebih kecil (Qdrant)

Usage:
    poetry run python scripts/ingest_vectors.py
    poetry run python scripts/ingest_vectors.py --collection reviews
    poetry run python scripts/ingest_vectors.py --resume          # lanjut dari checkpoint
    poetry run python scripts/ingest_vectors.py --embed_batch 50 --upsert_batch 20
"""

import os
import json
import time
import argparse
from pathlib import Path
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
EMBED_DIM       = 1536    # text-embedding-3-small fixed dimension
EMBED_BATCH     = 50      # texts per OpenAI embedding call
UPSERT_BATCH    = 20      # points per Qdrant upsert (kecil = aman dari timeout)
PROCESSED_DIR   = "./data/processed"
CHECKPOINT_DIR  = "./data/checkpoints"
MAX_RETRIES     = 5       # retry Qdrant upsert jika timeout


def get_embeddings_batch(client, texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts using OpenAI."""
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts,
    )
    return [item.embedding for item in sorted(response.data, key=lambda x: x.index)]


def upsert_with_retry(qdrant_client, collection_name: str, points, max_retries: int = MAX_RETRIES):
    """Upsert points ke Qdrant dengan retry + exponential backoff."""
    for attempt in range(max_retries):
        try:
            qdrant_client.upsert(collection_name=collection_name, points=points)
            return  # success
        except Exception as e:
            wait = 2 ** attempt  # 1s, 2s, 4s, 8s, 16s
            if attempt < max_retries - 1:
                tqdm.write(f"  ⚠️  Qdrant timeout (attempt {attempt+1}/{max_retries}), retry in {wait}s...")
                time.sleep(wait)
            else:
                raise RuntimeError(f"Qdrant upsert gagal setelah {max_retries} percobaan: {e}") from e


def load_checkpoint(checkpoint_path: str) -> int:
    """Load last saved batch index. Returns 0 if no checkpoint."""
    p = Path(checkpoint_path)
    if p.exists():
        data = json.loads(p.read_text())
        idx = data.get("last_batch_start", 0)
        print(f"  ▶️  Resuming from batch index {idx} (checkpoint found)")
        return idx
    return 0


def save_checkpoint(checkpoint_path: str, batch_start: int):
    """Save current progress to checkpoint file."""
    Path(checkpoint_path).parent.mkdir(parents=True, exist_ok=True)
    Path(checkpoint_path).write_text(json.dumps({"last_batch_start": batch_start}))


def ingest_collection(
    openai_client,
    qdrant_client,
    collection_name: str,
    docs_path: str,
    embed_batch: int = EMBED_BATCH,
    upsert_batch: int = UPSERT_BATCH,
    resume: bool = False,
):
    from qdrant_client.models import (
        Distance, VectorParams, PointStruct, PayloadSchemaType
    )

    checkpoint_path = f"{CHECKPOINT_DIR}/{collection_name}.json"

    # Load documents
    docs = []
    with open(docs_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                docs.append(json.loads(line))
    print(f"\n📄 {len(docs):,} docs → '{collection_name}'")
    print(f"   Embed batch : {embed_batch} | Upsert batch : {upsert_batch}")

    # Determine start index (resume or fresh)
    start_idx = load_checkpoint(checkpoint_path) if resume else 0

    # Setup collection (only if starting fresh)
    if start_idx == 0:
        existing = [c.name for c in qdrant_client.get_collections().collections]
        if collection_name in existing:
            print(f"  ⚠️  Recreating collection '{collection_name}'...")
            qdrant_client.delete_collection(collection_name)

        qdrant_client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=EMBED_DIM, distance=Distance.COSINE),
        )

        for field, ftype in [
            ("category_en", PayloadSchemaType.KEYWORD),
            ("avg_score",   PayloadSchemaType.FLOAT),
            ("sentiment",   PayloadSchemaType.KEYWORD),
        ]:
            try:
                qdrant_client.create_payload_index(collection_name, field, ftype)
            except Exception:
                pass
    else:
        print(f"  ℹ️  Skipping collection setup (resuming)")

    # ── Main loop: embed in bigger chunks, upsert in smaller chunks ───────────
    total_uploaded = start_idx  # count already-done points
    docs_to_process = docs[start_idx:]

    pbar = tqdm(total=len(docs), initial=start_idx, desc="  Uploading", unit="docs")

    i = 0
    while i < len(docs_to_process):
        # Step 1: embed a bigger batch
        embed_slice = docs_to_process[i : i + embed_batch]
        texts = [d["text"] for d in embed_slice]
        embeddings = get_embeddings_batch(openai_client, texts)

        # Step 2: upsert in smaller sub-batches to avoid Qdrant timeout
        for j in range(0, len(embed_slice), upsert_batch):
            sub_docs = embed_slice[j : j + upsert_batch]
            sub_embs = embeddings[j : j + upsert_batch]
            global_offset = start_idx + i + j

            points = [
                PointStruct(
                    id=global_offset + k,
                    vector=emb,
                    payload={
                        "doc_id": doc["id"],
                        "text":   doc["text"],
                        **doc.get("metadata", {}),
                    },
                )
                for k, (doc, emb) in enumerate(zip(sub_docs, sub_embs))
            ]

            upsert_with_retry(qdrant_client, collection_name, points)
            total_uploaded += len(points)
            pbar.update(len(points))
            time.sleep(0.1)  # gentle pacing

        # Save checkpoint after every embed batch
        save_checkpoint(checkpoint_path, start_idx + i + len(embed_slice))
        i += embed_batch

    pbar.close()

    # Clear checkpoint on success
    Path(checkpoint_path).unlink(missing_ok=True)
    print(f"  ✅ {total_uploaded:,} vectors uploaded to '{collection_name}'")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--collection",   choices=["products", "reviews", "all"], default="all")
    parser.add_argument("--embed_batch",  type=int, default=EMBED_BATCH,
                        help="Texts per OpenAI embedding call (default 50)")
    parser.add_argument("--upsert_batch", type=int, default=UPSERT_BATCH,
                        help="Points per Qdrant upsert call (default 20, lower = safer)")
    parser.add_argument("--resume", action="store_true",
                        help="Resume from last checkpoint instead of starting fresh")
    args = parser.parse_args()

    from utils.observability import get_openai_client, get_langfuse
    from qdrant_client import QdrantClient

    openai_client = get_openai_client()

    # Qdrant client dengan timeout lebih besar
    qdrant_client = QdrantClient(
        url=os.getenv("QDRANT_URL"),
        api_key=os.getenv("QDRANT_API_KEY"),
        timeout=60,   # detik — naikkan dari default 5s
    )

    print(f"🔧 Embedding model : {EMBEDDING_MODEL} (dim={EMBED_DIM})")
    print(f"🔧 Embed batch     : {args.embed_batch} | Upsert batch : {args.upsert_batch}")
    lf = get_langfuse()
    if lf:
        print("📊 Langfuse tracing : enabled")
    if args.resume:
        print("▶️  Resume mode : ON")

    processed = Path(PROCESSED_DIR)

    if args.collection in ("products", "all"):
        path = processed / "product_docs.jsonl"
        if path.exists():
            ingest_collection(
                openai_client, qdrant_client,
                os.getenv("QDRANT_COLLECTION_PRODUCTS", "olist_products"),
                str(path), args.embed_batch, args.upsert_batch, args.resume,
            )
        else:
            print("⚠️  product_docs.jsonl not found. Run prepare_data.py first.")

    if args.collection in ("reviews", "all"):
        path = processed / "review_docs.jsonl"
        if path.exists():
            ingest_collection(
                openai_client, qdrant_client,
                os.getenv("QDRANT_COLLECTION_REVIEWS", "olist_reviews"),
                str(path), args.embed_batch, args.upsert_batch, args.resume,
            )
        else:
            print("⚠️  review_docs.jsonl not found. Run prepare_data.py first.")

    if lf:
        lf.flush()
    print("\n🎉 Vector ingestion complete!")


if __name__ == "__main__":
    main()

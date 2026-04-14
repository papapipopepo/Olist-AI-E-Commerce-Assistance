# 📘 Setup Guide — Olist AI Assistant
## Final Project JCAI 2025 | Purwadhika

---

## 🗂️ Struktur Project

```
olist-final-project/
├── agents/
│   ├── orchestrator.py         ← Router multi-agent (gpt-4o-mini tool calling)
│   ├── rag_agent.py            ← Semantic search via Qdrant
│   ├── sql_agent.py            ← NL→SQL via gpt-4o-mini + SQLite
│   ├── recommendation_agent.py ← Product recommendations
│   └── analytics_agent.py     ← Business analytics
├── database/
│   ├── vector_store.py         ← Qdrant client (OpenAI embeddings)
│   └── sql_store.py            ← SQLite queries
├── utils/
│   ├── observability.py        ← Langfuse integration (tracing semua LLM calls)
│   ├── sentiment.py            ← Review sentiment (gpt-4o-mini)
│   └── image_search.py         ← CLIP multimodal search
├── scripts/
│   ├── prepare_data.py         ← CSV → SQLite + RAG documents
│   └── ingest_vectors.py       ← Embed (text-embedding-3-small) + upload Qdrant
├── streamlit/
│   └── app.py                  ← Streamlit UI (4 halaman)
├── main.py                     ← FastAPI REST API
├── pyproject.toml              ← Poetry dependency management
├── Dockerfile                  ← API container (Poetry-based)
├── Dockerfile.streamlit        ← Streamlit container
├── docker-compose.yml          ← Local dev
├── deploy_gcp.sh               ← GCP Cloud Run deploy
└── .env.example
```

---

## ✅ Prasyarat

| Tool | Versi | Cek |
|------|-------|-----|
| Python | 3.11+ | `python --version` |
| Poetry | 1.8+ | `poetry --version` |
| Docker | 24+ | `docker --version` |
| gcloud CLI | latest | `gcloud --version` |
| OpenAI API key | aktif | [platform.openai.com](https://platform.openai.com) |
| Qdrant Cloud | Free tier OK | [cloud.qdrant.io](https://cloud.qdrant.io) |
| Langfuse | Free tier | [cloud.langfuse.com](https://cloud.langfuse.com) |

### Install Poetry

```bash
curl -sSL https://install.python-poetry.org | python3 -
# Tambahkan ke PATH (ikuti instruksi output)
poetry --version  # verifikasi
```

---

## 🚀 Langkah Setup

### Step 1 — Install dependencies dengan Poetry

```bash
cd olist-final-project

# Install semua dependencies
poetry install

# Aktifkan virtual environment
poetry shell
```

Selanjutnya semua command dijalankan di dalam `poetry shell`,
atau dengan prefix `poetry run python ...`.

### Step 2 — Konfigurasi Environment

```bash
cp .env.example .env
# Edit .env
```

Isi nilai berikut:
```dotenv
OPENAI_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small

QDRANT_URL=https://xxxx.qdrant.io
QDRANT_API_KEY=...

LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com
```

### Step 3 — Download Olist Dataset

Download dari Kaggle ke folder `data/raw/`:
```
https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce
```

```
data/raw/
├── olist_customers_dataset.csv
├── olist_orders_dataset.csv
├── olist_order_items_dataset.csv
├── olist_order_payments_dataset.csv
├── olist_order_reviews_dataset.csv
├── olist_products_dataset.csv
├── olist_sellers_dataset.csv
├── product_category_name_translation.csv
└── olist_geolocation_dataset.csv
```

### Step 4 — Prepare Data

```bash
poetry run python scripts/prepare_data.py
# Output: database/olist.db + data/processed/*.jsonl
```

### Step 5 — Ingest Vectors ke Qdrant

```bash
poetry run python scripts/ingest_vectors.py
# Embed pakai text-embedding-3-small → upload ke Qdrant
# Semua embedding calls ter-trace ke Langfuse
```

> ⏱️ ~100 ribu produk + review ≈ 10-20 menit

### Step 6 — Jalankan Lokal

```bash
# Terminal 1: API
poetry run python main.py

# Terminal 2: Streamlit
poetry run streamlit run streamlit/app.py
```

- API Docs  : http://localhost:8000/docs
- Streamlit : http://localhost:8501
- Langfuse  : https://cloud.langfuse.com (lihat traces secara real-time)

### Step 7 — Docker

```bash
docker-compose build
docker-compose up -d
docker-compose logs -f api
```

### Step 8 — Deploy GCP

```bash
# Edit PROJECT_ID di deploy_gcp.sh
nano deploy_gcp.sh

gcloud auth login
chmod +x deploy_gcp.sh
./deploy_gcp.sh
```

---

## 📊 Langfuse — Cara Membaca Traces

Setelah setup, buka [cloud.langfuse.com](https://cloud.langfuse.com) dan lihat:

| Trace | Isi |
|-------|-----|
| `orchestrator_chat` | End-to-end conversation, tools yang dipanggil |
| `openai.chat.completions` | Setiap LLM call: model, token usage, latency |
| `openai.embeddings` | Embedding calls saat search |
| `rag_retrieval` | Hasil RAG: query, top score, jumlah hasil |
| `sql_query` | SQL yang di-generate, jumlah baris hasil |

---

## 🧪 Test API

```bash
# Health
curl http://localhost:8000/health

# Chat
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Produk elektronik terpopuler?"}'

# Search
curl -X POST http://localhost:8000/search/products \
  -H "Content-Type: application/json" \
  -d '{"query": "sepatu olahraga", "top_k": 5}'

# Analytics
curl http://localhost:8000/analytics/top_sellers?limit=5

# Recommend
curl -X POST http://localhost:8000/recommend \
  -H "Content-Type: application/json" \
  -d '{"preference": "produk dapur berkualitas"}'
```

---

## 🏗️ Stack Teknologi

| Komponen | Teknologi |
|----------|-----------|
| LLM | OpenAI `gpt-4o-mini` |
| Embedding | OpenAI `text-embedding-3-small` (dim=1536) |
| Vector DB | Qdrant Cloud |
| SQL DB | SQLite |
| Observability | Langfuse |
| API | FastAPI + Uvicorn |
| UI | Streamlit + Plotly |
| Packaging | Poetry |
| Container | Docker + GCP Cloud Run |

---

## ❓ FAQ

**Q: `poetry install` gagal karena torch**
→ Torch CPU-only sudah dikonfigurasi di `pyproject.toml` via pytorch-cpu source. Jika masih gagal:
```bash
poetry run pip install torch --index-url https://download.pytorch.org/whl/cpu
```

**Q: Langfuse tidak muncul traces**
→ Cek `LANGFUSE_PUBLIC_KEY` dan `LANGFUSE_SECRET_KEY` di `.env`. Pastikan tidak ada spasi.

**Q: `QDRANT collection not found`**
→ Jalankan `poetry run python scripts/ingest_vectors.py` terlebih dahulu.

**Q: Rate limit OpenAI saat ingest**
→ Naikkan `BATCH_SIZE` di `ingest_vectors.py` atau tambah `time.sleep()`.

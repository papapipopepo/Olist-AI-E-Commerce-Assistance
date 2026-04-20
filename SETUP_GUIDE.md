# Setup Guide — Olist AI Assistant
## Final Project JCAI 2026 | Purwadhika

---

## Prasyarat

| Tool | Versi | Cek |
|------|-------|-----|
| Python | 3.11+ | `python --version` |
| Poetry | 1.8+ | `poetry --version` |
| Docker | 24+ | `docker --version` |
| gcloud CLI | latest | `gcloud --version` |
| OpenAI API Key | aktif | [platform.openai.com](https://platform.openai.com) |
| Qdrant Cloud | Free tier OK | [cloud.qdrant.io](https://cloud.qdrant.io) |
| Langfuse | Free tier | [us.cloud.langfuse.com](https://us.cloud.langfuse.com) |

### Install Poetry

```bash
curl -sSL https://install.python-poetry.org | python3 -
poetry --version  # verifikasi
```

---

## Setup Lokal

### Step 1 — Install Dependencies

```bash
cd olist-final-project
poetry install
poetry shell
```

Selanjutnya semua command dijalankan di dalam `poetry shell`, atau dengan prefix `poetry run`.

### Step 2 — Konfigurasi Environment

```bash
cp .env.example .env
```

Isi `.env` dengan kredensial berikut:

```dotenv
OPENAI_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small

QDRANT_URL=https://xxxx.qdrant.io
QDRANT_API_KEY=...
QDRANT_COLLECTION_PRODUCTS=olist_products
QDRANT_COLLECTION_REVIEWS=olist_reviews

LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://us.cloud.langfuse.com

SQLITE_DB_PATH=./database/olist.db
```

### Step 3 — Download Dataset Olist

Download dari Kaggle ke folder `data/raw/`:
```
https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce
```

File yang dibutuhkan:
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
# Embed dengan text-embedding-3-small → upload ke Qdrant
```

> Estimasi waktu: 10–20 menit untuk ~100 ribu produk + ulasan.

### Step 6 — Jalankan Lokal

```bash
# Terminal 1: API
poetry run python main.py

# Terminal 2: Streamlit
poetry run streamlit run streamlit/app.py
```

| Layanan | URL |
|---------|-----|
| API Docs | http://localhost:8000/docs |
| Streamlit | http://localhost:8501 |
| Langfuse | https://us.cloud.langfuse.com |

### Step 7 — Docker Lokal (Opsional)

```bash
docker-compose build
docker-compose up -d
docker-compose logs -f api
```

---

## Deploy ke GCP Cloud Run

### Prasyarat GCP

```bash
# Login dan set project
gcloud auth login
gcloud config set project final-project-493417

# Aktifkan service yang dibutuhkan
gcloud services enable cloudbuild.googleapis.com run.googleapis.com artifactregistry.googleapis.com

# Buat Artifact Registry repository (sekali saja)
gcloud artifacts repositories create olist-api \
  --repository-format=docker \
  --location=asia-southeast1

# Beri izin Compute Engine SA untuk push ke Artifact Registry
PROJECT_NUMBER=$(gcloud projects describe final-project-493417 --format="value(projectNumber)")
gcloud projects add-iam-policy-binding final-project-493417 \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"
```

> **Catatan:** GCP project yang dibuat setelah Januari 2025 menggunakan Compute Engine default SA untuk Cloud Build, bukan Cloud Build SA.

### Build & Push Docker Image

```bash
# Di root project (ada cloudbuild.yaml)
gcloud builds submit --config cloudbuild.yaml
```

`cloudbuild.yaml` menggunakan `images:` field sehingga Cloud Build yang handle push ke Artifact Registry secara otomatis.

### Deploy ke Cloud Run

```bash
gcloud run deploy olist-api \
  --image asia-southeast1-docker.pkg.dev/final-project-493417/olist-api/olist-api \
  --region asia-southeast1 \
  --platform managed \
  --allow-unauthenticated \
  --memory 2Gi \
  --set-env-vars "^|^OPENAI_API_KEY=sk-...|^LLM_MODEL=gpt-4o-mini|^EMBEDDING_MODEL=text-embedding-3-small|^QDRANT_URL=https://...|^QDRANT_API_KEY=...|^QDRANT_COLLECTION_PRODUCTS=olist_products|^QDRANT_COLLECTION_REVIEWS=olist_reviews|^LANGFUSE_PUBLIC_KEY=pk-lf-...|^LANGFUSE_SECRET_KEY=sk-lf-...|^LANGFUSE_HOST=https://us.cloud.langfuse.com|^SQLITE_DB_PATH=/app/database/olist.db"
```

> `SQLITE_DB_PATH` harus menggunakan path absolut `/app/database/olist.db` (bukan `./database/olist.db`).

---

## Deploy Streamlit ke Streamlit Community Cloud

1. Push repo ke GitHub
2. Buka [share.streamlit.io](https://share.streamlit.io) → **New app**
3. Pilih repo, branch `main`, file path `streamlit/app.py`
4. Di **Settings → Secrets**, tambahkan:
   ```toml
   API_BASE_URL = "https://olist-api-h57doqcaba-as.a.run.app"
   ```
5. Klik **Deploy**

> Streamlit Cloud otomatis membaca `streamlit/requirements.txt` untuk install dependencies.

---

## Test API

```bash
# Health check
curl https://olist-api-h57doqcaba-as.a.run.app/health

# Chat
curl -X POST https://olist-api-h57doqcaba-as.a.run.app/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Produk elektronik terpopuler?", "session_id": "test"}'

# Product search
curl -X POST https://olist-api-h57doqcaba-as.a.run.app/search/products \
  -H "Content-Type: application/json" \
  -d '{"query": "sepatu olahraga", "top_k": 5}'

# Recommendations
curl -X POST https://olist-api-h57doqcaba-as.a.run.app/recommend \
  -H "Content-Type: application/json" \
  -d '{"preference": "produk dapur berkualitas"}'

# Analytics
curl https://olist-api-h57doqcaba-as.a.run.app/analytics/top_sellers?limit=5
```

---

## Langfuse — Cara Membaca Traces

Buka [us.cloud.langfuse.com](https://us.cloud.langfuse.com) setelah app berjalan:

| Trace | Isi |
|-------|-----|
| `orchestrator_chat` | End-to-end conversation, tools yang dipanggil |
| `openai.chat.completions` | Setiap LLM call: model, token usage, latency |
| `openai.embeddings` | Embedding calls saat search |
| `rag_retrieval` | Hasil RAG: query, top score, jumlah hasil |
| `sql_query` | SQL yang di-generate, jumlah baris hasil |

---

## FAQ

**Q: `poetry install` gagal karena torch**
```bash
poetry run pip install torch --index-url https://download.pytorch.org/whl/cpu
```

**Q: Langfuse tidak muncul traces**
→ Cek `LANGFUSE_PUBLIC_KEY` dan `LANGFUSE_SECRET_KEY` di `.env`. Pastikan `LANGFUSE_HOST=https://us.cloud.langfuse.com` (bukan `cloud.langfuse.com`).

**Q: `QDRANT collection not found`**
→ Jalankan `poetry run python scripts/ingest_vectors.py` terlebih dahulu.

**Q: Rate limit OpenAI saat ingest**
→ Kurangi `BATCH_SIZE` di `ingest_vectors.py` atau tambah `time.sleep()` antar batch.

**Q: Cloud Build gagal push ke Artifact Registry**
→ Pastikan Compute Engine default SA sudah punya role `roles/artifactregistry.writer`. GCP project baru (post-Jan 2025) menggunakan SA ini, bukan Cloud Build SA.

**Q: API di Cloud Run tidak bisa akses database**
→ Pastikan `SQLITE_DB_PATH=/app/database/olist.db` (absolut, bukan relatif). File `olist.db` harus di-copy ke dalam Docker image via `COPY ./database /app/database` di Dockerfile.

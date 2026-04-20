# Olist AI Assistant — E-Commerce Intelligence Platform

**Final Project JCAI - Purwadhika**

Kelompok 5:
- Ezra Satria Bagas Airlangga
- Fadhlan Rio Lazuardy

---

Aplikasi AI berbasis multi-agent untuk menganalisis data e-commerce Olist Brasil.
Pengguna dapat bertanya secara natural tentang produk, penjual, ulasan pelanggan, dan tren penjualan —
sistem akan secara otomatis memilih agent yang paling relevan untuk menjawab.

## Demo

| | URL |
|--|-----|
| Streamlit App | https://olist-ai-e-commerce-assistance-huaayxkcxxf8fzqgtqming.streamlit.app/ |
| FastAPI (Cloud Run) | https://olist-api-h57doqcaba-as.a.run.app |
| API Docs | https://olist-api-h57doqcaba-as.a.run.app/docs |

## Fitur Utama

- **Chat Assistant** — tanya bebas, dijawab oleh orchestrator yang memanggil agent sesuai konteks
- **Product Search** — semantic search berbasis teks atau gambar (image search via GPT-4o-mini Vision)
- **Recommendations** — rekomendasi produk berdasarkan preferensi, dikombinasikan dengan rating dan sentimen ulasan
- **Analytics Dashboard** — visualisasi revenue, top sellers, kategori produk, pengiriman, dan pembayaran

## Arsitektur

```
Streamlit UI  ──►  FastAPI (GCP Cloud Run)
                         │
           ┌─────────────┼──────────────┐
           ▼             ▼              ▼
      RAG Agent      SQL Agent    Analytics Agent
      (Qdrant)       (SQLite)
           │
      Image Search
      (GPT-4o-mini Vision)
```

Orchestrator menerima pesan pengguna dan memutuskan tool mana yang dipanggil menggunakan OpenAI function calling. Hasilnya dikembalikan ke pengguna dalam satu respons koheren.

## Tech Stack

| Layer | Teknologi |
|-------|-----------|
| LLM & Vision | OpenAI GPT-4o-mini |
| Embedding | OpenAI text-embedding-3-small |
| Vector Search | Qdrant Cloud |
| SQL Database | SQLite (dibundel dalam Docker image) |
| Observability | Langfuse |
| Backend API | FastAPI + Uvicorn |
| Frontend | Streamlit + Plotly |
| Container | Docker + GCP Cloud Run (asia-southeast1) |
| CI/CD | GCP Cloud Build + Artifact Registry |

## Struktur Project

```
olist-final-project/
├── agents/
│   ├── orchestrator.py         # Router multi-agent (function calling)
│   ├── rag_agent.py            # Semantic search via Qdrant
│   ├── sql_agent.py            # Natural language to SQL
│   ├── recommendation_agent.py # Rekomendasi produk
│   └── analytics_agent.py      # Business analytics
├── database/
│   ├── vector_store.py         # Qdrant operations
│   ├── sql_store.py            # SQLite queries
│   └── olist.db                # SQLite database (git-lfs tracked)
├── utils/
│   ├── image_search.py         # Multimodal image search
│   ├── observability.py        # Langfuse tracing
│   └── sentiment.py            # Sentiment analysis
├── scripts/
│   ├── prepare_data.py         # CSV → SQLite + dokumen RAG
│   └── ingest_vectors.py       # Embed dan upload ke Qdrant
├── streamlit/
│   ├── app.py                  # UI utama (4 halaman)
│   ├── requirements.txt        # Dependencies untuk Streamlit Cloud
│   └── image_example.jpg       # Contoh gambar untuk image search
├── main.py                     # FastAPI entry point
├── Dockerfile                  # Container API
├── cloudbuild.yaml             # GCP Cloud Build pipeline
├── docker-compose.yml          # Local development
└── pyproject.toml              # Poetry dependencies
```

## Menjalankan Secara Lokal

```bash
# Install dependencies
poetry install && poetry shell

# Salin dan isi environment variables
cp .env.example .env

# Siapkan database (jalankan sekali)
poetry run python scripts/prepare_data.py
poetry run python scripts/ingest_vectors.py

# Jalankan API (Terminal 1)
poetry run python main.py

# Jalankan Streamlit (Terminal 2)
poetry run streamlit run streamlit/app.py
```

Panduan lengkap setup dan deployment ke GCP tersedia di [SETUP_GUIDE.md](SETUP_GUIDE.md).

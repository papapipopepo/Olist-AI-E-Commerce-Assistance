# Olist E-Commerce AI Assistant
## Final Project JCAI 2026 — Purwadhika

Sistem multi-agent AI untuk platform e-commerce Olist Brasil. Menjawab pertanyaan tentang produk, penjual, ulasan, dan tren bisnis menggunakan kombinasi RAG (Qdrant), NL→SQL (SQLite), dan image search.

## Live Demo

| Layanan | URL |
|---------|-----|
| Streamlit App | https://olist-ai-e-commerce-assistance-huaayscod8fzqgtqming.streamlit.app |
| FastAPI Backend | https://olist-api-h57doqcaba-as.a.run.app |
| API Docs | https://olist-api-h57doqcaba-as.a.run.app/docs |

## Arsitektur

```
User → Streamlit UI → FastAPI (Cloud Run)
                          │
              ┌───────────┼───────────┐
              ▼           ▼           ▼
         RAG Agent    SQL Agent   Analytics Agent
         (Qdrant)     (SQLite)
              │
         Image Search
         (GPT-4o-mini Vision)
```

## Project Structure

```
olist-final-project/
├── agents/
│   ├── orchestrator.py         # Router multi-agent (gpt-4o-mini tool calling)
│   ├── rag_agent.py            # Semantic search via Qdrant
│   ├── sql_agent.py            # NL→SQL via gpt-4o-mini + SQLite
│   ├── recommendation_agent.py # Product recommendations (semantic + rating boost)
│   └── analytics_agent.py      # Business analytics
├── database/
│   ├── vector_store.py         # Qdrant client (text-embedding-3-small)
│   ├── sql_store.py            # SQLite queries
│   └── olist.db                # SQLite database (git-lfs)
├── utils/
│   ├── image_search.py         # Multimodal search (GPT-4o-mini vision)
│   ├── observability.py        # Langfuse tracing
│   └── sentiment.py            # Review sentiment analysis
├── scripts/
│   ├── prepare_data.py         # CSV → SQLite + RAG documents
│   └── ingest_vectors.py       # Embed + upload ke Qdrant
├── streamlit/
│   ├── app.py                  # Streamlit UI (4 halaman)
│   ├── requirements.txt        # Dependencies Streamlit Cloud
│   └── image_example.jpg       # Contoh gambar untuk image search
├── main.py                     # FastAPI REST API
├── Dockerfile                  # API container (Poetry-based)
├── cloudbuild.yaml             # GCP Cloud Build config
├── docker-compose.yml          # Local dev
└── pyproject.toml              # Poetry dependency management
```

## Stack Teknologi

| Komponen | Teknologi |
|----------|-----------|
| LLM | OpenAI `gpt-4o-mini` |
| Embedding | OpenAI `text-embedding-3-small` |
| Vector DB | Qdrant Cloud |
| SQL DB | SQLite |
| Observability | Langfuse |
| API | FastAPI + Uvicorn |
| UI | Streamlit + Plotly |
| Container | Docker + GCP Cloud Run |
| Build | GCP Cloud Build + Artifact Registry |

## Quick Start (Lokal)

```bash
# 1. Install dependencies
poetry install && poetry shell

# 2. Konfigurasi environment
cp .env.example .env  # isi kredensial

# 3. Prepare data (jalankan sekali)
poetry run python scripts/prepare_data.py
poetry run python scripts/ingest_vectors.py

# 4. Jalankan API
poetry run python main.py

# 5. Jalankan Streamlit (terminal baru)
poetry run streamlit run streamlit/app.py
```

Lihat [SETUP_GUIDE.md](SETUP_GUIDE.md) untuk panduan lengkap termasuk deploy ke GCP.

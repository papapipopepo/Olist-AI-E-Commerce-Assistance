# Olist E-Commerce AI Assistant
## Final Project JCAI - Purwadhika 2026

Multi-agent AI system using Claude + Qdrant + SQLite, deployed on GCP.

## Project Structure
```
olist-final-project/
├── agents/
│   ├── orchestrator.py       # Main router agent
│   ├── rag_agent.py          # Product/review semantic search
│   ├── sql_agent.py          # Structured data queries
│   ├── recommendation_agent.py
│   └── analytics_agent.py
├── utils/
│   ├── embeddings.py         # Claude embeddings helper
│   ├── sentiment.py          # Review sentiment analysis
│   ├── voice.py              # Voice input (Whisper)
│   └── image_search.py       # Multimodal image search (CLIP)
├── database/
│   ├── vector_store.py       # Qdrant operations
│   └── sql_store.py          # SQLite operations
├── scripts/
│   ├── prepare_data.py       # Data preparation pipeline
│   └── ingest_vectors.py     # Embed & upload to Qdrant
├── streamlit/
│   └── app.py                # Main Streamlit UI
├── main.py                   # FastAPI REST API
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## Setup
1. Copy `.env.example` to `.env` and fill in credentials
2. Run `python scripts/prepare_data.py` to prepare SQLite DB
3. Run `python scripts/ingest_vectors.py` to populate Qdrant
4. `docker build -t olist-ai .`
5. `docker run -p 8000:8000 olist-ai`
6. `streamlit run streamlit/app.py`

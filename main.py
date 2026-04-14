"""
main.py
--------
FastAPI REST API untuk Olist AI Assistant.
/chat sekarang mengembalikan metadata: agents_called + token_usage.
"""

import os
import uuid
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

_orchestrator = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _orchestrator
    from agents.orchestrator import OrchestratorAgent
    from utils.observability import get_langfuse
    _orchestrator = OrchestratorAgent()
    lf = get_langfuse()
    print("✅ Orchestrator ready" + (" | Langfuse tracing ON" if lf else " | Langfuse OFF"))
    yield
    from utils.observability import flush
    flush()
    print("👋 Shutdown complete")


app = FastAPI(
    title="Olist AI Assistant API",
    description="Multi-agent AI — JCAI Final Project 2025 | gpt-4o-mini + Qdrant + SQLite + Langfuse",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Models ───────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message:    str
    session_id: Optional[str] = None

class AgentCall(BaseModel):
    tool:          str
    name:          str
    icon:          str
    desc:          str
    input_summary: str

class TokenUsage(BaseModel):
    prompt_tokens:     int
    completion_tokens: int
    total_tokens:      int

class ChatResponse(BaseModel):
    response:      str
    session_id:    str
    agents_called: List[AgentCall] = []
    token_usage:   Optional[TokenUsage] = None
    llm_calls:     int = 1

class SearchRequest(BaseModel):
    query:      str
    category:   Optional[str]   = None
    min_rating: Optional[float] = None
    top_k:      int             = 5

class RecommendRequest(BaseModel):
    preference: str
    top_k:      int = 5


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"service": "Olist AI Assistant", "version": "1.0.0",
            "model": os.getenv("LLM_MODEL"), "docs": "/docs"}

@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    if _orchestrator is None:
        raise HTTPException(503, "Agent not initialized")
    session_id = req.session_id or str(uuid.uuid4())
    try:
        result = _orchestrator.chat_with_metadata(req.message, session_id=session_id)
        return ChatResponse(
            response=result["response"],
            session_id=session_id,
            agents_called=[AgentCall(**a) for a in result.get("agents_called", [])],
            token_usage=TokenUsage(**result["token_usage"]) if result.get("token_usage") else None,
            llm_calls=result.get("llm_calls", 1),
        )
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/chat/reset")
def reset_chat():
    if _orchestrator:
        _orchestrator.reset_conversation()
    return {"status": "ok"}


@app.post("/search/products")
def search_products(req: SearchRequest):
    try:
        from agents.rag_agent import RAGAgent
        results = RAGAgent().search_products(
            query=req.query, category=req.category,
            min_rating=req.min_rating, top_k=req.top_k,
        )
        return {"results": results, "count": len(results)}
    except Exception as e:
        raise HTTPException(500, f"Search error: {str(e)}")


@app.post("/search/image")
async def search_by_image(file: UploadFile = File(...), top_k: int = Form(5)):
    try:
        from agents.rag_agent import RAGAgent
        image_bytes = await file.read()
        if not image_bytes:
            raise HTTPException(400, "File kosong")
        results = RAGAgent().search_by_image(image_bytes, top_k=int(top_k))
        return {"results": results, "count": len(results)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Image search error: {str(e)}")


@app.post("/recommend")
def recommend(req: RecommendRequest):
    try:
        from agents.recommendation_agent import RecommendationAgent
        results = RecommendationAgent().recommend(preference=req.preference, top_k=req.top_k)
        return {"recommendations": results}
    except Exception as e:
        raise HTTPException(500, f"Recommendation error: {str(e)}")


@app.get("/analytics/{metric}")
def get_analytics(metric: str, state: Optional[str] = None, limit: int = 10):
    try:
        from agents.analytics_agent import AnalyticsAgent
        filters = {k: v for k, v in {"state": state, "limit": limit}.items() if v is not None}
        result = AnalyticsAgent().get(metric=metric, filters=filters)
        if "error" in result:
            raise HTTPException(400, result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Analytics error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", 8000)),
        reload=os.getenv("DEBUG", "false").lower() == "true",
    )

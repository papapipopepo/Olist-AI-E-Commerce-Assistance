"""
utils/observability.py
-----------------------
Langfuse integration untuk tracing semua LLM calls.

PENTING — dua client terpisah:
- get_openai_client()       → Langfuse-wrapped, untuk chat.completions (auto-traced)
- get_openai_embed_client() → Plain openai.OpenAI, untuk embeddings
  (Langfuse wrapper TIDAK support .embeddings.create, jadi wajib pakai plain client)
"""

import os
from dotenv import load_dotenv

load_dotenv()

_langfuse = None
_openai_chat_client = None    # Langfuse-wrapped (chat only)
_openai_embed_client = None   # Plain OpenAI (embeddings)


def get_langfuse():
    """Return singleton Langfuse client. Returns None jika tidak dikonfigurasi."""
    global _langfuse
    if _langfuse is not None:
        return _langfuse

    pub  = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    sec  = os.getenv("LANGFUSE_SECRET_KEY", "")
    host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

    if not pub or not sec or "..." in pub:
        print("⚠️  Langfuse not configured — tracing disabled")
        return None

    try:
        from langfuse import Langfuse
        _langfuse = Langfuse(public_key=pub, secret_key=sec, host=host)
        print(f"✅ Langfuse connected → {host}")
    except Exception as e:
        print(f"⚠️  Langfuse init failed: {e}")
        return None

    return _langfuse


def get_openai_client():
    """
    OpenAI client untuk CHAT COMPLETIONS — auto-instrumented oleh Langfuse.
    Gunakan hanya untuk: client.chat.completions.create(...)
    """
    global _openai_chat_client
    if _openai_chat_client is not None:
        return _openai_chat_client

    api_key = os.getenv("OPENAI_API_KEY")
    lf = get_langfuse()

    if lf is not None:
        try:
            from langfuse.openai import openai as lf_openai
            _openai_chat_client = lf_openai.OpenAI(api_key=api_key)
            return _openai_chat_client
        except Exception as e:
            print(f"⚠️  Langfuse OpenAI wrapper failed ({e}), using plain client")

    import openai
    _openai_chat_client = openai.OpenAI(api_key=api_key)
    return _openai_chat_client


def get_openai_embed_client():
    """
    OpenAI client untuk EMBEDDINGS — plain client tanpa Langfuse wrapper.
    Langfuse wrapper tidak support .embeddings.create(), jadi wajib plain.
    Gunakan untuk: client.embeddings.create(...)
    """
    global _openai_embed_client
    if _openai_embed_client is not None:
        return _openai_embed_client

    import openai
    _openai_embed_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _openai_embed_client


# ── Manual span helpers ───────────────────────────────────────────────────────

class _NoOp:
    def update(self, **kw): pass
    def end(self, **kw): pass
    def __enter__(self): return self
    def __exit__(self, *a): pass


def start_trace(name: str, user_id=None, session_id=None, input=None):
    lf = get_langfuse()
    if lf is None:
        return _NoOp()
    try:
        return lf.trace(name=name, user_id=user_id, session_id=session_id, input=input)
    except Exception:
        return _NoOp()


def trace_rag_retrieval(trace, query: str, results: list, collection: str):
    lf = get_langfuse()
    if lf is None or trace is None or isinstance(trace, _NoOp):
        return
    try:
        span = trace.span(
            name="rag_retrieval",
            input={"query": query, "collection": collection},
            output={"results_count": len(results),
                    "top_score": results[0].get("score") if results else None},
        )
        span.end()
    except Exception:
        pass


def trace_sql_query(trace, question: str, sql: str, row_count: int):
    lf = get_langfuse()
    if lf is None or trace is None or isinstance(trace, _NoOp):
        return
    try:
        span = trace.span(
            name="sql_query",
            input={"question": question},
            output={"sql": sql, "row_count": row_count},
        )
        span.end()
    except Exception:
        pass


def flush():
    lf = get_langfuse()
    if lf:
        try:
            lf.flush()
        except Exception:
            pass

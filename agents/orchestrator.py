"""
agents/orchestrator.py
-----------------------
Orchestrator agent menggunakan OpenAI gpt-4o-mini dengan tool calling.
Mengembalikan response + metadata: agent yang dipanggil & token usage.
"""

import os
import json
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

SYSTEM_PROMPT = """Kamu adalah asisten AI untuk platform e-commerce Olist Brasil.
Kamu membantu pengguna menemukan informasi tentang produk, penjual, pesanan, ulasan, dan tren penjualan.

Kamu memiliki akses ke beberapa tools:
- search_products: mencari produk berdasarkan deskripsi, kategori, atau fitur
- search_reviews: mencari ulasan pelanggan berdasarkan topik atau sentimen
- query_sql: menjalankan query ke database untuk data terstruktur (harga, lokasi, statistik)
- get_recommendations: mendapatkan rekomendasi produk berdasarkan preferensi
- get_analytics: mendapatkan analitik bisnis (tren, performa seller, dll)

Selalu berikan jawaban dalam Bahasa Indonesia yang ramah dan informatif.
Jika kamu menggunakan data dari tools, sebutkan sumbernya dengan singkat.
Jika pertanyaan tidak berkaitan dengan Olist/e-commerce, arahkan dengan sopan."""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": "Cari produk di database Olist berdasarkan deskripsi, kategori, atau fitur.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query":      {"type": "string"},
                    "category":   {"type": "string"},
                    "min_rating": {"type": "number"},
                    "sentiment":  {"type": "string", "enum": ["sangat positif","positif","netral","negatif","sangat negatif"]},
                    "top_k":      {"type": "integer"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_reviews",
            "description": "Cari ulasan pelanggan berdasarkan topik atau sentimen.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query":     {"type": "string"},
                    "sentiment": {"type": "string", "enum": ["sangat positif","positif","netral","negatif","sangat negatif"]},
                    "top_k":     {"type": "integer"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_sql",
            "description": "Query database SQL untuk data terstruktur: harga, lokasi seller, statistik, agregasi.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                },
                "required": ["question"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recommendations",
            "description": "Rekomendasi produk berdasarkan preferensi pengguna.",
            "parameters": {
                "type": "object",
                "properties": {
                    "preference":         {"type": "string"},
                    "exclude_product_id": {"type": "string"},
                    "top_k":              {"type": "integer"},
                },
                "required": ["preference"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_analytics",
            "description": "Analitik bisnis: top_sellers, monthly_revenue, category_stats, delivery_performance, payment_distribution, review_distribution.",
            "parameters": {
                "type": "object",
                "properties": {
                    "metric":  {"type": "string", "enum": ["top_sellers","monthly_revenue","category_stats","delivery_performance","payment_distribution","review_distribution"]},
                    "filters": {"type": "object"},
                },
                "required": ["metric"],
            },
        },
    },
]

# Human-readable agent labels
AGENT_LABELS = {
    "search_products":   {"name": "RAG Agent",            "icon": "🔍", "desc": "Semantic search produk di Qdrant"},
    "search_reviews":    {"name": "RAG Agent",            "icon": "💬", "desc": "Semantic search ulasan di Qdrant"},
    "query_sql":         {"name": "SQL Agent",            "icon": "🗄️",  "desc": "Query SQLite database"},
    "get_recommendations":{"name": "Recommendation Agent","icon": "⭐", "desc": "Product recommendation engine"},
    "get_analytics":     {"name": "Analytics Agent",      "icon": "📊", "desc": "Business analytics dari SQLite"},
}


class OrchestratorAgent:
    def __init__(self):
        from utils.observability import get_openai_client
        self.client = get_openai_client()
        self.conversation_history: list[dict] = []
        self._rag_agent = None
        self._sql_agent = None
        self._recommendation_agent = None
        self._analytics_agent = None

    @property
    def rag_agent(self):
        if not self._rag_agent:
            from agents.rag_agent import RAGAgent
            self._rag_agent = RAGAgent()
        return self._rag_agent

    @property
    def sql_agent(self):
        if not self._sql_agent:
            from agents.sql_agent import SQLAgent
            self._sql_agent = SQLAgent()
        return self._sql_agent

    @property
    def recommendation_agent(self):
        if not self._recommendation_agent:
            from agents.recommendation_agent import RecommendationAgent
            self._recommendation_agent = RecommendationAgent()
        return self._recommendation_agent

    @property
    def analytics_agent(self):
        if not self._analytics_agent:
            from agents.analytics_agent import AnalyticsAgent
            self._analytics_agent = AnalyticsAgent()
        return self._analytics_agent

    def _execute_tool(self, tool_name: str, tool_input: dict) -> str:
        try:
            if tool_name == "search_products":
                results = self.rag_agent.search_products(**tool_input)
                return json.dumps(results, ensure_ascii=False, indent=2)
            elif tool_name == "search_reviews":
                results = self.rag_agent.search_reviews(**tool_input)
                return json.dumps(results, ensure_ascii=False, indent=2)
            elif tool_name == "query_sql":
                return self.sql_agent.answer(tool_input["question"])
            elif tool_name == "get_recommendations":
                results = self.recommendation_agent.recommend(**tool_input)
                return json.dumps(results, ensure_ascii=False, indent=2)
            elif tool_name == "get_analytics":
                result = self.analytics_agent.get(**tool_input)
                return json.dumps(result, ensure_ascii=False, indent=2)
            else:
                return f"Tool '{tool_name}' tidak dikenali."
        except Exception as e:
            return f"Error saat menjalankan {tool_name}: {str(e)}"

    def chat(self, user_message: str, session_id: Optional[str] = None) -> str:
        """Process user message. Returns plain text response."""
        result = self.chat_with_metadata(user_message, session_id)
        return result["response"]

    def chat_with_metadata(self, user_message: str, session_id: Optional[str] = None) -> dict:
        """
        Process user message and return full metadata:
        {
            "response": str,
            "agents_called": [{"name", "icon", "desc", "tool", "input_summary"}],
            "token_usage": {"prompt_tokens", "completion_tokens", "total_tokens"},
            "llm_calls": int,
        }
        """
        from utils.observability import start_trace, flush
        import uuid

        trace = start_trace(
            name="orchestrator_chat",
            session_id=session_id or str(uuid.uuid4()),
            input=user_message,
        )

        self.conversation_history.append({"role": "user", "content": user_message})
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + self.conversation_history

        agents_called = []
        total_prompt_tokens     = 0
        total_completion_tokens = 0
        llm_calls               = 0

        try:
            while True:
                response = self.client.chat.completions.create(
                    model=LLM_MODEL,
                    messages=messages,
                    tools=TOOLS,
                    tool_choice="auto",
                    temperature=0.3,
                    max_tokens=2048,
                )
                llm_calls += 1

                # Accumulate token usage
                if response.usage:
                    total_prompt_tokens     += response.usage.prompt_tokens
                    total_completion_tokens += response.usage.completion_tokens

                msg = response.choices[0].message
                messages.append(msg)

                # No tool calls → final answer
                if not msg.tool_calls:
                    final = msg.content or "Maaf, saya tidak dapat memproses permintaan ini."
                    self.conversation_history.append({"role": "assistant", "content": final})
                    if hasattr(trace, "update"):
                        trace.update(output=final)
                    flush()
                    return {
                        "response": final,
                        "agents_called": agents_called,
                        "token_usage": {
                            "prompt_tokens":     total_prompt_tokens,
                            "completion_tokens": total_completion_tokens,
                            "total_tokens":      total_prompt_tokens + total_completion_tokens,
                        },
                        "llm_calls": llm_calls,
                    }

                # Execute tool calls
                for tc in msg.tool_calls:
                    tool_input = json.loads(tc.function.arguments)
                    tool_name  = tc.function.name

                    # Track which agent was called
                    label = AGENT_LABELS.get(tool_name, {"name": tool_name, "icon": "🤖", "desc": ""})
                    # Build short input summary
                    input_summary = ", ".join(f"{k}={repr(v)[:40]}" for k, v in tool_input.items())
                    agents_called.append({
                        "tool":          tool_name,
                        "name":          label["name"],
                        "icon":          label["icon"],
                        "desc":          label["desc"],
                        "input_summary": input_summary,
                    })

                    result = self._execute_tool(tool_name, tool_input)
                    messages.append({
                        "role":         "tool",
                        "tool_call_id": tc.id,
                        "content":      result,
                    })

        except Exception as e:
            flush()
            raise e

    def reset_conversation(self):
        self.conversation_history = []

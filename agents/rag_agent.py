"""
agents/rag_agent.py
--------------------
Handles semantic search over product and review documents stored in Qdrant.
"""

from typing import Optional, Union
from database.vector_store import VectorStore


class RAGAgent:
    def __init__(self):
        self.store = VectorStore()

    def search_products(
        self,
        query: str,
        category: Optional[str] = None,
        min_rating: Optional[float] = None,
        sentiment: Optional[str] = None,
        top_k: int = 5,
    ) -> list[dict]:
        """Search products by semantic similarity with optional filters."""
        results = self.store.search_products(
            query=query,
            top_k=top_k,
            category_filter=category,
            min_score=min_rating,
            sentiment_filter=sentiment,
        )
        return [
            {
                "product_id":      r["product_id"],
                "category":        r["category"],
                "avg_rating":      r["avg_score"],
                "avg_price":       r["avg_price"],
                "sentiment":       r["sentiment"],
                "relevance_score": round(r["score"], 3),
                "summary":         r["text"][:600],
            }
            for r in results
        ]

    def search_reviews(
        self,
        query: str,
        sentiment: Optional[str] = None,
        top_k: int = 5,
    ) -> list[dict]:
        """Search customer reviews semantically."""
        results = self.store.search_reviews(
            query=query,
            top_k=top_k,
            sentiment_filter=sentiment,
        )
        return [
            {
                "order_id":        r["order_id"],
                "review_score":    r["review_score"],
                "sentiment":       r["sentiment"],
                "relevance_score": round(r["score"], 3),
                "review_text":     r["text"][:300],
            }
            for r in results
        ]

    def search_by_image(self, image_input: Union[str, bytes], top_k: int = 5) -> list[dict]:
        """Find products similar to an uploaded image."""
        # ✅ Gunakan 'image_input' bukan 'image_path'
        results = self.store.search_by_image(image_input=image_input, top_k=top_k)
        return [
            {
                "product_id":      r["product_id"],
                "category":        r["category"],
                "relevance_score": round(r["score"], 3),
                "summary":         r["text"][:600],
            }
            for r in results
        ]

"""
agents/recommendation_agent.py
--------------------------------
Product recommendation using collaborative filtering + semantic similarity.
"""

import os
from typing import Optional
from database.vector_store import VectorStore
from database.sql_store import SQLStore


class RecommendationAgent:
    def __init__(self):
        self.vector_store = VectorStore()
        self.sql_store = SQLStore()

    def recommend(
        self,
        preference: str,
        exclude_product_id: Optional[str] = None,
        top_k: int = 5,
    ) -> list[dict]:
        """
        Recommend products based on:
        1. Semantic similarity to preference description (RAG)
        2. Boosted by high ratings and positive sentiment
        """
        # Get semantic candidates
        results = self.vector_store.search_products(
            query=preference,
            top_k=top_k * 3,   # fetch more, then re-rank
        )

        # Filter out excluded product
        if exclude_product_id:
            results = [r for r in results if r.get("product_id") != exclude_product_id]

        # Re-rank: combine semantic score + rating boost
        for r in results:
            rating = r.get("avg_score") or 3.0
            semantic = r.get("score", 0.5)
            r["combined_score"] = (semantic * 0.6) + ((rating / 5.0) * 0.4)

        results.sort(key=lambda x: x["combined_score"], reverse=True)
        top = results[:top_k]

        return [
            {
                "rank": i + 1,
                "product_id": r["product_id"],
                "category": r["category"],
                "avg_rating": r.get("avg_score"),
                "avg_price": r.get("avg_price"),
                "sentiment": r.get("sentiment"),
                "recommendation_score": round(r["combined_score"], 3),
                "reason": r["text"][:200],
            }
            for i, r in enumerate(top)
        ]

    def get_similar_products(self, product_id: str, top_k: int = 5) -> list[dict]:
        """Find products similar to a given product ID."""
        # Fetch the product's text to use as query
        try:
            results = self.vector_store.search_products(
                query=f"product id {product_id}",
                top_k=1,
            )
            if not results:
                return []
            product_text = results[0]["text"]
            return self.recommend(preference=product_text, exclude_product_id=product_id, top_k=top_k)
        except Exception:
            return []

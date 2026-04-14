"""
database/vector_store.py
-------------------------
Qdrant vector database operations untuk RAG retrieval.
Menggunakan query_points() — API baru Qdrant client >=1.7
(method .search() sudah deprecated dan dihapus di versi terbaru)
"""

import os
from typing import Optional
from dotenv import load_dotenv
from qdrant_client import QdrantClient, models

load_dotenv()


class VectorStore:
    def __init__(self):
        self.client = QdrantClient(
            url=os.getenv("QDRANT_URL"),
            api_key=os.getenv("QDRANT_API_KEY"),
            timeout=30,
        )
        self.products_col = os.getenv("QDRANT_COLLECTION_PRODUCTS", "olist_products")
        self.reviews_col  = os.getenv("QDRANT_COLLECTION_REVIEWS",  "olist_reviews")

    def _get_embedding(self, text: str) -> list[float]:
        """
        Embedding pakai plain OpenAI client (BUKAN Langfuse wrapper).
        Langfuse wrapper tidak support .embeddings.create().
        """
        from utils.observability import get_openai_embed_client
        client = get_openai_embed_client()
        response = client.embeddings.create(
            model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
            input=text,
        )
        return response.data[0].embedding

    def _build_filter(self, conditions: list) -> Optional[models.Filter]:
        return models.Filter(must=conditions) if conditions else None

    def search_products(
        self,
        query: str,
        top_k: int = 5,
        category_filter: Optional[str] = None,
        min_score: Optional[float] = None,
        sentiment_filter: Optional[str] = None,
    ) -> list[dict]:
        query_vector = self._get_embedding(query)

        conditions = []
        if category_filter:
            conditions.append(models.FieldCondition(
                key="category_en", match=models.MatchValue(value=category_filter)))
        if min_score is not None:
            conditions.append(models.FieldCondition(
                key="avg_score", range=models.Range(gte=min_score)))
        if sentiment_filter:
            conditions.append(models.FieldCondition(
                key="sentiment", match=models.MatchValue(value=sentiment_filter)))

        results = self.client.query_points(
            collection_name=self.products_col,
            query=query_vector,
            query_filter=self._build_filter(conditions),
            limit=top_k,
            with_payload=True,
        ).points

        return [
            {
                "score":      r.score,
                "text":       r.payload.get("text", ""),
                "product_id": r.payload.get("product_id", ""),
                "category":   r.payload.get("category_en", ""),
                "avg_score":  r.payload.get("avg_score"),
                "avg_price":  r.payload.get("avg_price"),
                "sentiment":  r.payload.get("sentiment", ""),
            }
            for r in results
        ]

    def search_reviews(
        self,
        query: str,
        top_k: int = 5,
        sentiment_filter: Optional[str] = None,
    ) -> list[dict]:
        query_vector = self._get_embedding(query)

        conditions = []
        if sentiment_filter:
            conditions.append(models.FieldCondition(
                key="sentiment", match=models.MatchValue(value=sentiment_filter)))

        results = self.client.query_points(
            collection_name=self.reviews_col,
            query=query_vector,
            query_filter=self._build_filter(conditions),
            limit=top_k,
            with_payload=True,
        ).points

        return [
            {
                "score":        r.score,
                "text":         r.payload.get("text", ""),
                "review_id":    r.payload.get("review_id", ""),
                "order_id":     r.payload.get("order_id", ""),
                "review_score": r.payload.get("review_score"),
                "sentiment":    r.payload.get("sentiment", ""),
            }
            for r in results
        ]

    def search_by_image(self, image_input, top_k: int = 5) -> list[dict]:
        from utils.image_search import get_image_embedding
        query_vector = get_image_embedding(image_input)

        results = self.client.query_points(
            collection_name=self.products_col,
            query=query_vector,
            limit=top_k,
            with_payload=True,
        ).points

        return [
            {
                "score":      r.score,
                "text":       r.payload.get("text", ""),
                "product_id": r.payload.get("product_id", ""),
                "category":   r.payload.get("category_en", ""),
            }
            for r in results
        ]

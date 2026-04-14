"""
utils/sentiment.py
-------------------
Sentiment analysis untuk review Olist menggunakan gpt-4o-mini.
"""

import os
import re
import json
from typing import Union
from dotenv import load_dotenv

load_dotenv()

LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

SENTIMENT_LABELS = ["sangat positif", "positif", "netral", "negatif", "sangat negatif"]
SCORE_TO_SENTIMENT = {5: "sangat positif", 4: "positif", 3: "netral", 2: "negatif", 1: "sangat negatif"}


def score_to_sentiment(score: Union[int, float]) -> str:
    return SCORE_TO_SENTIMENT.get(round(float(score)), "netral")


def analyze_sentiment_llm(text: str) -> dict:
    """Gunakan gpt-4o-mini untuk analisis sentimen teks review."""
    from utils.observability import get_openai_client
    client = get_openai_client()

    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {
                "role": "system",
                "content": "Kamu menganalisis sentimen ulasan e-commerce. Kembalikan JSON saja: {\"label\": \"<sangat positif|positif|netral|negatif|sangat negatif>\", \"confidence\": <0.0-1.0>, \"reason\": \"<1 kalimat>\"}",
            },
            {"role": "user", "content": f"Ulasan: {text[:400]}"},
        ],
        temperature=0,
        max_tokens=100,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content.strip()
    try:
        result = json.loads(raw)
        if result.get("label") not in SENTIMENT_LABELS:
            result["label"] = "netral"
        return result
    except Exception:
        return {"label": "netral", "confidence": 0.5, "reason": "Parse error"}


def batch_analyze(texts: list[str], scores: list = None) -> list[dict]:
    """
    Batch analysis. Jika scores tersedia → gunakan mapping cepat (tanpa API).
    Jika tidak → gunakan LLM per teks.
    """
    if scores:
        return [
            {"label": score_to_sentiment(s), "confidence": 0.95, "reason": f"Skor {s}/5"}
            for s in scores
        ]
    return [analyze_sentiment_llm(t) for t in texts]


def get_sentiment_summary(sentiments: list[str]) -> dict:
    from collections import Counter
    counts = Counter(sentiments)
    total  = len(sentiments)
    return {
        label: {
            "count": counts.get(label, 0),
            "pct":   round(counts.get(label, 0) / total * 100, 1) if total else 0,
        }
        for label in SENTIMENT_LABELS
    }

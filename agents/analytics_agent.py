"""
agents/analytics_agent.py
--------------------------
Returns analytics dari SQLite untuk dashboard visualizations.
sql_store sekarang mengembalikan list[dict] langsung (bukan DataFrame)
sehingga tidak perlu .to_dict() lagi dan NaN sudah dibersihkan.
"""

from typing import Optional
from database.sql_store import SQLStore


class AnalyticsAgent:
    def __init__(self):
        self.store = SQLStore()

    def get(self, metric: str, filters: Optional[dict] = None) -> dict:
        filters = filters or {}
        try:
            if metric == "top_sellers":
                data = self.store.get_top_sellers(
                    limit=filters.get("limit", 10),
                    state=filters.get("state"),
                )
                return {"metric": metric, "data": data}

            elif metric == "monthly_revenue":
                data = self.store.get_monthly_revenue()
                return {"metric": metric, "data": data}

            elif metric == "category_stats":
                data = self.store.get_category_stats()
                return {"metric": metric, "data": data}

            elif metric == "delivery_performance":
                data = self.store.get_delivery_performance()
                return {"metric": metric, "data": data}

            elif metric == "payment_distribution":
                data = self.store.get_payment_distribution()
                return {"metric": metric, "data": data}

            elif metric == "review_distribution":
                data = self.store.get_review_distribution()
                return {"metric": metric, "data": data}

            else:
                return {"error": f"Metric '{metric}' tidak dikenali."}

        except Exception as e:
            return {"error": str(e)}

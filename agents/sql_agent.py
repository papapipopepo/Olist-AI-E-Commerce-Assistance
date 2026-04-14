"""
agents/sql_agent.py
--------------------
Converts natural language → SQL using gpt-4o-mini, executes on SQLite.
All LLM calls traced via Langfuse automatically.
"""

import os
import re
import pandas as pd
from dotenv import load_dotenv
from database.sql_store import SQLStore

load_dotenv()

LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

SQL_SYSTEM_PROMPT = """Kamu adalah ahli SQL untuk database e-commerce Olist Brasil (SQLite).
Tugasmu: ubah pertanyaan natural language menjadi query SQL yang valid.

Schema database:
{schema}

Rules:
- Hanya SELECT queries (no INSERT/UPDATE/DELETE)
- Selalu LIMIT hasil (max 50 baris)
- Tabel utama: orders_master (denormalized, paling lengkap)
- Kembalikan HANYA SQL mentah — tanpa markdown, tanpa penjelasan
- Jika tidak bisa dijawab SQL: tulis CANNOT_QUERY: <alasan singkat>
"""


class SQLAgent:
    def __init__(self):
        from utils.observability import get_openai_client
        self.client = get_openai_client()
        self.store   = SQLStore()
        self._schema: str | None = None

    @property
    def schema(self) -> str:
        if self._schema is None:
            self._schema = self.store.get_schema()
        return self._schema

    def _generate_sql(self, question: str) -> str:
        response = self.client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": SQL_SYSTEM_PROMPT.format(schema=self.schema)},
                {"role": "user",   "content": question},
            ],
            temperature=0,
            max_tokens=512,
        )
        raw = response.choices[0].message.content.strip()
        # Strip markdown code fences if present
        raw = re.sub(r"```sql\s*|```", "", raw).strip()
        return raw

    def _format_df(self, df: pd.DataFrame) -> str:
        if df.empty:
            return "Tidak ada data ditemukan."
        if len(df) == 1 and len(df.columns) == 1:
            return str(df.iloc[0, 0])
        return df.to_string(index=False, max_rows=20)

    def answer(self, question: str) -> str:
        """Answer a natural-language question using SQL."""
        from utils.observability import trace_sql_query
        sql = self._generate_sql(question)

        if sql.upper().startswith("CANNOT_QUERY"):
            return sql.replace("CANNOT_QUERY:", "ℹ️").strip()

        try:
            df = self.store.execute_query(sql)
            result = self._format_df(df)
            trace_sql_query(None, question, sql, len(df))
            return f"```\n{result}\n```\n\n_(Query: `{sql[:120]}{'...' if len(sql)>120 else ''}`)_"
        except Exception as e:
            return f"Gagal menjalankan query: {e}\nSQL: {sql}"

"""
streamlit/app.py
-----------------
Streamlit UI — 4 halaman:
  1. 💬 Chat Assistant
  2. 🔍 Product Search (text + image)
  3. ⭐ Recommendations
  4. 📊 Analytics Dashboard
"""

import os, json, uuid, pathlib
import requests
import streamlit as st
import plotly.express as px
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

APP_DIR  = pathlib.Path(__file__).parent
API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")
IMAGE_EXAMPLE_FILE = os.path.join(os.path.dirname(__file__), "image_example")
IMAGE_EXAMPLE_PATH = None
try:
    with open(IMAGE_EXAMPLE_FILE, "r") as f:
        IMAGE_EXAMPLE_PATH = f.read().strip()
except Exception:
    IMAGE_EXAMPLE_PATH = None

# ─── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="Olist AI Assistant", page_icon="🛒",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""<style>
.main-header{background:linear-gradient(135deg,#667eea,#764ba2);padding:1.5rem 2rem;
  border-radius:12px;margin-bottom:1.5rem;color:white}
.chat-user{background:#667eea;color:white;padding:.8rem 1rem;border-radius:12px 12px 4px 12px;
  margin:.4rem 0;max-width:80%;margin-left:auto}
.chat-bot{background:#f0f2f6;padding:.8rem 1rem;border-radius:12px 12px 12px 4px;
  margin:.4rem 0;max-width:85%}
.product-card{border:1px solid #e0e0e0;border-radius:10px;padding:1rem;margin:.5rem 0;
  background:white;box-shadow:0 2px 4px rgba(0,0,0,.05)}
</style>""", unsafe_allow_html=True)

# ─── Session state ────────────────────────────────────────────────────────────
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "chat_metadata" not in st.session_state:
    st.session_state.chat_metadata = []  # list of metadata per message pair
if "image_results" not in st.session_state:
    st.session_state.image_results = None
if "image_description" not in st.session_state:
    st.session_state.image_description = None
if "image_bytes" not in st.session_state:
    st.session_state.image_bytes = None
if "text_search_results" not in st.session_state:
    st.session_state.text_search_results = None
if "text_search_query" not in st.session_state:
    st.session_state.text_search_query = ""

# ─── API helpers ──────────────────────────────────────────────────────────────
def api_chat(msg):
    """Returns (response_text, metadata_dict)."""
    try:
        r = requests.post(f"{API_BASE}/chat",
            json={"message": msg, "session_id": st.session_state.session_id}, timeout=60)
        r.raise_for_status()
        data = r.json()
        return data.get("response", ""), {
            "agents_called": data.get("agents_called", []),
            "token_usage":   data.get("token_usage"),
            "llm_calls":     data.get("llm_calls", 1),
        }
    except Exception as e:
        return f"⚠️ Error: {e}", {}

def api_search(query, category=None, min_rating=None, top_k=8):
    try:
        r = requests.post(f"{API_BASE}/search/products",
            json={"query": query, "category": category, "min_rating": min_rating, "top_k": top_k},
            timeout=30)
        r.raise_for_status()
        return r.json().get("results", [])
    except Exception as e:
        st.error(str(e)); return []

def api_recommend(preference, top_k=6):
    try:
        r = requests.post(f"{API_BASE}/recommend",
            json={"preference": preference, "top_k": top_k}, timeout=60)
        r.raise_for_status()
        return r.json().get("recommendations", [])
    except Exception as e:
        st.error(str(e)); return []

def api_analytics(metric, state=None, limit=10):
    try:
        params = {"limit": limit}
        if state: params["state"] = state
        r = requests.get(f"{API_BASE}/analytics/{metric}", params=params, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(str(e)); return {}

def api_image_search(image_bytes: bytes, top_k: int = 6):
    try:
        r = requests.post(
            f"{API_BASE}/search/image",
            files={"file": ("image.jpg", image_bytes, "image/jpeg")},
            data={"top_k": str(top_k)},
            timeout=60,
        )
        r.raise_for_status()
        return r.json().get("results", []), None
    except requests.HTTPError as e:
        try:
            detail = e.response.json().get("detail", str(e))
        except Exception:
            detail = str(e)
        return [], detail
    except Exception as e:
        return [], str(e)

def render_agent_trace(metadata: dict):
    """Render agent trace panel: which agents were called + token usage."""
    if not metadata:
        return
    agents = metadata.get("agents_called", [])
    token  = metadata.get("token_usage", {})
    llm_calls = metadata.get("llm_calls", 1)

    with st.expander("🔍 Agent Trace", expanded=False):
        # Token usage row
        if token:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Tokens", f"{token.get('total_tokens', 0):,}")
            c2.metric("Prompt Tokens", f"{token.get('prompt_tokens', 0):,}")
            c3.metric("Completion Tokens", f"{token.get('completion_tokens', 0):,}")
            c4.metric("LLM Calls", llm_calls)
            # Estimated cost (gpt-4o-mini: $0.15/1M input, $0.60/1M output)
            cost = (token.get("prompt_tokens", 0) * 0.00000015 +
                    token.get("completion_tokens", 0) * 0.0000006)
            st.caption(f"💵 Estimated cost: ~${cost:.5f} USD")

        st.markdown("---")

        # Agent flow
        if not agents:
            st.info("💬 Orchestrator menjawab langsung tanpa memanggil sub-agent")
        else:
            st.markdown(f"**Flow: Orchestrator → {len(agents)} tool call(s)**")
            cols_map = {
                "search_products":    "🔵",
                "search_reviews":     "🟢",
                "query_sql":          "🟠",
                "get_recommendations":"🟣",
                "get_analytics":      "🟡",
            }
            for i, agent in enumerate(agents):
                dot = cols_map.get(agent.get("tool", ""), "⚪")
                st.markdown(
                    f"{dot} **Step {i+1}** → `{agent['icon']} {agent['name']}` "
                    f"— _{agent['desc']}_  "
                    f"&nbsp;&nbsp;&nbsp;&nbsp;Input: `{agent['input_summary'][:80]}`"
                )

def render_product_cards(results):
    """Render product search results as cards."""
    SENTIMENT_COLORS = {
        "sangat positif": "#22c55e", "positif": "#86efac",
        "netral": "#fbbf24", "negatif": "#f97316", "sangat negatif": "#ef4444",
    }
    for r in results:
        sc = SENTIMENT_COLORS.get(r.get("sentiment", ""), "#94a3b8")
        st.markdown(f"""<div class="product-card">
            <b>🏷️ ID:</b> {r.get('product_id','N/A')} &nbsp;|&nbsp;
            <b>📦</b> {r.get('category','N/A')} &nbsp;|&nbsp;
            <b>⭐</b> {r.get('avg_rating') or r.get('avg_score','N/A')}/5 &nbsp;|&nbsp;
            <b>💰</b> BRL {r.get('avg_price','N/A')}<br>
            <span style="background:{sc}20;color:{sc};border:1px solid {sc};
              padding:1px 8px;border-radius:20px;font-size:.8em">
              {r.get('sentiment','')}
            </span> &nbsp;
            <b>Relevansi:</b> {r.get('relevance_score') or r.get('score',0):.0%}<br>
            <details><summary style="cursor:pointer;color:#667eea;font-size:.85em">Detail</summary>
            <small>{r.get('summary') or r.get('text','')[:300]}</small></details>
        </div>""", unsafe_allow_html=True)

def render_recommendation_cards(recs):
    """Render recommendation results as cards."""
    cols = st.columns(2)
    for i, r in enumerate(recs):
        with cols[i % 2]:
            score_pct = int(r.get("recommendation_score", 0) * 100)
            rating = r.get("avg_rating") or 0
            stars = "⭐" * int(round(rating)) if rating else ""
            st.markdown(f"""<div class="product-card">
                <div style="display:flex;justify-content:space-between">
                  <span style="font-size:1.2em">#{r['rank']}</span>
                  <span style="background:#667eea;color:white;padding:2px 8px;
                    border-radius:20px;font-size:.8em">{score_pct}% match</span>
                </div>
                <b>📦</b> {r.get('category','N/A')}<br>
                <b>⭐</b> {stars} ({rating:.1f} / 5)<br>
                <b>💰</b> BRL {r.get('avg_price') or 'N/A'}<br>
                <b>😊</b> {r.get('sentiment','N/A')}<br>
                <details><summary style="cursor:pointer;color:#667eea;font-size:.85em">Alasan rekomendasi</summary>
                <small>{r.get('reason','')[:250]}</small></details>
            </div>""", unsafe_allow_html=True)

# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="background:linear-gradient(135deg,#667eea,#764ba2);
      padding:.8rem 1rem;border-radius:10px;text-align:center;margin-bottom:.5rem">
      <span style="color:white;font-size:1.4em;font-weight:700">🛒 Olist AI</span><br>
      <span style="color:rgba(255,255,255,.8);font-size:.75em">E-commerce Assistant</span>
    </div>""", unsafe_allow_html=True)
    st.markdown("---")
    page = st.radio("Navigasi", [
        "💬 Chat Assistant", "🔍 Product Search",
        "⭐ Recommendations", "📊 Analytics Dashboard"])
    st.markdown("---")
    st.caption("Final Project JCAI 2025 — Purwadhika")
    st.caption(f"Model: `{os.getenv('LLM_MODEL','gpt-4o-mini')}`")
    try:
        requests.get(f"{API_BASE}/health", timeout=2)
        st.success("🟢 API Online")
    except:
        st.error("🔴 API Offline")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 1 — CHAT
# ══════════════════════════════════════════════════════════════════════════════
if page == "💬 Chat Assistant":
    st.markdown("""<div class="main-header">
        <h2 style="margin:0">💬 Olist AI Assistant</h2>
        <p style="margin:4px 0 0;opacity:.9">Tanya apa saja tentang produk, penjual, atau tren penjualan</p>
    </div>""", unsafe_allow_html=True)

    meta_idx = 0
    for i, msg in enumerate(st.session_state.chat_history):
        cls = "chat-user" if msg["role"] == "user" else "chat-bot"
        icon = "👤" if msg["role"] == "user" else "🤖"
        st.markdown(f'<div class="{cls}">{icon} {msg["content"]}</div>', unsafe_allow_html=True)
        # Show agent trace after each bot message
        if msg["role"] == "assistant" and meta_idx < len(st.session_state.chat_metadata):
            render_agent_trace(st.session_state.chat_metadata[meta_idx])
            meta_idx += 1

    with st.form("chat_form", clear_on_submit=True):
        c1, c2 = st.columns([5, 1])
        user_input = c1.text_input("Pesan", placeholder="Contoh: Produk elektronik rating terbaik?",
                                   label_visibility="collapsed")
        submitted = c2.form_submit_button("Kirim", use_container_width=True)

    if submitted and user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        with st.spinner("🤔 Memproses..."):
            resp, meta = api_chat(user_input)
        st.session_state.chat_history.append({"role": "assistant", "content": resp})
        st.session_state.chat_metadata.append(meta)
        st.rerun()

    st.markdown("**💡 Coba tanya:**")
    prompts = [
        "Produk apa yang paling banyak ulasan positif?",
        "Seller dengan revenue terbesar di SP?",
        "Rata-rata waktu pengiriman ke RJ?",
        "Rekomendasikan produk olahraga budget terjangkau",
    ]
    cols = st.columns(2)
    for i, p in enumerate(prompts):
        if cols[i % 2].button(p, key=f"qp{i}", use_container_width=True):
            st.session_state.chat_history.append({"role": "user", "content": p})
            with st.spinner("🤔 Memproses..."):
                resp, meta = api_chat(p)
            st.session_state.chat_history.append({"role": "assistant", "content": resp})
            st.session_state.chat_metadata.append(meta)
            st.rerun()

    if st.button("🗑️ Reset Percakapan"):
        st.session_state.chat_history = []
        st.session_state.chat_metadata = []
        try: requests.post(f"{API_BASE}/chat/reset", timeout=3)
        except: pass
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2 — PRODUCT SEARCH
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🔍 Product Search":
    st.markdown("""<div class="main-header">
        <h2 style="margin:0">🔍 Product Search</h2>
        <p style="margin:4px 0 0;opacity:.9">Cari produk menggunakan teks atau gambar</p>
    </div>""", unsafe_allow_html=True)

    tab_text, tab_img = st.tabs(["📝 Text Search", "🖼️ Image Search"])

    # ── Text Search ───────────────────────────────────────────────────────────
    with tab_text:
        c1, c2, c3 = st.columns([3, 1, 1])
        query = c1.text_input("Cari produk...", placeholder="Sepatu, tas, elektronik...",
                              value=st.session_state.text_search_query)
        cat_options = ["Semua","health_beauty","bed_bath_table","sports_leisure",
                       "furniture_decor","computers_accessories","housewares",
                       "watches_gifts","telephony","garden_tools"]
        cat_filter = c2.selectbox("Kategori", cat_options)
        min_rat    = c3.slider("Min Rating", 1.0, 5.0, 3.0, 0.5)

        if st.button("🔍 Cari", use_container_width=True) and query:
            st.session_state.text_search_query = query
            with st.spinner("Mencari..."):
                st.session_state.text_search_results = api_search(
                    query,
                    category=None if cat_filter == "Semua" else cat_filter,
                    min_rating=min_rat,
                )

        if st.session_state.text_search_results is not None:
            results = st.session_state.text_search_results
            if results:
                st.markdown(f"**{len(results)} produk ditemukan:**")
                render_product_cards(results)
            else:
                st.info("Tidak ada produk ditemukan. Coba query yang berbeda.")

        st.markdown("---")
        st.markdown("**💡 Coba contoh pencarian:**")
        text_examples = [
            "Sepatu olahraga ringan",
            "Tas kulit untuk kerja",
            "Headphone bluetooth terbaik",
            "Peralatan dapur anti lengket",
        ]
        cols_ex = st.columns(2)
        for i, ex in enumerate(text_examples):
            if cols_ex[i % 2].button(ex, key=f"ts_ex_{i}", use_container_width=True):
                st.session_state.text_search_query = ex
                with st.spinner(f"Mencari: {ex}..."):
                    st.session_state.text_search_results = api_search(ex, min_rating=3.0)
                st.rerun()

    # ── Image Search ──────────────────────────────────────────────────────────
    with tab_img:
        st.info("Upload gambar produk → GPT-4o-mini menganalisis → cari produk serupa di database")
        st.markdown("**Contoh gambar sepatu untuk dicoba:**")

        if IMAGE_EXAMPLE_PATH and os.path.exists(IMAGE_EXAMPLE_PATH):
            st.image(IMAGE_EXAMPLE_PATH, caption="Contoh sepatu untuk pencarian image search", width=320)
            if st.button("🔍 Cari Produk Mirip Sepatu Ini", use_container_width=True):
                try:
                    with open(IMAGE_EXAMPLE_PATH, "rb") as f:
                        example_bytes = f.read()
                    results, error = api_image_search(example_bytes, top_k=6)
                    if error:
                        st.error(f"Error: {error}")
                        st.session_state.image_results = []
                    else:
                        st.session_state.image_bytes = example_bytes
                        st.session_state.image_results = results
                except Exception as e:
                    st.error(f"Gagal memuat contoh gambar sepatu: {e}")
        else:
            st.warning("Contoh gambar sepatu tidak tersedia. Pastikan file 'streamlit/image_example' berisi path gambar yang valid.")

        uploaded = st.file_uploader(
            "Upload Gambar", type=["jpg", "jpeg", "png", "webp"],
            key="img_uploader"
        )

        # Simpan bytes ke session_state saat file baru diupload
        if uploaded is not None:
            current_bytes = uploaded.read()
            if current_bytes != st.session_state.get("image_bytes"):
                # File baru → reset hasil sebelumnya
                st.session_state.image_bytes = current_bytes
                st.session_state.image_results = None
                st.session_state.image_description = None

        if st.session_state.image_bytes:
            c1, c2 = st.columns([1, 2])
            c1.image(st.session_state.image_bytes, caption="Gambar yang diupload", width=220)

            with c2:
                if st.button("🔍 Cari Produk Serupa", use_container_width=True):
                    with st.spinner("🤖 GPT-4o-mini menganalisis gambar..."):
                        results, error = api_image_search(
                            st.session_state.image_bytes, top_k=6
                        )
                    if error:
                        st.error(f"Error: {error}")
                        st.session_state.image_results = []
                    else:
                        st.session_state.image_results = results

            # Tampilkan hasil (persisten setelah klik)
            if st.session_state.image_results is not None:
                results = st.session_state.image_results
                if results:
                    st.markdown(f"**{len(results)} produk serupa ditemukan:**")
                    for r in results:
                        description = r.get('summary') or r.get('text', '')
                        if not description:
                            description = "Deskripsi tidak tersedia."
                        st.markdown(f"""<div class="product-card">
                            <b>🏷️ ID:</b> {r.get('product_id','N/A')} &nbsp;|&nbsp;
                            <b>📦</b> {r.get('category','N/A')} &nbsp;|&nbsp;
                            <b>Skor:</b> {float(r.get('score',0)):.0%}<br>
                            <details><summary style="cursor:pointer;color:#667eea;font-size:.85em">Detail</summary>
                            <small>{description}</small></details>
                        </div>""", unsafe_allow_html=True)
                else:
                    st.warning("Tidak ada produk serupa ditemukan.")
        else:
            st.markdown("👆 Upload gambar untuk memulai pencarian")
            _example_path = APP_DIR / "image_example.jpg"
            if _example_path.exists():
                st.markdown("---")
                st.markdown("**💡 Atau coba contoh gambar:**")
                c1, c2 = st.columns([1, 3])
                c1.image(str(_example_path), caption="Contoh: sepatu", width=150)
                with c2:
                    if c2.button("👟 Gunakan contoh gambar sepatu", use_container_width=True):
                        st.session_state.image_bytes = _example_path.read_bytes()
                        st.session_state.image_results = None
                        st.session_state.image_description = None
                        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3 — RECOMMENDATIONS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "⭐ Recommendations":
    st.markdown("""<div class="main-header">
        <h2 style="margin:0">⭐ Product Recommendations</h2>
        <p style="margin:4px 0 0;opacity:.9">Rekomendasi produk berdasarkan preferensimu</p>
    </div>""", unsafe_allow_html=True)

    # Init session state untuk rekomendasi
    if "rec_results" not in st.session_state:
        st.session_state.rec_results = None
    if "rec_query" not in st.session_state:
        st.session_state.rec_query = ""

    # Input form
    pref = st.text_area(
        "Ceritakan apa yang kamu cari:",
        value=st.session_state.rec_query,
        placeholder="Saya mencari produk perawatan kulit natural dengan ulasan positif...",
        height=100,
        key="rec_textarea",
    )
    c1, c2 = st.columns([1, 3])
    top_k = c1.slider("Jumlah rekomendasi", 3, 10, 6)
    go    = c2.button("✨ Rekomendasikan", use_container_width=True)

    if go and pref:
        st.session_state.rec_query = pref
        with st.spinner("Mencari rekomendasi terbaik..."):
            st.session_state.rec_results = api_recommend(pref, top_k=top_k)

    # Tampilkan hasil (persisten)
    if st.session_state.rec_results is not None:
        if st.session_state.rec_results:
            st.markdown(f"### 🎯 Top {len(st.session_state.rec_results)} Rekomendasi")
            render_recommendation_cards(st.session_state.rec_results)
        else:
            st.warning("Tidak ada rekomendasi. Coba ubah deskripsi preferensimu.")

    # Quick examples — TANPA st.rerun(), langsung proses dan tampilkan
    st.markdown("---")
    st.markdown("**💡 Coba contoh ini:**")
    examples = [
        "Produk rumah tangga tahan lama, pengiriman cepat",
        "Gadget dan aksesoris teknologi untuk hadiah",
        "Produk olahraga outdoor ulasan positif",
        "Mainan anak aman dan edukatif",
    ]
    cols = st.columns(2)
    for i, ex in enumerate(examples):
        if cols[i % 2].button(ex, key=f"ex_{i}", use_container_width=True):
            st.session_state.rec_query = ex
            with st.spinner(f"Mencari rekomendasi untuk: {ex}"):
                st.session_state.rec_results = api_recommend(ex, top_k=top_k)
            st.rerun()  # rerun SETELAH hasil sudah disimpan ke session_state


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 4 — ANALYTICS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📊 Analytics Dashboard":
    st.markdown("""<div class="main-header">
        <h2 style="margin:0">📊 Analytics Dashboard</h2>
        <p style="margin:4px 0 0;opacity:.9">Business intelligence — Olist e-commerce Brasil</p>
    </div>""", unsafe_allow_html=True)

    tabs = st.tabs(["📈 Revenue", "🏪 Top Sellers", "📦 Kategori", "🚚 Pengiriman", "💳 Pembayaran"])

    with tabs[0]:
        with st.spinner("Loading..."):
            data = api_analytics("monthly_revenue")
        if data.get("data"):
            df = pd.DataFrame(data["data"])
            # Hapus baris dengan revenue None/NaN
            df = df.dropna(subset=["revenue"])
            df["revenue"] = pd.to_numeric(df["revenue"], errors="coerce").fillna(0)
            df["orders"]  = pd.to_numeric(df["orders"],  errors="coerce").fillna(0)
            fig = px.line(df, x="year_month", y="revenue", markers=True,
                          title="Monthly Revenue (BRL)", template="plotly_white",
                          color_discrete_sequence=["#667eea"])
            st.plotly_chart(fig, use_container_width=True)
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Revenue", f"BRL {df['revenue'].sum():,.0f}")
            c2.metric("Avg Bulanan",   f"BRL {df['revenue'].mean():,.0f}")
            c3.metric("Total Orders",  f"{df['orders'].sum():,.0f}")
        else:
            st.warning("Data revenue tidak tersedia.")

    with tabs[1]:
        state_sel = st.selectbox("Filter State", ["Semua","SP","RJ","MG","RS","PR"])
        with st.spinner("Loading..."):
            data = api_analytics("top_sellers",
                state=None if state_sel == "Semua" else state_sel, limit=15)
        if data.get("data"):
            df = pd.DataFrame(data["data"]).fillna(0)
            fig = px.bar(df, x="total_revenue", y="seller_id", orientation="h",
                         color="avg_rating", color_continuous_scale="Viridis",
                         title="Top Sellers by Revenue", template="plotly_white")
            fig.update_layout(yaxis=dict(categoryorder="total ascending"))
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(df, use_container_width=True)

    with tabs[2]:
        with st.spinner("Loading..."):
            data = api_analytics("category_stats")
        if data.get("data"):
            df = pd.DataFrame(data["data"]).fillna(0)
            c1, c2 = st.columns(2)
            with c1:
                fig = px.bar(df.head(15), x="category_en", y="total_orders",
                             color="avg_rating", color_continuous_scale="RdYlGn",
                             title="Orders per Category", template="plotly_white")
                fig.update_xaxes(tickangle=45)
                st.plotly_chart(fig, use_container_width=True)
            with c2:
                fig = px.scatter(df, x="avg_price", y="avg_rating", size="total_orders",
                                 color="late_pct", color_continuous_scale="RdYlGn_r",
                                 hover_name="category_en",
                                 title="Harga vs Rating",
                                 template="plotly_white")
                st.plotly_chart(fig, use_container_width=True)

    with tabs[3]:
        with st.spinner("Loading..."):
            data = api_analytics("delivery_performance")
        if data.get("data"):
            df = pd.DataFrame(data["data"]).fillna(0)
            fig = px.bar(df.sort_values("avg_delivery_days"),
                         x="customer_state", y="avg_delivery_days",
                         color="late_pct", color_continuous_scale="YlOrRd",
                         title="Rata-rata Hari Pengiriman per State",
                         template="plotly_white")
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(df, use_container_width=True)

    with tabs[4]:
        with st.spinner("Loading..."):
            data = api_analytics("payment_distribution")
        if data.get("data"):
            df = pd.DataFrame(data["data"]).fillna(0)
            c1, c2 = st.columns(2)
            with c1:
                fig = px.pie(df, names="payment_type", values="count",
                             title="Distribusi Metode Pembayaran",
                             template="plotly_white",
                             color_discrete_sequence=px.colors.qualitative.Set2)
                st.plotly_chart(fig, use_container_width=True)
            with c2:
                fig = px.bar(df, x="payment_type", y="avg_value", color="payment_type",
                             title="Nilai Rata-rata per Metode",
                             template="plotly_white",
                             color_discrete_sequence=px.colors.qualitative.Set2)
                st.plotly_chart(fig, use_container_width=True)

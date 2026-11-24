"""
InventoryIQ Streamlit app.
Run: streamlit run app.py
"""

import os
import sqlite3
from pathlib import Path

import httpx
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

DB_PATH = Path("db/inventoryiq.db")
CHROMA_DIR = Path("db/chroma")
CHROMA_SQLITE = CHROMA_DIR / "chroma.sqlite3"
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
NIM_MODEL = "nvidia/nemotron-3.5-lightning-30b-a3b"
EMBED_MODEL = "nvidia/nemotron-3-embed-1b"

st.set_page_config(
    page_title="InventoryIQ",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
<style>
  :root {
    --bg: #0b1020;
    --surface: rgba(16, 24, 40, 0.88);
    --surface-2: rgba(20, 30, 54, 0.92);
    --surface-3: rgba(12, 18, 34, 0.96);
    --border: rgba(148, 163, 184, 0.18);
    --text: #eef2ff;
    --muted: #a9b4cc;
    --accent: #36cfc9;
    --accent-2: #8bd450;
    --danger: #ff6b6b;
    --warn: #f8c15c;
    --ok: #53d38c;
    --shadow: 0 24px 60px rgba(0, 0, 0, 0.28);
  }

  .stApp {
    background:
      radial-gradient(circle at top left, rgba(54, 207, 201, 0.12), transparent 28%),
      radial-gradient(circle at top right, rgba(139, 212, 80, 0.12), transparent 24%),
      linear-gradient(180deg, #0a0f1d 0%, #0d1323 100%);
    color: var(--text);
  }

  .block-container {
    padding-top: 1.2rem;
    padding-bottom: 2.4rem;
    max-width: 1320px;
  }

  h1, h2, h3, h4, h5, h6, p, label, span, div {
    color: var(--text);
  }

  .app-shell {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 22px;
    padding: 1.1rem 1.15rem 1.35rem 1.15rem;
    box-shadow: var(--shadow);
    backdrop-filter: blur(14px);
  }

  .hero {
    background:
      linear-gradient(135deg, rgba(54, 207, 201, 0.12), rgba(139, 212, 80, 0.08)),
      rgba(14, 20, 36, 0.92);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 22px;
    padding: 1.5rem 1.5rem 1.35rem 1.5rem;
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
  }

  .eyebrow {
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-size: 0.74rem;
    color: var(--accent);
    margin-bottom: 0.45rem;
    font-weight: 700;
  }

  .hero-title {
    font-size: clamp(2.2rem, 3vw, 3.3rem);
    font-weight: 800;
    line-height: 1;
    margin: 0;
  }

  .hero-copy {
    color: var(--muted);
    font-size: 1.01rem;
    line-height: 1.6;
    margin: 0.9rem 0 0 0;
    max-width: 60rem;
  }

  .badge-row {
    display: flex;
    gap: 0.55rem;
    flex-wrap: wrap;
    margin-top: 1rem;
  }

  .badge {
    background: rgba(139, 212, 80, 0.16);
    border: 1px solid rgba(139, 212, 80, 0.25);
    color: #dff4c6;
    border-radius: 999px;
    padding: 0.35rem 0.68rem;
    font-size: 0.77rem;
    font-weight: 700;
  }

  .status-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 0.85rem;
    margin-top: 1.2rem;
  }

  .status-card, .metric-tile, .info-panel {
    background: var(--surface-2);
    border: 1px solid var(--border);
    border-radius: 18px;
    padding: 0.95rem 1rem;
  }

  .status-top, .metric-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
  }

  .status-dot {
    width: 0.7rem;
    height: 0.7rem;
    border-radius: 999px;
    display: inline-block;
    margin-right: 0.5rem;
    box-shadow: 0 0 0 4px rgba(255,255,255,0.03);
  }

  .status-ready { background: var(--ok); }
  .status-fallback { background: var(--warn); }
  .status-missing, .status-error, .status-offline { background: var(--danger); }

  .status-label {
    font-size: 0.95rem;
    font-weight: 700;
  }

  .status-detail, .subtle-copy {
    color: var(--muted);
    font-size: 0.84rem;
    line-height: 1.45;
  }

  .metric-value {
    font-size: 2rem;
    font-weight: 800;
    line-height: 1;
    margin-top: 0.5rem;
  }

  .metric-label {
    color: var(--muted);
    font-size: 0.84rem;
    margin-top: 0.35rem;
  }

  .section-head {
    margin: 0 0 0.4rem 0;
    font-size: 1.55rem;
    font-weight: 800;
  }

  .section-copy {
    color: var(--muted);
    margin: 0 0 1rem 0;
    line-height: 1.55;
  }

  .info-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.85rem;
  }

  .info-panel h4 {
    margin: 0 0 0.55rem 0;
    font-size: 1rem;
  }

  .info-panel ul {
    margin: 0;
    padding-left: 1rem;
    color: var(--muted);
  }

  .info-panel li {
    margin-bottom: 0.35rem;
  }

  .toolbar {
    background: var(--surface-3);
    border: 1px solid var(--border);
    border-radius: 18px;
    padding: 0.95rem 1rem;
    margin: 1rem 0;
  }

  .page-card {
    background: rgba(13, 19, 35, 0.74);
    border: 1px solid var(--border);
    border-radius: 20px;
    padding: 1.15rem 1.15rem 1.25rem 1.15rem;
    margin-top: 1rem;
  }

  .callout {
    border-radius: 16px;
    padding: 0.95rem 1rem;
    border: 1px solid transparent;
    margin-bottom: 0.8rem;
  }

  .callout-ok {
    background: rgba(83, 211, 140, 0.11);
    border-color: rgba(83, 211, 140, 0.22);
  }

  .callout-warn {
    background: rgba(248, 193, 92, 0.12);
    border-color: rgba(248, 193, 92, 0.22);
  }

  .callout-danger {
    background: rgba(255, 107, 107, 0.12);
    border-color: rgba(255, 107, 107, 0.22);
  }

  .small-kpi-row {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 0.85rem;
    margin-top: 1rem;
  }

  div[data-baseweb="select"] > div,
  div[data-baseweb="input"] > div,
  .stTextArea textarea {
    background: rgba(33, 39, 54, 0.9) !important;
    border-radius: 14px !important;
    border: 1px solid rgba(148, 163, 184, 0.18) !important;
  }

  .stSlider [data-baseweb="slider"] {
    padding-top: 0.45rem;
  }

  div[role="radiogroup"] {
    gap: 0.7rem;
  }

  .stDataFrame, .stPlotlyChart {
    border-radius: 16px;
    overflow: hidden;
  }

  @media (max-width: 1100px) {
    .status-grid, .info-grid, .small-kpi-row {
      grid-template-columns: 1fr 1fr;
    }
  }

  @media (max-width: 760px) {
    .status-grid, .info-grid, .small-kpi-row {
      grid-template-columns: 1fr;
    }
    .hero {
      padding: 1.2rem;
    }
  }
</style>
""",
    unsafe_allow_html=True,
)


@st.cache_resource
def get_conn():
    if not DB_PATH.exists():
        return None
    return sqlite3.connect(str(DB_PATH), check_same_thread=False)


@st.cache_data(ttl=300)
def load_inventory():
    conn = get_conn()
    if conn is None:
        return pd.DataFrame()
    return pd.read_sql("SELECT * FROM inventory", conn)


@st.cache_data(ttl=300)
def load_kpis():
    conn = get_conn()
    if conn is None:
        return {}
    df = pd.read_sql("SELECT key, value FROM kpi_summary", conn)
    return dict(zip(df["key"], df["value"]))


@st.cache_data(ttl=300)
def load_supplier_drift():
    conn = get_conn()
    if conn is None:
        return pd.DataFrame()
    return pd.read_sql("SELECT * FROM supplier_drift ORDER BY avg_drift_pct DESC", conn)


def sku_as_dict(row: pd.Series) -> dict:
    return row.to_dict()


@st.cache_data(ttl=300, show_spinner=False)
def get_runtime_status():
    status = {
        "database": {
            "label": "Database",
            "state": "ready" if DB_PATH.exists() else "missing",
            "detail": str(DB_PATH) if DB_PATH.exists() else "Run setup_db.py",
        },
        "rag_index": {
            "label": "RAG Index",
            "state": "ready" if CHROMA_SQLITE.exists() else "missing",
            "detail": str(CHROMA_DIR) if CHROMA_SQLITE.exists() else "Run rag/ingest.py",
        },
        "nemo": {
            "label": "NeMo Retriever",
            "state": "offline",
            "detail": "Set NVIDIA_API_KEY in .env",
        },
        "nim": {
            "label": "NIM",
            "state": "offline",
            "detail": "Set NVIDIA_API_KEY in .env",
        },
    }

    api_key = os.environ.get("NVIDIA_API_KEY", "")
    if not api_key:
        return status

    try:
        from openai import OpenAI

        client = OpenAI(
            base_url=NVIDIA_BASE_URL,
            api_key=api_key,
            timeout=httpx.Timeout(6.0, connect=3.0),
        )
    except Exception as e:
        detail = f"Client setup failed: {e}"
        status["nemo"] = {"label": "NeMo Retriever", "state": "error", "detail": detail}
        status["nim"] = {"label": "NIM", "state": "error", "detail": detail}
        return status

    try:
        client.embeddings.create(
            input=["inventory policy ping"],
            model=EMBED_MODEL,
            encoding_format="float",
            extra_body={"input_type": "query", "truncate": "END"},
        )
        status["nemo"] = {
            "label": "NeMo Retriever",
            "state": "ready",
            "detail": "NVIDIA retrieval endpoint reachable",
        }
    except Exception as e:
        status["nemo"] = {
            "label": "NeMo Retriever",
            "state": "fallback",
            "detail": f"Local embedding fallback active: {e}",
        }

    try:
        client.chat.completions.create(
            model=NIM_MODEL,
            messages=[{"role": "user", "content": "ping"}],
            temperature=0,
            max_tokens=1,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            stream=False,
        )
        status["nim"] = {
            "label": "NIM",
            "state": "ready",
            "detail": "LLM endpoint reachable",
        }
    except Exception as e:
        status["nim"] = {
            "label": "NIM",
            "state": "fallback",
            "detail": f"Offline answer mode active: {e}",
        }

    return status


def check_setup():
    if not DB_PATH.exists():
        st.error("Database not found. Run the setup pipeline first.")
        st.code(
            """python data/generate_inventory.py
python setup_db.py
python rag/ingest.py
streamlit run app.py"""
        )
        st.stop()


def format_currency(value: float) -> str:
    return f"${value:,.0f}"


def render_status_card(item: dict):
    state_class = {
        "ready": "status-ready",
        "fallback": "status-fallback",
        "missing": "status-missing",
        "error": "status-error",
        "offline": "status-offline",
    }.get(item["state"], "status-offline")
    return f"""
    <div class="status-card">
      <div class="status-top">
        <div class="status-label">
          <span class="status-dot {state_class}"></span>{item['label']}
        </div>
      </div>
      <div class="status-detail">{item['detail']}</div>
    </div>
    """


def render_metric_tile(value: str, label: str, eyebrow: str = ""):
    eyebrow_html = f'<div class="eyebrow" style="margin:0 0 0.35rem 0;">{eyebrow}</div>' if eyebrow else ""
    return f"""
    <div class="metric-tile">
      {eyebrow_html}
      <div class="metric-value">{value}</div>
      <div class="metric-label">{label}</div>
    </div>
    """


def render_hero():
    status = get_runtime_status()
    kpis = load_kpis()
    metric_html = [
        render_metric_tile(kpis.get("total_skus", "0"), "Tracked SKUs", "Inventory"),
        render_metric_tile(kpis.get("flagged_skus", "0"), "Flagged SLOB items", "Risk"),
        render_metric_tile(f"{kpis.get('avg_compliance_score', '0')}%", "Average compliance", "Policy"),
        render_metric_tile(kpis.get("suppliers_with_drift", "0"), "Suppliers drifting", "Lead times"),
    ]
    status_html = "".join(render_status_card(status[key]) for key in ["database", "rag_index", "nemo", "nim"])

    st.markdown(
        f"""
        <div class="hero">
          <div class="eyebrow">Inventory policy intelligence</div>
          <h1 class="hero-title">InventoryIQ</h1>
          <p class="hero-copy">
            A decision workspace for reorder point auditing, slow-moving stock review,
            supplier drift monitoring, and policy-grounded explanations. The experience
            is designed to work in both live NVIDIA mode and offline fallback mode,
            without hiding which one is active.
          </p>
          <div class="badge-row">
            <span class="badge">NVIDIA NeMo</span>
            <span class="badge">RAPIDS cuML</span>
            <span class="badge">NIM</span>
            <span class="badge">SQLite + ChromaDB</span>
          </div>
          <div class="status-grid">{status_html}</div>
          <div class="small-kpi-row">{''.join(metric_html)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_shell_open():
    st.markdown('<div class="app-shell">', unsafe_allow_html=True)


def render_shell_close():
    st.markdown("</div>", unsafe_allow_html=True)


def render_page_header(title: str, copy: str):
    st.markdown(
        f"""
        <div class="page-card" style="padding-bottom:1rem;">
          <h2 class="section-head">{title}</h2>
          <p class="section-copy">{copy}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_home():
    kpis = load_kpis()
    status = get_runtime_status()

    render_page_header(
        "What this workspace does",
        "InventoryIQ combines policy retrieval, anomaly review, and supplier lead-time analysis so planners can understand why a SKU needs attention and what action should happen next.",
    )

    st.markdown(
        """
        <div class="info-grid">
          <div class="info-panel">
            <h4>Policy intelligence</h4>
            <ul>
              <li>Grounds answers in the inventory policy document.</li>
              <li>Explains reorder point changes with policy and drift context.</li>
              <li>Supports operator Q and A without leaving the dashboard.</li>
            </ul>
          </div>
          <div class="info-panel">
            <h4>Operational monitoring</h4>
            <ul>
              <li>Flags obsolete and slow-moving stock.</li>
              <li>Surfaces supplier lead-time breaches and value at risk.</li>
              <li>Keeps SKU-level action recommendations close to the data.</li>
            </ul>
          </div>
          <div class="info-panel">
            <h4>Demo readiness</h4>
            <ul>
              <li>Shows whether NVIDIA services are live or in fallback mode.</li>
              <li>Works locally even when NeMo or NIM are unreachable.</li>
              <li>Separates setup health from business insights.</li>
            </ul>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("")
    cols = st.columns([1.1, 1.1, 1.2])
    with cols[0]:
        st.markdown(
            render_metric_tile(
                format_currency(float(kpis.get("total_slob_value_at_risk", "0"))),
                "Current value at risk",
                "Exposure",
            ),
            unsafe_allow_html=True,
        )
    with cols[1]:
        st.markdown(
            render_metric_tile(
                kpis.get("skus_below_rop", "0"),
                "SKUs currently below policy ROP",
                "Replenishment",
            ),
            unsafe_allow_html=True,
        )
    with cols[2]:
        if status["nim"]["state"] == "ready" and status["nemo"]["state"] == "ready":
            callout_class = "callout-ok"
            message = "Live NVIDIA mode is active. Retrieval and generation endpoints are reachable."
        elif status["rag_index"]["state"] == "ready":
            callout_class = "callout-warn"
            message = "Fallback mode is active. The app can still answer and analyze locally, but NVIDIA services are not currently reachable."
        else:
            callout_class = "callout-danger"
            message = "The app shell is available, but the RAG index still needs to be built before policy workflows are fully ready."
        st.markdown(f'<div class="callout {callout_class}">{message}</div>', unsafe_allow_html=True)

    st.markdown("")
    st.markdown(
        """
        <div class="toolbar">
          <h3 style="margin:0 0 0.4rem 0;">How to use the app</h3>
          <div class="subtle-copy">
            Start in <b>Overview</b> for portfolio health, move to <b>ROP Audit</b> when lead times drift,
            jump to <b>SLOB Watchlist</b> for liquidation and aging decisions, and use <b>Ask the Policy</b>
            when a planner needs the reasoning in plain language.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def tab_overview():
    kpis = load_kpis()
    df = load_inventory()
    sup = load_supplier_drift()

    if df.empty:
        st.warning("No data found. Run setup_db.py first.")
        return

    render_page_header(
        "Portfolio overview",
        "Track supplier drift, compliance distribution, and risk concentration before drilling into a SKU-level workflow.",
    )

    cards = [
        render_metric_tile(kpis.get("total_skus", "0"), "Total SKUs", "Scope"),
        render_metric_tile(kpis.get("flagged_skus", "0"), "SLOB flagged", "Attention"),
        render_metric_tile(f"{kpis.get('avg_compliance_score', '0')}%", "Average compliance", "Policy"),
        render_metric_tile(kpis.get("skus_below_rop", "0"), "Below reorder point", "Replenishment"),
        render_metric_tile(kpis.get("suppliers_with_drift", "0"), "Suppliers drifting", "Lead times"),
    ]
    st.markdown(f'<div class="small-kpi-row">{"".join(cards)}</div>', unsafe_allow_html=True)

    st.markdown("")
    left, right = st.columns(2)

    with left:
        st.markdown('<div class="page-card">', unsafe_allow_html=True)
        st.subheader("Supplier Lead-Time Drift")
        if not sup.empty:
            top_sup = sup.head(12).copy()
            top_sup["band"] = top_sup["avg_drift_pct"].apply(
                lambda x: "Critical" if x > 30 else ("Watch" if x > 10 else "Stable")
            )
            fig = px.bar(
                top_sup,
                x="supplier_id",
                y="avg_drift_pct",
                color="band",
                color_discrete_map={"Critical": "#ff6b6b", "Watch": "#f8c15c", "Stable": "#53d38c"},
                text=top_sup["avg_drift_pct"].round(1),
                labels={"supplier_id": "Supplier", "avg_drift_pct": "Average drift %"},
            )
            fig.update_traces(texttemplate="%{text}%", textposition="outside")
            fig.update_layout(
                height=340,
                margin=dict(l=10, r=10, t=10, b=10),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                legend_title_text="Severity",
            )
            fig.add_hline(y=20, line_dash="dash", line_color="#f8c15c")
            st.plotly_chart(fig, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown('<div class="page-card">', unsafe_allow_html=True)
        st.subheader("Compliance Score Distribution")
        fig2 = px.histogram(
            df,
            x="compliance_score",
            nbins=22,
            color_discrete_sequence=["#36cfc9"],
            labels={"compliance_score": "Compliance score"},
        )
        fig2.update_layout(
            height=340,
            margin=dict(l=10, r=10, t=10, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
        )
        fig2.add_vline(x=60, line_dash="dash", line_color="#f8c15c")
        fig2.add_vline(x=40, line_dash="dash", line_color="#ff6b6b")
        st.plotly_chart(fig2, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("")
    st.markdown('<div class="page-card">', unsafe_allow_html=True)
    st.subheader("SLOB Value at Risk by Category")
    slob_df = df[df["slob_flag"] != "NORMAL"]
    if slob_df.empty:
        st.info("No SLOB items found.")
    else:
        cat_risk = slob_df.groupby(["category", "slob_flag"])["stock_value_at_risk"].sum().reset_index()
        fig3 = px.bar(
            cat_risk,
            x="category",
            y="stock_value_at_risk",
            color="slob_flag",
            barmode="stack",
            color_discrete_map={"OBSOLETE": "#ff6b6b", "SLOW_MOVER": "#f8c15c"},
            labels={"stock_value_at_risk": "Value at risk ($)", "category": "Category"},
        )
        fig3.update_layout(
            height=320,
            margin=dict(l=10, r=10, t=10, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig3, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)


def tab_rop_audit():
    df = load_inventory()
    if df.empty:
        st.warning("No data. Run setup_db.py first.")
        return

    render_page_header(
        "Reorder Point Audit",
        "Compare policy reorder points against recommended values based on actual lead times, then generate an explanation for a selected SKU.",
    )

    st.markdown('<div class="toolbar">', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1.15, 1.15, 1.15])
    with col1:
        cats = ["All"] + sorted(df["category"].unique().tolist())
        cat_filter = st.selectbox("Category", cats)
    with col2:
        drift_min = st.slider("Min Drift %", 0, 200, 20)
    with col3:
        sort_by = st.selectbox(
            "Sort by",
            ["lead_time_drift_pct", "compliance_score", "recommended_rop"],
        )
    st.markdown("</div>", unsafe_allow_html=True)

    filtered = df.copy()
    if cat_filter != "All":
        filtered = filtered[filtered["category"] == cat_filter]
    filtered = filtered[filtered["lead_time_drift_pct"].abs() >= drift_min]
    filtered = filtered.sort_values(sort_by, ascending=(sort_by == "compliance_score"))

    def color_drift(val):
        if val > 30:
            return "background-color:#4d1e24;color:#ffd8db"
        if val > 10:
            return "background-color:#4c3a16;color:#fff0c7"
        return "background-color:#132a23;color:#d5ffe9"

    def color_score(val):
        if val < 40:
            return "background-color:#4d1e24;color:#ffd8db"
        if val < 60:
            return "background-color:#4c3a16;color:#fff0c7"
        return "background-color:#132a23;color:#d5ffe9"

    display_cols = [
        "sku_id",
        "product_name",
        "category",
        "supplier_id",
        "policy_reorder_point",
        "recommended_rop",
        "lead_time_drift_pct",
        "compliance_score",
        "recommended_action",
    ]
    display = filtered[display_cols].rename(
        columns={
            "sku_id": "SKU",
            "product_name": "Product",
            "category": "Category",
            "supplier_id": "Supplier",
            "policy_reorder_point": "Policy ROP",
            "recommended_rop": "Rec. ROP",
            "lead_time_drift_pct": "Drift %",
            "compliance_score": "Score",
            "recommended_action": "Action",
        }
    )

    st.markdown('<div class="page-card">', unsafe_allow_html=True)
    st.dataframe(
        display.style.map(color_drift, subset=["Drift %"]).map(color_score, subset=["Score"]),
        use_container_width=True,
        height=420,
    )
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("")
    st.markdown('<div class="page-card">', unsafe_allow_html=True)
    st.subheader("Explain a selected SKU")
    sku_ids = filtered["sku_id"].tolist()
    if sku_ids:
        picker_col, button_col = st.columns([1.4, 0.7])
        with picker_col:
            selected = st.selectbox("Select a SKU to explain", sku_ids)
        with button_col:
            trigger = st.button("Generate ROP Explanation", type="primary", use_container_width=True)

        if trigger:
            sku_row = df[df["sku_id"] == selected].iloc[0]
            with st.spinner("Generating explanation..."):
                try:
                    from rag.chain import explain_rop

                    answer = explain_rop(sku_as_dict(sku_row))
                except Exception as e:
                    answer = f"Error: {e}"

            drift = float(sku_row["lead_time_drift_pct"])
            if abs(drift) > 30:
                css = "callout callout-danger"
                label = f"High drift detected: {drift:.1f}%"
            elif abs(drift) > 10:
                css = "callout callout-warn"
                label = f"Moderate drift detected: {drift:.1f}%"
            else:
                css = "callout callout-ok"
                label = f"Low drift detected: {drift:.1f}%"

            st.markdown(f'<div class="{css}"><b>{selected}</b> - {sku_row["product_name"]}<br>{label}</div>', unsafe_allow_html=True)
            st.markdown(answer)
    else:
        st.info("No SKUs match the current filters.")
    st.markdown("</div>", unsafe_allow_html=True)


def tab_slob():
    df = load_inventory()
    if df.empty:
        st.warning("No data. Run setup_db.py first.")
        return

    render_page_header(
        "SLOB Watchlist",
        "Review obsolete and slow-moving stock by value at risk, inactivity window, and anomaly severity.",
    )

    st.markdown('<div class="toolbar">', unsafe_allow_html=True)
    c1, c2 = st.columns([1.2, 1.4])
    with c1:
        slob_filter = st.radio(
            "Show",
            ["All SLOB", "OBSOLETE only", "SLOW_MOVER only"],
            horizontal=True,
        )
    with c2:
        cat_filter = st.selectbox(
            "Category",
            ["All"] + sorted(df["category"].unique().tolist()),
            key="slob_cat",
        )
    st.markdown("</div>", unsafe_allow_html=True)

    slob_df = df[df["slob_flag"] != "NORMAL"].copy()
    if slob_filter == "OBSOLETE only":
        slob_df = slob_df[slob_df["slob_flag"] == "OBSOLETE"]
    elif slob_filter == "SLOW_MOVER only":
        slob_df = slob_df[slob_df["slob_flag"] == "SLOW_MOVER"]
    if cat_filter != "All":
        slob_df = slob_df[slob_df["category"] == cat_filter]
    slob_df = slob_df.sort_values("anomaly_score")

    obs = len(slob_df[slob_df["slob_flag"] == "OBSOLETE"])
    slow = len(slob_df[slob_df["slob_flag"] == "SLOW_MOVER"])
    total_risk = slob_df["stock_value_at_risk"].sum()

    cards = [
        render_metric_tile(str(obs), "Obsolete SKUs", "Aging"),
        render_metric_tile(str(slow), "Slow movers", "Velocity"),
        render_metric_tile(format_currency(total_risk), "Value at risk", "Exposure"),
    ]
    st.markdown(f'<div class="small-kpi-row" style="grid-template-columns:repeat(3,minmax(0,1fr));">{"".join(cards)}</div>', unsafe_allow_html=True)

    display_cols = [
        "sku_id",
        "product_name",
        "category",
        "slob_flag",
        "days_since_movement",
        "current_stock",
        "stock_value_at_risk",
        "anomaly_score",
        "recommended_action",
    ]
    display = slob_df[display_cols].rename(
        columns={
            "sku_id": "SKU",
            "product_name": "Product",
            "category": "Category",
            "slob_flag": "Status",
            "days_since_movement": "Days No Movement",
            "current_stock": "Stock",
            "stock_value_at_risk": "Value at Risk ($)",
            "anomaly_score": "Anomaly Score",
            "recommended_action": "Action",
        }
    )

    def color_status(val):
        if val == "OBSOLETE":
            return "background-color:#4d1e24;color:#ffd8db;font-weight:700"
        if val == "SLOW_MOVER":
            return "background-color:#4c3a16;color:#fff0c7;font-weight:700"
        return ""

    st.markdown('<div class="page-card">', unsafe_allow_html=True)
    st.dataframe(
        display.style.map(color_status, subset=["Status"]),
        use_container_width=True,
        height=420,
    )
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("")
    st.markdown('<div class="page-card">', unsafe_allow_html=True)
    st.subheader("Generate action guidance")
    sku_ids = slob_df["sku_id"].tolist()
    if sku_ids:
        picker_col, button_col = st.columns([1.4, 0.7])
        with picker_col:
            selected = st.selectbox("Select SLOB SKU", sku_ids, key="slob_sel")
        with button_col:
            trigger = st.button("Get NIM Recommendation", type="primary", use_container_width=True)

        if trigger:
            sku_row = df[df["sku_id"] == selected].iloc[0]
            with st.spinner("Generating recommendation..."):
                try:
                    from rag.chain import explain_slob

                    answer = explain_slob(sku_as_dict(sku_row))
                except Exception as e:
                    answer = f"Error: {e}"

            flag = sku_row["slob_flag"]
            css = "callout callout-danger" if flag == "OBSOLETE" else "callout callout-warn"
            st.markdown(
                f'<div class="{css}"><b>{selected}</b> - {sku_row["product_name"]}<br>{flag}, {sku_row["days_since_movement"]} days without movement</div>',
                unsafe_allow_html=True,
            )
            st.markdown(answer)
    else:
        st.info("No SLOB SKUs match the current filters.")
    st.markdown("</div>", unsafe_allow_html=True)


def tab_rag_chat():
    render_page_header(
        "Ask the Policy",
        "Use grounded policy Q and A for reorder logic, obsolescence thresholds, and action rules. If NVIDIA services are offline, the app will say so instead of pretending the answer is live.",
    )

    rag_ready = CHROMA_SQLITE.exists()
    if not rag_ready:
        st.warning("RAG index not found. Run `python rag/ingest.py` first.")

    samples = [
        "What is the reorder point formula?",
        "When is a SKU classified as obsolete?",
        "What actions should be taken for slow-moving items?",
        "What is our policy for lead-time drift above 20%?",
        "What service level target applies to Pharmaceuticals?",
        "How is the compliance score calculated?",
    ]

    st.markdown('<div class="page-card">', unsafe_allow_html=True)
    st.subheader("Sample questions")
    cols = st.columns(3)
    for i, question in enumerate(samples):
        with cols[i % 3]:
            if st.button(question, key=f"sample_{i}", use_container_width=True):
                st.session_state["policy_q"] = question
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("")
    st.markdown('<div class="page-card">', unsafe_allow_html=True)
    question = st.text_area(
        "Your question",
        value=st.session_state.get("policy_q", ""),
        placeholder="What does policy say about items with zero movement for 90 days?",
        height=110,
    )

    if st.button("Ask the Policy", type="primary", disabled=not rag_ready):
        if question.strip():
            with st.spinner("Searching policy context..."):
                try:
                    from rag.chain import answer_policy_question

                    answer = answer_policy_question(question.strip())
                except Exception as e:
                    answer = f"Error: {e}"

            st.markdown(f"**Question**  \n{question}")
            st.markdown("**Answer**")
            st.markdown(answer)

            if "chat_history" not in st.session_state:
                st.session_state["chat_history"] = []
            st.session_state["chat_history"].insert(0, (question, answer))
        else:
            st.warning("Please enter a question.")
    st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.get("chat_history"):
        st.markdown("")
        st.markdown('<div class="page-card">', unsafe_allow_html=True)
        st.subheader("Recent questions")
        for q, a in st.session_state["chat_history"][:5]:
            st.markdown(f"**Q:** {q}")
            st.markdown(f"**A:** {a}")
            st.markdown("---")
        st.markdown("</div>", unsafe_allow_html=True)


def render_navigation():
    options = ["Home", "Overview", "ROP Audit", "SLOB Watchlist", "Ask the Policy"]
    return st.radio(
        "Navigation",
        options,
        horizontal=True,
        label_visibility="collapsed",
    )


def main():
    check_setup()
    render_shell_open()
    render_hero()
    st.markdown("")
    active_view = render_navigation()

    if active_view == "Home":
        render_home()
    elif active_view == "Overview":
        tab_overview()
    elif active_view == "ROP Audit":
        tab_rop_audit()
    elif active_view == "SLOB Watchlist":
        tab_slob()
    else:
        tab_rag_chat()

    render_shell_close()


if __name__ == "__main__":
    main()

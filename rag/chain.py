"""
rag/chain.py
LangChain RAG chain using:
  - ChromaDB (NeMo-embedded policy documents)
  - NVIDIA NIM as the LLM endpoint

Three prompt templates:
  1. rop_explanation  — explain reorder-point decisions
  2. slob_action      — recommend action for SLOB items
  3. general_qa       — open-ended policy questions
"""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "")
NIM_BASE_URL   = "https://integrate.api.nvidia.com/v1"
NIM_MODEL      = "nvidia/nemotron-3.5-lightning-30b-a3b"
EMBED_MODEL    = "nvidia/nemotron-3-embed-1b"
CHROMA_DIR     = Path("db/chroma")
COLLECTION     = "inventory_policy"
TOP_K          = 4


# ── Prompt templates ──────────────────────────────────────────────────────────

ROP_TEMPLATE = """You are an expert inventory policy analyst.
Using the policy context below, explain the reorder point decision for this SKU in plain language.
Show the formula with actual numbers. State clearly if the current reorder point needs adjustment.

POLICY CONTEXT:
{context}

SKU DETAILS:
- SKU ID:                {sku_id}
- Product:               {product_name}
- Category:              {category}
- Current Stock:         {current_stock} units
- Policy Reorder Point:  {policy_rop} units
- Recommended ROP:       {recommended_rop} units
- Policy Lead Time:      {policy_lead_time} days
- Actual Lead Time:      {actual_lead_time} days
- Lead-Time Drift:       {drift_pct}%
- Avg Monthly Sales:     {avg_sales} units/month
- Safety Stock:          {safety_stock} units
- Compliance Score:      {compliance_score}/100

Answer in 3–5 sentences. Start with the reorder point formula, then explain the drift impact,
then give a clear recommendation. Keep it concise and actionable."""


SLOB_TEMPLATE = """You are an expert inventory policy analyst.
Using the policy context below, provide a specific action recommendation for this SLOB item.
Reference the exact policy section that applies.

POLICY CONTEXT:
{context}

SLOB ITEM DETAILS:
- SKU ID:               {sku_id}
- Product:              {product_name}
- Category:             {category}
- SLOB Classification:  {slob_flag}
- Days Since Movement:  {days_no_movement} days
- Current Stock:        {current_stock} units
- Stock Value at Risk:  ${stock_value}
- Avg Monthly Sales:    {avg_sales} units/month
- Anomaly Score:        {anomaly_score}
- Recommended Action:   {system_action}

Answer in 3–4 sentences. State the policy section that applies, explain why this item is flagged,
and give a specific, time-bound recommended action. Be direct."""


GENERAL_TEMPLATE = """You are an expert inventory policy analyst for InventoryIQ.
Answer the question below using only the provided policy context.
If the answer is not in the context, say so clearly — do not make up policy rules.

POLICY CONTEXT:
{context}

QUESTION: {question}

Answer concisely and cite the relevant policy section if applicable."""


# ── NeMo query embedding ──────────────────────────────────────────────────────

def embed_query(text: str) -> list:
    """Embed a query string using NeMo Retriever (query input_type)."""
    def fallback_query_embedding() -> list:
        import hashlib, math
        vec = []
        for i in range(384):
            h = hashlib.md5(f"{text}{i}".encode()).hexdigest()
            vec.append((int(h, 16) % 10000 - 5000) / 5000.0)
        norm = math.sqrt(sum(x**2 for x in vec)) or 1.0
        return [x / norm for x in vec]

    if not NVIDIA_API_KEY:
        return fallback_query_embedding()

    from openai import OpenAI
    try:
        client = OpenAI(base_url=NIM_BASE_URL, api_key=NVIDIA_API_KEY)
    except TypeError as e:
        if "proxies" in str(e):
            raise RuntimeError(
                "OpenAI/httpx version mismatch detected. "
                "Run: pip install \"httpx<0.28\" or reinstall requirements.txt."
            ) from e
        raise
    try:
        resp = client.embeddings.create(
            input=[text],
            model=EMBED_MODEL,
            encoding_format="float",
            extra_body={"input_type": "query", "truncate": "END"},
        )
        return resp.data[0].embedding
    except Exception:
        return fallback_query_embedding()


# ── Retriever ─────────────────────────────────────────────────────────────────

def retrieve_context(query: str, top_k: int = TOP_K) -> str:
    """Retrieve relevant policy chunks from ChromaDB."""
    import chromadb
    from chromadb.config import Settings
    from rag.ingest import NeMoEmbeddingFunction

    client = chromadb.PersistentClient(
        path=str(CHROMA_DIR),
        settings=Settings(anonymized_telemetry=False),
    )
    collection = client.get_collection(
        name=COLLECTION,
        embedding_function=NeMoEmbeddingFunction(),  # type: ignore
    )

    query_embedding = embed_query(query)
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas"],
    )

    docs = results["documents"][0]
    context = "\n\n---\n\n".join(docs)
    return context


# ── NIM LLM call ──────────────────────────────────────────────────────────────

def call_nim(prompt: str, max_tokens: int = 400) -> str:
    """Call NVIDIA NIM LLM endpoint."""
    if not NVIDIA_API_KEY:
        return (
            "⚠️  NVIDIA_API_KEY not set. Set it in your .env file to enable "
            "NIM-powered explanations. Get a free key at build.nvidia.com."
        )

    from openai import OpenAI
    try:
        client = OpenAI(base_url=NIM_BASE_URL, api_key=NVIDIA_API_KEY)
    except TypeError as e:
        if "proxies" in str(e):
            return (
                "⚠️  OpenAI/httpx version mismatch detected. "
                "Run: pip install \"httpx<0.28\" or reinstall requirements.txt."
            )
        raise

    try:
        resp = client.chat.completions.create(
            model=NIM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=max_tokens,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            stream=False,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return (
            "⚠️  NVIDIA NIM is currently unreachable. "
            f"Using offline mode instead. Details: {e}"
        )


# ── Public chain functions ────────────────────────────────────────────────────

def explain_rop(sku: dict) -> str:
    """Generate a plain-language ROP explanation for a given SKU dict."""
    query = (
        f"reorder point policy formula lead time safety stock {sku.get('category','')}"
    )
    try:
        context = retrieve_context(query)
    except Exception as e:
        context = f"(Context unavailable: {e})"

    prompt = ROP_TEMPLATE.format(
        context         = context,
        sku_id          = sku.get("sku_id", ""),
        product_name    = sku.get("product_name", ""),
        category        = sku.get("category", ""),
        current_stock   = sku.get("current_stock", 0),
        policy_rop      = sku.get("policy_reorder_point", 0),
        recommended_rop = sku.get("recommended_rop", 0),
        policy_lead_time= sku.get("policy_lead_time_days", 0),
        actual_lead_time= sku.get("actual_lead_time_days", 0),
        drift_pct       = sku.get("lead_time_drift_pct", 0),
        avg_sales       = sku.get("avg_monthly_sales", 0),
        safety_stock    = sku.get("safety_stock", 0),
        compliance_score= sku.get("compliance_score", 0),
    )
    return call_nim(prompt)


def explain_slob(sku: dict) -> str:
    """Generate a plain-language SLOB action recommendation for a given SKU dict."""
    query = (
        f"slow moving obsolete inventory policy action "
        f"{sku.get('slob_flag','').lower()} {sku.get('category','')}"
    )
    try:
        context = retrieve_context(query)
    except Exception as e:
        context = f"(Context unavailable: {e})"

    prompt = SLOB_TEMPLATE.format(
        context         = context,
        sku_id          = sku.get("sku_id", ""),
        product_name    = sku.get("product_name", ""),
        category        = sku.get("category", ""),
        slob_flag       = sku.get("slob_flag", ""),
        days_no_movement= sku.get("days_since_movement", 0),
        current_stock   = sku.get("current_stock", 0),
        stock_value     = sku.get("stock_value_at_risk", 0),
        avg_sales       = sku.get("avg_monthly_sales", 0),
        anomaly_score   = round(float(sku.get("anomaly_score", 0)), 3),
        system_action   = sku.get("recommended_action", ""),
    )
    return call_nim(prompt)


def answer_policy_question(question: str) -> str:
    """Answer a free-text policy question using RAG."""
    try:
        context = retrieve_context(question)
    except Exception as e:
        context = f"(Context unavailable: {e})"

    prompt = GENERAL_TEMPLATE.format(context=context, question=question)
    return call_nim(prompt, max_tokens=500)

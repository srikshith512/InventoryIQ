"""FastAPI layer for the InventoryIQ React application."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = ROOT_DIR / "db" / "inventoryiq.db"
CHROMA_PATH = ROOT_DIR / "db" / "chroma"
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")

app = FastAPI(title="InventoryIQ API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=800)


class InsightRequest(BaseModel):
    sku_id: str
    mode: Literal["rop", "slob"]


def connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise HTTPException(
            status_code=503,
            detail="Inventory database is missing. Run python setup_db.py first.",
        )
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def rows_as_dicts(cursor: sqlite3.Cursor) -> list[dict]:
    return [dict(row) for row in cursor.fetchall()]


def require_inventory(sku_id: str) -> dict:
    with connect() as conn:
        row = conn.execute("SELECT * FROM inventory WHERE sku_id = ?", (sku_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"SKU {sku_id} was not found.")
    return dict(row)


def offline_policy_reply(question: str) -> str:
    normalized = question.lower()
    if "reorder" in normalized or "rop" in normalized:
        return (
            "The recommended reorder point uses actual lead time: average daily demand x actual lead time + safety stock. "
            "Open a SKU in Inventory Explorer to see the calculation with its current numbers."
        )
    if "obsolete" in normalized or "slow" in normalized or "slob" in normalized:
        return (
            "Items with more than 90 days without movement are classified as obsolete; low monthly sales items are slow movers. "
            "Use the Watchlist filter to prioritise write-down, promotion, or supplier-return actions."
        )
    return (
        "The AI policy service is currently unavailable, but the operational dashboard remains live. "
        "Set NVIDIA_API_KEY and re-run the policy index to enable source-grounded answers."
    )


@app.get("/api/health")
def health() -> dict:
    database_ready = DB_PATH.exists()
    index_ready = CHROMA_PATH.exists() and any(CHROMA_PATH.iterdir()) if CHROMA_PATH.exists() else False
    nvidia_ready = bool(NVIDIA_API_KEY)
    return {
        "database": {"state": "ready" if database_ready else "missing", "label": "Operational data"},
        "rapids": {"state": "ready" if database_ready else "unknown", "label": "RAPIDS anomaly scores"},
        "retrieval": {
            "state": "ready" if index_ready else "missing",
            "label": "NeMo Retriever index",
        },
        "nim": {
            "state": "configured" if nvidia_ready else "offline",
            "label": "NVIDIA NIM policy AI",
        },
    }


@app.get("/api/dashboard")
def dashboard() -> dict:
    with connect() as conn:
        kpis = {row["key"]: row["value"] for row in conn.execute("SELECT key, value FROM kpi_summary")}
        category_rows = rows_as_dicts(
            conn.execute(
                """
                SELECT category, ROUND(AVG(compliance_score), 1) AS compliance,
                       SUM(CASE WHEN slob_flag != 'NORMAL' THEN 1 ELSE 0 END) AS flagged,
                       SUM(stock_value_at_risk) AS value_at_risk
                FROM inventory GROUP BY category ORDER BY value_at_risk DESC
                """
            )
        )
        supplier_rows = rows_as_dicts(
            conn.execute("SELECT * FROM supplier_drift ORDER BY avg_drift_pct DESC LIMIT 8")
        )
        priorities = rows_as_dicts(
            conn.execute(
                """
                SELECT sku_id, product_name, category, current_stock, policy_reorder_point,
                       lead_time_drift_pct, compliance_score, stock_value_at_risk,
                       recommended_action, slob_flag
                FROM inventory
                WHERE slob_flag != 'NORMAL' OR current_stock < policy_reorder_point
                ORDER BY stock_value_at_risk DESC LIMIT 8
                """
            )
        )
    return {"kpis": kpis, "categories": category_rows, "suppliers": supplier_rows, "priorities": priorities}


@app.get("/api/inventory")
def inventory(
    search: str = "",
    category: str = "all",
    status: str = "all",
    limit: int = Query(default=80, ge=1, le=500),
) -> dict:
    where: list[str] = []
    params: list[object] = []
    if search.strip():
        where.append("(sku_id LIKE ? OR product_name LIKE ? OR supplier_id LIKE ?)")
        term = f"%{search.strip()}%"
        params.extend([term, term, term])
    if category != "all":
        where.append("category = ?")
        params.append(category)
    if status == "below_rop":
        where.append("current_stock < policy_reorder_point")
    elif status == "slob":
        where.append("slob_flag != 'NORMAL'")
    elif status == "obsolete":
        where.append("slob_flag = 'OBSOLETE'")
    clause = f" WHERE {' AND '.join(where)}" if where else ""
    sql = (
        "SELECT * FROM inventory" + clause +
        " ORDER BY CASE WHEN slob_flag = 'OBSOLETE' THEN 0 WHEN current_stock < policy_reorder_point THEN 1 ELSE 2 END, "
        "stock_value_at_risk DESC LIMIT ?"
    )
    params.append(limit)
    with connect() as conn:
        items = rows_as_dicts(conn.execute(sql, params))
        categories = [row[0] for row in conn.execute("SELECT DISTINCT category FROM inventory ORDER BY category")]
    return {"items": items, "categories": categories}


@app.get("/api/inventory/{sku_id}")
def inventory_item(sku_id: str) -> dict:
    return require_inventory(sku_id)


@app.get("/api/suppliers")
def suppliers() -> dict:
    with connect() as conn:
        items = rows_as_dicts(conn.execute("SELECT * FROM supplier_drift ORDER BY avg_drift_pct DESC"))
    return {"items": items}


@app.post("/api/insights")
def insight(request: InsightRequest) -> dict:
    sku = require_inventory(request.sku_id)
    try:
        from rag.chain import explain_rop, explain_slob

        reply = explain_rop(sku) if request.mode == "rop" else explain_slob(sku)
    except Exception:
        reply = offline_policy_reply("reorder point" if request.mode == "rop" else "obsolete slow mover")
    return {"answer": reply, "sku": sku}


@app.post("/api/policy/ask")
def ask_policy(request: AskRequest) -> dict:
    try:
        from rag.chain import answer_policy_question

        answer = answer_policy_question(request.question)
    except Exception:
        answer = offline_policy_reply(request.question)
    return {"answer": answer, "question": request.question, "sources": ["inventory_policy.txt"]}

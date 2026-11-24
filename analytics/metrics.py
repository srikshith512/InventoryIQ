"""
analytics/metrics.py
Computes policy compliance scores, lead-time drift, SLOB flags,
and recommended reorder points from inventory data.
"""

import pandas as pd
import numpy as np
from datetime import datetime


# ── Helpers ───────────────────────────────────────────────────────────────────

def _avg_monthly_sales(row) -> float:
    cols = [c for c in row.index if c.startswith('sales_m')]
    vals = [row[c] for c in cols if not pd.isna(row[c])]
    return float(np.mean(vals)) if vals else 0.0


def _days_since_movement(last_movement_date: str) -> int:
    try:
        last = datetime.strptime(str(last_movement_date)[:10], '%Y-%m-%d')
        return (datetime.now() - last).days
    except Exception:
        return 999


# ── Core metric functions ─────────────────────────────────────────────────────

def compute_lead_time_drift(row) -> float:
    """
    Drift % = (actual - policy) / policy * 100
    Positive = supplier is slower than policy assumes.
    """
    policy = row['policy_lead_time_days']
    actual = row['actual_lead_time_days']
    if policy == 0:
        return 0.0
    return round((actual - policy) / policy * 100, 1)


def compute_recommended_rop(row, avg_sales: float) -> int:
    """
    Recommended ROP uses ACTUAL lead time (not policy).
    ROP = (avg_daily_demand × actual_lead_time) + safety_stock
    """
    avg_daily = avg_sales / 30.0
    rop = (avg_daily * row['actual_lead_time_days']) + row['safety_stock']
    return max(int(round(rop)), 0)


def classify_slob(row, days_no_movement: int, avg_sales: float) -> str:
    """
    Obsolete  : no movement > 90 days
    Slow-mover: avg monthly sales < 10 units
    Normal    : everything else
    """
    if days_no_movement > 90:
        return 'OBSOLETE'
    if avg_sales < 10:
        return 'SLOW_MOVER'
    return 'NORMAL'


def compute_compliance_score(drift_pct: float,
                              days_no_movement: int,
                              current_stock: int,
                              policy_rop: int,
                              anomaly_score: float = 0.0) -> float:
    """
    Score 0–100.  Penalties deducted for:
      - Lead-time drift (up to 35 pts)
      - SLOB / no-movement (up to 35 pts)
      - Below reorder point (up to 20 pts)
      - cuML anomaly severity (up to 10 pts)
    """
    # Lead-time drift penalty
    drift_penalty = min(35, abs(drift_pct) * 0.7)

    # SLOB penalty
    if days_no_movement > 180:
        slob_penalty = 35
    elif days_no_movement > 90:
        slob_penalty = 20
    elif days_no_movement > 60:
        slob_penalty = 8
    else:
        slob_penalty = 0

    # Stock below ROP penalty
    stock_penalty = 20 if current_stock < policy_rop else 0

    # cuML anomaly penalty (anomaly_score is negative; more negative = more anomalous)
    anomaly_penalty = min(10, max(0, -anomaly_score * 5))

    score = 100 - drift_penalty - slob_penalty - stock_penalty - anomaly_penalty
    return round(max(0.0, min(100.0, score)), 1)


def compute_stock_value_at_risk(current_stock: int, unit_cost: float) -> float:
    return round(current_stock * unit_cost, 2)


def recommend_action(slob_flag: str,
                     days_no_movement: int,
                     drift_pct: float,
                     compliance_score: float) -> str:
    if slob_flag == 'OBSOLETE':
        if days_no_movement > 180:
            return 'Write-Down / Dispose'
        return 'Review for Write-Down'
    if slob_flag == 'SLOW_MOVER':
        return 'Promote / Return to Supplier'
    if drift_pct > 30:
        return 'Escalate to Supplier — Lead Time SLA Breach'
    if compliance_score < 50:
        return 'Urgent Policy Review'
    if compliance_score < 75:
        return 'Monitor Closely'
    return 'Compliant — No Action'


# ── Main enrichment pipeline ──────────────────────────────────────────────────

def enrich_inventory(df: pd.DataFrame) -> pd.DataFrame:
    """
    Takes raw inventory DataFrame and returns enriched version
    with all computed metrics.
    """
    rows = []
    for _, row in df.iterrows():
        avg_sales       = _avg_monthly_sales(row)
        days_no_mov     = _days_since_movement(row['last_movement_date'])
        drift_pct       = compute_lead_time_drift(row)
        recommended_rop = compute_recommended_rop(row, avg_sales)
        slob_flag       = classify_slob(row, days_no_mov, avg_sales)

        # anomaly_score comes from cuML notebook; default 0 if not available
        anomaly_score = float(row.get('anomaly_score', 0.0) or 0.0)

        compliance = compute_compliance_score(
            drift_pct, days_no_mov,
            int(row['current_stock']),
            int(row['policy_reorder_point']),
            anomaly_score
        )

        stock_risk = compute_stock_value_at_risk(
            int(row['current_stock']), float(row['unit_cost'])
        )

        action = recommend_action(slob_flag, days_no_mov, drift_pct, compliance)

        rows.append({
            **{k: row[k] for k in row.index},
            'avg_monthly_sales':    round(avg_sales, 1),
            'days_since_movement':  days_no_mov,
            'lead_time_drift_pct':  drift_pct,
            'recommended_rop':      recommended_rop,
            'slob_flag':            slob_flag,
            'anomaly_score':        anomaly_score,
            'compliance_score':     compliance,
            'stock_value_at_risk':  stock_risk,
            'recommended_action':   action,
        })

    return pd.DataFrame(rows)

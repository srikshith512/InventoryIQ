"""
setup_db.py
Run after generate_inventory.py (and optionally after Colab notebook).

Steps:
  1. Load data/inventory.csv
  2. Merge anomaly scores from data/anomaly_scores.csv if it exists
     (exported from Google Colab RAPIDS cuML notebook)
  3. Run local sklearn Isolation Forest as fallback if Colab CSV missing
  4. Compute all metrics via analytics/metrics.py
  5. Write to db/inventoryiq.db (SQLite)

Usage:
  python setup_db.py
"""

import pandas as pd
import numpy as np
import sqlite3
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(__file__))
from analytics.metrics import enrich_inventory


DB_PATH        = 'db/inventoryiq.db'
INVENTORY_CSV  = 'data/inventory.csv'
ANOMALY_CSV    = 'data/anomaly_scores.csv'   # exported from Colab


def load_anomaly_scores(df: pd.DataFrame) -> pd.DataFrame:
    """
    Merge cuML anomaly scores if Colab CSV exists.
    Falls back to sklearn Isolation Forest locally.
    """
    if os.path.exists(ANOMALY_CSV):
        print("✅  Found data/anomaly_scores.csv — using RAPIDS cuML scores.")
        scores = pd.read_csv(ANOMALY_CSV)[['sku_id', 'anomaly_score', 'anomaly_label']]
        df = df.merge(scores, on='sku_id', how='left')
        df['anomaly_score']  = df['anomaly_score'].fillna(0.0)
        df['anomaly_label']  = df['anomaly_label'].fillna(1)
    else:
        print("⚠️   data/anomaly_scores.csv not found.")
        print("    Running sklearn Isolation Forest locally as fallback.")
        print("    For NVIDIA RAPIDS scores, run notebooks/gpu_anomaly_colab.ipynb on Colab T4.")
        try:
            from sklearn.ensemble import IsolationForest
            sales_cols = [c for c in df.columns if c.startswith('sales_m')]
            X = df[sales_cols].fillna(0).values
            iso = IsolationForest(contamination=0.15, random_state=42)
            df['anomaly_label'] = iso.fit_predict(X)          # -1 = anomaly
            df['anomaly_score']  = iso.score_samples(X)       # more negative = more anomalous
        except ImportError:
            print("    sklearn not installed — setting anomaly_score = 0")
            df['anomaly_score'] = 0.0
            df['anomaly_label'] = 1

    return df


def create_tables(conn: sqlite3.Connection):
    conn.executescript("""
        DROP TABLE IF EXISTS inventory;
        DROP TABLE IF EXISTS supplier_drift;
        DROP TABLE IF EXISTS kpi_summary;

        CREATE TABLE inventory (
            sku_id                  TEXT PRIMARY KEY,
            product_name            TEXT,
            category                TEXT,
            supplier_id             TEXT,
            unit_cost               REAL,
            current_stock           INTEGER,
            policy_reorder_point    INTEGER,
            recommended_rop         INTEGER,
            safety_stock            INTEGER,
            moq                     INTEGER,
            service_level_target    REAL,
            policy_lead_time_days   INTEGER,
            actual_lead_time_days   INTEGER,
            lead_time_drift_pct     REAL,
            last_movement_date      TEXT,
            days_since_movement     INTEGER,
            avg_monthly_sales       REAL,
            slob_flag               TEXT,
            anomaly_score           REAL,
            anomaly_label           INTEGER,
            compliance_score        REAL,
            stock_value_at_risk     REAL,
            recommended_action      TEXT
        );

        CREATE TABLE supplier_drift (
            supplier_id             TEXT PRIMARY KEY,
            avg_policy_lead_time    REAL,
            avg_actual_lead_time    REAL,
            avg_drift_pct           REAL,
            sku_count               INTEGER,
            breach_count            INTEGER
        );

        CREATE TABLE kpi_summary (
            key     TEXT PRIMARY KEY,
            value   TEXT
        );
    """)


def build_supplier_drift(df: pd.DataFrame) -> pd.DataFrame:
    grp = df.groupby('supplier_id').agg(
        avg_policy_lead_time  = ('policy_lead_time_days', 'mean'),
        avg_actual_lead_time  = ('actual_lead_time_days', 'mean'),
        avg_drift_pct         = ('lead_time_drift_pct',   'mean'),
        sku_count             = ('sku_id', 'count'),
        breach_count          = ('lead_time_drift_pct',
                                  lambda x: (x > 20).sum())
    ).reset_index()
    grp = grp.round(2)
    return grp


def build_kpi(df: pd.DataFrame) -> dict:
    slob = df[df['slob_flag'].isin(['SLOW_MOVER', 'OBSOLETE'])]
    return {
        'total_skus':             str(len(df)),
        'flagged_skus':           str(len(slob)),
        'obsolete_skus':          str(len(df[df['slob_flag'] == 'OBSOLETE'])),
        'slow_mover_skus':        str(len(df[df['slob_flag'] == 'SLOW_MOVER'])),
        'avg_compliance_score':   str(round(df['compliance_score'].mean(), 1)),
        'skus_below_rop':         str(len(df[df['current_stock'] < df['policy_reorder_point']])),
        'total_slob_value_at_risk': str(round(slob['stock_value_at_risk'].sum(), 2)),
        'suppliers_with_drift':   str(len(df[df['lead_time_drift_pct'] > 20]['supplier_id'].unique())),
    }


def main():
    os.makedirs('db', exist_ok=True)

    if not os.path.exists(INVENTORY_CSV):
        print("❌  data/inventory.csv not found. Run: python data/generate_inventory.py")
        sys.exit(1)

    print("📦  Loading inventory data...")
    df = pd.read_csv(INVENTORY_CSV)
    print(f"    Loaded {len(df)} SKUs")

    print("🔍  Merging anomaly scores...")
    df = load_anomaly_scores(df)

    print("📊  Computing metrics...")
    df = enrich_inventory(df)

    print("💾  Writing to SQLite...")
    conn = sqlite3.connect(DB_PATH)
    create_tables(conn)

    inv_cols = [
        'sku_id','product_name','category','supplier_id','unit_cost',
        'current_stock','policy_reorder_point','recommended_rop','safety_stock',
        'moq','service_level_target','policy_lead_time_days','actual_lead_time_days',
        'lead_time_drift_pct','last_movement_date','days_since_movement',
        'avg_monthly_sales','slob_flag','anomaly_score','anomaly_label',
        'compliance_score','stock_value_at_risk','recommended_action'
    ]
    df[inv_cols].to_sql('inventory', conn, if_exists='replace', index=False)

    supplier_df = build_supplier_drift(df)
    supplier_df.to_sql('supplier_drift', conn, if_exists='replace', index=False)

    kpi = build_kpi(df)
    kpi_df = pd.DataFrame(list(kpi.items()), columns=['key', 'value'])
    kpi_df.to_sql('kpi_summary', conn, if_exists='replace', index=False)

    conn.commit()
    conn.close()

    print(f"\n✅  Database ready: {DB_PATH}")
    print(f"   Total SKUs:          {kpi['total_skus']}")
    print(f"   Flagged (SLOB):      {kpi['flagged_skus']}")
    print(f"   Avg compliance:      {kpi['avg_compliance_score']}%")
    print(f"   SLOB value at risk:  ₹{kpi['total_slob_value_at_risk']}")
    print(f"\nNext: python rag/ingest.py")


if __name__ == '__main__':
    main()

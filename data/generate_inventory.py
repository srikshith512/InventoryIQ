"""
generate_inventory.py
Run this first: python data/generate_inventory.py
Generates 500 synthetic SKUs with 12-month sales history.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

np.random.seed(42)
random.seed(42)

N_SKUS = 500
CATEGORIES  = ['Electronics', 'Clothing', 'Food & Beverage', 'Hardware',
                'Office Supplies', 'Pharmaceuticals']
SUPPLIERS   = [f'SUP-{i:03d}' for i in range(1, 21)]

PRODUCT_NAMES = [
    "Wireless Keyboard", "USB-C Hub", "Thermal Paste", "Cable Ties",
    "Hand Sanitizer", "Safety Gloves", "Printer Paper", "Ballpoint Pens",
    "LED Strip Lights", "Ethernet Cable", "Power Strip", "Laptop Stand",
    "Monitor Arm", "Mouse Pad", "Webcam Cover", "Screen Cleaner",
    "Staple Remover", "Binder Clips", "File Folders", "Label Tape",
    "Sticky Notes", "Whiteboard Marker", "Push Pins", "Rubber Bands",
    "Packing Tape", "Bubble Wrap", "Shipping Labels", "Cardboard Box",
    "Foam Padding", "Zip Ties", "AA Batteries", "AAA Batteries",
    "Extension Cord", "Wall Plug Adapter", "Cable Organizer", "Velcro Strips",
    "Anti-Static Bag", "Heat Shrink Tubing", "Electrical Tape", "Wire Nuts",
]

data = []
for i in range(N_SKUS):
    sku_id   = f'SKU-{i+1:04d}'
    category = random.choice(CATEGORIES)
    name_base = random.choice(PRODUCT_NAMES)
    product_name = f"{name_base} {random.choice(['Pro','Plus','Lite','Max','Gen2','V3'])}"

    # ── Policy parameters ─────────────────────────────────────────────────────
    policy_lead_time      = random.randint(7, 30)
    policy_reorder_point  = random.randint(50, 500)
    safety_stock          = int(policy_reorder_point * random.uniform(0.15, 0.30))
    moq                   = random.choice([10, 25, 50, 100])
    service_level_target  = random.choice([0.90, 0.95, 0.99])

    # ── Actual lead time (some suppliers have drifted) ───────────────────────
    drift_class = random.random()
    if drift_class < 0.60:       # 60% — on-time
        drift_factor = np.random.normal(1.0, 0.05)
    elif drift_class < 0.85:     # 25% — moderate drift
        drift_factor = np.random.normal(1.3, 0.10)
    else:                        # 15% — severe drift
        drift_factor = np.random.normal(1.8, 0.20)

    actual_lead_time = max(1, int(policy_lead_time * drift_factor))

    # ── 12-month sales history ────────────────────────────────────────────────
    slob_class = random.random()
    if slob_class < 0.10:        # 10% obsolete — near-zero velocity
        base_velocity = random.uniform(0, 2)
    elif slob_class < 0.20:      # 10% slow-movers
        base_velocity = random.uniform(2, 15)
    else:                        # 80% normal
        base_velocity = random.uniform(20, 300)

    monthly_sales = []
    for m in range(12):
        seasonal = 1 + 0.25 * np.sin(2 * np.pi * (m - 3) / 12)
        noise    = np.random.normal(1.0, 0.15)
        sales    = max(0, int(base_velocity * seasonal * noise))
        monthly_sales.append(sales)

    # ── Last movement date ────────────────────────────────────────────────────
    if sum(monthly_sales[-3:]) == 0 or slob_class < 0.10:
        last_movement = datetime.now() - timedelta(days=random.randint(91, 400))
    elif slob_class < 0.20:
        last_movement = datetime.now() - timedelta(days=random.randint(30, 90))
    else:
        last_movement = datetime.now() - timedelta(days=random.randint(1, 29))

    current_stock = random.randint(0, int(policy_reorder_point * 2.5))
    unit_cost     = round(random.uniform(1.50, 499.99), 2)

    row = {
        'sku_id':                 sku_id,
        'product_name':           product_name[:60],
        'category':               category,
        'supplier_id':            random.choice(SUPPLIERS),
        'unit_cost':              unit_cost,
        'current_stock':          current_stock,
        'policy_reorder_point':   policy_reorder_point,
        'safety_stock':           safety_stock,
        'moq':                    moq,
        'service_level_target':   service_level_target,
        'policy_lead_time_days':  policy_lead_time,
        'actual_lead_time_days':  actual_lead_time,
        'last_movement_date':     last_movement.strftime('%Y-%m-%d'),
    }
    for m in range(12):
        row[f'sales_m{m+1:02d}'] = monthly_sales[m]

    data.append(row)

df = pd.DataFrame(data)
os.makedirs('data', exist_ok=True)
df.to_csv('data/inventory.csv', index=False)
print(f"✅ Generated {len(df)} SKUs → data/inventory.csv")
print(f"   Columns: {list(df.columns)}")

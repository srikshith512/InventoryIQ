"""
Convert the Kaggle e-grocery inventory dataset into InventoryIQ's input schema.

Source expected by default:
  Inventory Management E-Grocery - InventoryData.csv

Output:
  data/inventory.csv

Run from the project root:
  python data/prepare_kaggle_inventory.py
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
import os
import random
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = PROJECT_ROOT / "Inventory Management E-Grocery - InventoryData.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "inventory.csv"
BACKUP_OUTPUT = PROJECT_ROOT / "data" / "inventory_synthetic_backup.csv"

OUTPUT_COLUMNS = [
    "sku_id",
    "product_name",
    "category",
    "supplier_id",
    "unit_cost",
    "current_stock",
    "policy_reorder_point",
    "safety_stock",
    "moq",
    "service_level_target",
    "policy_lead_time_days",
    "actual_lead_time_days",
    "last_movement_date",
    "sales_m01",
    "sales_m02",
    "sales_m03",
    "sales_m04",
    "sales_m05",
    "sales_m06",
    "sales_m07",
    "sales_m08",
    "sales_m09",
    "sales_m10",
    "sales_m11",
    "sales_m12",
]


def parse_decimal(value: str | None, default: float = 0.0) -> float:
    """Parse Indonesian-style decimals/currency like '$2.084,25' and '70,68%'."""
    if value is None:
        return default

    text = str(value).strip()
    if not text:
        return default

    text = (
        text.replace("$", "")
        .replace("%", "")
        .replace("\u00a0", "")
        .replace(" ", "")
    )

    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")

    try:
        return float(text)
    except ValueError:
        return default


def parse_int(value: str | None, default: int = 0) -> int:
    return int(round(parse_decimal(value, float(default))))


def stable_rng(seed_text: str) -> random.Random:
    digest = hashlib.sha256(seed_text.encode("utf-8")).hexdigest()
    return random.Random(int(digest[:16], 16))


def service_level_from_abc(abc_class: str) -> float:
    abc = (abc_class or "").strip().upper()
    if abc == "A":
        return 0.99
    if abc == "B":
        return 0.95
    return 0.90


def infer_moq(row: dict[str, str]) -> int:
    avg_daily = parse_decimal(row.get("Avg_Daily_Sales"))
    order_frequency = parse_decimal(row.get("Order_Frequency_per_month"), 1.0)
    forecast_30d = parse_decimal(row.get("Forecast_Next_30d"))

    if order_frequency > 0:
        moq = max(1, int(round(forecast_30d / order_frequency)))
    else:
        moq = max(1, int(round(avg_daily * 7)))

    # Round into practical order quantities for a cleaner dashboard.
    if moq <= 10:
        return 10
    if moq <= 25:
        return 25
    if moq <= 50:
        return 50
    if moq <= 100:
        return 100
    return int(math.ceil(moq / 50) * 50)


def infer_actual_lead_time(row: dict[str, str]) -> int:
    policy_lead_time = max(1, parse_int(row.get("Lead_Time_Days"), 1))
    on_time_pct = parse_decimal(row.get("Supplier_OnTime_Pct"), 100.0)

    if on_time_pct >= 95:
        multiplier = 1.0
    else:
        multiplier = 1.0 + ((100.0 - on_time_pct) / 100.0)

    return max(1, int(round(policy_lead_time * multiplier)))


def infer_last_movement_date(row: dict[str, str], normalize_dates: bool) -> str:
    if not normalize_dates:
        raw = (row.get("Last_Purchase_Date") or row.get("Audit_Date") or "").strip()
        if raw:
            return raw[:10]

    status = (row.get("Inventory_Status") or "").strip().lower()
    avg_daily = parse_decimal(row.get("Avg_Daily_Sales"))
    rng = stable_rng(row.get("SKU_ID", ""))

    if status == "out of stock":
        days_ago = rng.randint(0, 10)
    elif status == "low stock":
        days_ago = rng.randint(3, 24)
    elif avg_daily < 1:
        days_ago = rng.randint(91, 240)
    elif avg_daily < 5:
        days_ago = rng.randint(31, 90)
    else:
        days_ago = rng.randint(1, 30)

    return (date.today() - timedelta(days=days_ago)).isoformat()


def monthly_sales(row: dict[str, str]) -> list[int]:
    avg_daily = parse_decimal(row.get("Avg_Daily_Sales"))
    forecast_30d = parse_decimal(row.get("Forecast_Next_30d"))
    accuracy = parse_decimal(row.get("Demand_Forecast_Accuracy_Pct"), 85.0) / 100.0
    churn = parse_decimal(row.get("SKU_Churn_Rate"))
    category = row.get("Category", "")
    rng = stable_rng(f"{row.get('SKU_ID', '')}|sales")

    base_monthly = forecast_30d if forecast_30d > 0 else avg_daily * 30
    volatility = max(0.08, min(0.35, (1.0 - accuracy) + (churn / 100.0)))
    category_phase = stable_rng(category).random() * 2 * math.pi

    values = []
    for month in range(12):
        seasonal = 1 + 0.18 * math.sin((2 * math.pi * month / 12) + category_phase)
        noise = rng.uniform(1 - volatility, 1 + volatility)
        values.append(max(0, int(round(base_monthly * seasonal * noise))))

    return values


def convert_row(row: dict[str, str], normalize_dates: bool) -> dict[str, object]:
    converted = {
        "sku_id": row.get("SKU_ID", "").strip(),
        "product_name": row.get("SKU_Name", "").strip()[:60],
        "category": row.get("Category", "").strip(),
        "supplier_id": row.get("Supplier_ID", "").strip(),
        "unit_cost": round(parse_decimal(row.get("Unit_Cost_USD")), 2),
        "current_stock": parse_int(row.get("Quantity_On_Hand")),
        "policy_reorder_point": parse_int(row.get("Reorder_Point")),
        "safety_stock": parse_int(row.get("Safety_Stock")),
        "moq": infer_moq(row),
        "service_level_target": service_level_from_abc(row.get("ABC_Class", "")),
        "policy_lead_time_days": max(1, parse_int(row.get("Lead_Time_Days"), 1)),
        "actual_lead_time_days": infer_actual_lead_time(row),
        "last_movement_date": infer_last_movement_date(row, normalize_dates),
    }

    for index, value in enumerate(monthly_sales(row), start=1):
        converted[f"sales_m{index:02d}"] = value

    return converted


def backup_existing_output(output_path: Path) -> None:
    if not output_path.exists() or BACKUP_OUTPUT.exists():
        return

    with output_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        first_row = next(reader, {})

    if (first_row.get("sku_id") or "").startswith("SKU-"):
        shutil.copy2(output_path, BACKUP_OUTPUT)
        print(f"Backed up existing synthetic inventory to {BACKUP_OUTPUT}")


def convert(source_path: Path, output_path: Path, normalize_dates: bool) -> int:
    if not source_path.exists():
        raise FileNotFoundError(f"Source file not found: {source_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    backup_existing_output(output_path)

    with source_path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        converted_rows = [convert_row(row, normalize_dates) for row in reader]

    if not converted_rows:
        raise ValueError(f"No rows found in {source_path}")

    with output_path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(converted_rows)

    return len(converted_rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert Kaggle e-grocery inventory data for InventoryIQ."
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--preserve-dates",
        action="store_true",
        help=(
            "Use the dataset's original Last_Purchase_Date values. By default, "
            "movement dates are normalized relative to today for a live demo."
        ),
    )
    args = parser.parse_args()

    rows = convert(
        source_path=args.source,
        output_path=args.output,
        normalize_dates=not args.preserve_dates,
    )

    print(f"Converted {rows} Kaggle rows to {args.output}")
    print("Next: remove or regenerate data/anomaly_scores.csv, then run setup_db.py.")


if __name__ == "__main__":
    main()

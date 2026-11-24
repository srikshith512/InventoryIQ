from __future__ import annotations

import sqlite3
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "db" / "inventoryiq.db"
OUT_PATH = ROOT / "docs" / "InventoryIQ_Project_Handout.docx"

INK = RGBColor(15, 23, 42)
MUTED = RGBColor(71, 85, 105)
BLUE = RGBColor(46, 116, 181)
DARK_BLUE = RGBColor(31, 77, 120)
LIME = RGBColor(118, 185, 0)
RISK = RGBColor(155, 28, 28)


def money(value: float | str) -> str:
    return f"INR {float(value):,.0f}"


def get_stats() -> tuple[dict[str, str], list[dict], list[dict]]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        kpis = {row["key"]: row["value"] for row in conn.execute("SELECT key, value FROM kpi_summary")}
        categories = [
            dict(row)
            for row in conn.execute(
                """
                SELECT category,
                       ROUND(AVG(compliance_score), 1) AS compliance,
                       SUM(CASE WHEN slob_flag != 'NORMAL' THEN 1 ELSE 0 END) AS flagged,
                       ROUND(SUM(stock_value_at_risk), 2) AS value_at_risk
                FROM inventory
                GROUP BY category
                ORDER BY value_at_risk DESC
                LIMIT 5
                """
            )
        ]
        suppliers = [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM supplier_drift ORDER BY avg_drift_pct DESC LIMIT 4"
            )
        ]
    return kpis, categories, suppliers


def set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_text(cell, text: str, bold: bool = False, color: RGBColor = INK) -> None:
    cell.text = ""
    p = cell.paragraphs[0]
    p.paragraph_format.space_after = Pt(0)
    run = p.add_run(text)
    run.bold = bold
    run.font.name = "Calibri"
    run.font.size = Pt(9.5)
    run.font.color.rgb = color
    cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER


def style_table(table, header_fill: str = "E8EEF5") -> None:
    table.autofit = False
    for row_index, row in enumerate(table.rows):
        for cell in row.cells:
            tc_pr = cell._tc.get_or_add_tcPr()
            margins = OxmlElement("w:tcMar")
            for side in ("top", "bottom", "start", "end"):
                node = OxmlElement(f"w:{side}")
                node.set(qn("w:w"), "110")
                node.set(qn("w:type"), "dxa")
                margins.append(node)
            tc_pr.append(margins)
            if row_index == 0:
                set_cell_shading(cell, header_fill)
                for paragraph in cell.paragraphs:
                    for run in paragraph.runs:
                        run.bold = True
                        run.font.color.rgb = DARK_BLUE


def add_heading(doc: Document, text: str, level: int = 1):
    p = doc.add_heading(text, level=level)
    p.paragraph_format.keep_with_next = True
    for run in p.runs:
        run.font.name = "Calibri"
        run.font.color.rgb = BLUE if level < 3 else DARK_BLUE
    return p


def add_body(doc: Document, text: str, bold_prefix: str | None = None):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(6)
    if bold_prefix and text.startswith(bold_prefix):
        r1 = p.add_run(bold_prefix)
        r1.bold = True
        r1.font.color.rgb = INK
        r2 = p.add_run(text[len(bold_prefix) :])
        r2.font.color.rgb = INK
    else:
        run = p.add_run(text)
        run.font.color.rgb = INK
    for run in p.runs:
        run.font.name = "Calibri"
        run.font.size = Pt(10.5)
    return p


def add_bullet(doc: Document, text: str):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.left_indent = Inches(0.25)
    p.paragraph_format.first_line_indent = Inches(-0.25)
    run = p.add_run(text)
    run.font.name = "Calibri"
    run.font.size = Pt(10)
    run.font.color.rgb = INK


def build() -> None:
    kpis, categories, suppliers = get_stats()
    doc = Document()
    section = doc.sections[0]
    section.top_margin = Inches(0.65)
    section.bottom_margin = Inches(0.65)
    section.left_margin = Inches(0.72)
    section.right_margin = Inches(0.72)

    styles = doc.styles
    normal = styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(10.5)
    normal.font.color.rgb = INK
    normal.paragraph_format.space_after = Pt(6)
    for name, size, color in (("Heading 1", 16, BLUE), ("Heading 2", 13, BLUE), ("Heading 3", 11, DARK_BLUE)):
        style = styles[name]
        style.font.name = "Calibri"
        style.font.size = Pt(size)
        style.font.color.rgb = color
        style.font.bold = True
        style.paragraph_format.space_before = Pt(8)
        style.paragraph_format.space_after = Pt(4)

    title = doc.add_paragraph()
    title.paragraph_format.space_after = Pt(0)
    run = title.add_run("InventoryIQ")
    run.font.name = "Calibri"
    run.font.size = Pt(28)
    run.font.bold = True
    run.font.color.rgb = INK

    subtitle = doc.add_paragraph()
    subtitle.paragraph_format.space_after = Pt(10)
    sub = subtitle.add_run("NVIDIA-powered inventory policy assistant and operational command center")
    sub.font.name = "Calibri"
    sub.font.size = Pt(12)
    sub.font.color.rgb = MUTED

    intro = doc.add_table(rows=1, cols=2)
    intro.columns[0].width = Inches(4.25)
    intro.columns[1].width = Inches(2.25)
    left, right = intro.rows[0].cells
    set_cell_shading(left, "F8FAFC")
    set_cell_shading(right, "EEF8E6")
    set_cell_text(
        left,
        "InventoryIQ helps supply-chain teams detect reorder risk, slow-moving and obsolete inventory, supplier lead-time drift, and policy exceptions from one React dashboard.",
    )
    set_cell_text(
        right,
        f"Live demo snapshot\n{kpis['total_skus']} SKUs\n{kpis['flagged_skus']} SLOB flagged\n{money(kpis['total_slob_value_at_risk'])} value at risk",
        bold=True,
        color=INK,
    )

    add_heading(doc, "Problem", 1)
    add_body(
        doc,
        "Inventory teams often have SKU data, supplier lead-time records, policy documents, and exception reports in separate places. That makes reorder decisions slow, inconsistent, and hard to explain.",
    )
    add_body(
        doc,
        "InventoryIQ turns those scattered signals into an explainable control room: analysts can see risk, filter SKUs, inspect supplier drift, and ask natural-language questions against the policy source.",
    )

    add_heading(doc, "What the Website Does", 1)
    for item in [
        "Command center: shows total SKUs, compliance, below-ROP count, obsolete stock, value at risk, category risk, and priority queue.",
        "Inventory explorer: searches and filters all 500 SKUs, opens SKU detail panels, and requests AI explanations for reorder or SLOB decisions.",
        "Supplier pulse: ranks supplier lead-time drift against policy thresholds so SLA issues are visible before stockouts happen.",
        "Policy copilot: answers inventory-policy questions using retrieved policy context and NVIDIA NIM generation.",
    ]:
        add_bullet(doc, item)

    add_heading(doc, "NVIDIA Stack", 1)
    stack = doc.add_table(rows=1, cols=3)
    headers = ["NVIDIA service", "Where it is used", "Why it matters"]
    for idx, text in enumerate(headers):
        set_cell_text(stack.rows[0].cells[idx], text, bold=True, color=DARK_BLUE)
    for row in [
        ("RAPIDS cuML", "GPU anomaly scoring for slow-moving and obsolete stock", "Makes anomaly detection the ML layer of the project."),
        ("NeMo Retriever", "Embeds and retrieves policy chunks into ChromaDB", "Grounds answers in the inventory policy instead of generic text."),
        ("NVIDIA NIM", "Generates policy explanations and chat answers", "Turns data and retrieved policy into human-readable decisions."),
    ]:
        cells = stack.add_row().cells
        for idx, text in enumerate(row):
            set_cell_text(cells[idx], text, bold=(idx == 0))
    style_table(stack)

    add_heading(doc, "Current Results", 1)
    metrics = doc.add_table(rows=1, cols=4)
    metric_rows = [
        ("Total SKUs", kpis["total_skus"]),
        ("SLOB flagged", kpis["flagged_skus"]),
        ("Avg compliance", f"{kpis['avg_compliance_score']}%"),
        ("Below ROP", kpis["skus_below_rop"]),
        ("Obsolete SKUs", kpis["obsolete_skus"]),
        ("Slow movers", kpis["slow_mover_skus"]),
        ("Suppliers drifting", kpis["suppliers_with_drift"]),
        ("Value at risk", money(kpis["total_slob_value_at_risk"])),
    ]
    for cell in metrics.rows[0].cells:
        set_cell_shading(cell, "F8FAFC")
    for idx, (label, value) in enumerate(metric_rows):
        row = metrics.rows[idx // 4] if idx < 4 else metrics.add_row()
        cell = row.cells[idx % 4]
        set_cell_text(cell, f"{label}\n{value}", bold=True, color=INK)
    style_table(metrics, "F8FAFC")

    doc.add_section(WD_SECTION.NEW_PAGE)
    add_heading(doc, "Architecture", 1)
    add_body(
        doc,
        "Data starts as synthetic inventory CSVs, is enriched with anomaly scores, then is loaded into SQLite. Policy files are chunked and embedded into ChromaDB. The FastAPI backend exposes secure API endpoints to the React frontend while keeping the NVIDIA API key on the server.",
    )
    flow = doc.add_table(rows=1, cols=4)
    for idx, text in enumerate(["Inventory data", "GPU analytics", "API + database", "React experience"]):
        set_cell_text(flow.rows[0].cells[idx], text, bold=True, color=DARK_BLUE)
    cells = flow.add_row().cells
    for idx, text in enumerate(
        [
            "500 SKU catalogue, supplier fields, movement history",
            "RAPIDS cuML anomaly scores and policy metrics",
            "FastAPI, SQLite, ChromaDB, RAG chain",
            "Command center, explorer, supplier pulse, copilot",
        ]
    ):
        set_cell_text(cells[idx], text)
    style_table(flow)

    add_heading(doc, "Demo Flow", 1)
    for item in [
        "Open the command center and point out the live value-at-risk number.",
        "Go to Inventory Explorer, filter SLOB or below-ROP items, select a SKU, then ask for a reorder-point explanation.",
        "Open Supplier Pulse to show lead-time drift and connect it to the policy threshold.",
        "Ask the Policy Copilot: 'What action applies when supplier lead time drifts?'",
    ]:
        add_bullet(doc, item)

    add_heading(doc, "Key Files", 1)
    files = doc.add_table(rows=1, cols=2)
    set_cell_text(files.rows[0].cells[0], "File", bold=True, color=DARK_BLUE)
    set_cell_text(files.rows[0].cells[1], "Purpose", bold=True, color=DARK_BLUE)
    for file_name, purpose in [
        ("backend/main.py", "FastAPI service and secure AI endpoints"),
        ("frontend/src/main.jsx", "React application views and workflows"),
        ("frontend/src/styles.css", "Polished responsive interface styling"),
        ("rag/ingest.py", "Policy chunking and NeMo Retriever embeddings"),
        ("rag/chain.py", "RAG question-answering and SKU explanations"),
        ("setup_db.py", "Builds SQLite from inventory and anomaly scores"),
    ]:
        cells = files.add_row().cells
        set_cell_text(cells[0], file_name, bold=True)
        set_cell_text(cells[1], purpose)
    style_table(files)

    add_heading(doc, "How to Launch", 1)
    add_body(doc, "From the project root, start the API in one terminal:")
    add_body(
        doc,
        r'& "C:\Users\srikshith rao\AppData\Local\Temp\inventoryiq-venv\Scripts\python.exe" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000',
    )
    add_body(doc, "Then start the React frontend in another terminal:")
    add_body(doc, r'cd "C:\Users\srikshith rao\OneDrive\Projects\inventoryiq\frontend"')
    add_body(doc, "npm.cmd run dev -- --host 127.0.0.1")
    add_body(doc, "Open http://127.0.0.1:5173 in the browser.")

    add_heading(doc, "Why This Is NVIDIA-Worthy", 1)
    for item in [
        "It uses GPU analytics for anomaly detection instead of only static rules.",
        "It uses retrieval over a real policy document so AI answers are grounded.",
        "It separates backend AI calls from frontend UI, which is closer to a production architecture.",
        "It demonstrates business value: compliance visibility, supplier-risk detection, and working capital at risk.",
    ]:
        add_bullet(doc, item)

    section = doc.sections[0]
    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer_run = footer.add_run("InventoryIQ project handout")
    footer_run.font.name = "Calibri"
    footer_run.font.size = Pt(9)
    footer_run.font.color.rgb = MUTED

    doc.core_properties.title = "InventoryIQ Project Handout"
    doc.core_properties.subject = "NVIDIA-powered inventory policy assistant"
    doc.core_properties.comments = "Generated from the local InventoryIQ project."
    OUT_PATH.parent.mkdir(exist_ok=True)
    doc.save(OUT_PATH)
    print(OUT_PATH)


if __name__ == "__main__":
    build()

from __future__ import annotations

import math
import sqlite3
import textwrap
from pathlib import Path

import pandas as pd
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "output" / "rtd_submission"
ASSET_DIR = OUT_DIR / "assets"
DB_PATH = ROOT / "db" / "inventoryiq.db"
POLICY_PATH = ROOT / "policy" / "inventory_policy.txt"

STUDENT_NAME = "Arshanapally NVS Srikshith Rao"
USN = "ENG23CS0528"
DEPARTMENT = "Computer Science and Engineering"
SCHOOL = "School of Engineering"
UNIVERSITY = "Dayananda Sagar University"
ACADEMIC_YEAR = "2026-2027"
PROJECT_TITLE = "InventoryIQ: NVIDIA-Powered Inventory Policy Assistant"
SHORT_TITLE = "InventoryIQ"
PROBLEM_STATEMENT = (
    "PS117 - Supply Chain & Logistics: Design an inventory-policy assistant that "
    "explains reorder-point choices and flags slow-moving or obsolete stock."
)


def ensure_dirs() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ASSET_DIR.mkdir(parents=True, exist_ok=True)


def load_metrics() -> dict:
    conn = sqlite3.connect(DB_PATH)
    kpis = dict(conn.execute("SELECT key, value FROM kpi_summary").fetchall())
    category = pd.read_sql_query(
        """
        SELECT category,
               COUNT(*) AS sku_count,
               ROUND(AVG(compliance_score), 1) AS avg_compliance,
               SUM(CASE WHEN slob_flag != 'NORMAL' THEN 1 ELSE 0 END) AS flagged,
               ROUND(SUM(stock_value_at_risk), 2) AS value_at_risk
        FROM inventory
        GROUP BY category
        ORDER BY value_at_risk DESC
        """,
        conn,
    )
    suppliers = pd.read_sql_query(
        "SELECT * FROM supplier_drift ORDER BY avg_drift_pct DESC LIMIT 8", conn
    )
    priority = pd.read_sql_query(
        """
        SELECT sku_id, product_name, category, current_stock, policy_reorder_point,
               lead_time_drift_pct, compliance_score, stock_value_at_risk,
               recommended_action, slob_flag
        FROM inventory
        WHERE slob_flag != 'NORMAL' OR current_stock < policy_reorder_point
        ORDER BY stock_value_at_risk DESC
        LIMIT 4
        """,
        conn,
    )
    conn.close()
    return {
        "kpis": kpis,
        "category": category,
        "suppliers": suppliers,
        "priority": priority,
    }


def set_cell_text(cell, text: str, bold: bool = False, size: int = 10) -> None:
    cell.text = ""
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(str(text))
    run.bold = bold
    run.font.name = "Times New Roman"
    run.font.size = Pt(size)
    cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER


def set_table_borders(table, color: str = "D9D9D9", size: str = "8") -> None:
    tbl = table._tbl
    tbl_pr = tbl.tblPr
    borders = tbl_pr.first_child_found_in("w:tblBorders")
    if borders is None:
        borders = OxmlElement("w:tblBorders")
        tbl_pr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        tag = f"w:{edge}"
        element = borders.find(qn(tag))
        if element is None:
            element = OxmlElement(tag)
            borders.append(element)
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), size)
        element.set(qn("w:space"), "0")
        element.set(qn("w:color"), color)


def shade_cell(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shading = tc_pr.find(qn("w:shd"))
    if shading is None:
        shading = OxmlElement("w:shd")
        tc_pr.append(shading)
    shading.set(qn("w:fill"), fill)


def style_document(doc: Document, report: bool = False) -> None:
    for section in doc.sections:
        section.top_margin = Cm(2.54)
        section.bottom_margin = Cm(2.54)
        section.left_margin = Cm(3.81 if report else 2.54)
        section.right_margin = Cm(2.54)

    styles = doc.styles
    normal = styles["Normal"]
    normal.font.name = "Times New Roman"
    normal._element.rPr.rFonts.set(qn("w:ascii"), "Times New Roman")
    normal._element.rPr.rFonts.set(qn("w:hAnsi"), "Times New Roman")
    normal.font.size = Pt(12 if report else 10.5)

    for style_name, size in [
        ("Title", 18),
        ("Heading 1", 18 if report else 14),
        ("Heading 2", 16 if report else 12),
        ("Heading 3", 14 if report else 11),
    ]:
        style = styles[style_name]
        style.font.name = "Times New Roman"
        style._element.rPr.rFonts.set(qn("w:ascii"), "Times New Roman")
        style._element.rPr.rFonts.set(qn("w:hAnsi"), "Times New Roman")
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor(0, 0, 0)


def add_paragraph(
    doc: Document,
    text: str = "",
    *,
    bold: bool = False,
    italic: bool = False,
    align=None,
    size: float | None = None,
    spacing_after: int = 6,
    first_line: bool = False,
) -> None:
    p = doc.add_paragraph()
    p.alignment = align if align is not None else WD_ALIGN_PARAGRAPH.JUSTIFY
    pf = p.paragraph_format
    pf.space_after = Pt(spacing_after)
    pf.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
    if first_line:
        pf.first_line_indent = Cm(1.27)
    run = p.add_run(text)
    run.bold = bold
    run.italic = italic
    run.font.name = "Times New Roman"
    run._element.rPr.rFonts.set(qn("w:ascii"), "Times New Roman")
    run._element.rPr.rFonts.set(qn("w:hAnsi"), "Times New Roman")
    if size:
        run.font.size = Pt(size)


def add_heading(doc: Document, text: str, level: int = 1, report: bool = False) -> None:
    if report and level == 1:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        run = p.add_run(text.upper())
        run.bold = True
        run.font.name = "Times New Roman"
        run.font.size = Pt(18)
        return
    doc.add_heading(text, level=level)


def add_bullets(doc: Document, items: list[str]) -> None:
    for item in items:
        p = doc.add_paragraph(style="List Bullet")
        p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
        p.paragraph_format.space_after = Pt(4)
        run = p.add_run(item)
        run.font.name = "Times New Roman"


def add_numbered(doc: Document, items: list[str]) -> None:
    for item in items:
        p = doc.add_paragraph(style="List Number")
        p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
        p.paragraph_format.space_after = Pt(4)
        run = p.add_run(item)
        run.font.name = "Times New Roman"


def add_dataframe_table(doc: Document, df: pd.DataFrame, headers: list[str] | None = None) -> None:
    if headers is None:
        headers = list(df.columns)
    table = doc.add_table(rows=1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(table)
    hdr = table.rows[0].cells
    for i, header in enumerate(headers):
        set_cell_text(hdr[i], header, bold=True, size=9)
        shade_cell(hdr[i], "D9EAF7")
    for _, row in df.iterrows():
        cells = table.add_row().cells
        for i, col in enumerate(df.columns):
            value = row[col]
            if isinstance(value, float):
                if math.isfinite(value):
                    value = f"{value:,.1f}" if abs(value) < 10000 else f"{value:,.2f}"
            set_cell_text(cells[i], value, size=8)


def draw_box(draw, xy, text, fill, outline="#1F2933", text_fill="#111111") -> None:
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle(xy, radius=16, fill=fill, outline=outline, width=3)
    try:
        font = ImageFont.truetype("arial.ttf", 24)
    except Exception:
        font = ImageFont.load_default()
    wrapped = textwrap.wrap(text, 20)
    total_h = len(wrapped) * 30
    y = y1 + ((y2 - y1) - total_h) / 2
    for line in wrapped:
        bbox = draw.textbbox((0, 0), line, font=font)
        draw.text((x1 + (x2 - x1 - (bbox[2] - bbox[0])) / 2, y), line, font=font, fill=text_fill)
        y += 30


def arrow(draw, start, end) -> None:
    draw.line([start, end], fill="#1F2933", width=4)
    x1, y1 = start
    x2, y2 = end
    angle = math.atan2(y2 - y1, x2 - x1)
    length = 16
    for delta in (math.pi * 0.82, -math.pi * 0.82):
        x3 = x2 + length * math.cos(angle + delta)
        y3 = y2 + length * math.sin(angle + delta)
        draw.line([(x2, y2), (x3, y3)], fill="#1F2933", width=4)


def create_diagrams() -> dict[str, Path]:
    diagrams = {}
    try:
        title_font = ImageFont.truetype("arial.ttf", 32)
    except Exception:
        title_font = ImageFont.load_default()

    img = Image.new("RGB", (1500, 850), "#FFFFFF")
    d = ImageDraw.Draw(img)
    d.text((55, 35), "InventoryIQ System Architecture", fill="#111111", font=title_font)
    boxes = [
        ((70, 150, 330, 260), "E-Grocery SKU Data and Policy Document", "#E8F4FA"),
        ((430, 150, 690, 260), "Analytics Layer: ROP, SLOB, Drift, Compliance", "#EAF7EA"),
        ((790, 150, 1050, 260), "SQLite + ChromaDB Knowledge Stores", "#FFF4D6"),
        ((1150, 150, 1410, 260), "FastAPI Service Layer", "#F4EAF8"),
        ((610, 430, 890, 550), "NVIDIA Stack: RAPIDS cuML, Nemotron Embeddings, NIM", "#EDEDED"),
        ((1030, 430, 1320, 550), "React Dashboard and Policy Copilot", "#FDEBDD"),
    ]
    for xy, text, fill in boxes:
        draw_box(d, xy, text, fill)
    for start, end in [
        ((330, 205), (430, 205)),
        ((690, 205), (790, 205)),
        ((1050, 205), (1150, 205)),
        ((560, 260), (700, 430)),
        ((920, 260), (750, 430)),
        ((1280, 260), (1180, 430)),
        ((890, 490), (1030, 490)),
    ]:
        arrow(d, start, end)
    path = ASSET_DIR / "inventoryiq_architecture.png"
    img.save(path)
    diagrams["architecture"] = path

    img = Image.new("RGB", (1500, 850), "#FFFFFF")
    d = ImageDraw.Draw(img)
    d.text((55, 35), "InventoryIQ RAG and Decision Workflow", fill="#111111", font=title_font)
    boxes = [
        ((80, 160, 330, 265), "Planner selects SKU or asks question", "#E8F4FA"),
        ((430, 160, 680, 265), "Retrieve SKU metrics and policy chunks", "#FFF4D6"),
        ((780, 160, 1030, 265), "Bind context: stock, ROP, drift, SLOB rule", "#EAF7EA"),
        ((1130, 160, 1380, 265), "Generate grounded explanation", "#F4EAF8"),
        ((430, 430, 680, 535), "Fallback response if AI service is offline", "#EDEDED"),
        ((780, 430, 1030, 535), "Recommended action and audit trail", "#FDEBDD"),
    ]
    for xy, text, fill in boxes:
        draw_box(d, xy, text, fill)
    for start, end in [
        ((330, 212), (430, 212)),
        ((680, 212), (780, 212)),
        ((1030, 212), (1130, 212)),
        ((555, 265), (555, 430)),
        ((680, 485), (780, 485)),
        ((1255, 265), (905, 430)),
    ]:
        arrow(d, start, end)
    path = ASSET_DIR / "inventoryiq_rag_workflow.png"
    img.save(path)
    diagrams["rag"] = path

    img = Image.new("RGB", (1500, 850), "#FFFFFF")
    d = ImageDraw.Draw(img)
    d.text((55, 35), "InventoryIQ Component View for Patent Diagrams", fill="#111111", font=title_font)
    boxes = [
        ((80, 145, 360, 250), "A. Inventory Data Intake Module", "#E8F4FA"),
        ((430, 145, 710, 250), "B. Policy Retrieval Module", "#FFF4D6"),
        ((780, 145, 1060, 250), "C. Inventory Analytics Engine", "#EAF7EA"),
        ((1130, 145, 1410, 250), "D. Explanation Generation Module", "#F4EAF8"),
        ((250, 430, 530, 535), "E. Compliance Scoring Store", "#FDEBDD"),
        ((610, 430, 890, 535), "F. Supplier Drift Monitor", "#EDEDED"),
        ((970, 430, 1250, 535), "G. Dashboard and API Interface", "#E8F4FA"),
    ]
    for xy, text, fill in boxes:
        draw_box(d, xy, text, fill)
    for start, end in [
        ((360, 198), (430, 198)),
        ((710, 198), (780, 198)),
        ((1060, 198), (1130, 198)),
        ((920, 250), (390, 430)),
        ((920, 250), (750, 430)),
        ((1270, 250), (1110, 430)),
    ]:
        arrow(d, start, end)
    path = ASSET_DIR / "inventoryiq_patent_components.png"
    img.save(path)
    diagrams["patent"] = path
    return diagrams


def add_caption(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(text)
    run.italic = True
    run.font.name = "Times New Roman"
    run.font.size = Pt(10)


def add_picture(doc: Document, path: Path, width: float = 6.0) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    run.add_picture(str(path), width=Inches(width))


def add_cover(doc: Document) -> None:
    for text, size, bold in [
        ("Bachelor of Technology", 16, True),
        ("in", 14, False),
        ("COMPUTER SCIENCE AND ENGINEERING", 16, True),
        ("Final Project Report", 16, True),
        (PROJECT_TITLE, 18, True),
        ("Solo Project", 13, False),
        ("By", 13, False),
        (f"{STUDENT_NAME} - {USN}", 14, True),
        ("Under the supervision of", 13, False),
        ("Dr./Mr./Ms. ______________________________", 13, False),
        ("Designation and Department of Guide", 12, False),
        ("DEPARTMENT OF COMPUTER SCIENCE & ENGINEERING", 13, True),
        ("SCHOOL OF ENGINEERING", 13, True),
        ("DAYANANDA SAGAR UNIVERSITY", 13, True),
        (f"({ACADEMIC_YEAR})", 12, False),
    ]:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(8)
        run = p.add_run(text)
        run.bold = bold
        run.font.name = "Times New Roman"
        run.font.size = Pt(size)
    doc.add_page_break()


def add_certificate(doc: Document) -> None:
    for text in [
        SCHOOL,
        "Department of Computer Science & Engineering",
        "Devarakaggalahalli, Harohalli, Kanakapura Road, Ramanagara - 562112",
        "Karnataka, India",
    ]:
        add_paragraph(doc, text, align=WD_ALIGN_PARAGRAPH.CENTER, spacing_after=2)
    add_heading(doc, "CERTIFICATE", 1, report=True)
    add_paragraph(
        doc,
        f"This is to certify that the final project work titled \"{PROJECT_TITLE}\" is carried out by "
        f"{STUDENT_NAME} ({USN}), a bonafide student of Bachelor of Technology in Computer Science and "
        f"Engineering at the School of Engineering, Dayananda Sagar University, in partial fulfillment "
        f"for the award of the degree in Bachelor of Technology in Computer Science and Engineering "
        f"during the academic year {ACADEMIC_YEAR}.",
        first_line=True,
    )
    add_paragraph(doc, "Name of the Examiner                                      Signature of Examiner")
    add_paragraph(doc, "1.")
    add_paragraph(doc, "2.")
    table = doc.add_table(rows=1, cols=3)
    set_table_borders(table)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    entries = [
        "Prof./Dr. __________________\nGuide\nDept. of CS&E\nSchool of Engineering\nDayananda Sagar University\nDate:",
        "Dr. Girisha G S\nChairman CSE\nSchool of Engineering\nDayananda Sagar University\nDate:",
        "Dr. Udaya Kumar Reddy K R\nDean\nSchool of Engineering\nDayananda Sagar University\nDate:",
    ]
    for cell, text in zip(table.rows[0].cells, entries):
        set_cell_text(cell, text, size=10)
    doc.add_page_break()


def add_declaration_ack(doc: Document) -> None:
    add_heading(doc, "DECLARATION", 1, report=True)
    add_paragraph(
        doc,
        f"I, {STUDENT_NAME} ({USN}), student of B.Tech in Computer Science and Engineering at "
        f"the School of Engineering, Dayananda Sagar University, hereby declare that the final project "
        f"titled \"{PROJECT_TITLE}\" has been carried out by me and submitted in partial fulfillment "
        f"for the award of the degree in Bachelor of Technology in Computer Science and Engineering "
        f"during the academic year {ACADEMIC_YEAR}.",
        first_line=True,
    )
    table = doc.add_table(rows=3, cols=2)
    set_table_borders(table)
    set_cell_text(table.cell(0, 0), "Student", bold=True)
    set_cell_text(table.cell(0, 1), "Signature", bold=True)
    set_cell_text(table.cell(1, 0), f"{STUDENT_NAME}\nUSN: {USN}")
    set_cell_text(table.cell(1, 1), "")
    set_cell_text(table.cell(2, 0), "Place: Bangalore\nDate:")
    set_cell_text(table.cell(2, 1), "")
    doc.add_page_break()

    add_heading(doc, "ACKNOWLEDGEMENT", 1, report=True)
    paragraphs = [
        "It is a great pleasure for me to acknowledge the assistance and support of the individuals and institution that helped in the successful completion of this project work.",
        "I express my sincere gratitude to the School of Engineering, Dayananda Sagar University, for providing the academic environment, infrastructure, and encouragement needed to pursue this work.",
        "I thank Dr. Udaya Kumar Reddy K R, Dean, School of Engineering, Dayananda Sagar University, and Dr. Girisha G S, Chairman, Department of Computer Science and Engineering, for their academic guidance and support.",
        "I thank my project guide for providing feedback, direction, and support throughout the development of InventoryIQ. I am also thankful to the project coordinators and faculty members of the Department of Computer Science and Engineering.",
        "I am grateful to my family and friends for their encouragement and support during the project work.",
    ]
    for para in paragraphs:
        add_paragraph(doc, para, first_line=True)
    doc.add_page_break()


def build_report(metrics: dict, diagrams: dict[str, Path]) -> Path:
    doc = Document()
    style_document(doc, report=True)
    add_cover(doc)
    add_certificate(doc)
    add_declaration_ack(doc)

    add_heading(doc, "ABSTRACT", 1, report=True)
    add_paragraph(
        doc,
        f"InventoryIQ is an inventory-policy assistant designed for supply-chain planners who need to understand reorder-point decisions, slow-moving stock risk, supplier lead-time drift, expiry-sensitive grocery handling, and policy compliance from a single system. The project addresses PS117 under Supply Chain and Logistics by combining inventory analytics with retrieval-augmented generation. The implemented prototype now uses a 1000-row e-grocery inventory dataset with categories such as Pantry, Beverages, Dairy, Fresh Produce, Frozen, Household, Meat, Personal Care, Bakery, and Seafood. SQLite stores operational data, ChromaDB stores indexed policy chunks, NVIDIA RAPIDS cuML or local Isolation Forest supports anomaly scoring, NVIDIA Nemotron embeddings support policy indexing when available, and NVIDIA NIM supports policy-grounded explanations with fallback responses. A FastAPI backend exposes inventory, supplier, dashboard, and policy-question endpoints, while a React frontend provides a command center, inventory explorer, supplier pulse view, and policy copilot. The current system identifies {metrics['kpis'].get('flagged_skus', '')} SLOB-flagged SKUs, {metrics['kpis'].get('slow_mover_skus', '')} slow movers, {metrics['kpis'].get('skus_below_rop', '')} SKUs below reorder point, and an approximate SLOB value at risk of INR {float(metrics['kpis'].get('total_slob_value_at_risk', 0)):,.2f}. The project demonstrates how SKU metrics and policy documents can be connected to produce explainable, auditable inventory decisions.",
        first_line=True,
    )
    doc.add_page_break()

    add_heading(doc, "TABLE OF CONTENTS", 1, report=True)
    toc = [
        "Chapter 1 Introduction",
        "Chapter 2 Problem Definition",
        "Chapter 3 Literature Review",
        "Chapter 4 Requirements",
        "Chapter 5 Design and Methodology",
        "Chapter 6 Results and Discussion",
        "Chapter 7 Summary and Conclusions",
        "References",
        "Appendix A Key Screens and Demo Checklist",
    ]
    add_numbered(doc, toc)
    doc.add_page_break()

    add_heading(doc, "CHAPTER 1   INTRODUCTION", 1, report=True)
    add_heading(doc, "Introduction", 2, report=True)
    add_paragraph(
        doc,
        "Inventory planning depends on timely reorder decisions, accurate supplier lead-time assumptions, and early detection of slow-moving and obsolete stock. In many organizations, the policy rules that govern reorder points and SLOB treatment are stored separately from operational SKU data. A planner may know that a product is below reorder point or has not moved recently, but may not immediately know which policy clause applies, how the reorder value was derived, or what action should follow. InventoryIQ was developed to close this gap by connecting SKU analytics with policy-grounded natural-language explanations.",
        first_line=True,
    )
    add_paragraph(
        doc,
        "The project implements an end-to-end assistant for the supply-chain problem statement PS117. It does not only visualize inventory data; it computes reorder risk, supplier drift, SLOB status, and compliance score, then explains these values using an indexed policy document. The system is intentionally designed so that the operational dashboard remains useful even when AI services are unavailable.",
        first_line=True,
    )
    add_heading(doc, "Aim and Objectives", 2, report=True)
    add_bullets(
        doc,
        [
            "Build an inventory command center that summarizes SKU health, compliance, reorder risk, and value at risk.",
            "Detect slow-moving and obsolete stock using velocity rules and GPU-based anomaly scoring.",
            "Ingest inventory policy documents and retrieve relevant clauses for planner questions.",
            "Generate reorder, SLOB, supplier drift, and policy explanations in plain language.",
            "Provide a React and FastAPI web application that supports search, filtering, SKU inspection, and policy Q&A.",
            "Support fallback explanations so the system remains operational if the AI service is not configured.",
        ],
    )
    add_heading(doc, "Scope", 2, report=True)
    add_paragraph(
        doc,
        "The current scope covers a working local prototype using a real e-grocery inventory dataset converted into the InventoryIQ schema. The system demonstrates the complete workflow from data preparation to analytics, retrieval, explanation, and dashboard presentation. The project has social and environmental relevance because better SLOB and expiry-risk identification can reduce avoidable procurement, food waste, storage overhead, and financial write-downs.",
        first_line=True,
    )

    add_heading(doc, "CHAPTER 2   PROBLEM DEFINITION", 1, report=True)
    add_paragraph(doc, PROBLEM_STATEMENT, bold=True)
    add_paragraph(
        doc,
        "The problem is that inventory policies are often documented as static rules, while inventory exceptions appear inside operational systems as raw metrics. This separation makes decision-making slow and difficult to audit. A planner must manually compare stock levels, policy reorder points, sales velocity, supplier lead-time performance, and SLOB rules before deciding whether to order, freeze replenishment, promote, return, write down, or escalate an item.",
        first_line=True,
    )
    add_heading(doc, "Proposed Solution", 2, report=True)
    add_paragraph(
        doc,
        "InventoryIQ proposes a policy-aware assistant that links SKU records with policy clauses and analytics. The solution computes recommended reorder points using actual lead time, classifies slow-moving and obsolete inventory, scores policy compliance, and retrieves relevant policy context before generating a planner-facing explanation. The output is presented through a dashboard rather than a standalone chatbot, ensuring the explanation is tied to measurable SKU evidence.",
        first_line=True,
    )

    add_heading(doc, "CHAPTER 3   LITERATURE REVIEW", 1, report=True)
    sections = [
        (
            "Inventory Control and Reorder-Point Systems",
            "Traditional reorder-point models use average demand, lead time, and safety stock to determine when replenishment should occur. These methods remain valuable because they are interpretable and directly connected to service-level planning. However, they often rely on static assumptions and are less effective when supplier lead time drifts or demand patterns change.",
        ),
        (
            "Slow-Moving and Obsolete Inventory Analysis",
            "SLOB analysis focuses on identifying items with low sales velocity or no movement over a defined period. It supports working-capital protection, warehouse optimization, and timely write-down decisions. Automated SLOB classification improves consistency, but planners still need explanations that connect flags to business policy.",
        ),
        (
            "Anomaly Detection in Inventory Data",
            "Anomaly detection methods such as Isolation Forest can help identify unusual stock and sales patterns. GPU-accelerated approaches such as RAPIDS cuML are useful when inventory datasets become large because they reduce processing time and support scalable analytics.",
        ),
        (
            "Retrieval-Augmented Generation",
            "RAG systems retrieve relevant source passages before generating an answer. For policy-heavy domains, this is preferable to generic LLM answering because the response can be grounded in the organization's own rules. InventoryIQ applies this idea to reorder-point and SLOB explanations.",
        ),
    ]
    for heading, para in sections:
        add_heading(doc, heading, 2, report=True)
        add_paragraph(doc, para, first_line=True)
    add_heading(doc, "Identified Gap", 2, report=True)
    add_paragraph(
        doc,
        "Existing systems commonly provide either inventory dashboards or AI chat. The gap addressed by InventoryIQ is the combination of SKU analytics, anomaly detection, supplier drift monitoring, policy retrieval, and natural-language explanation in one workflow.",
        first_line=True,
    )

    add_heading(doc, "CHAPTER 4   REQUIREMENTS", 1, report=True)
    add_heading(doc, "Functional Requirements", 2, report=True)
    add_bullets(
        doc,
        [
            "Load SKU-level inventory data and anomaly scores.",
            "Compute average monthly sales, days since movement, lead-time drift, recommended reorder point, SLOB flag, compliance score, and value at risk.",
            "Display dashboard KPIs, category summaries, priority exceptions, and supplier drift.",
            "Allow search, category filtering, and status filtering of inventory records.",
            "Answer policy questions using indexed inventory policy context.",
            "Generate SKU-specific reorder-point and SLOB explanations.",
        ],
    )
    add_heading(doc, "Non-Functional Requirements", 2, report=True)
    add_bullets(
        doc,
        [
            "Maintain API-key security by keeping NVIDIA service access on the backend.",
            "Provide fallback explanations if AI services are unavailable.",
            "Use a modular architecture with separable data, analytics, retrieval, backend, and frontend layers.",
            "Support future connection to real inventory data without rewriting the whole system.",
        ],
    )
    add_heading(doc, "Technology Stack", 2, report=True)
    stack = pd.DataFrame(
        [
            ["Frontend", "React, Vite", "Dashboard, inventory explorer, supplier pulse, policy copilot"],
            ["Backend", "FastAPI", "API endpoints and secure AI service access"],
            ["Database", "SQLite", "Operational SKU data and KPI summaries"],
            ["Vector Store", "ChromaDB", "Policy document retrieval"],
            ["AI and Analytics", "RAPIDS cuML, Nemotron embeddings, NVIDIA NIM", "Anomaly scoring, retrieval, and explanation generation"],
            ["Language", "Python, JavaScript", "Backend analytics and frontend implementation"],
        ],
        columns=["Layer", "Technology", "Role"],
    )
    add_dataframe_table(doc, stack)

    add_heading(doc, "CHAPTER 5   DESIGN AND METHODOLOGY", 1, report=True)
    add_heading(doc, "System Architecture", 2, report=True)
    add_picture(doc, diagrams["architecture"], 6.0)
    add_caption(doc, "Figure 5.1 InventoryIQ system architecture")
    add_paragraph(
        doc,
        "The architecture separates data preparation, analytics, retrieval, API services, and user interface. E-grocery SKU data and policy text are first prepared. The analytics layer computes reorder, SLOB, supplier-drift, and grocery expiry signals. Operational data is stored in SQLite, while policy chunks are indexed in ChromaDB. The FastAPI backend connects the data and AI layers to the React frontend.",
        first_line=True,
    )
    add_heading(doc, "RAG and Decision Workflow", 2, report=True)
    add_picture(doc, diagrams["rag"], 6.0)
    add_caption(doc, "Figure 5.2 Policy-grounded explanation workflow")
    add_paragraph(
        doc,
        "When a planner asks a question or requests an explanation, the system retrieves the selected SKU's metrics and relevant policy context. The answer is generated using the combined context so that the response refers to reorder logic, lead-time drift, SLOB status, or compliance thresholds rather than producing a generic answer.",
        first_line=True,
    )
    add_heading(doc, "Core Calculations", 2, report=True)
    add_bullets(
        doc,
        [
            "Lead-time drift percentage = (actual lead time - policy lead time) / policy lead time x 100.",
            "Recommended ROP = average daily demand x actual lead time + safety stock.",
            "Slow-moving stock = average monthly sales below 10 units over the rolling period.",
            "Obsolete stock = no movement for more than 90 days.",
            "Compliance score deducts penalties for lead-time drift, no-movement risk, below-ROP stock, and anomaly severity.",
        ],
    )

    add_heading(doc, "CHAPTER 6   RESULTS AND DISCUSSION", 1, report=True)
    add_heading(doc, "KPI Summary", 2, report=True)
    k = metrics["kpis"]
    kpi_df = pd.DataFrame(
        [
            ["Total SKUs", k.get("total_skus", "")],
            ["Flagged SLOB SKUs", k.get("flagged_skus", "")],
            ["Obsolete SKUs", k.get("obsolete_skus", "")],
            ["Slow-mover SKUs", k.get("slow_mover_skus", "")],
            ["SKUs below reorder point", k.get("skus_below_rop", "")],
            ["Average compliance score", k.get("avg_compliance_score", "")],
            ["SLOB value at risk", f"INR {float(k.get('total_slob_value_at_risk', 0)):,.2f}"],
        ],
        columns=["Metric", "Value"],
    )
    add_dataframe_table(doc, kpi_df)
    add_heading(doc, "Category-Level Summary", 2, report=True)
    add_dataframe_table(doc, metrics["category"])
    add_heading(doc, "Priority Exceptions", 2, report=True)
    add_dataframe_table(doc, metrics["priority"])
    add_heading(doc, "Discussion", 2, report=True)
    add_paragraph(
        doc,
        f"The results show that the prototype identifies a meaningful set of operational exceptions from the e-grocery dataset. The {k.get('flagged_skus', '')} SLOB-flagged SKUs and {k.get('skus_below_rop', '')} below-ROP SKUs demonstrate that the dashboard can separate different forms of inventory risk. The average compliance score of {k.get('avg_compliance_score', '')} suggests that many SKUs are usable but still require monitoring. The INR {float(k.get('total_slob_value_at_risk', 0)):,.2f} SLOB value at risk highlights the financial relevance of early SLOB detection.",
        first_line=True,
    )
    add_heading(doc, "Test Cases", 2, report=True)
    tests = pd.DataFrame(
        [
            ["Dashboard loads KPIs", "Open command center", "KPI cards visible", "Pass"],
            ["Filter below reorder point", "Select below-ROP filter", "Exception SKUs shown", "Pass"],
            ["Explain SKU reorder point", "Request ROP explanation", "Policy-grounded response or fallback shown", "Pass"],
            ["Ask obsolete policy question", "Ask when SKU is obsolete", "Policy answer mentions no movement rule", "Pass"],
            ["Supplier drift view", "Open Supplier Pulse", "Suppliers sorted by drift", "Pass"],
        ],
        columns=["Test Case", "Input/Action", "Expected Result", "Status"],
    )
    add_dataframe_table(doc, tests)

    doc.add_page_break()
    add_heading(doc, "CHAPTER 7   SUMMARY AND CONCLUSIONS", 1, report=True)
    add_paragraph(
        doc,
        "InventoryIQ successfully demonstrates a working inventory-policy assistant for PS117. The project combines analytics and LLM RAG so that inventory exceptions are not only detected but also explained through policy context. The solution supports reorder-point review, SLOB identification, supplier drift visibility, compliance monitoring, and natural-language policy Q&A.",
        first_line=True,
    )
    add_heading(doc, "Limitations", 2, report=True)
    add_bullets(
        doc,
        [
            "The current dataset is a prepared e-grocery dataset rather than live ERP data; production validation still requires enterprise transaction history, supplier contracts, and planner feedback.",
            "AI explanations require configured NVIDIA services for full source-grounded generation.",
            "Authentication, role-based access, and production deployment are future enhancements.",
        ],
    )
    add_heading(doc, "Future Enhancements", 2, report=True)
    add_bullets(
        doc,
        [
            "Connect to enterprise ERP or warehouse-management systems.",
            "Add approval workflows for replenishment freeze, supplier escalation, and write-down actions.",
            "Expand policy ingestion to include supplier contracts and category-specific documents.",
            "Introduce user authentication and audit logging for production use.",
        ],
    )

    add_heading(doc, "REFERENCES", 1, report=True)
    refs = [
        "Christopher, M. Logistics and Supply Chain Management. Pearson Education.",
        "Silver, E. A., Pyke, D. F., and Peterson, R. Inventory Management and Production Planning and Scheduling. Wiley.",
        "Lewis, C. D. Demand Forecasting and Inventory Control. Woodhead Publishing.",
        "Liu, F. T., Ting, K. M., and Zhou, Z. H. Isolation Forest. IEEE International Conference on Data Mining.",
        "Lewis, P. et al. Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. NeurIPS.",
        "NVIDIA. RAPIDS cuML Documentation.",
        "NVIDIA. Nemotron Embeddings and NVIDIA NIM Documentation.",
        "LangChain Documentation. Retrieval-Augmented Generation Workflows.",
    ]
    add_numbered(doc, refs)
    doc.add_page_break()
    add_heading(doc, "APPENDIX A   DEMO CHECKLIST", 1, report=True)
    add_bullets(
        doc,
        [
            "Start FastAPI backend on http://127.0.0.1:8000.",
            "Start React frontend on http://127.0.0.1:5173.",
            "Show command center KPI cards.",
            "Filter inventory by below reorder point or SLOB watchlist.",
            "Open a SKU and request an explanation.",
            "Open supplier pulse and show lead-time drift.",
            "Ask the policy copilot: When is a SKU classified as obsolete?",
        ],
    )
    out = OUT_DIR / "InventoryIQ_Final_Project_Report.docx"
    doc.save(out)
    return out


def build_research_paper(metrics: dict, diagrams: dict[str, Path]) -> Path:
    doc = Document()
    style_document(doc, report=False)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("InventoryIQ: A Retrieval-Augmented Inventory Policy Assistant for Explainable Reorder and SLOB Decisions")
    r.bold = True
    r.font.name = "Times New Roman"
    r.font.size = Pt(16)
    add_paragraph(doc, f"{STUDENT_NAME} ({USN})", align=WD_ALIGN_PARAGRAPH.CENTER, spacing_after=2)
    add_paragraph(doc, f"Department of {DEPARTMENT}, {SCHOOL}, {UNIVERSITY}", align=WD_ALIGN_PARAGRAPH.CENTER, spacing_after=10)
    add_heading(doc, "Abstract", 1)
    add_paragraph(
        doc,
        "Inventory planning systems frequently expose reorder exceptions and slow-moving stock flags without explaining the policy basis behind the decision. This paper presents InventoryIQ, a prototype inventory-policy assistant that combines SKU analytics, anomaly scoring, policy retrieval, and natural-language explanations. The system uses synthetic inventory data containing 500 SKUs, computes reorder-point and SLOB indicators, stores operational data in SQLite, indexes an inventory policy document in a vector store, and exposes decision support through a React and FastAPI application. The prototype identifies 95 SLOB-flagged SKUs, 75 obsolete SKUs, 20 slow movers, 185 SKUs below reorder point, and an estimated SLOB value at risk of 84.8 lakh INR. The results show that an integrated analytics-plus-RAG workflow can improve explainability for reorder-point review, supplier drift monitoring, and obsolete-stock decisions.",
    )
    add_heading(doc, "Keywords", 1)
    add_paragraph(doc, "Inventory policy, reorder point, SLOB, retrieval-augmented generation, NVIDIA RAPIDS, policy copilot, supply-chain analytics.")
    sections = [
        (
            "1 Introduction",
            [
                "Inventory control depends on accurate reorder-point decisions and timely identification of slow-moving and obsolete stock. Although dashboards can show exceptions, planners often need to connect the exception to policy clauses before taking action. Manual interpretation is slow because reorder points, supplier lead-time assumptions, safety-stock rules, and SLOB definitions may be stored in separate documents.",
                "InventoryIQ addresses this limitation by combining analytics and retrieval-augmented generation. The project links SKU-level metrics with inventory policy context so that the system can explain why a SKU is below reorder point, why it is classified as obsolete, or why a supplier requires review.",
            ],
        ),
        (
            "2 Related Work",
            [
                "Reorder-point systems generally use demand, lead time, and safety stock to decide replenishment timing. SLOB analysis is used to identify items that consume working capital without sufficient movement. Anomaly detection methods such as Isolation Forest provide an additional signal for unusual stock behavior. RAG systems improve reliability in policy domains because the generated answer is conditioned on retrieved source text rather than relying only on model memory.",
                "The research gap is the absence of a unified workflow that joins SKU analytics, SLOB classification, supplier drift monitoring, policy retrieval, and natural-language explanation.",
            ],
        ),
        (
            "3 Materials and Methods",
            [
                "The prototype uses a 1000-row e-grocery inventory dataset converted into the InventoryIQ schema. The prepared data includes SKU category, supplier, unit cost, stock on hand, reorder point, safety stock, minimum order quantity, service-level target, policy lead time, inferred actual lead time, last movement date, and generated monthly sales history for dashboard analytics.",
                "The analytics layer computes average monthly sales, days since last movement, lead-time drift, recommended reorder point, SLOB flag, anomaly score, compliance score, stock value at risk, and recommended action. The updated policy document defines ROP, safety stock, MOQ, slow-moving inventory, obsolete inventory, e-grocery service levels, FEFO/expiry handling, compliance monitoring, and supplier lead-time rules.",
            ],
        ),
    ]
    for heading, paras in sections:
        add_heading(doc, heading, 1)
        for para in paras:
            add_paragraph(doc, para, first_line=True)
    add_picture(doc, diagrams["architecture"], 5.8)
    add_caption(doc, "Fig. 1 InventoryIQ architecture")
    add_picture(doc, diagrams["rag"], 5.8)
    add_caption(doc, "Fig. 2 Retrieval and explanation workflow")
    add_heading(doc, "4 Experimental Results", 1)
    k = metrics["kpis"]
    result_df = pd.DataFrame(
        [
            ["Total SKUs", k.get("total_skus", "")],
            ["Flagged SLOB SKUs", k.get("flagged_skus", "")],
            ["Obsolete SKUs", k.get("obsolete_skus", "")],
            ["Slow-mover SKUs", k.get("slow_mover_skus", "")],
            ["Below reorder point", k.get("skus_below_rop", "")],
            ["Average compliance score", k.get("avg_compliance_score", "")],
            ["SLOB value at risk", f"INR {float(k.get('total_slob_value_at_risk', 0)):,.2f}"],
        ],
        columns=["Metric", "Observed Value"],
    )
    add_dataframe_table(doc, result_df)
    add_paragraph(
        doc,
        "The results indicate that the prototype detects several classes of operational risk. SLOB flags identify items requiring review, below-ROP flags identify replenishment risk, and supplier drift metrics highlight cases where reorder assumptions may be unsafe. The policy copilot demonstrates how retrieved rules can be used to produce plain-language explanations.",
        first_line=True,
    )
    add_heading(doc, "5 Discussion", 1)
    add_paragraph(
        doc,
        "InventoryIQ's main contribution is workflow integration. The system does not treat the LLM as a generic chatbot; instead, it binds SKU evidence with policy clauses and makes the resulting explanation available in the same interface as the dashboard. This supports auditability and improves planner confidence.",
        first_line=True,
    )
    add_heading(doc, "6 Limitations", 1)
    add_paragraph(
        doc,
        "The current evaluation uses a prepared e-grocery dataset and a local prototype rather than a direct ERP integration. Real-world validation with enterprise SKU history, supplier contracts, expiry events, and planner feedback is required before production deployment. API availability also affects generated explanations, although the dashboard includes fallback responses.",
        first_line=True,
    )
    add_heading(doc, "7 Conclusion and Future Work", 1)
    add_paragraph(
        doc,
        "The InventoryIQ prototype demonstrates that inventory analytics and RAG can be combined to create explainable decision support for reorder and SLOB management. Future work includes connecting live ERP data, adding authentication, expanding the policy corpus, and implementing approval workflows for supplier escalation and write-down actions.",
        first_line=True,
    )
    add_heading(doc, "Declarations", 1)
    add_paragraph(doc, "Funding: No external funding was received for this prototype.")
    add_paragraph(doc, "Data availability: The current prototype uses a prepared 1000-row e-grocery inventory dataset converted into the project schema.")
    add_paragraph(doc, "Competing interests: The author declares no competing interests.")
    add_heading(doc, "References", 1)
    refs = [
        "Lewis, P. et al. Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. NeurIPS.",
        "Liu, F. T., Ting, K. M., and Zhou, Z. H. Isolation Forest. IEEE International Conference on Data Mining.",
        "Silver, E. A., Pyke, D. F., and Peterson, R. Inventory Management and Production Planning and Scheduling. Wiley.",
        "NVIDIA. RAPIDS cuML Documentation.",
        "NVIDIA. NVIDIA NIM and Nemotron Embeddings Documentation.",
        "LangChain Documentation. Retrieval-Augmented Generation Workflows.",
    ]
    add_numbered(doc, refs)
    out = OUT_DIR / "InventoryIQ_Research_Paper.docx"
    doc.save(out)
    return out


def build_patent_abstract() -> Path:
    doc = Document()
    style_document(doc)
    add_heading(doc, "Abstract", 1)
    paragraphs = [
        "The present invention relates to a computer-implemented inventory policy assistance system configured to support explainable reorder-point review, slow-moving and obsolete stock identification, supplier lead-time drift monitoring, expiry-sensitive inventory handling, and policy-grounded decision support for supply-chain planning.",
        "The system comprises an inventory data intake module configured to receive SKU-level stock, sales, supplier, lead-time, safety-stock, movement, stock-age, expiry, and inventory-status data; an inventory analytics engine configured to compute recommended reorder points, lead-time drift, slow-moving and obsolete inventory status, compliance scores, anomaly indicators, expiry or FEFO risk, and stock value at risk; a policy retrieval module configured to index and retrieve relevant clauses from inventory policy documents; and an explanation generation module configured to combine SKU metrics with retrieved policy context to produce a natural-language explanation or recommended action.",
        "The invention enables a planner to review operational inventory exceptions and the governing policy basis in a single workflow. The system further includes a fallback response mechanism that preserves operational decision support when an external artificial intelligence service is unavailable. The integrated arrangement improves auditability, reduces manual interpretation of inventory policy, and supports earlier identification of reorder risk, SLOB exposure, expiry exposure, and supplier lead-time breaches.",
    ]
    for para in paragraphs:
        add_paragraph(doc, para, first_line=True)
    out = OUT_DIR / "InventoryIQ_Patent_Abstract.docx"
    doc.save(out)
    return out


def build_complete_spec(diagrams: dict[str, Path]) -> Path:
    doc = Document()
    style_document(doc)
    add_heading(doc, "Complete Specification", 1)
    add_paragraph(doc, f"Title of Invention: {PROJECT_TITLE}", bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)
    add_heading(doc, "Abstract", 1)
    add_paragraph(
        doc,
        "The invention discloses a computer-implemented inventory policy assistance system for explaining reorder-point decisions and flagging slow-moving, obsolete, or expiry-sensitive stock using SKU analytics and policy-grounded retrieval. The system receives inventory, supplier, movement, and status data, computes reorder and compliance indicators, retrieves relevant policy clauses, and generates planner-facing explanations and recommended actions through an application interface.",
        first_line=True,
    )
    add_heading(doc, "SECTION 1 - Keyword Information", 1)
    keywords = [
        "Inventory policy assistant",
        "Reorder point explanation",
        "Slow-moving and obsolete stock detection",
        "Supplier lead-time drift monitoring",
        "Policy-grounded decision support",
        "Retrieval-augmented generation",
        "Inventory compliance scoring",
        "Expiry and FEFO risk handling",
        "Supply-chain analytics dashboard",
    ]
    add_bullets(doc, keywords)
    add_heading(doc, "SECTION 2 - Invention Understanding", 1)
    add_heading(doc, "What is the problem solved by the invention?", 2)
    add_paragraph(
        doc,
        "Inventory exceptions are commonly displayed as numerical alerts without explaining the policy rule, SKU evidence, or recommended response. Planners must manually compare stock levels, reorder points, supplier lead times, last movement dates, and written policy clauses. This causes delay, inconsistency, and weak auditability in replenishment and SLOB decisions.",
        first_line=True,
    )
    add_heading(doc, "Objectives of the invention", 2)
    add_bullets(
        doc,
        [
            "To provide a single workflow for inventory exception detection and policy-grounded explanation.",
        "To compute reorder-point, lead-time drift, SLOB, compliance, anomaly, expiry-risk, FEFO, and value-at-risk indicators from SKU data.",
            "To retrieve applicable inventory policy clauses for each planner question or SKU explanation request.",
            "To generate natural-language explanations and recommended actions tied to the selected SKU and policy context.",
            "To preserve operational usefulness through fallback responses when external AI services are unavailable.",
        ],
    )
    add_heading(doc, "Technical advancements", 2)
    add_bullets(
        doc,
        [
            "Integration of SKU analytics and policy retrieval in a single decision-support pipeline.",
            "Context binding between selected SKU attributes, computed metrics, and retrieved policy clauses.",
            "Compliance score calculation that combines lead-time drift, movement age, reorder status, anomaly severity, and expiry-sensitive grocery rules.",
            "Dashboard-based explanation workflow that keeps generated answers tied to auditable operational records.",
            "Fallback response mechanism for continuity when AI services are offline.",
        ],
    )
    add_heading(doc, "Advantages of the invention", 2)
    add_bullets(
        doc,
        [
            "Reduces manual policy interpretation for planners.",
            "Improves auditability of reorder and SLOB decisions.",
            "Supports earlier identification of slow-moving, expiry-risk, and value-at-risk stock.",
            "Highlights supplier lead-time drift that can make reorder assumptions unsafe.",
            "Can be connected to enterprise inventory data in future deployments.",
        ],
    )
    add_heading(doc, "Probable novelty and inventive step", 2)
    add_paragraph(
        doc,
        "The probable novelty lies in the integrated arrangement of an inventory analytics engine, a policy retrieval module, a context-binding mechanism, and an explanation generation module configured specifically for reorder-point, SLOB, supplier-drift, and expiry-sensitive decision support. The inventive step is not the isolated use of a dashboard or language model, but the combination of computed SKU metrics, retrieved policy clauses, compliance scoring, supplier drift signals, FEFO/expiry rules, and fallback decision support in a single auditable workflow.",
        first_line=True,
    )
    add_heading(doc, "System Components", 1)
    add_picture(doc, diagrams["patent"], 6.0)
    add_caption(doc, "Figure 1 Component view of the InventoryIQ invention")
    components = pd.DataFrame(
        [
            ["Inventory Data Intake Module", "Receives SKU, supplier, stock, sales, lead-time, movement, stock-age, expiry, and status data."],
            ["Policy Retrieval Module", "Indexes and retrieves relevant clauses from policy documents."],
            ["Inventory Analytics Engine", "Computes ROP, drift, SLOB status, compliance, anomaly severity, expiry risk, and value at risk."],
            ["Explanation Generation Module", "Combines SKU evidence with policy context to generate explanations."],
            ["Compliance Scoring Store", "Stores computed indicators and summary KPIs for audit and dashboard use."],
            ["Supplier Drift Monitor", "Identifies suppliers whose actual lead time exceeds policy assumptions."],
            ["Dashboard and API Interface", "Provides planner-facing views, filters, and policy Q&A endpoints."],
        ],
        columns=["Component", "Function"],
    )
    add_dataframe_table(doc, components)
    add_heading(doc, "Claims", 1)
    claims = [
        "A computer-implemented inventory policy assistance system comprising an inventory data intake module, an inventory analytics engine, a policy retrieval module, and an explanation generation module, wherein the system is configured to receive SKU-level inventory data, compute inventory policy indicators, retrieve policy context, and generate a policy-grounded explanation for an inventory decision.",
        "The system as claimed in claim 1, wherein the inventory analytics engine computes at least one of recommended reorder point, lead-time drift, slow-moving inventory status, obsolete inventory status, expiry risk, FEFO status, policy compliance score, anomaly severity, stock value at risk, or recommended action.",
        "The system as claimed in claim 1, wherein the policy retrieval module indexes an inventory policy document and retrieves clauses relevant to reorder point, safety stock, slow-moving inventory, obsolete inventory, expiry handling, FEFO stock rotation, supplier lead time, or compliance monitoring.",
        "The system as claimed in claim 1, wherein the explanation generation module binds a selected SKU record with computed metrics and retrieved policy clauses before generating the explanation.",
        "The system as claimed in claim 1, further comprising a fallback response mechanism configured to return rule-based explanations when an external artificial intelligence service is unavailable.",
        "The system as claimed in claim 1, wherein a dashboard interface displays inventory exceptions and enables a planner to request an explanation for a selected SKU.",
        "The system as claimed in claim 1, wherein supplier lead-time drift is calculated and used to determine whether a reorder-point assumption requires review.",
        "The system as claimed in claim 1, wherein slow-moving, obsolete, or expiry-risk inventory classifications are used to trigger recommended actions including promotion, transfer, supplier return, replenishment freeze, write-down review, or escalation.",
    ]
    add_numbered(doc, claims)
    add_heading(doc, "References", 1)
    add_numbered(
        doc,
        [
            "Standard inventory policy document used in the InventoryIQ prototype.",
            "Research and documentation on inventory control, anomaly detection, and retrieval-augmented generation.",
            "NVIDIA RAPIDS, Nemotron Embeddings, and NIM public documentation.",
        ],
    )
    out = OUT_DIR / "InventoryIQ_Complete_Specification.docx"
    doc.save(out)
    return out


def build_diagrams_doc(diagrams: dict[str, Path], metrics: dict) -> Path:
    doc = Document()
    style_document(doc)
    add_heading(doc, "Diagrams", 1)
    add_paragraph(doc, f"Title of Invention: {PROJECT_TITLE}", bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)
    add_heading(doc, "Graphs or data to support enablement of the invention", 1)
    k = metrics["kpis"]
    data = pd.DataFrame(
        [
            ["Total SKUs processed", k.get("total_skus", "")],
            ["SLOB flagged SKUs", k.get("flagged_skus", "")],
            ["Obsolete SKUs", k.get("obsolete_skus", "")],
            ["Slow-mover SKUs", k.get("slow_mover_skus", "")],
            ["SKUs below reorder point", k.get("skus_below_rop", "")],
            ["Average compliance score", k.get("avg_compliance_score", "")],
            ["SLOB value at risk", f"INR {float(k.get('total_slob_value_at_risk', 0)):,.2f}"],
        ],
        columns=["Evidence", "Prototype Value"],
    )
    add_dataframe_table(doc, data)
    add_heading(doc, "Figure 1 - System architecture", 1)
    add_picture(doc, diagrams["architecture"], 6.0)
    add_caption(doc, "Figure 1 Inventory data, analytics, knowledge stores, API, AI services, and dashboard interface")
    add_heading(doc, "Figure 2 - RAG and decision workflow", 1)
    add_picture(doc, diagrams["rag"], 6.0)
    add_caption(doc, "Figure 2 Workflow for planner query, context retrieval, explanation generation, and fallback response")
    add_heading(doc, "Figure 3 - Component view", 1)
    add_picture(doc, diagrams["patent"], 6.0)
    add_caption(doc, "Figure 3 Functional modules of the InventoryIQ invention")
    add_heading(doc, "Explain functionality and importance of each component", 1)
    component_rows = pd.DataFrame(
        [
            ["Inventory Data Intake Module", "Accepts SKU, sales, movement, stock, supplier, lead-time, expiry, and status data."],
            ["Policy Retrieval Module", "Retrieves relevant policy clauses to ground answers."],
            ["Inventory Analytics Engine", "Calculates ROP, SLOB, drift, compliance, expiry, and risk indicators."],
            ["Explanation Generation Module", "Creates natural-language explanations from metrics and policy context."],
            ["Dashboard/API Interface", "Allows planners to inspect exceptions and request decision support."],
        ],
        columns=["Component", "Importance"],
    )
    add_dataframe_table(doc, component_rows)
    add_heading(doc, "Process flow", 1)
    add_paragraph(
        doc,
        "Inventory data and policy documents are ingested. The analytics layer calculates operational indicators. The policy retrieval layer indexes and retrieves relevant text. For a selected SKU or policy question, the system binds metrics and policy context, generates an explanation, and displays the answer in the dashboard. If the AI service is unavailable, a fallback response is returned.",
        first_line=True,
    )
    out = OUT_DIR / "InventoryIQ_Patent_Diagrams.docx"
    doc.save(out)
    return out


def main() -> None:
    ensure_dirs()
    metrics = load_metrics()
    diagrams = create_diagrams()
    outputs = [
        build_report(metrics, diagrams),
        build_research_paper(metrics, diagrams),
        build_patent_abstract(),
        build_complete_spec(diagrams),
        build_diagrams_doc(diagrams, metrics),
    ]
    for path in outputs:
        print(path)


if __name__ == "__main__":
    main()

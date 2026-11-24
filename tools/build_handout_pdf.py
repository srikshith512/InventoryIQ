from __future__ import annotations

import sqlite3
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "db" / "inventoryiq.db"
OUT_PATH = ROOT / "output" / "pdf" / "InventoryIQ_Project_Handout.pdf"

INK = colors.HexColor("#0F172A")
MUTED = colors.HexColor("#475569")
BLUE = colors.HexColor("#2E74B5")
DARK_BLUE = colors.HexColor("#1F4D78")
LIME = colors.HexColor("#76B900")
LIGHT = colors.HexColor("#F8FAFC")
GRID = colors.HexColor("#CBD5E1")
SOFT_GREEN = colors.HexColor("#EEF8E6")


def money(value: float | str) -> str:
    return f"INR {float(value):,.0f}"


def get_stats() -> tuple[dict[str, str], list[dict]]:
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
                LIMIT 4
                """
            )
        ]
    return kpis, categories


def footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setStrokeColor(LIME)
    canvas.setLineWidth(1)
    canvas.line(doc.leftMargin, 0.52 * inch, LETTER[0] - doc.rightMargin, 0.52 * inch)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(doc.leftMargin, 0.36 * inch, "InventoryIQ project handout")
    canvas.drawRightString(LETTER[0] - doc.rightMargin, 0.36 * inch, f"Page {doc.page}")
    canvas.restoreState()


def p(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(text.replace("&", "&amp;"), style)


def bullet_list(items: list[str], styles) -> ListFlowable:
    return ListFlowable(
        [ListItem(p(item, styles["BulletText"]), leftIndent=10) for item in items],
        bulletType="bullet",
        start="circle",
        leftIndent=14,
        bulletFontSize=7,
        bulletColor=LIME,
    )


def simple_table(data, widths, header=True) -> Table:
    table = Table(data, colWidths=widths, hAlign="LEFT", repeatRows=1 if header else 0)
    commands = [
        ("BOX", (0, 0), (-1, -1), 0.55, GRID),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, GRID),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TEXTCOLOR", (0, 0), (-1, -1), INK),
        ("FONTSIZE", (0, 0), (-1, -1), 8.7),
    ]
    if header:
        commands.extend(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EEF5")),
                ("TEXTCOLOR", (0, 0), (-1, 0), DARK_BLUE),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]
        )
    table.setStyle(TableStyle(commands))
    return table


def build() -> None:
    kpis, categories = get_stats()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    doc = BaseDocTemplate(
        str(OUT_PATH),
        pagesize=LETTER,
        leftMargin=0.65 * inch,
        rightMargin=0.65 * inch,
        topMargin=0.58 * inch,
        bottomMargin=0.66 * inch,
        title="InventoryIQ Project Handout",
        author="InventoryIQ",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal")
    doc.addPageTemplates([PageTemplate(id="default", frames=[frame], onPage=footer)])

    base = getSampleStyleSheet()
    styles = {
        "Title": ParagraphStyle(
            "Title",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=28,
            leading=31,
            textColor=INK,
            alignment=TA_LEFT,
            spaceAfter=2,
        ),
        "Subtitle": ParagraphStyle(
            "Subtitle",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=11,
            leading=14,
            textColor=MUTED,
            spaceAfter=10,
        ),
        "H1": ParagraphStyle(
            "H1",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=14.5,
            leading=17,
            textColor=BLUE,
            spaceBefore=8,
            spaceAfter=5,
        ),
        "Body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=12.2,
            textColor=INK,
            spaceAfter=5,
        ),
        "BulletText": ParagraphStyle(
            "BulletText",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.2,
            leading=11.4,
            textColor=INK,
            spaceAfter=2.5,
        ),
        "Small": ParagraphStyle(
            "Small",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=MUTED,
        ),
        "Metric": ParagraphStyle(
            "Metric",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=12,
            alignment=TA_CENTER,
            textColor=INK,
        ),
    }

    story = [
        p("InventoryIQ", styles["Title"]),
        p("NVIDIA-powered inventory policy assistant and operational command center", styles["Subtitle"]),
    ]

    intro = Table(
        [
            [
                p(
                    "InventoryIQ helps supply-chain teams detect reorder risk, slow-moving and obsolete inventory, supplier lead-time drift, and policy exceptions from one React dashboard.",
                    styles["Body"],
                ),
                p(
                    f"<b>Live demo snapshot</b><br/>{kpis['total_skus']} SKUs<br/>{kpis['flagged_skus']} SLOB flagged<br/>{money(kpis['total_slob_value_at_risk'])} value at risk",
                    styles["Metric"],
                ),
            ]
        ],
        colWidths=[4.35 * inch, 2.15 * inch],
        hAlign="LEFT",
    )
    intro.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, 0), LIGHT),
                ("BACKGROUND", (1, 0), (1, 0), SOFT_GREEN),
                ("BOX", (0, 0), (-1, -1), 0.5, GRID),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, GRID),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.extend([intro, Spacer(1, 7)])

    story.extend(
        [
            p("Problem", styles["H1"]),
            p(
                "Inventory data, supplier lead-time records, policy documents, and exception reports usually live in separate places. That makes decisions slow, inconsistent, and hard to explain.",
                styles["Body"],
            ),
            p(
                "InventoryIQ turns those signals into an explainable control room where analysts can see risk, filter SKUs, inspect supplier drift, and ask questions against the policy source.",
                styles["Body"],
            ),
            p("What the Website Does", styles["H1"]),
            bullet_list(
                [
                    "Command center: live KPIs, value at risk, category risk, and priority queue.",
                    "Inventory explorer: search/filter 500 SKUs and request AI reorder or SLOB explanations.",
                    "Supplier pulse: ranks lead-time drift against policy thresholds.",
                    "Policy copilot: answers policy questions using retrieved context and NIM generation.",
                ],
                styles,
            ),
            p("NVIDIA Stack", styles["H1"]),
            simple_table(
                [
                    ["NVIDIA service", "Where it is used", "Why it matters"],
                    ["RAPIDS cuML", "GPU anomaly scoring for SLOB risk", "Makes anomaly detection the ML layer."],
                    ["NeMo Retriever", "Embeds and retrieves policy chunks", "Grounds answers in the inventory policy."],
                    ["NVIDIA NIM", "Generates explanations and chat answers", "Turns data and policy into decisions."],
                ],
                [1.35 * inch, 2.55 * inch, 2.6 * inch],
            ),
            p("Current Results", styles["H1"]),
        ]
    )

    metrics = [
        ["Total SKUs", kpis["total_skus"], "SLOB flagged", kpis["flagged_skus"]],
        ["Avg compliance", f"{kpis['avg_compliance_score']}%", "Below ROP", kpis["skus_below_rop"]],
        ["Obsolete SKUs", kpis["obsolete_skus"], "Slow movers", kpis["slow_mover_skus"]],
        ["Suppliers drifting", kpis["suppliers_with_drift"], "Value at risk", money(kpis["total_slob_value_at_risk"])],
    ]
    story.append(simple_table(metrics, [1.25 * inch, 1.35 * inch, 1.35 * inch, 2.55 * inch], header=False))

    category_rows = [["Category", "Flagged SKUs", "Compliance", "Value at risk"]]
    for row in categories:
        category_rows.append(
            [
                row["category"],
                str(row["flagged"]),
                f"{row['compliance']}%",
                money(row["value_at_risk"]),
            ]
        )
    story.extend([Spacer(1, 5), simple_table(category_rows, [1.8 * inch, 1.25 * inch, 1.2 * inch, 2.25 * inch])])

    story.append(PageBreak())
    story.extend(
        [
            p("Architecture", styles["H1"]),
            p(
                "Data starts as synthetic inventory CSVs, is enriched with anomaly scores, then loaded into SQLite. Policy files are chunked and embedded into ChromaDB. FastAPI exposes secure endpoints to the React frontend while keeping the NVIDIA API key on the server.",
                styles["Body"],
            ),
            simple_table(
                [
                    ["Layer", "Purpose"],
                    ["Inventory data", "500 SKU catalogue, supplier fields, movement history, and policy thresholds."],
                    ["GPU analytics", "RAPIDS cuML anomaly scores plus compliance, SLOB, reorder, and drift metrics."],
                    ["API + database", "FastAPI, SQLite, ChromaDB, and the RAG chain that protects the NVIDIA API key."],
                    ["React experience", "Command center, inventory explorer, supplier pulse, and policy copilot."],
                ],
                [1.65 * inch, 4.85 * inch],
            ),
            p("Demo Flow", styles["H1"]),
            bullet_list(
                [
                    "Open the command center and point out the live value-at-risk number.",
                    "Use Inventory Explorer, filter SLOB or below-ROP items, select a SKU, and ask for an explanation.",
                    "Open Supplier Pulse to show lead-time drift and connect it to policy thresholds.",
                    "Ask Policy Copilot: What action applies when supplier lead time drifts?",
                ],
                styles,
            ),
            p("Key Files", styles["H1"]),
            simple_table(
                [
                    ["File", "Purpose"],
                    ["backend/main.py", "FastAPI service and secure AI endpoints"],
                    ["frontend/src/main.jsx", "React application views and workflows"],
                    ["frontend/src/styles.css", "Responsive interface styling"],
                    ["rag/ingest.py", "Policy chunking and NeMo Retriever embeddings"],
                    ["rag/chain.py", "RAG question-answering and SKU explanations"],
                    ["setup_db.py", "Builds SQLite from inventory and anomaly scores"],
                ],
                [2.05 * inch, 4.45 * inch],
            ),
            p("How to Launch", styles["H1"]),
            p(
                'Terminal 1: & "C:\\Users\\srikshith rao\\AppData\\Local\\Temp\\inventoryiq-venv\\Scripts\\python.exe" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000',
                styles["Small"],
            ),
            p(
                'Terminal 2: cd "C:\\Users\\srikshith rao\\OneDrive\\Projects\\inventoryiq\\frontend" then run npm.cmd run dev -- --host 127.0.0.1',
                styles["Small"],
            ),
            p("Open http://127.0.0.1:5173 in the browser.", styles["Small"]),
            p("Why This Is NVIDIA-Worthy", styles["H1"]),
            bullet_list(
                [
                    "Uses GPU analytics for anomaly detection instead of only static rules.",
                    "Uses retrieval over a real policy document so AI answers are grounded.",
                    "Separates backend AI calls from frontend UI for a more production-like architecture.",
                    "Shows business value through compliance visibility, supplier-risk detection, and working capital at risk.",
                ],
                styles,
            ),
        ]
    )

    doc.build(story)
    print(OUT_PATH)


if __name__ == "__main__":
    build()

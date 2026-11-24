from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pdfplumber
from docx import Document
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "rtd_submission"

SOURCES = [
    Path(r"C:\Users\srikshith rao\Downloads\Abstract.docx"),
    Path(r"C:\Users\srikshith rao\Downloads\CompleteSpecifications.docx"),
    Path(r"C:\Users\srikshith rao\Downloads\Diagrams.docx"),
    Path(r"C:\Users\srikshith rao\Downloads\ResearchPaper_Template.pdf"),
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def clean_text(value: str) -> str:
    return "\n".join(line.rstrip() for line in value.replace("\r", "\n").splitlines()).strip()


def extract_docx(path: Path) -> tuple[dict, str]:
    document = Document(path)
    lines: list[str] = []
    paragraph_count = 0
    table_count = 0
    image_count = 0

    for index, paragraph in enumerate(document.paragraphs, start=1):
        text = clean_text(paragraph.text)
        if text:
            paragraph_count += 1
            style_name = paragraph.style.name if paragraph.style is not None else "Unknown"
            lines.append(f"[Paragraph {index} | style={style_name}]")
            lines.append(text)
            lines.append("")

    for table_index, table in enumerate(document.tables, start=1):
        table_count += 1
        lines.append(f"[Table {table_index}]")
        for row in table.rows:
            cells = [clean_text(cell.text).replace("\n", " / ") for cell in row.cells]
            lines.append(" | ".join(cells))
        lines.append("")

    for rel in document.part.rels.values():
        if "image" in rel.reltype:
            image_count += 1

    metadata = {
        "path": str(path),
        "sha256": sha256(path),
        "paragraphs_with_text": paragraph_count,
        "tables": table_count,
        "images": image_count,
        "sections": len(document.sections),
    }
    return metadata, "\n".join(lines).strip() + "\n"


def extract_pdf(path: Path) -> tuple[dict, str]:
    reader = PdfReader(str(path))
    page_count = len(reader.pages)
    lines: list[str] = []

    with pdfplumber.open(path) as pdf:
        for page_index, page in enumerate(pdf.pages, start=1):
            text = clean_text(page.extract_text() or "")
            lines.append(f"[Page {page_index}]")
            lines.append(text if text else "[No extractable text]")
            lines.append("")

    metadata = {
        "path": str(path),
        "sha256": sha256(path),
        "pages": page_count,
    }
    return metadata, "\n".join(lines).strip() + "\n"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    inventory = []

    for source in SOURCES:
        if not source.exists():
            inventory.append({"path": str(source), "missing": True})
            continue

        if source.suffix.lower() == ".docx":
            metadata, text = extract_docx(source)
        elif source.suffix.lower() == ".pdf":
            metadata, text = extract_pdf(source)
        else:
            continue

        output_path = OUT_DIR / f"{source.stem}_extracted.txt"
        output_path.write_text(text, encoding="utf-8")
        metadata["extract_path"] = str(output_path)
        inventory.append(metadata)

    (OUT_DIR / "source_inventory.json").write_text(
        json.dumps(inventory, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()

from __future__ import annotations

from pathlib import Path

from docx import Document


FILES = [
    Path(r"C:\Users\srikshith rao\Downloads\Document format Details.docx"),
    Path(r"C:\Users\srikshith rao\Downloads\Project Report Content (1).docx"),
    Path(r"C:\Users\srikshith rao\Downloads\1. Cover page.docx"),
    Path(r"C:\Users\srikshith rao\Downloads\2. CERTIFICATE (1).docx"),
    Path(r"C:\Users\srikshith rao\Downloads\3. DECLARATION.docx"),
    Path(r"C:\Users\srikshith rao\Downloads\4. ACKNOWLEDGEMENT.docx"),
]


def main() -> None:
    for path in FILES:
        print(f"--- {path.name}")
        document = Document(path)
        texts = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
        print(f"paragraphs={len(texts)} tables={len(document.tables)} sections={len(document.sections)}")
        for text in texts[:40]:
            print(text)
        for table_index, table in enumerate(document.tables[:3], start=1):
            print(f"[table {table_index}]")
            for row in table.rows[:8]:
                print(" | ".join(cell.text.strip().replace("\n", " / ") for cell in row.cells))


if __name__ == "__main__":
    main()

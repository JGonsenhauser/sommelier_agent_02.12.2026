"""
Convert a PDF into an XLSX for downstream ingestion.
Tries table extraction first; falls back to raw text if no tables found.
"""
from __future__ import annotations

from pathlib import Path
from typing import List
import logging

import pandas as pd
import pdfplumber

logger = logging.getLogger(__name__)


def extract_tables(pdf_path: Path) -> List[pd.DataFrame]:
    tables: List[pd.DataFrame] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_tables = page.extract_tables()
            for table in page_tables:
                if not table or len(table) < 2:
                    continue
                tables.append(pd.DataFrame(table))
    return tables


def extract_text_lines(pdf_path: Path) -> pd.DataFrame:
    lines = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            for line in text.splitlines():
                cleaned = line.strip()
                if cleaned:
                    lines.append({"page": page_number, "raw_text": cleaned})
    return pd.DataFrame(lines)


def convert_pdf_to_xlsx(pdf_path: Path, xlsx_path: Path) -> Path:
    tables = extract_tables(pdf_path)
    if tables:
        combined = pd.concat(tables, ignore_index=True)
        combined.to_excel(xlsx_path, index=False, header=False)
        logger.info("Extracted %s tables to %s", len(tables), xlsx_path)
        return xlsx_path

    text_df = extract_text_lines(pdf_path)
    text_df.to_excel(xlsx_path, index=False)
    logger.warning("No tables found; saved raw text to %s", xlsx_path)
    return xlsx_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    pdf_file = Path("MAASS Beverage List 1.17.26.docx editing .docx.pdf")
    output_file = Path("data/raw/maass_wine_list.xlsx")

    if not pdf_file.exists():
        raise SystemExit("MAASS PDF not found in project root.")

    convert_pdf_to_xlsx(pdf_file, output_file)

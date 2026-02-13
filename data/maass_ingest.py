"""
MAASS beverage list ingestion utility.
Extracts tables from the MAASS PDF, normalizes columns, loads into Redis,
then embeds into Pinecone with a dedicated list_id and master list entry.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional
import logging
import re

import pandas as pd
import pdfplumber

from data.wine_data_loader import WineDataLoader
from data.embedding_pipeline import EmbeddingPipeline

logger = logging.getLogger(__name__)

STANDARD_COLUMNS = [
    "producer",
    "wine_name",
    "region",
    "country",
    "vintage",
    "price",
    "grapes",
    "wine_type",
    "tasting_note",
    "alcohol_content",
]

REQUIRED_COLUMNS = {"producer", "region", "country", "price", "wine_type"}


def extract_tables(pdf_path: Path) -> List[pd.DataFrame]:
    """Extract tables from a PDF using pdfplumber."""
    tables: List[pd.DataFrame] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_tables = page.extract_tables()
            for table in page_tables:
                if not table or len(table) < 2:
                    continue
                df = pd.DataFrame(table)
                tables.append(df)
    return tables


def normalize_headers(df: pd.DataFrame) -> pd.DataFrame:
    """Use first row as header if it looks like a header row."""
    header_candidates = df.iloc[0].fillna("").astype(str).str.lower().tolist()
    header_text = " ".join(header_candidates)
    if any(key in header_text for key in ["producer", "wine", "vintage", "price", "region"]):
        df = df[1:].copy()
        df.columns = header_candidates
    return df


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize column names and align to standard schema."""
    def slugify(value: str) -> str:
        return re.sub(r"[^a-z0-9]", "", str(value).lower())

    df = df.rename(columns={col: slugify(col) for col in df.columns})

    aliases = {
        "winename": "wine_name",
        "wine": "wine_name",
        "winetype": "wine_type",
        "type": "wine_type",
        "varietal": "grapes",
        "varietals": "grapes",
        "variety": "grapes",
        "grape": "grapes",
        "notes": "tasting_note",
        "tastingnotes": "tasting_note",
        "description": "tasting_note",
        "abv": "alcohol_content",
        "alcohol": "alcohol_content",
    }
    df = df.rename(columns={col: aliases.get(col, col) for col in df.columns})

    for col in STANDARD_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    return df[STANDARD_COLUMNS]


def export_maass_to_csv(pdf_path: Path, csv_path: Path) -> Path:
    """Extract tables from the MAASS PDF and export a normalized CSV."""
    tables = extract_tables(pdf_path)
    if not tables:
        raise ValueError("No tables detected in PDF; provide a CSV/XLSX instead.")

    normalized_tables = []
    for table in tables:
        table = normalize_headers(table)
        normalized_tables.append(normalize_columns(table))

    combined = pd.concat(normalized_tables, ignore_index=True)
    combined.to_csv(csv_path, index=False)
    logger.info("Exported normalized CSV to %s", csv_path)
    return csv_path


def normalize_xlsx_to_csv(xlsx_path: Path, csv_path: Path) -> Path:
    """Normalize a raw XLSX export into a structured CSV."""
    df = pd.read_excel(xlsx_path, header=None)

    records = []
    for _, row in df.iterrows():
        cells = [str(cell).strip() for cell in row.tolist() if pd.notna(cell) and str(cell).strip()]
        if not cells:
            continue

        raw_text = " ".join(cells)
        numbers = re.findall(r"\d+(?:\.\d+)?", raw_text)
        price = float(numbers[-1]) if numbers else None

        vintage_match = re.findall(r"\b(19|20)\d{2}\b", raw_text)
        vintage = None
        if vintage_match:
            vintage = int(vintage_match[-1])

        cleaned = raw_text
        if price is not None:
            cleaned = re.sub(rf"\b{re.escape(str(int(price)))}\b", "", cleaned)
            cleaned = re.sub(rf"\b{re.escape(str(price))}\b", "", cleaned)
        if vintage is not None:
            cleaned = re.sub(rf"\b{vintage}\b", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" -")

        if "," in cleaned:
            producer, wine_name = cleaned.split(",", 1)
            producer = producer.strip()
            wine_name = wine_name.strip()
        else:
            producer = cleaned.strip()
            wine_name = ""

        if not producer or price is None:
            continue

        records.append({
            "producer": producer,
            "wine_name": wine_name,
            "region": "unknown",
            "country": "unknown",
            "vintage": vintage or "",
            "price": price,
            "grapes": "",
            "wine_type": "unknown",
            "tasting_note": "",
            "alcohol_content": "",
        })

    normalized = pd.DataFrame(records, columns=STANDARD_COLUMNS)
    normalized.to_csv(csv_path, index=False)
    logger.info("Normalized raw XLSX to %s", csv_path)
    return csv_path


def ingest_maass_list(
    source_path: Path,
    business_id: str = "maass",
    business_name: str = "MAASS Beverage List",
    location: Optional[str] = None,
    list_id: Optional[str] = None,
    namespace: str = "maass_wine_list",
    producers_namespace: str = "producers",
) -> int:
    """Extract, load, and embed the MAASS beverage list."""
    csv_path = Path("data/raw/maass_wine_list.csv")
    # Create output directory if it doesn't exist
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    
    if source_path.suffix.lower() == ".pdf":
        export_maass_to_csv(source_path, csv_path)
    elif source_path.suffix.lower() in {".xlsx", ".xls"}:
        raw_df = pd.read_excel(source_path)
        
        # Check if file is already in correct format
        expected_cols = {"Producer", "Label", "Region", "Country", "Grapes", "Major Region"}
        if expected_cols.issubset(set(raw_df.columns)):
            # File is already properly structured - just normalize column names
            logger.info("File already has correct structure; converting to CSV")
            # Rename to match standard schema
            raw_df_renamed = raw_df.rename(columns={
                'Producer': 'producer',
                'Label': 'wine_name',
                'Grapes': 'grapes',
                'Region': 'region',
                'Major Region': 'major_region',
                'Country': 'country',
            })
            # Add missing required columns
            raw_df_renamed['wine_type'] = 'unknown'
            raw_df_renamed['price'] = 0.0
            raw_df_renamed['tasting_note'] = ''
            raw_df_renamed['vintage'] = ''
            raw_df_renamed['alcohol_content'] = ''
            
            # Select only the standard columns
            standard_cols = [
                'producer', 'wine_name', 'region', 'country', 'vintage', 'price',
                'grapes', 'wine_type', 'tasting_note', 'alcohol_content'
            ]
            raw_df_renamed = raw_df_renamed[standard_cols]
            raw_df_renamed.to_csv(csv_path, index=False)
            logger.info(f"Converted structured XLSX to {csv_path} with {len(raw_df_renamed)} rows")
        elif REQUIRED_COLUMNS.issubset(set(raw_df.columns)):
            raw_df.to_csv(csv_path, index=False)
            logger.info("Copied structured XLSX to %s", csv_path)
        else:
            normalize_xlsx_to_csv(source_path, csv_path)
    else:
        raise ValueError("Unsupported source file format.")

    qr_id = f"qr_{business_id}"
    effective_list_id = list_id or namespace
    pipeline = EmbeddingPipeline()

    try:
        loader = WineDataLoader()
        wines_loaded = loader.load_business_wine_list(
            business_id=business_id,
            business_name=business_name,
            wine_list_file=csv_path,
            location=location
        )
        embedded = pipeline.embed_business_wines(
            qr_id=qr_id,
            list_id=effective_list_id,
            also_add_to_master=True,
            namespace=namespace,
            also_add_to_producers=True,
            producers_namespace=producers_namespace
        )
    except Exception as exc:
        logger.warning("Redis unavailable; embedding directly from CSV: %s", exc)
        loader = WineDataLoader(redis_required=False)
        wines = loader.parse_wine_list(csv_path, qr_id=qr_id)
        wines_loaded = len(wines)
        embedded = pipeline.embed_wines(
            wines=wines,
            qr_id=qr_id,
            list_id=effective_list_id,
            also_add_to_master=True,
            namespace=namespace,
            also_add_to_producers=True,
            producers_namespace=producers_namespace
        )

    logger.info("Loaded %s wines, embedded %s vectors", wines_loaded, embedded)
    return embedded


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    xlsx_file = Path("data/raw/maass_wine_list.xlsx")
    pdf_file = Path("MAASS Beverage List 1.17.26.docx editing .docx.pdf")

    if xlsx_file.exists():
        source = xlsx_file
    elif pdf_file.exists():
        source = pdf_file
    else:
        raise SystemExit("MAASS source file not found.")

    ingest_maass_list(source)

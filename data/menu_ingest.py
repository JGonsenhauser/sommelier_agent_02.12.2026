"""
Restaurant menu ingestion utility.
Extracts dishes from PDF/CSV/XLSX, embeds into Pinecone for wine-dish pairing.

Usage:
    python -m data.menu_ingest --restaurant_id maass --file path/to/menu.pdf
    python -m data.menu_ingest --restaurant_id maass --file path/to/menu.csv
"""
from __future__ import annotations

import argparse
import logging
import re
import uuid
from pathlib import Path
from typing import List, Optional

import pandas as pd
import pdfplumber

from data.menu_schema import MenuDish
from data.embedding_pipeline import EmbeddingPipeline

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# PDF extraction
# ---------------------------------------------------------------------------

def extract_menu_from_pdf(pdf_path: Path) -> pd.DataFrame:
    """Extract menu items from a PDF.

    Attempts table extraction first, then falls back to text parsing
    if no tables are detected.
    """
    tables: List[pd.DataFrame] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_tables = page.extract_tables()
            for table in page_tables:
                if not table or len(table) < 2:
                    continue
                df = pd.DataFrame(table)
                tables.append(df)

    if tables:
        combined = pd.concat(tables, ignore_index=True)
        combined = _normalize_menu_headers(combined)
        return _normalize_menu_columns(combined)

    # Fallback: parse raw text line-by-line
    logger.info("No tables found in PDF; falling back to text extraction")
    return _parse_menu_text_from_pdf(pdf_path)


def _parse_menu_text_from_pdf(pdf_path: Path) -> pd.DataFrame:
    """Parse menu items from raw PDF text when tables aren't detected.

    Handles two common formats:
    1. Bullet-style menus (e.g., "• Dish Name" on one line, description on next)
    2. Single-line menus with optional trailing prices
    """
    records: List[dict] = []
    # Common bullet characters
    bullet_chars = {"•", "·", "●", "▪", "◆", "◇", "■", "□", "–", "—"}

    with pdfplumber.open(pdf_path) as pdf:
        all_lines: List[str] = []
        for page in pdf.pages:
            text = page.extract_text() or ""
            all_lines.extend(text.split("\n"))

    current_category = ""
    i = 0
    while i < len(all_lines):
        line = all_lines[i].strip()
        i += 1

        if not line:
            continue

        # Strip leading bullet characters
        stripped = line.lstrip("".join(bullet_chars)).strip()
        has_bullet = stripped != line.strip()

        # Detect category headers: short lines, no bullet, title-cased
        # (e.g., "Snacks", "Starters", "Sweets", "Main Courses")
        if (
            not has_bullet
            and len(stripped.split()) <= 3
            and stripped[0:1].isupper()
            and " - " not in stripped
        ):
            current_category = stripped
            continue

        # If this line has a bullet, it's a dish name
        if has_bullet:
            dish_name = stripped

            # Try to extract a trailing price from the dish name line
            price_match = re.search(r"\$?\s*(\d+(?:\.\d{2})?)\s*$", dish_name)
            price = float(price_match.group(1)) if price_match else None
            if price_match:
                dish_name = dish_name[: price_match.start()].strip()

            # Look ahead: next non-empty line without a bullet is the description
            description = ""
            if i < len(all_lines):
                next_line = all_lines[i].strip()
                next_stripped = next_line.lstrip("".join(bullet_chars)).strip()
                next_has_bullet = next_stripped != next_line.strip()

                # Description lines don't start with a bullet and are either
                # lowercase or start with punctuation (e.g., quotes)
                first_char = next_line[0:1]
                is_description = (
                    next_line
                    and not next_has_bullet
                    and (first_char.islower() or not first_char.isalpha())
                )
                if is_description:
                    description = next_line
                    # Check for price on description line
                    if price is None:
                        price_match = re.search(r"\$?\s*(\d+(?:\.\d{2})?)\s*$", description)
                        if price_match:
                            price = float(price_match.group(1))
                            description = description[: price_match.start()].strip()
                    i += 1  # consume the description line

            records.append({
                "name": dish_name,
                "description": description,
                "category": current_category,
                "price": price,
            })
            continue

        # Fallback for non-bullet lines that look like dish entries
        # (e.g., lines with a trailing price)
        price_match = re.search(r"\$?\s*(\d+(?:\.\d{2})?)\s*$", stripped)
        price = float(price_match.group(1)) if price_match else None
        name_part = stripped
        if price_match:
            name_part = stripped[: price_match.start()].strip().rstrip("-–—.")

        if name_part and len(name_part) > 3:
            for sep in [" - ", " – ", ": "]:
                if sep in name_part:
                    name, desc = name_part.split(sep, 1)
                    break
            else:
                name = name_part
                desc = ""

            records.append({
                "name": name.strip(),
                "description": desc.strip(),
                "category": current_category,
                "price": price,
            })

    return pd.DataFrame(records) if records else pd.DataFrame(columns=["name", "description", "category", "price"])


# ---------------------------------------------------------------------------
# CSV / XLSX loading
# ---------------------------------------------------------------------------

def load_menu_from_file(file_path: Path) -> pd.DataFrame:
    """Load a menu from CSV or XLSX."""
    suffix = file_path.suffix.lower()
    if suffix == ".csv":
        df = pd.read_csv(file_path)
    elif suffix in {".xlsx", ".xls"}:
        df = pd.read_excel(file_path)
    else:
        raise ValueError(f"Unsupported file format: {suffix}")

    return _normalize_menu_columns(df)


# ---------------------------------------------------------------------------
# Column normalisation helpers
# ---------------------------------------------------------------------------

def _normalize_menu_headers(df: pd.DataFrame) -> pd.DataFrame:
    """Promote first row to header if it looks like one."""
    first_row = df.iloc[0].fillna("").astype(str).str.lower().tolist()
    joined = " ".join(first_row)
    if any(kw in joined for kw in ["name", "dish", "item", "description", "price", "category"]):
        df = df[1:].copy()
        df.columns = first_row
    return df


def _normalize_menu_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise column names to the standard menu schema."""
    slug = lambda v: re.sub(r"[^a-z0-9]", "", str(v).lower())
    df = df.rename(columns={col: slug(col) for col in df.columns})

    aliases = {
        "dish": "name",
        "dishname": "name",
        "item": "name",
        "itemname": "name",
        "title": "name",
        "desc": "description",
        "ingredients": "description",
        "details": "description",
        "section": "category",
        "type": "category",
        "course": "category",
    }
    df = df.rename(columns={col: aliases.get(col, col) for col in df.columns})

    for col in ["name", "description", "category", "price"]:
        if col not in df.columns:
            df[col] = "" if col != "price" else None

    return df[["name", "description", "category", "price"]]


# ---------------------------------------------------------------------------
# Embedding & upsert
# ---------------------------------------------------------------------------

def ingest_menu(
    source_path: Path,
    restaurant_id: str,
    namespace: Optional[str] = None,
) -> int:
    """Extract, embed, and upsert a restaurant menu into Pinecone.

    Returns the number of dishes embedded.
    """
    namespace = namespace or f"{restaurant_id}_menu"

    # ---- Load ----
    suffix = source_path.suffix.lower()
    if suffix == ".pdf":
        df = extract_menu_from_pdf(source_path)
    elif suffix in {".csv", ".xlsx", ".xls"}:
        df = load_menu_from_file(source_path)
    else:
        raise ValueError(f"Unsupported file format: {suffix}")

    # Drop rows without a dish name
    df = df[df["name"].astype(str).str.strip().ne("")]
    df = df.fillna("")

    if df.empty:
        logger.warning("No menu items found in %s", source_path)
        return 0

    logger.info("Parsed %d menu items from %s", len(df), source_path)

    # ---- Build MenuDish objects ----
    dishes: List[MenuDish] = []
    for _, row in df.iterrows():
        price = None
        raw_price = row.get("price", "")
        if raw_price not in ("", None):
            try:
                price = float(str(raw_price).replace("$", "").replace(",", "").strip())
            except (ValueError, TypeError):
                pass

        dishes.append(MenuDish(
            name=str(row["name"]).strip(),
            description=str(row.get("description", "")).strip(),
            category=str(row.get("category", "")).strip(),
            price=price,
            restaurant_id=restaurant_id,
        ))

    # ---- Embed & upsert ----
    pipeline = EmbeddingPipeline()
    texts = [dish.to_embedding_text() for dish in dishes]
    embeddings = pipeline.get_embeddings(texts)

    vectors = []
    for dish, embedding in zip(dishes, embeddings):
        vectors.append({
            "id": f"{restaurant_id}_menu_{dish.dish_id}",
            "values": embedding,
            "metadata": dish.to_pinecone_metadata(),
        })

    # Upsert in batches of 100
    batch_size = 100
    total = 0
    for i in range(0, len(vectors), batch_size):
        batch = vectors[i : i + batch_size]
        try:
            pipeline.index.upsert(vectors=batch, namespace=namespace)
            total += len(batch)
            logger.info("Upserted batch %d: %d dishes", i // batch_size + 1, len(batch))
        except Exception as e:
            logger.error("Error upserting batch: %s", e)

    logger.info("Successfully embedded %d menu items into namespace '%s'", total, namespace)
    return total


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="Ingest a restaurant menu into Pinecone")
    parser.add_argument("--restaurant_id", required=True, help="Restaurant identifier (e.g., 'maass')")
    parser.add_argument("--file", required=True, help="Path to menu file (PDF, CSV, or XLSX)")
    parser.add_argument("--namespace", default=None, help="Pinecone namespace (default: {restaurant_id}_menu)")
    args = parser.parse_args()

    source = Path(args.file)
    if not source.exists():
        raise SystemExit(f"File not found: {source}")

    count = ingest_menu(source, args.restaurant_id, namespace=args.namespace)
    print(f"Done — embedded {count} menu items.")

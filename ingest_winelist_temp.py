"""Parse data/winelist_temp.md and replace the restaurant Pinecone list."""
from __future__ import annotations

import hashlib
import math
import re
from pathlib import Path

try:
    from pinecone import Pinecone
    from config import settings
except Exception:  # demo server has no Pinecone / .env
    Pinecone = None
    settings = None

MD_PATH = Path("data/winelist_temp.md")
NAMESPACE = "maass_wine_list"
LIST_ID = "maass_wine_list"
QR_ID = "qr_maass"
RESTAURANT = "maass"
DIM = 1024

LINE_RE = re.compile(
    r"^(?P<vintage>NV|\d{4}(?:\s*[–-]\s*\d{4})?)\s*\|\s*"
    r"(?P<producer>.+?)\s*\|\s*"
    r"(?P<label>.+?)\s*\|\s*"
    r"(?P<region>.+?)\s*\|\s*"
    r"(?P<country>.+?)\s*\|\s*"
    r"\$(?P<price>[0-9,]+)\+?(?:\s*[–-]\s*\$?(?P<price2>[0-9,]+))?"
    r"(?:\s*\((?P<stylehint>red|white)\))?\s*$",
    re.IGNORECASE,
)
NOVINTAGE_RE = re.compile(
    r"^(?P<producer>.+?)\s*\|\s*"
    r"(?P<label>.+?)\s*\|\s*"
    r"(?P<region>.+?)\s*\|\s*"
    r"(?P<country>.+?)\s*\|\s*"
    r"\$(?P<price>[0-9,]+)\+?(?:\s*[–-]\s*\$?(?P<price2>[0-9,]+))?\s*$"
)
STYLE_RE = re.compile(
    r"^(Reds|Whites|Sparkling|Still)\b",
    re.IGNORECASE,
)


def hash_vector(text: str, dim: int = DIM) -> list[float]:
    vec = [0.0] * dim
    for token in re.findall(r"[a-z0-9]+", text.lower()):
        digest = hashlib.md5(token.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:2], "big") % dim
        sign = 1.0 if digest[2] % 2 == 0 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def price_range(price: int) -> str:
    if price < 50:
        return "<$50"
    if price < 100:
        return "$50-100"
    if price < 200:
        return "$100-200"
    return "$200+"


def _skip_list_row(vintage: str, label: str, producer: str = "") -> bool:
    """Drop grouping notes that are not a single bottle."""
    v = (vintage or "").lower()
    lab = (label or "").lower()
    prod = (producer or "").lower()
    if "range" in v or "range" in prod:
        return True
    if "etc" in lab or "selections" in lab:
        return True
    if "|" in (producer or "") or "|" in (label or ""):
        return True
    # Dual SKUs ("Malbec / Bramare") but keep Champagne "Collection / Brut".
    if " / " in lab and not any(ok in lab for ok in ("brut", "collection", "rosé", "rose", "blanc")):
        return True
    reds = ("malbec", "cabernet", "pinot noir", "syrah", "merlot")
    whites = ("chardonnay", "sauvignon blanc", "riesling", "chenin")
    if any(r in lab for r in reds) and any(w in lab for w in whites):
        return True
    return False


def infer_style(section: str, major: str, hint: str | None, label: str) -> str:
    if hint:
        return hint.lower()
    lab = (label or "").lower()
    maj = (major or "").lower()
    if any(g in lab for g in ("cabernet sauvignon", "pinot noir", "barolo", "barbaresco", "brunello", "malbec", "syrah", "zinfandel")) and "blanc" not in lab and "blanc de" not in lab:
        return "red"
    blob = f"{section} {major} {label}".lower()
    if any(w in blob for w in ("sparkling", "champagne", "prosecco", "cava", "corpinnat", "brut")):
        return "sparkling"
    if re.search(r"\bwhites?\b", blob):
        return "white"
    if re.search(r"\breds?\b", blob):
        return "red"
    if "sancerre" in blob and "rouge" not in lab:
        return "white"
    if any(w in blob for w in (
        "chardonnay", "riesling", "sauvignon", "chenin", "fiano", "arneis",
        "pinot gris", "blanc", "xarel", "viura", "white wine", "gravonia",
    )):
        return "white"
    red_regions = (
        "napa", "sonoma", "barolo", "barbaresco", "brunello", "chianti", "bolgheri",
        "pauillac", "saint-julien", "saint-estèphe", "margaux", "pomerol", "saint-émilion",
        "rioja", "ribera", "mclaren", "barossa", "willamette", "burgundy",
    )
    if "sancerre" in maj:
        return "white"
    if any(r in blob for r in red_regions):
        return "red"
    return "red"


def infer_grapes(label: str, region: str, major: str, style: str) -> str:
    blob = f"{label} {region} {major}".lower()
    pairs = [
        ("geyserville", "Zinfandel"),
        ("blanc de blancs", "Chardonnay"),
        ("pinot noir", "Pinot Noir"),
        ("pinot gris", "Pinot Gris"),
        ("chardonnay", "Chardonnay"),
        ("cabernet", "Cabernet Sauvignon"),
        ("zinfandel", "Zinfandel"),
        ("malbec", "Malbec"),
        ("syrah", "Syrah"),
        ("shiraz", "Shiraz"),
        ("grenache", "Grenache"),
        ("riesling", "Riesling"),
        ("sauvignon", "Sauvignon Blanc"),
        ("arneis", "Arneis"),
        ("moscato", "Moscato"),
        ("xarel", "Xarel-lo"),
        ("fiano", "Fiano"),
        ("roussanne", "Roussanne"),
        ("semillon", "Semillon"),
        ("brunello", "Sangiovese Grosso"),
        ("chianti", "Sangiovese"),
        ("barolo", "Nebbiolo"),
        ("barbaresco", "Nebbiolo"),
        ("amarone", "Corvina"),
        ("prosecco", "Glera"),
        ("valdobbiadene", "Glera"),
    ]
    for needle, grapes in pairs:
        if needle in blob:
            return grapes
    major_l = major.lower()
    if style == "sparkling":
        if "prosecco" in major_l or "valdobbiadene" in blob:
            return "Glera"
        if "pened" in blob or "cava" in blob or "corpinnat" in blob:
            return "Macabeo, Xarel-lo, Parellada"
        return "Chardonnay, Pinot Noir, Pinot Meunier"
    if style == "white":
        if "sancerre" in major_l or "sancerre" in blob:
            return "Sauvignon Blanc"
        if "xarel" in blob:
            return "Xarel-lo"
        if "burgundy" in major_l or "chablis" in blob or "meursault" in blob:
            return "Chardonnay"
        if "alsace" in major_l:
            return "Riesling"
        if "bordeaux" in major_l:
            return "Sauvignon Blanc, Semillon"
        if "rioja" in major_l:
            return "Viura"
        return "White blend"
    if "sancerre" in blob:
        return "Pinot Noir" if style == "red" else "Sauvignon Blanc"
    if "willamette" in blob or "dundee" in blob or "eola" in blob or "ribbon" in blob:
        return "Pinot Noir"
    if "burgundy" in major_l:
        return "Pinot Noir"
    if "piedmont" in major_l:
        return "Nebbiolo"
    if "brunello" in major_l:
        return "Sangiovese Grosso"
    if "chianti" in major_l:
        return "Sangiovese"
    if "bordeaux" in major_l or "pauillac" in blob or "saint-julien" in blob or "margaux" in blob:
        return "Cabernet Sauvignon, Merlot"
    if "rioja" in major_l or "ribera" in major_l:
        return "Tempranillo"
    if "barossa" in major_l or "mclaren" in major_l:
        return "Shiraz"
    if "napa" in blob or "sonoma" in blob or "knights" in blob:
        return "Cabernet Sauvignon"
    if "bolgheri" in blob or "tuscany" in major_l:
        return "Cabernet Sauvignon, Sangiovese"
    return "Red blend" if style == "red" else "White blend"


def parse_list(text: str) -> list[dict]:
    major = ""
    section = ""
    wines = []
    seen = set()
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.lower().startswith("winelist"):
            continue
        if STYLE_RE.match(line):
            section = STYLE_RE.match(line).group(1)
            continue
        if "|" not in line:
            if line.startswith("(") or line.endswith(":"):
                continue
            if re.match(r"^[A-Z].{2,80}$", line) and not line.endswith("."):
                major = re.sub(r"\s*\(.*\)$", "", line).strip()
                section = ""
            continue
        match = LINE_RE.match(line) or NOVINTAGE_RE.match(line)
        if not match:
            continue
        data = match.groupdict()
        vintage = (data.get("vintage") or "").strip()
        if vintage.lower() == "nv":
            vintage = "NV"
        producer = data["producer"].strip()
        label = data["label"].strip()
        if _skip_list_row(vintage, label, producer):
            continue
        region = data["region"].strip()
        country = data["country"].strip()
        price = int(data["price"].replace(",", ""))
        if data.get("price2"):
            price = (price + int(data["price2"].replace(",", ""))) // 2
        hint = data.get("stylehint")
        style = infer_style(section, major, hint, label)
        grapes = infer_grapes(label, region, major, style)
        key = (producer.lower(), label.lower(), vintage, region.lower())
        if key in seen:
            continue
        seen.add(key)
        text_field = (
            f"Producer: {producer} | Label: {label} | Grapes: {grapes} | "
            f"Region: {region} | Major Region: {major or region} | "
            f"Country: {country} | Wine Style: {style}"
        )
        wines.append(
            {
                "vintage": vintage,
                "producer": producer,
                "label": label,
                "region": region,
                "major_region": major or region,
                "country": country,
                "price": price,
                "price_range": price_range(price),
                "wine_style": style,
                "grapes": grapes,
                "text": text_field,
            }
        )
    return wines


def upsert_wines(wines: list[dict]) -> int:
    pc = Pinecone(api_key=settings.pinecone_api_key)
    index = pc.Index(settings.pinecone_index_name)
    try:
        index.delete(delete_all=True, namespace=NAMESPACE)
        print(f"Cleared namespace {NAMESPACE}")
    except Exception as exc:
        print(f"Clear note: {exc}")

    vectors = []
    for wine in wines:
        master_id = hashlib.md5(
            f"{wine['producer']}_{wine['label']}_{wine['grapes']}_{wine['region']}_{wine['country']}".encode()
        ).hexdigest()
        vectors.append(
            {
                "id": f"maass_{LIST_ID}_wine_{master_id[:8]}",
                "values": hash_vector(wine["text"]),
                "metadata": {
                    "producer": wine["producer"],
                    "label": wine["label"],
                    "wine_name": wine["label"],
                    "grapes": wine["grapes"],
                    "region": wine["region"],
                    "major_region": wine["major_region"],
                    "country": wine["country"],
                    "vintage": wine["vintage"],
                    "text": wine["text"],
                    "sync_version": 2,
                    "price_range": wine["price_range"],
                    "price": wine["price"],
                    "wine_style": wine["wine_style"],
                    "wine_type": wine["wine_style"],
                    "tasting_keywords": "",
                    "list_id": LIST_ID,
                    "qr_id": QR_ID,
                    "restaurant": RESTAURANT,
                    "source": "winelist_temp",
                },
            }
        )

    batch = 100
    for i in range(0, len(vectors), batch):
        index.upsert(vectors=vectors[i : i + batch], namespace=NAMESPACE)
        print(f"Upserted {min(i + batch, len(vectors))}/{len(vectors)}")
    return len(vectors)


def main() -> None:
    wines = parse_list(MD_PATH.read_text(encoding="utf-8"))
    print(f"Parsed {len(wines)} wines from {MD_PATH}")
    styles = {}
    for wine in wines:
        styles[wine["wine_style"]] = styles.get(wine["wine_style"], 0) + 1
    print("By style:", styles)
    count = upsert_wines(wines)
    print(f"Done. {count} wines in {NAMESPACE}")


if __name__ == "__main__":
    main()

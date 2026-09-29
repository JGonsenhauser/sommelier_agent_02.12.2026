"""Parse data/winelist_temp.md and replace the restaurant Pinecone list."""
from __future__ import annotations

import hashlib
import math
import re
from pathlib import Path

try:
    from pinecone import Pinecone
    from config import settings
except Exception:
    Pinecone = None
    settings = None

MD_PATH = Path("data/winelist_temp.md")
NAMESPACE = "maass_wine_list"
LIST_ID = "maass_wine_list"
QR_ID = "qr_maass"
RESTAURANT = "maass"
DIM = 1024

_EXTRA_FIELDS = (
    r"(?:\s*\|\s*(?P<sub_region>[^|]*))?"
    r"(?:\s*\|\s*(?P<inventory>[^|]*))?"
    r"(?:\s*\|\s*(?P<stock>[^|]*))?"
    r"(?:\s*\|\s*(?P<edited>[^|]*))?"
    r"\s*$"
)

LINE_RE = re.compile(
    r"^(?P<vintage>NV|\d{4}(?:\s*[–-]\s*\d{4})?(?:\s+range)?)\s*\|\s*"
    r"(?P<producer>.+?)\s*\|\s*"
    r"(?P<label>.+?)\s*\|\s*"
    r"(?P<region>.+?)\s*\|\s*"
    r"(?P<country>.+?)\s*\|\s*"
    r"\$(?P<price>[0-9,]+)(?:\s*[–-]\s*\$?(?P<price2>[0-9,]+))?"
    r"(?:\s*\((?P<stylehint>red|white)\))?"
    + _EXTRA_FIELDS,
    re.IGNORECASE,
)
NOVINTAGE_RE = re.compile(
    r"^(?P<producer>.+?)\s*\|\s*"
    r"(?P<label>.+?)\s*\|\s*"
    r"(?P<region>.+?)\s*\|\s*"
    r"(?P<country>.+?)\s*\|\s*"
    r"\$(?P<price>[0-9,]+)(?:\s*[–-]\s*\$?(?P<price2>[0-9,]+))?"
    + _EXTRA_FIELDS,
    re.IGNORECASE,
)
STYLE_RE = re.compile(
    r"^(Reds|Whites|Sparkling|Still|Rose|Rosé)\b",
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


def infer_style(section: str, major: str, hint: str | None, label: str) -> str:
    if hint:
        return hint.lower()
    if (section or "").strip().lower() in {"rose", "rosé"}:
        return "rose"
    blob = f"{section} {major} {label}".lower()
    if any(w in blob for w in ("sparkling", "champagne", "prosecco", "cava", "corpinnat", "brut")):
        return "sparkling"
    if re.search(r"\bwhites?\b", blob):
        return "white"
    if re.search(r"\breds?\b", blob):
        return "red"
    if any(w in blob for w in ("chardonnay", "riesling", "sauvignon", "chenin", "fiano", "arneis", "pinot gris", "blanc")):
        return "white"
    red_regions = (
        "napa", "sonoma", "barolo", "barbaresco", "brunello", "chianti", "bolgheri",
        "pauillac", "saint-julien", "saint-estèphe", "margaux", "pomerol", "saint-émilion",
        "rioja", "ribera", "mclaren", "barossa", "willamette", "burgundy",
    )
    if any(r in blob for r in red_regions):
        return "red"
    return "red"


def infer_grapes(label: str, region: str, major: str, style: str) -> str:
    blob = f"{label} {region} {major}".lower()
    pairs = [
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
        if "burgundy" in major_l or "chablis" in blob or "meursault" in blob:
            return "Chardonnay"
        if "sancerre" in major_l:
            return "Sauvignon Blanc"
        if "alsace" in major_l:
            return "Riesling"
        if "bordeaux" in major_l:
            return "Sauvignon Blanc, Semillon"
        if "rioja" in major_l:
            return "Viura"
        return "Chardonnay"
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
        if not line or line.lower().startswith("winelist") or line.lower().startswith("generated from"):
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
        region = data["region"].strip()
        country = data["country"].strip()
        price = int(data["price"].replace(",", ""))
        if data.get("price2"):
            price = (price + int(data["price2"].replace(",", ""))) // 2
        hint = data.get("stylehint")
        style = infer_style(section, major, hint, label)
        grapes = infer_grapes(label, region, major, style)
        sub_region = (data.get("sub_region") or "").strip()
        inventory_raw = (data.get("inventory") or "").strip()
        inventory_count = int(inventory_raw) if inventory_raw.isdigit() else None
        stock_raw = (data.get("stock") or "").strip().lower()
        in_stock = stock_raw not in {"out", "0", "false", "no"}
        last_edit_date = (data.get("edited") or "").strip()
        key = (
            producer.lower(),
            label.lower(),
            vintage,
            region.lower(),
            sub_region.lower(),
            price,
            inventory_count,
            in_stock,
        )
        if key in seen:
            continue
        seen.add(key)
        wine = {
            "vintage": vintage,
            "producer": producer,
            "label": label,
            "region": region,
            "sub_region": sub_region,
            "major_region": major or region,
            "country": country,
            "price": price,
            "price_range": price_range(price),
            "wine_style": style,
            "grapes": grapes,
            "inventory_count": inventory_count,
            "in_stock": in_stock,
            "last_edit_date": last_edit_date,
        }
        wine["text"] = compose_text(wine)
        wines.append(wine)
    return wines


def compose_text(wine: dict) -> str:
    return (
        f"Producer: {wine.get('producer', '')} | Label: {wine.get('label', '')} | "
        f"Grapes: {wine.get('grapes', '')} | Region: {wine.get('region', '')} | "
        f"Sub Region: {wine.get('sub_region', '')} | "
        f"Major Region: {wine.get('major_region') or wine.get('region', '')} | "
        f"Country: {wine.get('country', '')} | Wine Style: {wine.get('wine_style', '')}"
    )


def _list_ids(index, namespace: str) -> list[str]:
    ids = []
    for page in index.list(namespace=namespace):
        vectors = getattr(page, "vectors", None)
        items = vectors if vectors is not None else page
        for item in items:
            ids.append(item.id if hasattr(item, "id") else str(item))
    return ids


def _prepare_wine(wine: dict) -> dict:
    prepared = dict(wine)
    if not prepared.get("wine_style"):
        prepared["wine_style"] = infer_style(
            "",
            prepared.get("major_region", ""),
            None,
            prepared.get("label", ""),
        )
    if not prepared.get("grapes"):
        prepared["grapes"] = infer_grapes(
            prepared.get("label", ""),
            prepared.get("region", ""),
            prepared.get("major_region", ""),
            prepared["wine_style"],
        )
    if not prepared.get("major_region"):
        prepared["major_region"] = prepared.get("region", "")
    price = prepared.get("price") or 0
    prepared["price"] = int(price) if isinstance(price, float) and price.is_integer() else price
    prepared["price_range"] = price_range(int(float(prepared["price"])))
    prepared["text"] = compose_text(prepared)
    if not prepared.get("id"):
        prepared["id"] = hashlib.md5(
            f"{prepared['producer']}_{prepared['label']}_{prepared['grapes']}_{prepared['region']}_{prepared['country']}".encode()
        ).hexdigest()
    return prepared


def _metadata(wine: dict) -> dict:
    metadata = {
        "producer": wine.get("producer", ""),
        "label": wine.get("label", ""),
        "wine_name": wine.get("label", ""),
        "grapes": wine.get("grapes", ""),
        "region": wine.get("region", ""),
        "sub_region": wine.get("sub_region", ""),
        "major_region": wine.get("major_region", ""),
        "country": wine.get("country", ""),
        "vintage": wine.get("vintage", ""),
        "text": wine.get("text", ""),
        "sync_version": 2,
        "price_range": wine.get("price_range", ""),
        "price": wine.get("price", 0),
        "wine_style": wine.get("wine_style", ""),
        "wine_type": wine.get("wine_style", ""),
        "tasting_keywords": "",
        "list_id": LIST_ID,
        "qr_id": QR_ID,
        "restaurant": RESTAURANT,
        "source": "wine_master",
        "in_stock": bool(wine.get("in_stock", True)),
        "last_edit_date": wine.get("last_edit_date") or "",
        "master_id": wine.get("id", ""),
    }
    if wine.get("inventory_count") is not None:
        metadata["inventory_count"] = int(wine["inventory_count"])
    return metadata


def _upsert_batches(index, vectors: list[dict]) -> None:
    batch = 100
    for i in range(0, len(vectors), batch):
        index.upsert(vectors=vectors[i : i + batch], namespace=NAMESPACE)
        print(f"Upserted {min(i + batch, len(vectors))}/{len(vectors)}")


def upsert_wines(wines: list[dict]) -> int:
    """Publish wines into the restaurant search list, then drop stale rows."""
    pc = Pinecone(api_key=settings.pinecone_api_key)
    index = pc.Index(settings.pinecone_index_name)
    prepared = [_prepare_wine(wine) for wine in wines]
    vectors = [
        {
            "id": f"maass_{wine['id']}",
            "values": hash_vector(wine["text"]),
            "metadata": _metadata(wine),
        }
        for wine in prepared
    ]
    new_ids = {vector["id"] for vector in vectors}
    _upsert_batches(index, vectors)
    try:
        stale = [wine_id for wine_id in _list_ids(index, NAMESPACE) if wine_id not in new_ids]
        for i in range(0, len(stale), 100):
            index.delete(ids=stale[i : i + 100], namespace=NAMESPACE)
        if stale:
            print(f"Removed {len(stale)} stale wines from {NAMESPACE}")
    except Exception as exc:
        print(f"Prune failed ({exc}); replacing {NAMESPACE}")
        index.delete(delete_all=True, namespace=NAMESPACE)
        _upsert_batches(index, vectors)
    return len(vectors)


def main() -> None:
    from data.wine_master import load_wines, master_exists

    if master_exists():
        wines = load_wines()
        print(f"Loaded {len(wines)} wines from the wine master")
    else:
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

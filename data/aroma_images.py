"""Aroma pictures for tasting notes. Matches are stored on the bottle."""
from __future__ import annotations

import io
import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FOLDER = ROOT / "wine_aromas_images"
MAX_IMAGES = 4
MAX_NUMBER = 163

# Extra phrases that mean the same picture. Longer phrases are tried first.
_ALIASES = {
    "004": ("green apple",),
    "005": ("yellow apple",),
    "034": ("blackcurrant", "black currant", "cassis"),
    "074": ("star anise", "licorice", "liquorice", "anise"),
    "081": ("brioche", "toast", "bread crust"),
    "084": ("dark chocolate", "chocolate"),
    "092": ("wet stone", "wet stones", "crushed stone"),
    "095": ("slate", "mineral", "minerality", "mineral edge"),
    "101": ("oyster shell", "salinity", "saline"),
    "069": ("black pepper", "peppery"),
    "076": ("vanilla",),
    "077": ("oak", "oaky"),
    "080": ("smoke", "smoky"),
    "044": ("honey", "honeyed"),
    "008": ("citrus",),
    "015": ("stone fruit",),
    "027": ("red cherry", "red cherries", "cherry", "cherries", "red fruit"),
    "030": ("plum", "plums"),
    "032": ("berries", "berry", "wild berries"),
    "031": ("red currant",),
    "035": ("dark cherry", "dark cherries", "black fruit", "dark fruit"),
    "037": ("olive", "olives"),
    "048": ("violets",),
    "060": ("crushed herbs", "herbs", "herb"),

    "083": ("espresso", "espresso bean"),
    "149": ("pine", "resin", "pine needle"),
    "155": ("dried herb", "oregano"),
    "156": ("pencil", "pencil shaving", "pencil lead"),
    "096": ("undergrowth", "underbrush"),
    "099": ("iron",),
    "151": ("autumn leaves", "wet leaves", "fallen leaves"),
    "153": ("damp soil", "wet soil", "damp earth", "earth", "earthy"),
    "158": ("game", "gamey"),
    "159": ("meaty",),
    "160": ("warm brick", "terracotta"),
    "161": ("savory", "savoury"),
    "057": ("sappy green", "sappy"),
    "163": ("spice", "spices", "baking spice"),
}


def _label(slug: str) -> str:
    return slug.replace("_", " ")


def catalog() -> list[dict]:
    items = []
    if not FOLDER.is_dir():
        return items
    for path in sorted(FOLDER.glob("[0-9][0-9][0-9]_*.jpg")):
        match = re.match(r"(\d{3})_(.+)\.jpg$", path.name)
        if not match:
            continue
        number = match.group(1)
        if not 4 <= int(number) <= MAX_NUMBER:
            continue
        slug = match.group(2)
        phrases = [_label(slug)]
        for extra in _ALIASES.get(number, ()):
            if extra not in phrases:
                phrases.append(extra)
        items.append({
            "id": number,
            "file": path.name,
            "label": _label(slug),
            "phrases": phrases,
        })
    return items


@lru_cache(maxsize=1)
def _catalog() -> tuple:
    return tuple(
        (item["id"], item["file"], item["label"], tuple(item["phrases"]))
        for item in catalog()
    )


def match_aromas(note: str, limit: int = MAX_IMAGES) -> list[dict]:
    """Up to four pictures named in the note, in the order they are mentioned."""
    text = (note or "").lower().replace("’", "'")
    if not text.strip():
        return []
    hits = []
    for number, filename, label, phrases in _catalog():
        for phrase in phrases:
            pattern = r"\b" + re.escape(phrase.lower()) + r"\b"
            for found in re.finditer(pattern, text):
                hits.append((len(phrase), found.start(), found.span(), number, filename, label))
    hits.sort(key=lambda hit: (-hit[0], hit[1]))
    chosen = []
    spans = []
    seen = set()
    for _length, start, span, number, filename, label in hits:
        if number in seen:
            continue
        if any(span[0] < end and start_at < span[1] for start_at, end in spans):
            continue
        seen.add(number)
        chosen.append((start, {"id": number, "file": filename, "label": label}))
        spans.append(span)
    chosen.sort(key=lambda item: item[0])
    return [item for _start, item in chosen[:limit]]


def pictures_for(note: str, stored_ids) -> tuple[list[dict], list[str] | None]:
    """Use the remembered pictures, or match the note and return ids to store."""
    known = {number: {"id": number, "file": filename, "label": label} for number, filename, label, _phrases in _catalog()}
    if stored_ids is not None:
        items = [known[number] for number in stored_ids if number in known][:MAX_IMAGES]
        return aroma_payload(items), None
    items = match_aromas(note)
    return aroma_payload(items), [item["id"] for item in items]


def aroma_payload(items: list[dict]) -> list[dict]:
    return [
        {
            "id": item["id"],
            "label": item["label"],
            "src": f"/aromas/{item['id']}.jpg?v=2",
        }
        for item in items
    ]


def file_for(number: str) -> Path | None:
    number = (number or "").strip()
    if not re.fullmatch(r"\d{3}", number):
        return None
    if not 4 <= int(number) <= MAX_NUMBER:
        return None
    matches = list(FOLDER.glob(f"{number}_*.jpg"))
    return matches[0] if matches else None


def _focus_crop(image):
    """Square crop on the subject. These shots leave the object low and centered."""
    width, height = image.size
    side = int(min(width, height) * 0.56)
    center_x = width // 2
    center_y = int(height * 0.56)
    left = max(0, min(width - side, center_x - side // 2))
    top = max(0, min(height - side, center_y - side // 2))
    return image.crop((left, top, left + side, top + side))


@lru_cache(maxsize=128)
def thumbnail(number: str, edge: int = 220) -> bytes | None:
    path = file_for(number)
    if path is None or not path.is_file():
        return None
    from PIL import Image

    image = _focus_crop(Image.open(path).convert("RGB"))
    image.thumbnail((edge, edge))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=82, optimize=True)
    return buffer.getvalue()

"""The one wine master.

Admin edits are stored in data/wine_master.json. save_all rewrites
data/winelist_temp.md from that file and publishes the same rows to the
live search list. Do not keep a second hand-edited copy.
"""
from __future__ import annotations

import json
import threading
import uuid
from datetime import date, datetime
from pathlib import Path

MASTER_PATH = Path(__file__).parent / "wine_master.json"
MD_PATH = Path(__file__).parent / "winelist_temp.md"
_lock = threading.Lock()

_VISIBLE = (
    "producer",
    "label",
    "vintage",
    "country",
    "region",
    "sub_region",
    "price",
    "inventory_count",
    "in_stock",
)


def master_exists() -> bool:
    return MASTER_PATH.exists()


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def _style_heading(style: str | None) -> str:
    value = (style or "red").strip().lower()
    return {
        "red": "Reds",
        "white": "Whites",
        "sparkling": "Sparkling",
        "rose": "Rose",
        "rosé": "Rose",
    }.get(value, "Reds")


def _clean_cell(value: object) -> str:
    return str(value or "").replace("|", "/").strip()


def parse_price(value: object) -> int | float:
    if isinstance(value, bool) or value is None or value == "":
        raise ValueError("price is required")
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        text = str(value).strip().replace("$", "").replace(",", "")
        if not text:
            raise ValueError("price is required")
        number = float(text)
    if number < 0:
        raise ValueError("price cannot be negative")
    if number.is_integer():
        return int(number)
    return round(number, 2)


def _inventory(value: object) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ValueError("inventory_count must be a number")
    if isinstance(value, (int, float)):
        number = int(value)
    else:
        text = str(value).strip()
        if not text:
            return None
        if not text.isdigit():
            raise ValueError("inventory_count must be a whole number")
        number = int(text)
    if number < 0:
        raise ValueError("inventory_count cannot be negative")
    return number


def _as_bool(value: object, default: bool = True) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in {"0", "false", "no", "out", "out_of_stock"}


def wine_is_in_stock(metadata: dict | None) -> bool:
    if not metadata:
        return True
    return _as_bool(metadata.get("in_stock", True), default=True)


def _bottle_key(wine: dict) -> tuple:
    return (
        str(wine.get("producer") or "").strip().lower(),
        str(wine.get("label") or wine.get("wine_name") or "").strip().lower(),
        str(wine.get("vintage") or "").strip().lower(),
        str(wine.get("region") or "").strip().lower(),
    )


def guest_stock() -> tuple[dict, dict]:
    """In-stock flags from the master, keyed by id and by bottle."""
    by_id: dict[str, bool] = {}
    by_bottle: dict[tuple, bool] = {}
    for wine in load_wines():
        stocked = wine_is_in_stock(wine)
        wine_id = str(wine.get("id") or "")
        if wine_id:
            by_id[wine_id] = stocked
        bottle = _bottle_key(wine)
        by_bottle[bottle] = by_bottle.get(bottle, False) or stocked
    return by_id, by_bottle


def visible_to_guest(metadata: dict | None, by_id: dict | None = None, by_bottle: dict | None = None) -> bool:
    """A bottle can be shown or recommended only when the master says it is in stock."""
    if not metadata or not wine_is_in_stock(metadata):
        return False
    if by_id is None or by_bottle is None:
        by_id, by_bottle = guest_stock()
    master_id = str(metadata.get("master_id") or metadata.get("id") or "")
    if master_id and master_id in by_id:
        return bool(by_id[master_id])
    bottle = _bottle_key(metadata)
    if bottle in by_bottle:
        return bool(by_bottle[bottle])
    if master_id:
        return False
    return False


def _blank_record() -> dict:
    return {
        "id": uuid.uuid4().hex,
        "producer": "",
        "label": "",
        "vintage": "",
        "country": "",
        "region": "",
        "sub_region": "",
        "major_region": "",
        "price": 0,
        "grapes": "",
        "wine_style": "",
        "last_edit_date": date.today().isoformat(),
        "inventory_count": 1,
        "in_stock": True,
        "tasting_note": "",
    }


def load_wines() -> list[dict]:
    if not MASTER_PATH.exists():
        return []
    payload = json.loads(MASTER_PATH.read_text(encoding="utf-8"))
    wines = payload.get("wines", payload if isinstance(payload, list) else [])
    return [dict(wine) for wine in wines]


def _record_from_parsed(wine: dict, default_date: str) -> dict:
    record = _blank_record()
    record.update(
        {
            "producer": wine.get("producer", ""),
            "label": wine.get("label", ""),
            "vintage": wine.get("vintage", ""),
            "country": wine.get("country", ""),
            "region": wine.get("region", ""),
            "sub_region": wine.get("sub_region", ""),
            "major_region": wine.get("major_region") or wine.get("region", ""),
            "price": wine.get("price", 0),
            "grapes": wine.get("grapes", ""),
            "wine_style": wine.get("wine_style", ""),
            "last_edit_date": wine.get("last_edit_date") or default_date,
            "inventory_count": 1 if wine.get("inventory_count") is None else wine.get("inventory_count"),
            "in_stock": wine.get("in_stock", True),
            "tasting_note": wine.get("tasting_note") or "",
        }
    )
    if record["inventory_count"] == 0:
        record["in_stock"] = False
    return record


def import_markdown() -> list[dict]:
    from ingest_winelist_temp import parse_list

    if not MD_PATH.exists():
        return []
    default_date = datetime.fromtimestamp(MD_PATH.stat().st_mtime).date().isoformat()
    parsed = parse_list(MD_PATH.read_text(encoding="utf-8"))
    return [_record_from_parsed(wine, default_date) for wine in parsed]


def _fill_inventory(wines: list[dict]) -> bool:
    changed = False
    for wine in wines:
        if wine.get("inventory_count") is None:
            wine["inventory_count"] = 1
            changed = True
        if wine.get("inventory_count") == 0 and wine.get("in_stock", True):
            wine["in_stock"] = False
            changed = True
    return changed


def ensure_master() -> list[dict]:
    with _lock:
        if MASTER_PATH.exists():
            wines = load_wines()
        else:
            wines = import_markdown()
        if _fill_inventory(wines) or not MASTER_PATH.exists():
            _write_master(wines)
            _atomic_write(MD_PATH, render_markdown(wines))
        return wines


def note_worth_saving(note: str) -> bool:
    text = (note or "").strip()
    if len(text) < 40:
        return False
    if text.startswith("A ") and " featuring " in text:
        return False
    return True


def save_tasting_note(wine_id: str, note: str) -> None:
    """Store a finished tasting note on the master wine so the next open is instant."""
    text = (note or "").strip()
    if not note_worth_saving(text):
        return
    with _lock:
        wines = load_wines()
        for wine in wines:
            if wine.get("id") != wine_id:
                continue
            if (wine.get("tasting_note") or "").strip() == text:
                return
            wine["tasting_note"] = text
            _write_master(wines)
            return


def _write_master(wines: list[dict]) -> None:
    payload = {"version": 1, "wines": wines}
    _atomic_write(MASTER_PATH, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def render_markdown(wines: list[dict]) -> str:
    lines = [
        "Winelist for Jarvis",
        "",
        "Generated from data/wine_master.json. Edit wines in the admin dashboard. save_all rewrites this file.",
        "",
    ]
    current_major = None
    current_style = None
    for wine in wines:
        major = _clean_cell(wine.get("major_region") or wine.get("region") or wine.get("country") or "List")
        style = _style_heading(wine.get("wine_style"))
        if major != current_major:
            lines.append(major)
            current_major = major
            current_style = None
        if style != current_style:
            lines.append(style)
            current_style = style
        price = wine.get("price", 0)
        price_text = str(int(price)) if isinstance(price, float) and float(price).is_integer() else str(price)
        inventory = wine.get("inventory_count")
        inventory_text = "" if inventory is None else str(inventory)
        stock = "in" if wine.get("in_stock", True) else "out"
        lines.append(
            " | ".join(
                [
                    _clean_cell(wine.get("vintage")),
                    _clean_cell(wine.get("producer")),
                    _clean_cell(wine.get("label")),
                    _clean_cell(wine.get("region")),
                    _clean_cell(wine.get("country")),
                    f"${price_text}",
                    _clean_cell(wine.get("sub_region")),
                    inventory_text,
                    stock,
                    _clean_cell(wine.get("last_edit_date")),
                ]
            )
        )
    lines.append("")
    return "\n".join(lines)


def _changed(old: dict, new: dict) -> bool:
    for field in _VISIBLE:
        if old.get(field) != new.get(field):
            return True
    return False


def normalize_wines(rows: list[dict], previous: list[dict] | None = None) -> list[dict]:
    previous_by_id = {wine["id"]: wine for wine in (previous or []) if wine.get("id")}
    today = date.today().isoformat()
    cleaned = []
    errors = []
    seen_ids = set()
    for index, raw in enumerate(rows, start=1):
        try:
            wine_id = str(raw.get("id") or "").strip() or uuid.uuid4().hex
            if wine_id in seen_ids:
                wine_id = uuid.uuid4().hex
            seen_ids.add(wine_id)
            old = previous_by_id.get(wine_id, {})
            producer = _clean_cell(raw.get("producer"))
            label = _clean_cell(raw.get("label"))
            if not producer or not label:
                raise ValueError("producer and label are required")
            inventory = _inventory(raw.get("inventory_count"))
            if inventory is None:
                inventory = 1
            in_stock = _as_bool(raw.get("in_stock", True))
            if inventory == 0:
                in_stock = False
            record = {
                "id": wine_id,
                "producer": producer,
                "label": label,
                "vintage": _clean_cell(raw.get("vintage")),
                "country": _clean_cell(raw.get("country")),
                "region": _clean_cell(raw.get("region")),
                "sub_region": _clean_cell(raw.get("sub_region")),
                "major_region": _clean_cell(raw.get("major_region") or old.get("major_region") or raw.get("region")),
                "price": parse_price(raw.get("price")),
                "grapes": _clean_cell(raw.get("grapes") or old.get("grapes")),
                "wine_style": _clean_cell(raw.get("wine_style") or old.get("wine_style")).lower(),
                "inventory_count": inventory,
                "in_stock": in_stock,
                "tasting_note": (raw.get("tasting_note") or old.get("tasting_note") or "").strip(),
                "last_edit_date": old.get("last_edit_date") or today,
            }
            if not old or _changed(old, record):
                record["last_edit_date"] = today
            cleaned.append(record)
        except ValueError as exc:
            errors.append(f"Row {index}: {exc}")
    if errors:
        raise ValueError("; ".join(errors[:8]))
    return cleaned


def save_all(rows: list[dict]) -> dict:
    """Write the master, regenerate the markdown list, publish live search."""
    with _lock:
        previous = load_wines() if MASTER_PATH.exists() else []
        wines = normalize_wines(rows, previous)
        from ingest_winelist_temp import _prepare_wine

        wines = [_prepare_wine(wine) for wine in wines]
        _write_master(wines)
        _atomic_write(MD_PATH, render_markdown(wines))
    pinecone_updated = False
    pinecone_error = ""
    try:
        from ingest_winelist_temp import upsert_wines

        upsert_wines(wines)
        pinecone_updated = True
    except Exception as exc:
        pinecone_error = str(exc)
    if pinecone_updated:
        message = f"Saved {len(wines)} wines. The live list matches this master."
    else:
        message = (
            f"Saved {len(wines)} wines to the master. "
            f"The live search list did not update: {pinecone_error}"
        )
    return {
        "saved": len(wines),
        "wines": wines,
        "pinecone_updated": pinecone_updated,
        "message": message,
    }

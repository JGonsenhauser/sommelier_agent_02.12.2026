"""The one wine master.

On the live site this is Redis, so an admin save survives the next visit.
Without Redis, the same records sit in data/wine_master.json.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
WINE_FILE = ROOT / "data" / "wine_master.json"
LIST_FILE = ROOT / "data" / "winelist_temp.md"
ACTIVITY_FILE = ROOT / "data" / "activity_log.jsonl"
WINES_KEY = "jarvis:wine_master:v1"
ACTIVITY_KEY = "jarvis:activity:v1"
BLOB_WINES = "jarvis-wine-master.json"
BLOB_ACTIVITY = "jarvis-activity.json"
_lock = threading.Lock()
_client = None
_client_ready = False
_redis_error = ""


def _blob_token() -> str:
    return (os.getenv("BLOB_READ_WRITE_TOKEN") or "").strip()


def _blob_store_id(token: str) -> str:
    parts = token.split("_")
    return parts[3] if len(parts) > 3 else ""


def _blob_put(pathname: str, text: str) -> None:
    token = _blob_token()
    body = text.encode("utf-8")
    request = urllib.request.Request(
        "https://vercel.com/api/blob/?" + urllib.parse.urlencode({"pathname": pathname}),
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "x-api-version": "12",
            "x-vercel-blob-store-id": _blob_store_id(token),
            "x-content-type": "application/json",
            "x-add-random-suffix": "0",
            "x-allow-overwrite": "1",
            "x-vercel-blob-access": "private",
        },
        method="PUT",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        response.read()


def _blob_get(pathname: str) -> str | None:
    token = _blob_token()
    # cache=0 reads the latest overwrite. A normal blob URL can stay stale for a minute.
    url = f"https://{_blob_store_id(token)}.private.blob.vercel-storage.com/{pathname}?cache=0"
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def redis_status() -> str:
    url = (os.getenv("REDIS_URL") or "").strip()
    if not url:
        return "missing"
    if _redis() is not None:
        return "ok"
    return _redis_error or "unreachable"


def _redis():
    global _client, _client_ready, _redis_error
    if _client_ready:
        return _client
    _client_ready = True
    url = (os.getenv("REDIS_URL") or "").strip()
    if not url:
        _redis_error = "missing"
        return None
    try:
        import redis

        client = redis.Redis.from_url(url, socket_connect_timeout=8, decode_responses=True)
        client.ping()
        _client = client
        _redis_error = ""
    except Exception as exc:
        _redis_error = f"{type(exc).__name__}: {str(exc).replace(url, '')[:180]}"
        logger.error("Wine master could not reach Redis: %s", _redis_error)
        _client = None
    return _client


def _stable_id(wine: dict) -> str:
    found = str(wine.get("id") or "").strip()
    if found:
        return found
    raw = "|".join(
        str(wine.get(field) or "").strip().lower()
        for field in ("producer", "label", "vintage", "region")
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _from_parsed(wine: dict) -> dict:
    inventory = wine.get("inventory_count")
    if inventory is None:
        inventory = 1
    in_stock = wine.get("in_stock", True)
    if inventory == 0:
        in_stock = False
    record = {
        "id": _stable_id(wine),
        "producer": wine.get("producer") or "",
        "label": wine.get("label") or "",
        "vintage": str(wine.get("vintage") or ""),
        "country": wine.get("country") or "",
        "region": wine.get("region") or "",
        "sub_region": wine.get("sub_region") or "",
        "major_region": wine.get("major_region") or wine.get("region") or "",
        "price": int(wine.get("price") or 0),
        "grapes": wine.get("grapes") or "",
        "wine_style": (wine.get("wine_style") or "").lower(),
        "inventory_count": inventory,
        "in_stock": bool(in_stock),
        "tasting_note": (wine.get("tasting_note") or "").strip(),
        "last_edit_date": wine.get("last_edit_date") or date.today().isoformat(),
    }
    if "aroma_ids" in wine:
        record["aroma_ids"] = _clean_aroma_ids(wine.get("aroma_ids"))
    return record


def _clean_aroma_ids(value) -> list[str]:
    cleaned = []
    for item in value or []:
        number = str(item or "").strip()
        if len(number) == 3 and number.isdigit() and number not in cleaned:
            cleaned.append(number)
        if len(cleaned) == 4:
            break
    return cleaned


def _seed_from_markdown() -> list[dict]:
    from ingest_winelist_temp import parse_list

    if not LIST_FILE.exists():
        return []
    return [_from_parsed(wine) for wine in parse_list(LIST_FILE.read_text(encoding="utf-8"))]


def _read_file() -> list[dict]:
    if not WINE_FILE.exists():
        return []
    payload = json.loads(WINE_FILE.read_text(encoding="utf-8"))
    wines = payload.get("wines", payload if isinstance(payload, list) else [])
    return [_from_parsed(wine) for wine in wines]


def _write_file(wines: list[dict]) -> None:
    WINE_FILE.parent.mkdir(parents=True, exist_ok=True)
    WINE_FILE.write_text(
        json.dumps({"version": 1, "wines": wines}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def load_wines() -> list[dict]:
    """Read the one master. Blob is the live store. Redis is the fallback."""
    client = _redis()
    with _lock:
        if _blob_token():
            raw = _blob_get(BLOB_WINES)
            if raw:
                payload = json.loads(raw)
                stored = payload.get("wines")
                if isinstance(stored, list) and stored:
                    return [_from_parsed(wine) for wine in stored]
            wines = _seed_from_markdown()
            _blob_put(BLOB_WINES, json.dumps({"version": 1, "wines": wines}))
            return wines
        if client is not None:
            raw = client.get(WINES_KEY)
            if raw:
                payload = json.loads(raw)
                return [_from_parsed(wine) for wine in payload.get("wines", [])]
            wines = _seed_from_markdown()
            client.set(WINES_KEY, json.dumps({"version": 1, "wines": wines}))
            return wines
        if os.getenv("VERCEL"):
            raise RuntimeError("The master database is not reachable: " + redis_status())
        wines = _read_file()
        if wines:
            return wines
        wines = _seed_from_markdown()
        if wines:
            _write_file(wines)
        return wines


def guest_wines() -> list[dict]:
    return [wine for wine in load_wines() if wine.get("in_stock", True) and wine.get("inventory_count") != 0]


def save_wines(wines: list[dict]) -> list[dict]:
    cleaned = [_from_parsed(wine) for wine in wines]
    payload = json.dumps({"version": 1, "wines": cleaned})
    client = _redis()
    with _lock:
        if _blob_token():
            _blob_put(BLOB_WINES, payload)
        elif os.getenv("VERCEL"):
            raise RuntimeError("The wine list could not be saved. The master database is not reachable.")
        elif client is not None:
            client.set(WINES_KEY, payload)
        else:
            _write_file(cleaned)
    return cleaned


def _bottle_family(wine: dict) -> tuple[str, str, str]:
    producer = (wine.get("producer") or "").strip().lower()
    label = (wine.get("label") or wine.get("wine_name") or "").strip().lower()
    vintage = str(wine.get("vintage") or "").strip().lower()
    return producer, label, vintage


def other_vintage_notes(wine: dict, wines: list) -> list[tuple[str, str]]:
    """Notes already stored for other years of this producer and label."""
    producer, label, vintage = _bottle_family(wine)
    if not producer or not label:
        return []
    my_id = str(wine.get("id") or wine.get("wine_id") or "")
    found = []
    for other in wines:
        other_id = str(other.get("id") or other.get("wine_id") or "")
        if my_id and other_id == my_id:
            continue
        other_producer, other_label, other_vintage = _bottle_family(other)
        if (other_producer, other_label) != (producer, label) or other_vintage == vintage:
            continue
        text = (other.get("tasting_note") or "").strip()
        if text:
            found.append((str(other.get("vintage") or "another year"), text))
    return found


def _note_words(wine: dict, note: str) -> str:
    """Drop the shared name and year so two vintages are compared by what they say."""
    text = (note or "").lower()
    for token in (
        wine.get("producer"),
        wine.get("label"),
        wine.get("wine_name"),
        wine.get("region"),
        wine.get("grapes"),
        wine.get("vintage"),
    ):
        word = str(token or "").strip().lower()
        if len(word) > 2:
            text = text.replace(word, " ")
    return " ".join(text.split())


def note_repeats_other_vintage(wine: dict, note: str, wines: list) -> bool:
    """True when this text matches another vintage of the same producer and label."""
    from difflib import SequenceMatcher

    text = (note or "").strip().lower()
    if len(text) < 40:
        return False
    producer, label, vintage = _bottle_family(wine)
    if not producer or not label:
        return False
    my_id = str(wine.get("id") or wine.get("wine_id") or "")
    mine = _note_words(wine, text)
    for other in wines:
        other_id = str(other.get("id") or other.get("wine_id") or "")
        if my_id and other_id == my_id:
            continue
        other_producer, other_label, other_vintage = _bottle_family(other)
        if (other_producer, other_label) != (producer, label) or other_vintage == vintage:
            continue
        other_note = (other.get("tasting_note") or "").strip().lower()
        if not other_note:
            continue
        if text == other_note:
            return True
        other_words = _note_words(other, other_note)
        if mine and other_words and (
            mine == other_words or SequenceMatcher(None, mine, other_words).ratio() > 0.72
        ):
            return True
    return False


def save_tasting_note(wine_id: str, note: str) -> None:
    save_tasting_notes({wine_id: note})


def save_tasting_notes(updates: dict) -> None:
    """Write every note in one pass so a second bottle cannot erase the first."""
    cleaned = {}
    for wine_id, note in (updates or {}).items():
        text = (note or "").strip()
        key = str(wine_id or "").strip()
        if key and len(text) >= 40:
            cleaned[key] = text
    if not cleaned:
        return
    wines = load_wines()
    changed = False
    for wine in wines:
        text = cleaned.get(wine.get("id") or "")
        if not text or (wine.get("tasting_note") or "").strip() == text:
            continue
        others = [item for item in wines if item.get("id") != wine.get("id")]
        if note_repeats_other_vintage(wine, text, others):
            continue
        wine["tasting_note"] = text
        changed = True
    if changed:
        save_wines(wines)


def save_aroma_ids(updates: dict) -> None:
    """Remember which aroma pictures belong to each bottle. One write for the batch."""
    cleaned = {}
    for wine_id, numbers in (updates or {}).items():
        key = str(wine_id or "").strip()
        if key:
            cleaned[key] = _clean_aroma_ids(numbers)
    if not cleaned:
        return
    wines = load_wines()
    changed = False
    for wine in wines:
        key = wine.get("id") or ""
        if key not in cleaned:
            continue
        if wine.get("aroma_ids") == cleaned[key]:
            continue
        wine["aroma_ids"] = cleaned[key]
        changed = True
    if changed:
        save_wines(wines)


def normalize_admin_rows(rows: list[dict], previous: list[dict]) -> list[dict]:
    previous_by_id = {wine["id"]: wine for wine in previous if wine.get("id")}
    today = date.today().isoformat()
    cleaned = []
    errors = []
    seen = set()
    for index, raw in enumerate(rows, start=1):
        try:
            producer = str(raw.get("producer") or "").strip()
            label = str(raw.get("label") or "").strip()
            if not producer or not label:
                raise ValueError("producer and label are required")
            wine_id = str(raw.get("id") or "").strip() or uuid.uuid4().hex[:16]
            if wine_id in seen:
                wine_id = uuid.uuid4().hex[:16]
            seen.add(wine_id)
            old = previous_by_id.get(wine_id, {})
            inventory = raw.get("inventory_count")
            if inventory is None or inventory == "":
                inventory = 1
            inventory = int(inventory)
            if inventory < 0:
                raise ValueError("inventory cannot be negative")
            price = raw.get("price")
            if price is None or price == "":
                raise ValueError("price is required")
            price = float(str(price).replace("$", "").replace(",", ""))
            if price < 0:
                raise ValueError("price cannot be negative")
            if float(price).is_integer():
                price = int(price)
            in_stock = raw.get("in_stock", True)
            if isinstance(in_stock, str):
                in_stock = in_stock.strip().lower() not in {"0", "false", "no", "out", "out_of_stock"}
            if inventory == 0:
                in_stock = False
            record = _from_parsed(
                {
                    **old,
                    **raw,
                    "id": wine_id,
                    "producer": producer,
                    "label": label,
                    "price": price,
                    "inventory_count": inventory,
                    "in_stock": bool(in_stock),
                    "tasting_note": raw.get("tasting_note") or old.get("tasting_note") or "",
                    "grapes": raw.get("grapes") or old.get("grapes") or "",
                    "wine_style": raw.get("wine_style") or old.get("wine_style") or "",
                    "major_region": raw.get("major_region") or old.get("major_region") or raw.get("region") or "",
                }
            )
            visible = ("producer", "label", "vintage", "country", "region", "sub_region", "price", "inventory_count", "in_stock")
            if not old or any(old.get(field) != record.get(field) for field in visible):
                record["last_edit_date"] = today
            else:
                record["last_edit_date"] = old.get("last_edit_date") or today
            cleaned.append(record)
        except (TypeError, ValueError) as exc:
            errors.append(f"Row {index}: {exc}")
    kept = []
    for record in cleaned:
        if note_repeats_other_vintage(record, record.get("tasting_note") or "", kept):
            record["tasting_note"] = ""
        kept.append(record)
    if errors:
        raise ValueError("; ".join(errors[:8]))
    return cleaned


def append_event(event: dict) -> None:
    line = json.dumps(event, ensure_ascii=False)
    client = _redis()
    with _lock:
        if _blob_token():
            current = _blob_get(BLOB_ACTIVITY)
            events = json.loads(current) if current else []
            events.append(json.loads(line))
            _blob_put(BLOB_ACTIVITY, json.dumps(events))
            return
        if client is not None:
            client.rpush(ACTIVITY_KEY, line)
            return
        if os.getenv("VERCEL"):
            return
        ACTIVITY_FILE.parent.mkdir(parents=True, exist_ok=True)
        with ACTIVITY_FILE.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")


def read_events() -> list[dict]:
    client = _redis()
    lines: list[str] = []
    blob_events: list[dict] | None = None
    with _lock:
        if _blob_token():
            current = _blob_get(BLOB_ACTIVITY)
            blob_events = json.loads(current) if current else []
        elif client is not None:
            lines = client.lrange(ACTIVITY_KEY, 0, -1) or []
        elif ACTIVITY_FILE.exists():
            lines = ACTIVITY_FILE.read_text(encoding="utf-8").splitlines()
    if blob_events is not None:
        return blob_events
    events = []
    for line in lines:
        line = (line or "").strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def write_events(events: list[dict]) -> None:
    """Replace the activity log. Used to drop guest email addresses."""
    client = _redis()
    with _lock:
        if _blob_token():
            _blob_put(BLOB_ACTIVITY, json.dumps(events, ensure_ascii=False))
            return
        if client is not None:
            client.delete(ACTIVITY_KEY)
            for event in events:
                client.rpush(ACTIVITY_KEY, json.dumps(event, ensure_ascii=False))
            return
        if os.getenv("VERCEL"):
            return
        ACTIVITY_FILE.parent.mkdir(parents=True, exist_ok=True)
        lines = [json.dumps(event, ensure_ascii=False) for event in events]
        ACTIVITY_FILE.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def clear_events() -> None:
    client = _redis()
    with _lock:
        if _blob_token():
            _blob_put(BLOB_ACTIVITY, "[]")
            return
        if client is not None:
            client.delete(ACTIVITY_KEY)
            return
        if ACTIVITY_FILE.exists():
            ACTIVITY_FILE.unlink()

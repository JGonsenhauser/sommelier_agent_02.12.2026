"""Guest search counts for the admin information tab.

One append-only log. Wine records themselves stay in the wine master.
"""
from __future__ import annotations

import json
import logging
import re
import threading
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

LOG_PATH = Path(__file__).parent / "activity_log.jsonl"
_lock = threading.Lock()

_STOP = {
    "a", "an", "the", "for", "and", "with", "from", "around", "about",
    "under", "over", "than", "less", "more", "wine", "wines", "please",
    "something", "looking", "want", "need", "me", "my", "to", "of", "in",
    "on", "at", "by", "or", "red", "white", "rose", "rosé", "champagne",
    "sparkling", "full", "bodied", "light", "crisp", "medium", "preferences",
    "drink", "food", "steak", "seafood", "pasta", "cheese", "any", "price",
    "body", "color", "just", "like", "some", "that", "this", "very",
}


def _append(event: dict) -> None:
    from data.master_store import append_event

    append_event(event)


def _read() -> list[dict]:
    from data.master_store import read_events

    return read_events()


def normalize_color(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip().lower()
    if "champagne" in text or "sparkling" in text:
        return "sparkling"
    if "rosé" in text or re.search(r"\brose\b", text):
        return "rosé"
    if re.search(r"\bred\b", text):
        return "red"
    if re.search(r"\bwhite\b", text):
        return "white"
    return None


_COLOR_LABEL = {"red": "Red", "white": "White", "rosé": "Rosé", "sparkling": "Sparkling"}


def color_label(value: str) -> str:
    return _COLOR_LABEL.get(value, value)


def normalize_price(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip().lower()
    if text in {"any", "any price"}:
        return "any price"
    under = re.search(r"under\s*\$?\s*(\d+)", text)
    if under:
        return f"under ${under.group(1)}"
    around = re.search(r"(?:around|about)\s*\$?\s*(\d+)", text)
    if around:
        return f"around ${around.group(1)}"
    band = re.search(r"\$?\s*(\d+)\s*[-–]\s*\$?\s*(\d+)", text)
    if band:
        return f"${band.group(1)}–${band.group(2)}"
    return None


def keywords_from_text(text: str | None) -> list[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z'-]{2,}", (text or "").lower())
    return [word for word in words if word not in _STOP]


_FILLER = {
    "a", "an", "the", "for", "and", "with", "from", "to", "of", "in",
    "on", "at", "by", "or", "me", "my", "please", "just", "like", "some",
    "that", "this", "very", "wine", "wines", "something", "looking",
    "want", "need", "about", "around",
}

_BUTTON_LABELS = {
    "color": {
        "white": "White",
        "red": "Red",
        "rose": "Rosé",
        "rosé": "Rosé",
        "champagne": "Champagne",
    },
    "body": {
        "light": "Light",
        "crisp": "Crisp",
        "medium": "Medium",
        "full": "Full",
    },
    "price": {
        "under $10": "Under $10",
        "under $20": "Under $20",
        "under $35": "Under $35",
        "any price": "Any price",
    },
    "food": {
        "steak": "Steak",
        "seafood": "Seafood",
        "pasta": "Pasta",
        "cheese": "Cheese",
    },
}


def description_terms(text: str | None) -> list[str]:
    """Words typed in the text box, used to describe a wine."""
    seen = []
    for word in re.findall(r"[a-zA-Z][a-zA-Z'-]{2,}", (text or "").lower()):
        if word in _FILLER or word in seen:
            continue
        seen.append(word.capitalize())
    return seen


def selected_buttons(
    color: str | None = None,
    body: str | None = None,
    price: str | None = None,
    food: str | None = None,
) -> list[str]:
    """Labels of the guide buttons chosen for this search."""
    labels = []
    for section, value in (
        ("color", color),
        ("body", body),
        ("price", price),
        ("food", food),
    ):
        if not value:
            continue
        key = value.strip().lower()
        labels.append(_BUTTON_LABELS[section].get(key, value.strip()))
    return labels


def _typed_from_query(query: str) -> str:
    if ". Preferences:" in query:
        return query.split(". Preferences:", 1)[0].strip()
    return query or ""


def _place_names(wines: list[dict]) -> dict[str, str]:
    names: dict[str, str] = {}
    for wine in wines:
        for field in ("major_region", "region", "sub_region", "country"):
            name = str(wine.get(field) or "").strip()
            if len(name) >= 3:
                names.setdefault(name.lower(), name)
    return names


def regions_mentioned(text: str, wines: list[dict]) -> list[str]:
    blob = (text or "").lower()
    if not blob.strip():
        return []
    occupied = [False] * len(blob)
    found: list[str] = []
    for key in sorted(_place_names(wines), key=len, reverse=True):
        start = 0
        while True:
            index = blob.find(key, start)
            if index < 0:
                break
            end = index + len(key)
            before = index == 0 or not blob[index - 1].isalnum()
            after = end >= len(blob) or not blob[end].isalnum()
            if before and after and not any(occupied[index:end]):
                for mark in range(index, end):
                    occupied[mark] = True
                found.append(_place_names(wines)[key])
                break
            start = index + 1
    return found


def _lexicon(wines: list[dict]) -> set[str]:
    words = set(_STOP)
    for wine in wines:
        blob = " ".join(
            str(wine.get(field) or "")
            for field in (
                "producer", "label", "region", "sub_region", "country",
                "major_region", "grapes", "wine_style",
            )
        )
        words.update(keywords_from_text(blob))
    return words


def unmatched_terms(text: str, wines: list[dict]) -> list[str]:
    known = _lexicon(wines)
    seen = []
    for word in keywords_from_text(text):
        if word not in known and word not in seen:
            seen.append(word)
    return seen


def record_search(
    query: str,
    color: str | None = None,
    price_band: str | None = None,
    text: str | None = None,
    wines: list[dict] | None = None,
    body: str | None = None,
    food: str | None = None,
    button_labels: list[str] | None = None,
) -> None:
    query = (query or "").strip()
    if not query:
        return
    typed = text if text is not None else _typed_from_query(query)
    catalog = wines or []
    blob = f"{typed} {query}"
    chosen = [str(label).strip() for label in (button_labels or []) if str(label).strip()]
    _append(
        {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "kind": "search",
            "color": normalize_color(color) or normalize_color(query),
            "price": normalize_price(price_band) or normalize_price(query),
            "buttons": chosen or selected_buttons(color, body, price_band, food),
            "descriptions": description_terms(typed),
            "regions": regions_mentioned(blob, catalog),
            "unmatched": unmatched_terms(typed, catalog),
        }
    )


def record_email(email: str, wines: list[dict] | None = None, producer: str = "", label: str = "", vintage: str = "") -> None:
    """Log bottles that were emailed. Guest addresses are not stored on this demo."""
    del email
    names = []
    for wine in wines or []:
        name = " ".join(
            part
            for part in (
                str(wine.get("vintage") or ""),
                str(wine.get("producer") or ""),
                str(wine.get("wine_name") or wine.get("label") or ""),
            )
            if part
        ).strip()
        if name:
            names.append(name)
    if not names:
        single = " ".join(part for part in (vintage, producer, label) if part).strip()
        if single:
            names.append(single)
    if not names:
        return
    _append(
        {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "kind": "email",
            "wines": names,
            "wine": names[0],
        }
    )


def redact_stored_emails() -> int:
    """Delete guest email addresses already saved in the activity log."""
    events = _read()
    removed = 0
    for event in events:
        if event.pop("email", None):
            removed += 1
    if removed:
        from data.master_store import write_events

        write_events(events)
    return removed


def _ranked(counter: Counter) -> list[dict]:
    return [{"value": value, "count": count} for value, count in counter.most_common() if value]


_DEMO_MISSED_PRODUCERS = ("Screaming Eagle", "Harlan Estate")
_DEMO_MISSED_GRAPES = (
    ("California Primitivo", ("california",), "primitivo"),
    ("Australian Sangiovese", ("australia",), "sangiovese"),
)


def _carries_place_grape(wines: list[dict], places: tuple[str, ...], grape: str) -> bool:
    grape = grape.lower()
    for wine in wines:
        grapes = str(wine.get("grapes") or "").lower()
        if grape not in grapes:
            continue
        place = " ".join(
            str(wine.get(field) or "")
            for field in ("country", "major_region", "region", "sub_region")
        ).lower()
        if any(name in place for name in places):
            return True
    return False


def demo_missed_searches(wines: list[dict]) -> list[dict]:
    """Producers and place-specific grapes a guest can ask for that this list does not carry."""
    producers = {str(wine.get("producer") or "").strip().lower() for wine in wines}
    rows = []
    for name in _DEMO_MISSED_PRODUCERS:
        if not any(name.lower() in producer for producer in producers if producer):
            rows.append({"value": name, "count": 1})
    for label, places, grape in _DEMO_MISSED_GRAPES:
        if not _carries_place_grape(wines, places, grape):
            rows.append({"value": label, "count": 1})
    return rows


def clear_activity() -> None:
    from data.master_store import clear_events

    clear_events()


def insights(wines: list[dict]) -> dict:
    try:
        redact_stored_emails()
    except Exception:
        logger.warning("Could not remove stored guest emails", exc_info=True)
    colors: Counter = Counter()
    prices: Counter = Counter()
    buttons: Counter = Counter()
    descriptions: Counter = Counter()
    regions: Counter = Counter()
    emailed: Counter = Counter()
    sends: list[dict] = []
    for event in _read():
        kind = event.get("kind")
        if kind == "search":
            color = event.get("color")
            if color == "champagne":
                color = "sparkling"
            if color:
                colors[color_label(color)] += 1
            if event.get("price"):
                prices[event["price"]] += 1
            for label in event.get("buttons") or []:
                buttons[label] += 1
            typed_terms = event.get("descriptions")
            if typed_terms is None and "buttons" not in event:
                typed_terms = event.get("keywords") or []
            for term in typed_terms or []:
                descriptions[term] += 1
            for region in event.get("regions") or []:
                regions[region] += 1
        elif kind == "email":
            names = [name for name in (event.get("wines") or []) if name]
            if not names and event.get("wine"):
                names = [event["wine"]]
            for name in names:
                emailed[name] += 1
            if names:
                sends.append(
                    {
                        "wines": names,
                        "ts": event.get("ts") or "",
                    }
                )
    return {
        "colors": _ranked(colors),
        "regions": _ranked(regions),
        "prices": _ranked(prices),
        "keywords": _ranked(buttons),
        "descriptions": _ranked(descriptions),
        "emailed": _ranked(emailed),
        "sends": list(reversed(sends))[:40],
        "search_count": sum(colors.values()),
    }

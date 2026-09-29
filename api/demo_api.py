"""Guest PWA: local wine list + optional Grok notes (Vercel / no Pinecone)."""
from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
from io import BytesIO
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")
logger = logging.getLogger(__name__)

from restaurants.restaurant_config import (
    get_restaurant_config,
    list_restaurant_configs,
    PRODUCT_LOGO,
    PRODUCT_NAME,
    GUEST_ID,
)
from data import crm_store
from data.mailer import build_body, send_wine_email
from data.sommelier_knowledge import (
    parse_intent,
    sommelier_score,
    passes_color_lock,
    passes_profile,
    approachable_note,
    guest_intro,
    named_miss_intro,
    complementary_picks,
)

MOBILE = ROOT / "mobile"
LIST_PATH = ROOT / "data" / "winelist_temp.md"
PUBLIC_BASE = (os.getenv("PUBLIC_BASE_URL") or "https://jarvis.agenthaus.io").strip().rstrip("/")

app = FastAPI(title="Jarvis Sommelier", docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[PUBLIC_BASE, "http://127.0.0.1:8000", "http://localhost:8000"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
crm_store.init_db()


def catalog() -> list:
    """In-stock bottles from the one master list."""
    from data.master_store import guest_wines

    return guest_wines()


def guest_url(restaurant_id: str = GUEST_ID) -> str:
    return f"{PUBLIC_BASE}/?r={restaurant_id}"


def _xai_key() -> str:
    raw = (os.getenv("XAI_API_KEY") or "").strip()
    if raw:
        if raw.startswith("xai-"):
            return raw
        try:
            from crypto_utils import SecureKeyManager
            return SecureKeyManager(encryption_key=os.getenv("ENCRYPTION_KEY")).decrypt_key(raw)
        except Exception:
            return raw
    connector = (os.getenv("CONNECT_XAI") or "").strip()
    if not connector:
        return ""
    try:
        from data.vercel_connect import get_token
        return get_token(connector, subject={"type": "app"}) or ""
    except Exception:
        return ""


def _qr_png_bytes(url: str) -> bytes:
    import qrcode
    qr = qrcode.QRCode(box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1C1A16", back_color="#F3EEE6")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


try:
    png = _qr_png_bytes(guest_url(GUEST_ID))
    (MOBILE / "qr.png").write_bytes(png)
except Exception:
    pass


GUEST_GROK_MODEL = "grok-4.20-0309-non-reasoning"


def _guest_grok_model() -> str:
    raw = (os.getenv("XAI_GUEST_MODEL") or "").strip()
    if raw:
        return raw
    chat = (os.getenv("XAI_CHAT_MODEL") or "").strip()
    if chat and "non-reasoning" in chat.lower():
        return chat
    if chat and "reasoning" in chat.lower():
        return GUEST_GROK_MODEL
    return chat or GUEST_GROK_MODEL


def _enrich_with_grok(query: str, wines: list, menu: list, restaurant_name: str):
    key = _xai_key()
    if not key or not wines:
        return wines, None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=key, base_url="https://api.x.ai/v1", timeout=6.0, max_retries=0)
        numbered = "\n".join(
            f"{i+1}. {w.get('vintage','')} {w.get('producer','')} {w.get('wine_name','')} "
            f"| {w.get('grapes','')} | {w.get('wine_type','')} | {w.get('region','')} | {w.get('country','')}"
            for i, w in enumerate(wines)
        )
        model = _guest_grok_model()
        kwargs = dict(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"You are the house sommelier at {restaurant_name}. "
                        "Bottles are already chosen. Do not change them. "
                        "Write like a kind person at the table. Everyday words. "
                        "Never call a Premier Cru a Grand Cru. Never call Napa Cab or Zinfandel "
                        "a Super Tuscan or Burgundy. Never call a French wine Italian. "
                        "Never call Pinot Noir Sangiovese. "
                        "Use the country on each line. Only describe the bottles given. "
                        "No jargon, scores, or 'notes of'. JSON only."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f'The guest said: "{query}"\n'
                        f"{numbered}\n"
                        "JSON only:\n"
                        '{"intro":"one sentence","picks":['
                        '{"n":1,"why":"one sentence","note":"two short everyday sentences"},'
                        '{"n":2,"why":"...","note":"..."}]}'
                    ),
                },
            ],
            temperature=0.3,
            max_tokens=220,
        )
        if model.startswith(("grok-4.5", "grok-4.6")):
            kwargs["extra_body"] = {"reasoning_effort": "low"}
        response = client.chat.completions.create(**kwargs)
        raw = (response.choices[0].message.content or "").strip()
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        payload = json.loads(match.group(0) if match else raw)
        intro = str(payload.get("intro") or "").strip() or None
        for item in payload.get("picks") or []:
            idx = int(item.get("n", 0)) - 1
            if 0 <= idx < len(wines):
                if item.get("why"):
                    wines[idx]["why"] = str(item["why"]).strip()
                if item.get("note"):
                    wines[idx]["tasting_note"] = str(item["note"]).strip()
        return wines, intro
    except Exception as exc:
        logger.warning("Grok notes skipped: %s", exc)
        return wines, None


def _grok_pick_and_note(query: str, ranked: list, restaurant_name: str):
    """Master-sommelier pick from wines that already passed hard filters.

    Returns (picked_catalog_rows, intro) or (None, None) to fall back to the ranker.
    """
    key = _xai_key()
    pool = [w for w in ranked if float(w.get("_score") or 0) > -1][:12]
    if not key or len(pool) < 1:
        return None, None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=key, base_url="https://api.x.ai/v1", timeout=6.0, max_retries=0)
        numbered = "\n".join(
            f"{i+1}. {w.get('vintage','')} {w.get('producer','')} {w.get('label') or w.get('wine_name','')} "
            f"| {w.get('grapes','')} | {w.get('region','')} | {w.get('country','')} | ${w.get('price','')}"
            for i, w in enumerate(pool)
        )
        model = _guest_grok_model()
        kwargs = dict(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"You are a Master Sommelier at {restaurant_name}. "
                        "Choose only from the numbered list. Never invent a bottle. "
                        "Old World = Europe (France, Italy, Spain, Germany, Portugal). "
                        "New World = USA, Australia, Chile, Argentina, New Zealand, South Africa. "
                        "Syrah Old World = Northern Rhône, not Australian Shiraz. "
                        "If no bottle on the list truly matches, return {\"intro\":\"...\",\"picks\":[]}. "
                        "Pick exactly two bottles. Never mention a region or grape that is not on those two lines. "
                        "Everyday words. JSON only."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f'The guest said: "{query}"\n'
                        f"{numbered}\n"
                        "JSON only:\n"
                        '{"intro":"one sentence","picks":['
                        '{"n":1,"why":"one sentence","note":"two short everyday sentences"},'
                        '{"n":2,"why":"...","note":"..."}]}'
                    ),
                },
            ],
            temperature=0.2,
            max_tokens=280,
        )
        if model.startswith(("grok-4.5", "grok-4.6")):
            kwargs["extra_body"] = {"reasoning_effort": "low"}
        response = client.chat.completions.create(**kwargs)
        raw = (response.choices[0].message.content or "").strip()
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        payload = json.loads(match.group(0) if match else raw)
        intro = str(payload.get("intro") or "").strip() or None
        picked = []
        seen = set()
        for item in (payload.get("picks") or [])[:2]:
            idx = int(item.get("n", 0)) - 1
            if 0 <= idx < len(pool) and idx not in seen:
                seen.add(idx)
                wine = dict(pool[idx])
                if item.get("why"):
                    wine["_grok_why"] = str(item["why"]).strip()
                if item.get("note"):
                    wine["_grok_note"] = str(item["note"]).strip()
                picked.append(wine)
        return picked, intro
    except Exception as exc:
        logger.warning("Grok pick skipped: %s", exc)
        return None, None


_GENERIC_NOTE = (
    "more savory than sweet",
    "tastes like the place",
    "earthy here means",
    "leads with fruit, not oak",
    "straightforward in the glass",
    "straightforward, and true to the place",
    "enough snap for tomato sauce",
)


def _generic_note(text: str) -> bool:
    low = (text or "").lower()
    if any(phrase in low for phrase in _GENERIC_NOTE):
        return True
    return "one sentence" in low or "this bottle only" in low


def _stored_note_ready(wine: dict, rows: list) -> bool:
    """A saved note can be shown as-is. The request does not need to write one."""
    from data.master_store import note_repeats_other_vintage

    note = (wine.get("tasting_note") or "").strip()
    if len(note) <= 40 or _generic_note(note):
        return False
    check = {
        "id": wine.get("wine_id") or wine.get("id") or "",
        "producer": wine.get("producer") or "",
        "label": wine.get("wine_name") or wine.get("label") or "",
        "vintage": wine.get("vintage") or "",
    }
    return not note_repeats_other_vintage(check, note, rows)


def _keep_why(text: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned or _generic_note(cleaned):
        return ""
    return cleaned


def _notes_too_alike(notes: list[str]) -> bool:
    if len(notes) < 2:
        return False
    from difflib import SequenceMatcher
    a, b = notes[0].lower(), notes[1].lower()
    if SequenceMatcher(None, a, b).ratio() > 0.62:
        return True
    words_a = set(a.split())
    words_b = set(b.split())
    shared = [word for word in words_a & words_b if len(word) > 4]
    return len(shared) > 8


def _fallback_note(wine: dict) -> str:
    producer = wine.get("producer") or "This grower"
    label = wine.get("label") or wine.get("wine_name") or "this bottle"
    region = wine.get("region") or "its region"
    grapes = wine.get("grapes") or "the grape on the label"
    year = str(wine.get("vintage") or "").strip()
    if not year.isdigit():
        return (
            f"{producer} {label} is {grapes} from {region}. "
            "This bottling has its own shape and is not another year of the same wine."
        )
    shapes = (
        "tight and herbal, slow to open",
        "ripe and dark through the middle",
        "fragrant first, then firm",
        "lean, savory, and stony",
        "soft, round, and ready earlier",
        "deep, spicy, and closed",
        "bright, salty, and quick on the finish",
    )
    fruits = (
        "sour cherry and orange peel",
        "blackberry and cedar",
        "raspberry and dried rose",
        "plum and tobacco",
        "cranberry and white pepper",
        "black cherry and cocoa",
        "red currant and bay leaf",
    )
    number = int(year)
    return (
        f"{year} {producer} {label}: {shapes[number % len(shapes)]}. "
        f"Fruit runs to {fruits[(number * 3) % len(fruits)]}."
    )


def _write_distinct_notes(query: str, wines: list, restaurant_name: str) -> bool:
    """One tasting note per bottle, tied to that producer, grape, and place."""
    key = _xai_key()
    if not key or not wines:
        return False
    lines = "\n".join(
        f"{i+1}. {w.get('vintage','')} {w.get('producer','')} {w.get('wine_name') or w.get('label','')} "
        f"| grapes: {w.get('grapes') or 'unknown'} | {w.get('region','')} | {w.get('country','')}"
        for i, w in enumerate(wines)
    )
    try:
        from openai import OpenAI
        client = OpenAI(api_key=key, base_url="https://api.x.ai/v1", timeout=14.0, max_retries=0)
        model = _guest_grok_model()
        response = client.chat.completions.create(
            model=model,
            temperature=0.4,
            max_tokens=420,
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"You are the sommelier at {restaurant_name}. "
                        "Write a different tasting note for each numbered bottle. "
                        "Each note is two or three sentences and must name that vintage year, "
                        "the producer, the grape, and the village or region on that line. "
                        "Say what that grower is known for in that place. "
                        "A different vintage of the same producer and label must get a different note. "
                        "Do not reuse a sentence, an aroma list, or a closing line. "
                        "Never write 'more savory than sweet', 'tastes like the place', "
                        "'Earthy here means', 'one sentence', or 'this bottle only'. "
                        "Write place names in plain letters. JSON only."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f'Guest: "{query}"\n{lines}\n'
                        'JSON only: {"notes":[{"n":1,"note":"two or three sentences naming this producer, grape, and place"},'
                        '{"n":2,"note":"two or three different sentences for the second bottle"}]}'
                    ),
                },
            ],
        )
        raw = (response.choices[0].message.content or "").strip()
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        payload = json.loads(match.group(0) if match else raw)
        by_index = {}
        for item in payload.get("notes") or []:
            idx = int(item.get("n", 0)) - 1
            note = str(item.get("note") or "").strip()
            if 0 <= idx < len(wines) and note and not _generic_note(note):
                by_index[idx] = note
        if len(by_index) != len(wines):
            return False
        texts = [by_index[i] for i in range(len(wines))]
        if _notes_too_alike(texts):
            return False
        for i, wine in enumerate(wines):
            wine["tasting_note"] = by_index[i]
            wine["why"] = ""
        return True
    except Exception as exc:
        logger.warning("Distinct notes skipped: %s", exc)
        return False


class RecommendationRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    restaurant_id: str = GUEST_ID
    channel: str = "pwa"
    text: str | None = None
    buttons: list[str] | None = None
    language: str | None = None


class EmailWineNote(BaseModel):
    wine_id: str
    tasting_note: str = ""


class EmailWineRequest(BaseModel):
    email: str
    restaurant_id: str = GUEST_ID
    recommendation_id: str | None = None
    wine_ids: list[str] | None = None
    notes: list[EmailWineNote] | None = None


def _price_filter(query: str):
    q = query.lower()
    m = re.search(r"between\s*\$?(\d+)\s*and\s*\$?(\d+)", q)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        return min(a, b), max(a, b)
    m = re.search(r"under\s*\$?(\d+)", q)
    if m:
        return None, int(m.group(1))
    if "cellar" in q or "splurge" in q:
        return 252, None
    return None, None


def _price_chosen(query: str) -> bool:
    q = (query or "").lower()
    if "cellar" in q or "splurge" in q:
        return True
    if re.search(r"\b(?:under|over|around|about|between)\b", q) and re.search(r"\d", q):
        return True
    if re.search(r"\$\s?\d+", q):
        return True
    return False


def _amount(wine: dict) -> int:
    try:
        return int(float(wine.get("price") or 0))
    except (TypeError, ValueError):
        return 0


def _low_then_mid(wines: list) -> list:
    """One bottle under $100, then one over $101 and under $160."""
    from data.sommelier_knowledge import wine_key

    low = [wine for wine in wines if _amount(wine) < 100]
    mid = [wine for wine in wines if 101 < _amount(wine) < 160]
    chosen = []
    if low:
        chosen.append(low[0])
    if mid:
        partner = next(
            (wine for wine in mid if not chosen or wine_key(wine) != wine_key(chosen[0])),
            None,
        )
        if partner:
            chosen.append(partner)
    return chosen


def _style(query: str):
    intent = parse_intent(query)
    return intent.color


def _score(query: str, wine: dict) -> float:
    q = query.lower()
    hay = " ".join(
        str(wine.get(k, ""))
        for k in ("producer", "label", "grapes", "region", "major_region", "wine_style", "text")
    ).lower()
    tokens = [t for t in re.findall(r"[a-z]+", q) if len(t) > 2 and t not in {"wine", "with", "the", "and", "crisp", "clean"}]
    hits = sum(1 for t in tokens if t in hay)
    base = hits / max(len(tokens), 1)
    style = wine.get("wine_style", "")
    grapes = str(wine.get("grapes", "")).lower()
    if "steak" in q or "strip" in q:
        if style == "red":
            base += 0.4
        if any(g in grapes for g in ("cabernet", "nebbiolo", "sangiovese", "syrah", "malbec")):
            base += 0.4
    if "oyster" in q:
        if style in {"white", "sparkling"}:
            base += 0.5
        if any(g in grapes for g in ("chablis", "muscadet", "sauvignon")):
            base += 0.4
    if "chicken" in q and style in {"white", "red"}:
        base += 0.25
    if "pinot" in q and "pinot" in grapes:
        base += 0.6
    return sommelier_score(query, wine, base=base)


def _pair(query: str, wine: dict, menu: list) -> str | None:
    q = query.lower()
    mapping = [
        ("hard cheese", "Black Truffle Tagliatelle"),
        ("soft cheese", "Apple and Burrata"),
        ("cream sauce", "Black Truffle Tagliatelle"),
        ("branzino", "Black Cod"),
        ("oyster", "Wellfleet Oysters"),
        ("steak", "Prime NY Strip Gratin"),
        ("chicken", "Brioche Stuffed Amish Chicken"),
        ("caviar", "Kaluga Caviar"),
    ]
    for needle, dish in mapping:
        if needle in q:
            found = next((d for d in menu if d["name"] == dish), None)
            if found:
                return f"{found['name']} — {found['description']}"
    if wine.get("wine_style") == "red":
        found = next((d for d in menu if d["name"] == "Prime NY Strip Gratin"), None)
        if found and ("steak" in q or "strip" in q):
            return f"{found['name']} — {found['description']}"
    return None


def _guest_wine(wine: dict, query: str, menu: list, rank: int) -> dict:
    why, note = approachable_note(wine, query)
    return {
        "wine_id": wine.get("id") or f"demo_{wine['producer']}_{wine['label']}_{wine.get('vintage','')}".replace(" ", "_")[:80],
        "producer": wine["producer"],
        "wine_name": wine.get("label") or "",
        "region": wine.get("region") or "",
        "country": wine.get("country") or "",
        "vintage": str(wine.get("vintage") or ""),
        "price": str(wine.get("price") or ""),
        "grapes": wine.get("grapes") or "",
        "wine_type": wine.get("wine_style") or "",
        "tasting_note": (wine.get("tasting_note") or "").strip() or note,
        "why": why,
        "food_pairing": _pair(query, wine, menu),
        "score": wine.get("_score", 0),
    }


@app.get("/", include_in_schema=False)
async def index(request: Request):
    """Marketing page for a plain visit. QR links and the demo button open the guest app."""
    query = request.query_params
    if any(query.get(key) for key in ("demo", "r", "restaurant", "outlet")):
        return FileResponse(MOBILE / "index.html")
    return FileResponse(MOBILE / "landing.html")


@app.get("/demo", include_in_schema=False)
@app.get("/qr", include_in_schema=False)
@app.get("/showcase", include_in_schema=False)
@app.get("/showcase.html", include_in_schema=False)
async def showcase():
    return FileResponse(MOBILE / "showcase.html")


@app.get("/admin", include_in_schema=False)
async def admin():
    return FileResponse(MOBILE / "admin.html")


@app.get("/manifest.json", include_in_schema=False)
async def manifest(r: str = GUEST_ID):
    config = get_restaurant_config(r) or get_restaurant_config(GUEST_ID)
    public = config.to_public_dict() if config else {"name": PRODUCT_NAME}
    return JSONResponse(
        {
            "name": "Jarvis Sommelier",
            "short_name": "Jarvis",
            "start_url": f"/?r={GUEST_ID}",
            "display": "standalone",
            "background_color": public.get("background_color") or "#F3EEE6",
            "theme_color": public.get("background_color") or "#F3EEE6",
            "icons": [{"src": "brand-logo.png", "sizes": "512x512", "type": "image/png"}],
        }
    )


@app.get("/api/restaurants")
async def restaurants():
    return {"restaurants": [{"id": c.restaurant_id, "name": c.name} for c in list_restaurant_configs()]}


@app.get("/api/restaurants/{restaurant_id}")
async def restaurant(restaurant_id: str):
    config = get_restaurant_config(restaurant_id)
    if not config:
        raise HTTPException(404, "Restaurant not found")
    public = config.to_public_dict()
    public["wine_count"] = len(catalog())
    return public


OUTLET_IDS = ("pool", "in-room", "beach", "golf", "steakhouse")


@app.get("/api/outlets/{outlet_id}/qr.png", include_in_schema=False)
async def outlet_qr(outlet_id: str):
    if outlet_id not in OUTLET_IDS:
        raise HTTPException(404, "Outlet not found")
    return Response(
        _qr_png_bytes(f"{PUBLIC_BASE}/?outlet={outlet_id}"),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@app.get("/api/brand/logo", include_in_schema=False)
async def product_logo():
    if not PRODUCT_LOGO.exists():
        raise HTTPException(404, "Logo not found")
    return FileResponse(PRODUCT_LOGO)


@app.get("/api/restaurants/{restaurant_id}/logo", include_in_schema=False)
async def logo(restaurant_id: str):
    config = get_restaurant_config(restaurant_id)
    if config and config.branded and config.logo_path and Path(config.logo_path).exists():
        return FileResponse(config.logo_path)
    if PRODUCT_LOGO.exists():
        return FileResponse(PRODUCT_LOGO)
    raise HTTPException(404, "Logo not found")


@app.post("/api/recommend")
async def recommend(body: RecommendationRequest):
    try:
        from data.activity_log import record_search
        from data.master_store import load_wines

        record_search(
            body.query,
            text=body.text if body.text is not None else body.query,
            wines=load_wines(),
            button_labels=body.buttons or [],
        )
    except Exception as exc:
        logger.warning("Search log skipped: %s", exc)
    from data.guest_language import localize_answer, prepare_search

    search_query, answer_lang = prepare_search(body.text, body.query, body.language)
    config = get_restaurant_config(body.restaurant_id)
    if not config:
        raise HTTPException(404, "Restaurant not found")
    lo, hi = _price_filter(search_query)
    intent = parse_intent(search_query)
    style = intent.color

    def consider(wine, ignore_price=False):
        if wine.get("in_stock") is False or wine.get("inventory_count") == 0:
            return None
        price = int(wine["price"])
        if not ignore_price:
            if lo is not None and price < lo:
                return None
            if hi is not None and price > hi:
                return None
        if not passes_color_lock(search_query, wine):
            return None
        if not passes_profile(search_query, wine):
            return None
        item = dict(wine)
        item["_score"] = _score(search_query, wine)
        if ignore_price and hi is not None:
            item["_score"] -= abs(price - hi) / 500.0
        return item

    pool = [w for w in (consider(wine) for wine in catalog()) if w]
    relaxed = None
    # Cellar is a floor: never pad with a $20 bottle. One honest bottle is enough.
    if len(pool) < 2 and hi and not lo:
        relaxed = "Nothing sat in that exact price band; these are the closest that still match the style."
        pool = [w for w in (consider(wine, ignore_price=True) for wine in catalog()) if w]
    pool.sort(key=lambda w: w["_score"], reverse=True)
    ranked = [w for w in pool if w["_score"] > -1]
    seen = crm_store.recent_wine_keys(body.restaurant_id)
    picked = complementary_picks(ranked, seen_ids=seen, query=search_query)
    grok_intro = None
    if ranked and (intent.named or intent.world) and _price_chosen(search_query):
        grok_picked, grok_intro = _grok_pick_and_note(search_query, ranked, config.name)
        if grok_picked is not None:
            picked = grok_picked
    if not _price_chosen(search_query):
        paired = _low_then_mid(ranked or pool)
        if paired:
            picked = paired
    menu = config.load_menu()
    wines = [_guest_wine(w, search_query, menu, i) for i, w in enumerate(picked)]
    from data.master_store import load_wines, note_repeats_other_vintage, save_tasting_notes

    catalog_rows = load_wines()
    for src, dst in zip(picked, wines):
        if src.get("_grok_why"):
            dst["why"] = src["_grok_why"]
        stored = (src.get("tasting_note") or "").strip()
        if (
            len(stored) > 40
            and not _generic_note(stored)
            and not note_repeats_other_vintage(src, stored, catalog_rows)
        ):
            dst["tasting_note"] = stored
        elif src.get("_grok_note") and not _generic_note(src.get("_grok_note")):
            dst["tasting_note"] = src["_grok_note"]
    notes_ready = bool(picked) and all(_stored_note_ready(src, catalog_rows) for src in picked)
    if not notes_ready:
        if not grok_intro:
            wines, grok_intro = _enrich_with_grok(search_query, wines, menu, config.name)
        if wines and not _write_distinct_notes(search_query, wines, config.name):
            alike = _notes_too_alike([wine.get("tasting_note") or "" for wine in wines])
            for wine in wines:
                wine["why"] = ""
                if alike or _generic_note(wine.get("tasting_note") or ""):
                    wine["tasting_note"] = _fallback_note(wine)
        for wine in wines:
            if _stored_note_ready(wine, catalog_rows):
                continue
            check = {
                "id": wine.get("wine_id") or wine.get("id") or "",
                "producer": wine.get("producer") or "",
                "label": wine.get("wine_name") or wine.get("label") or "",
                "vintage": wine.get("vintage") or "",
            }
            wine["tasting_note"] = _ensure_tasting_note(check | {"grapes": wine.get("grapes"), "region": wine.get("region"), "country": wine.get("country"), "wine_style": wine.get("wine_type")})
        save_tasting_notes({
            (wine.get("wine_id") or wine.get("id") or ""): (wine.get("tasting_note") or "")
            for wine in wines
            if _stored_note_ready(wine, catalog_rows)
        })
    from data.aroma_images import pictures_for
    from data.master_store import save_aroma_ids

    aroma_updates = {}
    for src, dst in zip(picked, wines):
        stored = src.get("aroma_ids") if "aroma_ids" in src else None
        payload, fresh = pictures_for(dst.get("tasting_note") or "", stored)
        dst["aromas"] = payload
        wine_id = src.get("id") or dst.get("wine_id") or ""
        if fresh is not None and wine_id:
            aroma_updates[wine_id] = fresh
    if aroma_updates:
        try:
            save_aroma_ids(aroma_updates)
        except Exception:
            logger.warning("Could not remember aroma pictures", exc_info=True)
    intro = grok_intro or guest_intro(search_query)
    if not wines:
        intro = named_miss_intro(search_query) or (
            "Nothing on this list matched what you asked for. I won't substitute a random bottle."
        )
    if answer_lang != "en":
        intro, relaxed, wines = localize_answer(answer_lang, intro, relaxed, wines)
    rec_id = None
    if wines:
        rec_id = crm_store.log_recommendation(
            restaurant_id=body.restaurant_id,
            query=body.query,
            wines=wines,
            intro=intro,
            relaxed=relaxed or "",
            latency_ms=int(time.time() * 0) or 1,
            channel="demo",
        )
    return {
        "recommendation_id": rec_id,
        "intro": intro,
        "wines": [{k: v for k, v in w.items() if k != "score"} for w in wines],
        "query": body.query,
        "restaurant_name": config.name,
        "relaxed": relaxed,
        "language": answer_lang,
        "error": None,
    }


@app.post("/api/transcribe")
async def transcribe(request: Request):
    """Turn a short voice clip into text and a language code."""
    audio = await request.body()
    if not audio:
        raise HTTPException(400, "I didn't hear anything.")
    if len(audio) > 2_000_000:
        raise HTTPException(413, "That clip is too long. Try a shorter request.")
    try:
        from data.guest_language import transcribe_audio

        mime = (request.headers.get("content-type") or "audio/wav").split(";")[0].strip()
        return transcribe_audio(audio, mime, "guest.wav")
    except Exception as exc:
        logger.warning("Transcription failed: %s", exc)
        raise HTTPException(502, "I couldn't hear that. Please try again.") from exc


def _mail_row(wine: dict) -> dict:
    return {
        "wine_id": wine.get("id") or wine.get("wine_id") or "",
        "vintage": str(wine.get("vintage") or ""),
        "producer": wine.get("producer") or "",
        "wine_name": wine.get("label") or wine.get("wine_name") or "",
        "region": wine.get("region") or "",
        "price": wine.get("price") or "",
        "tasting_note": (wine.get("tasting_note") or "").strip(),
        "why": wine.get("why") or "",
        "food_pairing": wine.get("food_pairing") or "",
    }


@app.post("/api/email-wine")
async def email_wine(body: EmailWineRequest, request: Request):
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", body.email or ""):
        raise HTTPException(400, "Please enter a valid email.")
    chosen: list[dict] = []
    from data.master_store import load_wines, note_repeats_other_vintage, save_tasting_notes

    if body.wine_ids:

        by_id = {item.get("id"): item for item in load_wines()}
        for wine_id in body.wine_ids[:2]:
            wine = by_id.get(wine_id)
            if not wine or wine.get("in_stock") is False or wine.get("inventory_count") == 0:
                continue
            chosen.append(wine)
        if not chosen:
            raise HTTPException(404, "Select a bottle from the list.")
        shown = {
            (item.wine_id or "").strip(): (item.tasting_note or "").strip()
            for item in (body.notes or [])
        }
        to_store = {}
        for wine in chosen:
            note = shown.get(wine.get("id") or "")
            if (
                note
                and len(note) > 40
                and not _generic_note(note)
                and not note_repeats_other_vintage(wine, note, list(by_id.values()))
            ):
                wine["tasting_note"] = note[:1200]
                to_store[wine.get("id") or ""] = wine["tasting_note"]
        save_tasting_notes(to_store)
    else:
        row = crm_store.get_recommendation(body.recommendation_id or "")
        if not row:
            raise HTTPException(404, "Those bottles are no longer on this table.")
        chosen = json.loads(row["wines_json"] or "[]")
    for wine in chosen:
        current = (wine.get("tasting_note") or "").strip()
        if len(current) > 40 and not _generic_note(current):
            continue
        wine["tasting_note"] = _ensure_tasting_note(wine)
    wines = [_mail_row(wine) for wine in chosen]
    oidc = request.headers.get("x-vercel-oidc-token") or ""
    sent, status = send_wine_email(body.email, PRODUCT_NAME, wines, oidc=oidc)
    try:
        crm_store.log_email_lead(
            restaurant_id=body.restaurant_id,
            email=body.email,
            wines=wines,
            recommendation_id=body.recommendation_id,
            sent=sent,
            error="" if sent or status == "saved" else status,
        )
    except Exception as exc:
        logger.warning("Email lead skipped: %s", exc)
    if sent:
        try:
            from data.activity_log import record_email

            record_email(body.email, wines)
        except Exception as exc:
            logger.warning("Email log skipped: %s", exc)
        noun = "bottle" if len(wines) == 1 else "bottles"
        return {"ok": True, "message": f"Sent. Check your inbox for the {noun}."}
    if status == "saved":
        raise HTTPException(status_code=503, detail="Email is not connected yet.")
    logger.warning("Wine email failed: %s", status)
    raise HTTPException(status_code=502, detail="We could not send that just now. Please try again.")


@app.post("/api/admin/login")
async def admin_login(request: Request):
    data = await request.json()
    if data.get("password") != "maass-admin":
        raise HTTPException(401, "Wrong password")
    resp = JSONResponse({"ok": True})
    resp.set_cookie("jarvis_admin", "demo", httponly=True, samesite="lax")
    return resp


@app.get("/api/admin/report")
async def admin_report(request: Request, restaurant_id: str | None = None):
    if request.cookies.get("jarvis_admin") != "demo":
        raise HTTPException(401, "Admin login required")
    data = crm_store.report(restaurant_id=restaurant_id)
    recs = []
    for row in data["recommendations"]:
        wines = json.loads(row.get("wines_json") or "[]")
        recs.append(
            {
                "id": row["id"],
                "ts": row["ts"],
                "restaurant_id": row["restaurant_id"],
                "query": row["query"],
                "wines": wines,
            }
        )
    leads = [
        {
            "id": row["id"],
            "ts": row["ts"],
            "email": row["email"],
            "sent": bool(row["sent"]),
            "wines": json.loads(row.get("wines_json") or "[]"),
        }
        for row in data["leads"]
    ]
    return {"recommendations": recs, "leads": leads, "top_wines": data["top_wines"]}


@app.get("/api/health")
async def health(request: Request):
    from data.vercel_connect import oidc_token

    from data.master_store import redis_status

    return {
        "status": "live",
        "redis": redis_status(),
        "wines": len(catalog()),
        "grok": bool(_xai_key()),
        "connect": bool(oidc_token() or request.headers.get("x-vercel-oidc-token")),
        "public_base_url": PUBLIC_BASE,
    }


@app.get("/qr.png", include_in_schema=False)
async def qr_png():
    return Response(content=_qr_png_bytes(guest_url(GUEST_ID)), media_type="image/png")


def _public_bottle(wine: dict) -> dict:
    return {
        "id": wine.get("id") or "",
        "producer": wine.get("producer") or "",
        "label": wine.get("label") or "",
        "vintage": wine.get("vintage") or "",
        "country": wine.get("country") or "",
        "region": wine.get("region") or "",
        "sub_region": wine.get("sub_region") or "",
        "major_region": wine.get("major_region") or "",
        "price": wine.get("price"),
        "in_stock": bool(wine.get("in_stock", True)),
        "wine_style": wine.get("wine_style") or "",
        "tasting_note": (wine.get("tasting_note") or "").strip(),
        "inventory_count": wine.get("inventory_count", 1),
        "grapes": wine.get("grapes") or "",
        "last_edit_date": wine.get("last_edit_date") or "",
    }


def _bearer(request: Request) -> str:
    header = request.headers.get("authorization") or ""
    if header.lower().startswith("bearer "):
        return header.split(" ", 1)[1].strip()
    return ""


def _require_token(request: Request) -> None:
    from data.admin_access import session_ok

    if not session_ok(_bearer(request)):
        raise HTTPException(401, "Enter the admin pin.")


class AdminPinBody(BaseModel):
    pin: str


class AdminWineBody(BaseModel):
    wines: list


@app.get("/api/wines")
async def public_wine_list():
    from data.master_store import guest_wines

    wines = guest_wines()
    return {"wines": [_public_bottle(wine) for wine in wines], "count": len(wines)}


def _ensure_tasting_note(wine: dict) -> str:
    """Return this vintage's own note. Another year of the same wine cannot share it."""
    from data.master_store import load_wines, note_repeats_other_vintage, other_vintage_notes, save_tasting_note

    rows = load_wines()
    year = str(wine.get("vintage") or "").strip()
    producer = wine.get("producer") or ""
    label = wine.get("label") or wine.get("wine_name") or ""
    siblings = [f"{vintage}: {text}" for vintage, text in other_vintage_notes(wine, rows)]
    stored = (wine.get("tasting_note") or "").strip()
    if len(stored) > 40 and not _generic_note(stored) and not note_repeats_other_vintage(wine, stored, rows):
        return stored

    def acceptable(text: str) -> bool:
        return len(text) > 40 and not _generic_note(text) and not note_repeats_other_vintage(wine, text, rows)

    note = ""
    if _xai_key():
        sibling_block = "\n".join(siblings[:4]) or "None yet."
        try:
            from openai import OpenAI

            client = OpenAI(api_key=_xai_key(), base_url="https://api.x.ai/v1")
            reply = client.chat.completions.create(
                model=_guest_grok_model(),
                messages=[
                    {
                        "role": "user",
                        "content": (
                            "Write a tasting note in 3 sentences. No headers. "
                            f"This is only the {year or 'current'} vintage of {producer} {label} "
                            f"from {wine.get('region','')}, {wine.get('country','')}. "
                            f"Grapes: {wine.get('grapes','')}. Style: {wine.get('wine_style','')}. "
                            f"Name the year {year}. "
                            "A different vintage of this same producer and label must not share this note. "
                            f"Do not repeat these other vintages:\n{sibling_block}"
                        ),
                    }
                ],
                temperature=0.7,
                max_tokens=220,
            )
            generated = (reply.choices[0].message.content or "").strip()
            if acceptable(generated):
                note = generated
        except Exception as exc:
            logger.warning("Tasting note skipped: %s", exc)
    if not note:
        note = _fallback_note(wine)
    if acceptable(note):
        save_tasting_note(wine.get("id") or wine.get("wine_id") or "", note)
    return note


@app.get("/api/wines/{wine_id}/note")
async def public_tasting_note(wine_id: str):
    from data.master_store import load_wines

    wine = next((item for item in load_wines() if item.get("id") == wine_id), None)
    if not wine or wine.get("in_stock") is False or wine.get("inventory_count") == 0:
        raise HTTPException(404, "Wine not found")
    note = _ensure_tasting_note(wine)
    payload = _public_bottle(wine)
    payload["tasting_note"] = note
    return payload


@app.post("/api/admin/unlock")
async def admin_unlock(body: AdminPinBody):
    from data.admin_access import unlock

    try:
        token, demo = unlock(body.pin)
    except ValueError as exc:
        raise HTTPException(401, str(exc)) from exc
    return {"ok": True, "token": token, "demo": demo}


@app.post("/api/admin/demo")
async def admin_demo_session():
    """Open the demo back office. This session cannot write the live wine master."""
    from data.admin_access import open_demo_session

    return {"ok": True, "token": open_demo_session(), "demo": True}


@app.post("/api/admin/lock")
async def admin_lock(request: Request):
    from data.admin_access import drop_session

    drop_session(_bearer(request))
    return {"ok": True}


@app.get("/api/admin/wines")
async def admin_wines(request: Request):
    _require_token(request)
    from data.master_store import load_wines

    wines = load_wines()
    return {"wines": [_public_bottle(wine) for wine in wines], "count": len(wines)}


@app.post("/api/admin/wines")
async def admin_save_wines(body: AdminWineBody, request: Request):
    _require_token(request)
    from data.admin_access import session_is_demo
    from data.master_store import load_wines, normalize_admin_rows, save_wines

    if session_is_demo(_bearer(request)):
        current = load_wines()
        return {
            "saved": 0,
            "demo": True,
            "pinecone_updated": False,
            "message": "this is a demo",
            "wines": [_public_bottle(wine) for wine in current],
        }
    try:
        wines = normalize_admin_rows(body.wines, load_wines())
        saved = save_wines(wines)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    return {
        "saved": len(saved),
        "pinecone_updated": False,
        "message": f"Updated the list. {len(saved)} wines are on the master.",
        "wines": [_public_bottle(wine) for wine in saved],
    }


@app.get("/api/admin/insights")
async def admin_insights(request: Request):
    _require_token(request)
    from data.activity_log import demo_missed_searches, insights as activity_insights
    from data.admin_access import session_is_demo
    from data.master_store import load_wines

    wines = load_wines()
    payload = activity_insights(wines)
    if session_is_demo(_bearer(request)):
        payload["descriptions"] = demo_missed_searches(wines)
    return JSONResponse(payload, headers={"Cache-Control": "no-store"})


@app.post("/api/admin/insights/reset")
async def admin_reset_insights(body: AdminPinBody, request: Request):
    _require_token(request)
    from data.activity_log import clear_activity
    from data.admin_access import drop_session, session_is_demo, unlock

    try:
        extra, pin_is_demo = unlock(body.pin)
    except ValueError as exc:
        raise HTTPException(401, str(exc)) from exc
    drop_session(extra)
    if pin_is_demo or session_is_demo(_bearer(request)):
        return {"ok": True, "demo": True, "message": "this is a demo"}
    clear_activity()
    return {"ok": True}


@app.get("/aromas/{number}.jpg", include_in_schema=False)
async def aroma_image(number: str):
    from data.aroma_images import thumbnail

    body = thumbnail(number)
    if not body:
        raise HTTPException(404, "Aroma not found")
    return Response(body, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})


@app.get("/logo/{name}", include_in_schema=False)
async def agenthaus_logo(name: str):
    if name not in {"03-spine-ring.png", "agenthaus-mark.png"}:
        raise HTTPException(404, "Logo not found")
    path = ROOT / "logo" / name
    if not path.is_file():
        raise HTTPException(404, "Logo not found")
    return FileResponse(path)


app.mount("/", StaticFiles(directory=str(MOBILE), html=True), name="pwa")

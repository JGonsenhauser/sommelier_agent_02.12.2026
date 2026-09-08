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

from ingest_winelist_temp import parse_list
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
CATALOG = parse_list(LIST_PATH.read_text(encoding="utf-8"))


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


def _guest_grok_model() -> str:
    raw = (os.getenv("XAI_GUEST_MODEL") or os.getenv("XAI_CHAT_MODEL") or "grok-4-fast").strip()
    if "reasoning" in raw.lower():
        return "grok-4-fast"
    return raw or "grok-4-fast"


def _enrich_with_grok(query: str, wines: list, menu: list, restaurant_name: str):
    key = _xai_key()
    if not key or not wines:
        return wines, None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=key, base_url="https://api.x.ai/v1", timeout=6.0, max_retries=0)
        numbered = "\n".join(
            f"{i+1}. {w.get('vintage','')} {w.get('producer','')} {w.get('wine_name','')} "
            f"| {w.get('grapes','')} | {w.get('wine_type','')} | {w.get('region','')}"
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


class RecommendationRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    restaurant_id: str = GUEST_ID
    channel: str = "pwa"


class EmailWineRequest(BaseModel):
    email: str
    restaurant_id: str = GUEST_ID
    recommendation_id: str | None = None


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
        return 250, None
    return None, None


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
        if found and ("steak" in q or "red" in q):
            return f"{found['name']} — {found['description']}"
    return None


def _guest_wine(wine: dict, query: str, menu: list, rank: int) -> dict:
    why, note = approachable_note(wine, query)
    return {
        "wine_id": f"demo_{wine['producer']}_{wine['label']}_{wine.get('vintage','')}".replace(" ", "_")[:80],
        "producer": wine["producer"],
        "wine_name": wine.get("label") or "",
        "region": wine.get("region") or "",
        "country": wine.get("country") or "",
        "vintage": str(wine.get("vintage") or ""),
        "price": str(wine.get("price") or ""),
        "grapes": wine.get("grapes") or "",
        "wine_type": wine.get("wine_style") or "",
        "tasting_note": note,
        "why": why,
        "food_pairing": _pair(query, wine, menu),
        "score": wine.get("_score", 0),
    }


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(MOBILE / "index.html")


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
    public["wine_count"] = len(CATALOG)
    return public


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
    config = get_restaurant_config(body.restaurant_id)
    if not config:
        raise HTTPException(404, "Restaurant not found")
    lo, hi = _price_filter(body.query)
    intent = parse_intent(body.query)
    style = intent.color

    def consider(wine, ignore_price=False):
        price = int(wine["price"])
        if not ignore_price:
            if lo is not None and price < lo:
                return None
            if hi is not None and price > hi:
                return None
        if not passes_color_lock(body.query, wine):
            return None
        if not passes_profile(body.query, wine):
            return None
        item = dict(wine)
        item["_score"] = _score(body.query, wine)
        if ignore_price and hi is not None:
            item["_score"] -= abs(price - hi) / 500.0
        return item

    pool = [w for w in (consider(wine) for wine in CATALOG) if w]
    relaxed = None
    if len(pool) < 2 and (lo or hi):
        relaxed = "Nothing sat in that exact price band; these are the closest that still match the style."
        pool = [w for w in (consider(wine, ignore_price=True) for wine in CATALOG) if w]
    pool.sort(key=lambda w: w["_score"], reverse=True)
    ranked = [w for w in pool if w["_score"] > -1]
    seen = crm_store.recent_wine_keys(body.restaurant_id)
    picked = complementary_picks(ranked, seen_ids=seen)
    menu = config.load_menu()
    wines = [_guest_wine(w, body.query, menu, i) for i, w in enumerate(picked)]
    wines, grok_intro = _enrich_with_grok(body.query, wines, menu, config.name)
    intro = grok_intro or guest_intro(body.query)
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
        "error": None,
    }


@app.post("/api/email-wine")
async def email_wine(body: EmailWineRequest):
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", body.email or ""):
        raise HTTPException(400, "Please enter a valid email.")
    row = crm_store.get_recommendation(body.recommendation_id or "")
    if not row:
        raise HTTPException(404, "Those bottles are no longer on this table.")
    wines = json.loads(row["wines_json"] or "[]")
    sent, status = send_wine_email(body.email, PRODUCT_NAME, wines)
    crm_store.log_email_lead(
        restaurant_id=body.restaurant_id,
        email=body.email,
        wines=wines,
        recommendation_id=body.recommendation_id,
        sent=sent,
        error="" if sent or status == "saved" else status,
    )
    if sent:
        return {"ok": True, "message": "Sent. Check your inbox for the two bottles."}
    if status == "saved":
        return {"ok": True, "message": "Saved for you. The sommelier desk has a copy."}
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
async def health():
    from data.vercel_connect import oidc_token

    return {
        "status": "live",
        "wines": len(CATALOG),
        "grok": bool(_xai_key()),
        "connect": bool(oidc_token()),
        "public_base_url": PUBLIC_BASE,
    }


@app.get("/qr.png", include_in_schema=False)
async def qr_png():
    return Response(content=_qr_png_bytes(guest_url(GUEST_ID)), media_type="image/png")


app.mount("/", StaticFiles(directory=str(MOBILE), html=True), name="pwa")

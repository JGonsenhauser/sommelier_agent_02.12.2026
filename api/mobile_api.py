"""FastAPI backend: guest PWA, recommendations, email CRM, admin reports."""
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, Request, Response, Cookie
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
import hmac
import hashlib
import logging
import os
import re
import socket
import time
from collections import defaultdict, deque
from pathlib import Path

import qrcode

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import settings
from restaurants.restaurant_config import (
    get_restaurant_config,
    list_restaurant_configs,
    PRODUCT_LOGO,
    PRODUCT_NAME,
    GUEST_ID,
)
from restaurants.wine_recommender_optimized import OptimizedWineRecommender
from data.embedding_pipeline import EmbeddingError
from data import crm_store
from data.mailer import send_wine_email

ROOT_DIR = Path(__file__).parent.parent
MOBILE_DIR = ROOT_DIR / "mobile"
QR_PATH = ROOT_DIR / "restaurants" / "maass" / "static" / "maass_qr.png"
QR_MOBILE_PATH = MOBILE_DIR / "qr.png"
API_PORT = 8000
ADMIN_COOKIE = "jarvis_admin"

recommenders: Dict[str, OptimizedWineRecommender] = {}
_rate_hits: Dict[str, deque] = defaultdict(deque)


def detect_lan_ip() -> str:
    ips = []
    try:
        hostname = socket.gethostname()
        ips.extend(socket.gethostbyname_ex(hostname)[2])
    except Exception:
        pass
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.connect(("8.8.8.8", 80))
        ips.append(probe.getsockname()[0])
        probe.close()
    except Exception:
        pass
    for ip in ips:
        if ip.startswith("192.168."):
            return ip
    for ip in ips:
        if ip.startswith("10.") or ip.startswith("172.16.") or ip.startswith("172.17.") or ip.startswith("172.18."):
            return ip
    for ip in ips:
        if ip and not ip.startswith("127.") and not ip.startswith("100."):
            return ip
    return ips[0] if ips else "127.0.0.1"


def phone_base_url() -> str:
    public = (os.getenv("PUBLIC_BASE_URL") or settings.public_base_url or "").strip().rstrip("/")
    if public:
        return public
    return f"http://{detect_lan_ip()}:{API_PORT}"


def guest_url(restaurant_id: str = GUEST_ID) -> str:
    return f"{phone_base_url()}/?r={restaurant_id}"


def write_guest_qr(url: str) -> Path:
    QR_PATH.parent.mkdir(parents=True, exist_ok=True)
    MOBILE_DIR.mkdir(parents=True, exist_ok=True)
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=12,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1C1A16", back_color="#F3EEE6")
    try:
        img.save(str(QR_PATH))
        img.save(str(QR_MOBILE_PATH))
        logger.info("Guest QR points to %s", url)
    except OSError as exc:
        logger.warning("Could not write QR image (read-only disk): %s", exc)
    return QR_PATH


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(request: Request, max_hits: int = 30, window_s: int = 600) -> None:
    ip = _client_ip(request)
    now = time.time()
    hits = _rate_hits[ip]
    while hits and now - hits[0] > window_s:
        hits.popleft()
    if len(hits) >= max_hits:
        raise HTTPException(status_code=429, detail="Please wait a moment before asking again.")
    hits.append(now)


def _admin_secret() -> bytes:
    raw = (settings.admin_secret or settings.encryption_key or "dev-admin-secret").encode()
    return raw


def sign_admin() -> str:
    ts = str(int(time.time()))
    sig = hmac.new(_admin_secret(), ts.encode(), hashlib.sha256).hexdigest()
    return f"{ts}.{sig}"


def valid_admin(token: Optional[str]) -> bool:
    if not token or "." not in token:
        return False
    ts, sig = token.split(".", 1)
    try:
        age = time.time() - int(ts)
    except ValueError:
        return False
    if age > 60 * 60 * 24 * 7:
        return False
    expected = hmac.new(_admin_secret(), ts.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig, expected)


def require_admin(token: Optional[str]) -> None:
    if not valid_admin(token):
        raise HTTPException(status_code=401, detail="Admin login required")


PHONE_URL = phone_base_url()

app = FastAPI(
    title="Jarvis Sommelier API",
    description="Guest wine recommendations for restaurants and hotels",
    version="2.0.0",
    docs_url="/docs" if settings.environment == "development" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list(),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class GuestWine(BaseModel):
    wine_id: str
    producer: str
    wine_name: Optional[str] = ""
    region: str
    country: Optional[str] = ""
    vintage: Optional[str] = ""
    price: Optional[str] = ""
    grapes: Optional[str] = ""
    wine_type: str
    tasting_note: str
    why: Optional[str] = None
    food_pairing: Optional[str] = None


WineRecommendation = GuestWine


class RecommendationRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    restaurant_id: str = GUEST_ID
    channel: str = "pwa"


class RecommendationResponse(BaseModel):
    recommendation_id: Optional[str] = None
    intro: Optional[str] = None
    wines: List[GuestWine]
    query: str
    restaurant_name: str
    relaxed: Optional[str] = None
    error: Optional[str] = None


class EmailWineRequest(BaseModel):
    email: str
    restaurant_id: str = GUEST_ID
    recommendation_id: Optional[str] = None


class AdminLoginRequest(BaseModel):
    password: str


def get_recommender(restaurant_id: str) -> OptimizedWineRecommender:
    config = get_restaurant_config(restaurant_id)
    if not config:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    key = config.restaurant_id
    if key not in recommenders:
        recommenders[key] = OptimizedWineRecommender(config)
    return recommenders[key]


def to_guest_wine(wine: dict) -> GuestWine:
    return GuestWine(
        wine_id=str(wine.get("wine_id") or ""),
        producer=wine.get("producer") or "",
        wine_name=wine.get("wine_name") or "",
        region=wine.get("region") or "",
        country=wine.get("country") or "",
        vintage=str(wine.get("vintage") or ""),
        price=str(wine.get("price") or ""),
        grapes=wine.get("grapes") or "",
        wine_type=wine.get("wine_type") or "",
        tasting_note=wine.get("tasting_note") or "",
        why=wine.get("why") or None,
        food_pairing=wine.get("food_pairing"),
    )


@app.get("/", include_in_schema=False)
async def pwa_index():
    return FileResponse(MOBILE_DIR / "index.html")


@app.get("/demo", include_in_schema=False)
@app.get("/qr", include_in_schema=False)
@app.get("/showcase", include_in_schema=False)
@app.get("/showcase.html", include_in_schema=False)
async def showcase_page():
    return FileResponse(MOBILE_DIR / "showcase.html")


@app.get("/admin", include_in_schema=False)
async def admin_page():
    return FileResponse(MOBILE_DIR / "admin.html")


@app.get("/manifest.json", include_in_schema=False)
async def dynamic_manifest(r: str = GUEST_ID):
    config = get_restaurant_config(r) or get_restaurant_config(GUEST_ID)
    return JSONResponse(
        {
            "name": "Jarvis Sommelier",
            "short_name": "Jarvis",
            "description": "Your sommelier",
            "start_url": f"/?r={GUEST_ID}",
            "scope": "/",
            "display": "standalone",
            "background_color": config.background_color if config else "#F3EEE6",
            "theme_color": config.background_color if config else "#F3EEE6",
            "orientation": "portrait",
            "icons": [
                {"src": "brand-logo.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
                {"src": "apple-touch-icon.png", "sizes": "180x180", "type": "image/png", "purpose": "any"},
            ],
        }
    )


@app.get("/api/restaurants")
async def list_restaurants():
    return {
        "restaurants": [
            {"id": c.restaurant_id, "name": c.name, "location": c.location}
            for c in list_restaurant_configs()
        ]
    }


@app.get("/api/restaurants/{restaurant_id}")
async def get_restaurant(restaurant_id: str):
    config = get_restaurant_config(restaurant_id)
    if not config:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    public = config.to_public_dict()
    rec = recommenders.get(restaurant_id)
    if rec:
        catalog = rec.pipeline._namespace_catalog.get(config.namespace) or []
        public["wine_count"] = len(catalog)
    return public


@app.get("/api/brand/logo", include_in_schema=False)
async def product_logo():
    if not PRODUCT_LOGO.exists():
        raise HTTPException(status_code=404, detail="Logo not found")
    return FileResponse(PRODUCT_LOGO)


@app.get("/api/restaurants/{restaurant_id}/logo", include_in_schema=False)
async def restaurant_logo(restaurant_id: str):
    config = get_restaurant_config(restaurant_id)
    if config and config.branded and config.logo_path and Path(config.logo_path).exists():
        return FileResponse(config.logo_path)
    if PRODUCT_LOGO.exists():
        return FileResponse(PRODUCT_LOGO)
    raise HTTPException(status_code=404, detail="Logo not found")


@app.post("/api/recommend")
async def recommend_wines(request: RecommendationRequest, raw: Request) -> RecommendationResponse:
    rate_limit(raw, max_hits=40, window_s=600)
    start_time = time.time()
    config = get_restaurant_config(request.restaurant_id)
    if not config:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    recommender = get_recommender(request.restaurant_id)
    try:
        wines, intro, relaxed = recommender.recommend(request.query)
        guest = [to_guest_wine(w) for w in wines]
        rec_id = None
        if wines:
            rec_id = crm_store.log_recommendation(
                restaurant_id=request.restaurant_id,
                query=request.query,
                wines=wines,
                intro=intro or "",
                relaxed=relaxed or "",
                latency_ms=int((time.time() - start_time) * 1000),
                channel=request.channel or "pwa",
            )
        return RecommendationResponse(
            recommendation_id=rec_id,
            intro=intro or None,
            wines=guest,
            query=request.query,
            restaurant_name=config.name,
            relaxed=relaxed or None,
        )
    except EmbeddingError:
        return RecommendationResponse(
            wines=[],
            query=request.query,
            restaurant_name=config.name,
            error="The cellar is taking a moment. Please try again shortly.",
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("recommend failed")
        raise HTTPException(status_code=500, detail="Something went wrong looking through the list.")


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@app.post("/api/email-wine")
async def email_wine(body: EmailWineRequest, raw: Request):
    rate_limit(raw, max_hits=10, window_s=600)
    email = (body.email or "").strip().lower()
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Please enter a valid email.")
    config = get_restaurant_config(body.restaurant_id)
    if not config:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    if not body.recommendation_id:
        raise HTTPException(status_code=400, detail="Missing recommendation.")
    row = crm_store.get_recommendation(body.recommendation_id)
    if not row or row["restaurant_id"] != body.restaurant_id:
        raise HTTPException(status_code=404, detail="Those bottles are no longer on this table.")
    import json
    wines = json.loads(row["wines_json"] or "[]")
    sent, status = send_wine_email(email, config.name, wines)
    crm_store.log_email_lead(
        restaurant_id=body.restaurant_id,
        email=email,
        wines=wines,
        recommendation_id=body.recommendation_id,
        sent=sent,
        error="" if sent or status == "saved" else status,
    )
    if sent:
        return {"ok": True, "message": "Sent. Your server can pour whenever you are ready."}
    if status == "saved":
        return {
            "ok": True,
            "message": "Saved for you. The sommelier desk has a copy.",
        }
    raise HTTPException(status_code=502, detail="We could not send that just now. Please try again.")


@app.post("/api/admin/login")
async def admin_login(body: AdminLoginRequest, response: Response):
    expected = settings.resolved_admin_password()
    if not expected or not hmac.compare_digest(body.password, expected):
        raise HTTPException(status_code=401, detail="Wrong password")
    response.set_cookie(
        key=ADMIN_COOKIE,
        value=sign_admin(),
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
    )
    return {"ok": True}


@app.post("/api/admin/logout")
async def admin_logout(response: Response):
    response.delete_cookie(ADMIN_COOKIE)
    return {"ok": True}


@app.get("/api/admin/report")
async def admin_report(
    restaurant_id: Optional[str] = None,
    jarvis_admin: Optional[str] = Cookie(default=None, alias=ADMIN_COOKIE),
):
    require_admin(jarvis_admin)
    data = crm_store.report(restaurant_id=restaurant_id)
    import json
    recs = []
    for row in data["recommendations"]:
        wines = json.loads(row.get("wines_json") or "[]")
        scores = json.loads(row.get("scores_json") or "{}")
        recs.append(
            {
                "id": row["id"],
                "ts": row["ts"],
                "restaurant_id": row["restaurant_id"],
                "query": row["query"],
                "intro": row.get("intro"),
                "relaxed": row.get("relaxed"),
                "latency_ms": row.get("latency_ms"),
                "wines": [
                    {**w, "score": scores.get(w.get("wine_id"))}
                    for w in wines
                ],
            }
        )
    leads = []
    for row in data["leads"]:
        leads.append(
            {
                "id": row["id"],
                "ts": row["ts"],
                "restaurant_id": row["restaurant_id"],
                "email": row["email"],
                "sent": bool(row["sent"]),
                "recommendation_id": row.get("recommendation_id"),
                "wines": json.loads(row.get("wines_json") or "[]"),
            }
        )
    return {"recommendations": recs, "leads": leads, "top_wines": data["top_wines"]}


@app.on_event("startup")
async def warmup():
    crm_store.init_db()
    write_guest_qr(guest_url(GUEST_ID))
    config = get_restaurant_config(GUEST_ID)
    if config:
        recommenders[config.restaurant_id] = OptimizedWineRecommender(config)
        logger.info("Warmed recommender for %s", config.restaurant_id)


@app.get("/api/health")
async def health_check():
    payload = {
        "status": "healthy",
        "active_restaurants": len(recommenders),
    }
    if settings.environment == "development":
        payload["phone_url"] = guest_url(GUEST_ID)
        payload["showcase_url"] = f"{PHONE_URL}/showcase"
    return payload


app.mount("/", StaticFiles(directory=str(MOBILE_DIR), html=True), name="pwa")


if __name__ == "__main__":
    import uvicorn
    print(f"Phone app:  {guest_url(GUEST_ID)}")
    print(f"QR display: {PHONE_URL}/showcase")
    print(f"Admin:      {PHONE_URL}/admin")
    uvicorn.run(app, host="0.0.0.0", port=8000)

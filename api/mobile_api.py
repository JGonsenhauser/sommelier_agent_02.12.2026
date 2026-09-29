"""
FastAPI backend for mobile wine sommelier app.
Much faster than Streamlit for mobile devices.

Usage:
    uvicorn api.mobile_api:app --reload --port 8000

Then access: http://localhost:8000/docs
"""
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import Any, List, Optional
import sys
import logging
import os
import socket
from pathlib import Path

import qrcode

logger = logging.getLogger(__name__)

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import settings
from restaurants.restaurant_config import get_restaurant_config
from restaurants.wine_recommender_optimized import OptimizedWineRecommender
from data.embedding_pipeline import EmbeddingError
from data.admin_access import drop_session, ensure_pin_file, open_demo_session, session_is_demo, session_ok, unlock
from data.activity_log import clear_activity
from data.activity_log import insights as activity_insights
from data.activity_log import record_search
from data.wine_master import ensure_master, load_wines, note_worth_saving, save_all, save_tasting_note, wine_is_in_stock

ROOT_DIR = Path(__file__).parent.parent
MOBILE_DIR = ROOT_DIR / "mobile"
QR_PATH = ROOT_DIR / "restaurants" / "maass" / "static" / "maass_qr.png"
QR_MOBILE_PATH = MOBILE_DIR / "qr.png"
API_PORT = 8000


def detect_lan_ip() -> str:
    """Prefer a private LAN address (Wi-Fi) over Tailscale/loopback."""
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


def write_lan_qr(url: str) -> Path:
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
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(str(QR_PATH))
    img.save(str(QR_MOBILE_PATH))
    logger.info("Phone QR points to %s", url)
    return QR_PATH


PHONE_URL = phone_base_url()
write_lan_qr(PHONE_URL)

app = FastAPI(
    title="Jarvis Wine Sommelier API",
    description="Fast mobile API for restaurant wine recommendations",
    version="1.0.0"
)

# Enable CORS for mobile apps
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cache recommenders per restaurant
recommenders = {}


class WineRecommendation(BaseModel):
    """Wine recommendation response model."""
    wine_id: str
    producer: str
    wine_name: Optional[str] = ""
    region: str
    country: Optional[str] = ""
    vintage: Optional[str] = ""
    price: Optional[str] = ""
    text: Optional[str] = ""  # Formatted display text from schema
    grapes: Optional[str] = ""
    wine_type: str
    price_range: str
    tasting_note: str
    food_pairing: Optional[str] = None  # Now optional (None if not requested)
    score: float


class RecommendationRequest(BaseModel):
    """Request model for wine recommendations."""
    query: str
    restaurant_id: str = "maass"
    color: Optional[str] = None
    body: Optional[str] = None
    price_band: Optional[str] = None
    food: Optional[str] = None
    text: Optional[str] = None


class AdminPinRequest(BaseModel):
    pin: str


class AdminWineSaveRequest(BaseModel):
    wines: List[Any]


class RecommendationResponse(BaseModel):
    """Response model for wine recommendations."""
    wines: List[WineRecommendation]
    query: str
    restaurant_name: str
    processing_time: float
    error: Optional[str] = None


@app.get("/", include_in_schema=False)
async def pwa_index():
    """Installable phone app."""
    return FileResponse(MOBILE_DIR / "index.html")


@app.get("/showcase", include_in_schema=False)
@app.get("/showcase.html", include_in_schema=False)
async def showcase_page():
    """Laptop display: large QR for guests to scan."""
    return FileResponse(MOBILE_DIR / "showcase.html")


@app.get("/api/restaurants")
async def list_restaurants():
    """List available restaurants."""
    # In production, query database for all restaurants
    return {
        "restaurants": [
            {
                "id": "maass",
                "name": "MAASS",
                "location": "New York, NY",
                "wine_count": 282
            }
        ]
    }


@app.get("/api/restaurants/{restaurant_id}")
async def get_restaurant(restaurant_id: str):
    """Get restaurant details."""
    config = get_restaurant_config(restaurant_id)
    if not config:
        raise HTTPException(status_code=404, detail="Restaurant not found")

    return {
        "id": config.restaurant_id,
        "name": config.name,
        "location": config.location,
        "wine_count": config.wine_count,
        "primary_color": config.primary_color,
        "accent_color": config.accent_color
    }


@app.post("/api/recommend")
async def recommend_wines(request: RecommendationRequest) -> RecommendationResponse:
    """
    Get wine recommendations based on user query.

    Example request:
    ```json
    {
        "query": "Full body Chianti around 125",
        "restaurant_id": "maass"
    }
    ```
    """
    import time
    start_time = time.time()
    record_search(
        request.query,
        request.color,
        request.price_band,
        request.text,
        wines=load_wines(),
        body=request.body,
        food=request.food,
    )

    # Get or create recommender for restaurant
    # Force recreation on each request during development to pick up code changes
    # TODO: Remove in production for better performance
    config = get_restaurant_config(request.restaurant_id)
    if not config:
        raise HTTPException(status_code=404, detail="Restaurant not found")

    if request.restaurant_id not in recommenders:
        recommenders[request.restaurant_id] = OptimizedWineRecommender(config)
    recommender = recommenders[request.restaurant_id]

    # Get recommendations
    try:
        wines = recommender.get_full_recommendation(request.query)

        if not wines:
            return RecommendationResponse(
                wines=[],
                query=request.query,
                restaurant_name=recommender.config.name,
                processing_time=time.time() - start_time
            )

        # Convert to response model with explicit type coercion
        wine_recommendations = []
        for wine in wines:
            # Defensively coerce all fields
            price_val = wine.get("price", "")
            price_str = str(price_val) if price_val else ""

            vintage_val = wine.get("vintage", "")
            vintage_str = str(vintage_val) if vintage_val else ""

            rec = WineRecommendation(
                wine_id=wine["wine_id"],
                producer=wine["producer"],
                wine_name=wine.get("wine_name", ""),
                region=wine["region"],
                country=wine.get("country", ""),
                vintage=vintage_str,
                price=price_str,
                text=wine.get("text", ""),  # Include formatted text field
                grapes=wine.get("grapes", ""),
                wine_type=wine["wine_type"],
                price_range=wine["price_range"],
                tasting_note=wine.get("tasting_note", ""),
                food_pairing=wine.get("food_pairing"),  # Pass None if not set
                score=float(wine["score"]),
            )
            wine_recommendations.append(rec)

        return RecommendationResponse(
            wines=wine_recommendations,
            query=request.query,
            restaurant_name=recommender.config.name,
            processing_time=time.time() - start_time
        )

    except EmbeddingError as e:
        logger.warning(f"Embedding service down: {e}")
        return RecommendationResponse(
            wines=[],
            query=request.query,
            restaurant_name=config.name if config else "Unknown",
            processing_time=time.time() - start_time,
            error="Our wine search is momentarily refreshing — like a good decant! Please try again in a few seconds."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting recommendations: {str(e)}")


@app.get("/api/recommend")
async def recommend_wines_get(
    query: str = Query(..., description="Wine preference query"),
    restaurant_id: str = Query("maass", description="Restaurant ID")
) -> RecommendationResponse:
    """
    GET endpoint for wine recommendations (easier for testing).

    Example: /api/recommend?query=full%20body%20chianti%20around%20125&restaurant_id=maass
    """
    request = RecommendationRequest(query=query, restaurant_id=restaurant_id)
    return await recommend_wines(request)


def _public_wine(wine: dict) -> dict:
    return {
        "id": wine.get("id", ""),
        "producer": wine.get("producer") or "",
        "label": wine.get("label") or "",
        "vintage": wine.get("vintage") or "",
        "region": wine.get("region") or "",
        "sub_region": wine.get("sub_region") or "",
        "country": wine.get("country") or "",
        "major_region": wine.get("major_region") or wine.get("region") or "",
        "price": wine.get("price"),
        "in_stock": bool(wine.get("in_stock", True)),
        "wine_style": (wine.get("wine_style") or "").lower(),
        "tasting_note": (wine.get("tasting_note") or "").strip(),
    }


def _maass_recommender():
    if "maass" not in recommenders:
        config = get_restaurant_config("maass")
        if not config:
            raise HTTPException(status_code=404, detail="Restaurant not found")
        recommenders["maass"] = OptimizedWineRecommender(config)
    return recommenders["maass"]


@app.get("/api/wines")
async def public_wine_list():
    """Guest-facing bottle list. The master file is the only copy."""
    wines = [wine for wine in (load_wines() or ensure_master()) if wine_is_in_stock(wine)]
    return {"wines": [_public_wine(wine) for wine in wines], "count": len(wines)}


@app.get("/api/wines/{wine_id}/note")
async def public_tasting_note(wine_id: str):
    """One tasting note for a bottle the guest selected from the list."""
    wines = load_wines() or ensure_master()
    wine = next((item for item in wines if item.get("id") == wine_id), None)
    if not wine or not wine_is_in_stock(wine):
        raise HTTPException(status_code=404, detail="Wine not found")
    stored = (wine.get("tasting_note") or "").strip()
    if note_worth_saving(stored):
        payload = _public_wine(wine)
        payload["tasting_note"] = stored
        return payload
    recommender = _maass_recommender()
    note = recommender.get_tasting_note_cached(
        wine.get("producer") or "",
        wine.get("region") or "",
        wine.get("label") or "",
        wine.get("grapes") or "",
        wine.get("wine_style") or "",
        wine.get("vintage") or "",
    )
    if not note or len(note) < 10:
        note = recommender._fallback_note(
            {
                "wine_type": wine.get("wine_style") or "wine",
                "region": wine.get("region") or "the list",
                "grapes": wine.get("grapes") or "classic varietals",
            }
        )
    if note_worth_saving(note):
        save_tasting_note(wine_id, note)
    payload = _public_wine(wine)
    payload["tasting_note"] = note
    return payload


def _admin_token(authorization: Optional[str]) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Enter the admin pin.")
    token = authorization.split(" ", 1)[1].strip()
    if not session_ok(token):
        raise HTTPException(status_code=401, detail="Enter the admin pin.")
    return token


def _refresh_live_catalog() -> None:
    recommender = recommenders.get("maass")
    pipeline = getattr(recommender, "pipeline", None) if recommender else None
    if pipeline:
        pipeline.invalidate_catalog("maass_wine_list")


@app.post("/api/admin/unlock")
async def admin_unlock(request: AdminPinRequest):
    """Check the pin file and open an admin session. The pin is never returned."""
    try:
        token, demo = unlock(request.pin)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return {"ok": True, "token": token, "demo": demo}


@app.post("/api/admin/demo")
async def admin_demo_session():
    """Open the demo back office. This session cannot write the live wine master."""
    return {"ok": True, "token": open_demo_session(), "demo": True}


@app.post("/api/admin/lock")
async def admin_lock(authorization: Optional[str] = Header(default=None)):
    token = authorization.split(" ", 1)[1].strip() if authorization and " " in authorization else ""
    drop_session(token)
    return {"ok": True}


@app.get("/api/admin/wines")
async def admin_wines(authorization: Optional[str] = Header(default=None)):
    _admin_token(authorization)
    wines = ensure_master()
    return {"wines": wines, "count": len(wines)}


@app.post("/api/admin/wines")
async def admin_save_wines(
    request: AdminWineSaveRequest,
    authorization: Optional[str] = Header(default=None),
):
    """save_all: write the master, the markdown list, and the live search list."""
    token = _admin_token(authorization)
    if session_is_demo(token):
        current = load_wines() or ensure_master()
        return {
            "saved": 0,
            "demo": True,
            "pinecone_updated": False,
            "message": "this is a demo",
            "wines": current,
        }
    try:
        result = save_all(request.wines)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result["pinecone_updated"]:
        _refresh_live_catalog()
    return {
        "saved": result["saved"],
        "pinecone_updated": result["pinecone_updated"],
        "message": result["message"],
        "wines": result["wines"],
    }


@app.get("/api/admin/insights")
async def admin_insights(authorization: Optional[str] = Header(default=None)):
    token = _admin_token(authorization)
    wines = load_wines() or ensure_master()
    payload = activity_insights(wines)
    if session_is_demo(token):
        from data.activity_log import demo_missed_searches

        payload["descriptions"] = demo_missed_searches(wines)
    return JSONResponse(payload, headers={"Cache-Control": "no-store"})


@app.post("/api/admin/insights/reset")
async def admin_reset_insights(
    request: AdminPinRequest,
    authorization: Optional[str] = Header(default=None),
):
    """Erase saved search counts after the admin pin is entered again."""
    token = _admin_token(authorization)
    try:
        extra, pin_is_demo = unlock(request.pin)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    drop_session(extra)
    if pin_is_demo or session_is_demo(token):
        return {"ok": True, "demo": True, "message": "this is a demo"}
    clear_activity()
    return {"ok": True}


@app.on_event("startup")
async def warmup_recommender():
    ensure_pin_file()
    ensure_master()
    config = get_restaurant_config("maass")
    if not config:
        return
    recommenders["maass"] = OptimizedWineRecommender(config)
    logger.info("Warmed recommender for maass")


@app.get("/api/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "phone_url": PHONE_URL,
        "showcase_url": f"{PHONE_URL}/showcase",
        "active_restaurants": len(recommenders),
        "cached_recommenders": list(recommenders.keys())
    }


app.mount("/", StaticFiles(directory=str(MOBILE_DIR), html=True), name="pwa")


if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*60)
    print("Starting Jarvis Wine Sommelier API")
    print("="*60)
    print(f"\nPhone app:  {PHONE_URL}")
    print(f"QR display: {PHONE_URL}/showcase")
    print("API docs:   http://localhost:8000/docs")
    print("\nPress CTRL+C to stop\n")

    uvicorn.run(app, host="0.0.0.0", port=8000)

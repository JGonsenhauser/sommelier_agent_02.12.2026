"""
FastAPI backend for mobile wine sommelier app.
Much faster than Streamlit for mobile devices.

Usage:
    uvicorn api.mobile_api:app --reload --port 8000

Then access: http://localhost:8000/docs
"""
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import sys
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from restaurants.restaurant_config import get_restaurant_config
from restaurants.wine_recommender_optimized import OptimizedWineRecommender
from data.embedding_pipeline import EmbeddingError

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


class RecommendationResponse(BaseModel):
    """Response model for wine recommendations."""
    wines: List[WineRecommendation]
    query: str
    restaurant_name: str
    processing_time: float
    error: Optional[str] = None


@app.get("/")
async def root():
    """API health check."""
    return {
        "status": "online",
        "message": "Jarvis Wine Sommelier API",
        "version": "1.0.0"
    }


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

    # Get or create recommender for restaurant
    # Force recreation on each request during development to pick up code changes
    # TODO: Remove in production for better performance
    config = get_restaurant_config(request.restaurant_id)
    if not config:
        raise HTTPException(status_code=404, detail="Restaurant not found")

    # Recreate recommender to pick up code changes
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


@app.get("/api/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "active_restaurants": len(recommenders),
        "cached_recommenders": list(recommenders.keys())
    }


if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*60)
    print("Starting Jarvis Wine Sommelier API")
    print("="*60)
    print("\nAPI Documentation: http://localhost:8000/docs")
    print("Test endpoint: http://localhost:8000/api/recommend?query=bold%20red%20wine&restaurant_id=maass")
    print("\nPress CTRL+C to stop\n")

    uvicorn.run(app, host="0.0.0.0", port=8000)

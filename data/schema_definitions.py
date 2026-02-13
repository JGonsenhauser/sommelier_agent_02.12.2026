"""
Data schema definitions for Wine Sommelier Agent.
Defines Redis hash structures and Pinecone metadata schemas.
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class WineType(str, Enum):
    """Wine type categories."""
    RED = "red"
    WHITE = "white"
    ROSE = "rosé"
    SPARKLING = "sparkling"
    DESSERT = "dessert"
    UNKNOWN = "unknown"


class WineStyle(str, Enum):
    """Wine style preferences."""
    LIGHT_CRISP = "light/crisp"
    MEDIUM = "medium"
    FULL_BODIED = "full-bodied"
    BOLD = "bold"
    SWEET = "sweet"


class PriceRange(str, Enum):
    """Price range categories."""
    BUDGET = "<$50"
    MID = "$50-100"
    PREMIUM = "$100-200"
    LUXURY = "$200+"


# ============ Redis Hash Schemas ============

class Wine(BaseModel):
    """
    Redis Key: wine:{qr_id}:{wine_id}
    
    Stores individual wine details for a specific business location.
    """
    wine_id: str = Field(..., description="Unique wine identifier")
    qr_id: str = Field(..., description="Business QR code identifier")
    producer: str = Field(..., description="Wine producer/winery name")
    wine_name: Optional[str] = Field(None, description="Specific wine name")
    region: str = Field(..., description="Wine region (e.g., Napa Valley, Bordeaux)")
    country: str = Field(..., description="Country of origin")
    vintage: Optional[int] = Field(None, description="Vintage year")
    price: float = Field(..., description="Price per bottle")
    grapes: List[str] = Field(..., description="List of grape varietals")
    wine_type: WineType = Field(..., description="Wine type category")
    tasting_note: str = Field(..., description="Professional tasting description")
    alcohol_content: Optional[float] = Field(None, description="ABV percentage")
    
    def to_redis_hash(self) -> Dict[str, str]:
        """Convert to Redis hash format (all string values)."""
        return {
            "wine_id": self.wine_id,
            "qr_id": self.qr_id,
            "producer": self.producer,
            "wine_name": self.wine_name or "",
            "region": self.region,
            "country": self.country,
            "vintage": str(self.vintage) if self.vintage else "",
            "price": str(self.price),
            "grapes": ",".join(self.grapes),
            "wine_type": self.wine_type.value,
            "tasting_note": self.tasting_note,
            "alcohol_content": str(self.alcohol_content) if self.alcohol_content else "",
        }
    
    @classmethod
    def from_redis_hash(cls, data: Dict[str, str]) -> "Wine":
        """Create Wine instance from Redis hash."""
        return cls(
            wine_id=data["wine_id"],
            qr_id=data["qr_id"],
            producer=data["producer"],
            wine_name=data.get("wine_name") or None,
            region=data["region"],
            country=data["country"],
            vintage=int(data["vintage"]) if data.get("vintage") else None,
            price=float(data["price"]),
            grapes=data["grapes"].split(",") if data["grapes"] else [],
            wine_type=WineType(data["wine_type"]),
            tasting_note=data["tasting_note"],
            alcohol_content=float(data["alcohol_content"]) if data.get("alcohol_content") else None,
        )


class Business(BaseModel):
    """
    Redis Key: business:{business_id}
    
    Stores business/restaurant details and wine list reference.
    """
    business_id: str = Field(..., description="Unique business identifier")
    name: str = Field(..., description="Business/restaurant name")
    location: Optional[str] = Field(None, description="Physical address")
    qr_code: str = Field(..., description="QR code value (matches qr_id)")
    wine_list_count: int = Field(0, description="Number of wines in list")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    def to_redis_hash(self) -> Dict[str, str]:
        """Convert to Redis hash format."""
        return {
            "business_id": self.business_id,
            "name": self.name,
            "location": self.location or "",
            "qr_code": self.qr_code,
            "wine_list_count": str(self.wine_list_count),
            "created_at": self.created_at.isoformat(),
        }
    
    @classmethod
    def from_redis_hash(cls, data: Dict[str, str]) -> "Business":
        """Create Business instance from Redis hash."""
        return cls(
            business_id=data["business_id"],
            name=data["name"],
            location=data.get("location") or None,
            qr_code=data["qr_code"],
            wine_list_count=int(data["wine_list_count"]),
            created_at=datetime.fromisoformat(data["created_at"]),
        )


class UserPreferences(BaseModel):
    """User preferences collected during conversation."""
    wine_type: Optional[WineType] = None
    style: Optional[WineStyle] = None
    budget: Optional[PriceRange] = None
    preferred_grapes: List[str] = Field(default_factory=list)
    preferred_regions: List[str] = Field(default_factory=list)
    occasion: Optional[str] = None
    food_pairing: Optional[str] = None


class Session(BaseModel):
    """
    Redis Key: session:{session_id}
    
    Stores user session data including preferences and conversation history.
    """
    session_id: str = Field(..., description="Unique session identifier")
    business_id: str = Field(..., description="Associated business")
    user_preferences: UserPreferences = Field(default_factory=UserPreferences)
    conversation_history: List[Dict[str, str]] = Field(default_factory=list)
    recommendations_shown: List[str] = Field(default_factory=list, description="Wine IDs recommended")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_active: datetime = Field(default_factory=datetime.utcnow)
    
    def to_redis_hash(self) -> Dict[str, str]:
        """Convert to Redis hash format."""
        import json
        return {
            "session_id": self.session_id,
            "business_id": self.business_id,
            "user_preferences": self.user_preferences.model_dump_json(),
            "conversation_history": json.dumps(self.conversation_history),
            "recommendations_shown": json.dumps(self.recommendations_shown),
            "created_at": self.created_at.isoformat(),
            "last_active": self.last_active.isoformat(),
        }
    
    @classmethod
    def from_redis_hash(cls, data: Dict[str, str]) -> "Session":
        """Create Session instance from Redis hash."""
        import json
        return cls(
            session_id=data["session_id"],
            business_id=data["business_id"],
            user_preferences=UserPreferences.model_validate_json(data["user_preferences"]),
            conversation_history=json.loads(data["conversation_history"]),
            recommendations_shown=json.loads(data["recommendations_shown"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            last_active=datetime.fromisoformat(data["last_active"]),
        )


# ============ Pinecone Vector Metadata Schema ============

class WineEmbedding(BaseModel):
    """
    Metadata schema for Pinecone wine embeddings (Master/Core).
    Follows unified schema for cross-namespace consistency.
    """
    # Core Metadata (Master namespace)
    producer: str
    label: Optional[str] = None
    grapes: str
    region: str
    major_region: Optional[str] = None
    country: str
    text: str  # Standardized embedding text
    sync_version: int = 1
    
    def to_pinecone_metadata(self) -> Dict[str, Any]:
        """Convert to Pinecone metadata format (master namespace)."""
        return {
            "producer": self.producer,
            "label": self.label or "",
            "grapes": self.grapes,
            "region": self.region,
            "major_region": self.major_region or self.region,
            "country": self.country,
            "text": self.text,
            "sync_version": self.sync_version,
        }


class RestaurantWineEmbedding(BaseModel):
    """
    Metadata schema for Pinecone wine embeddings (Restaurant namespace).
    Extends core metadata with restaurant-specific fields.
    """
    # Core Metadata
    producer: str
    label: Optional[str] = None
    grapes: str
    region: str
    major_region: Optional[str] = None
    country: str
    text: str
    sync_version: int = 1
    
    # Restaurant-Specific
    price_range: str  # "<$50", "$50-100", "$100-200", "$200+"
    price: Optional[float] = None
    tasting_keywords: str
    list_id: str
    qr_id: str
    restaurant: str  # e.g., "maass"
    
    # Legacy/Traceability
    wine_id: Optional[str] = None
    
    def to_pinecone_metadata(self) -> Dict[str, Any]:
        """Convert to Pinecone metadata format (restaurant namespace)."""
        return {
            # Core
            "producer": self.producer,
            "label": self.label or "",
            "grapes": self.grapes,
            "region": self.region,
            "major_region": self.major_region or self.region,
            "country": self.country,
            "text": self.text,
            "sync_version": self.sync_version,
            # Restaurant
            "price_range": self.price_range,
            "price": self.price,
            "tasting_keywords": self.tasting_keywords,
            "list_id": self.list_id,
            "qr_id": self.qr_id,
            "restaurant": self.restaurant,
        }


# ============ Redis Key Patterns ============

class RedisKeys:
    """Redis key pattern definitions."""
    
    @staticmethod
    def wine(qr_id: str, wine_id: str) -> str:
        """Redis key for wine data: wine:{qr_id}:{wine_id}"""
        return f"wine:{qr_id}:{wine_id}"
    
    @staticmethod
    def business(business_id: str) -> str:
        """Redis key for business data: business:{business_id}"""
        return f"business:{business_id}"
    
    @staticmethod
    def session(session_id: str) -> str:
        """Redis key for session data: session:{session_id}"""
        return f"session:{session_id}"
    
    @staticmethod
    def wine_list_index(qr_id: str) -> str:
        """Redis set key for wine list index: wine_list:{qr_id}"""
        return f"wine_list:{qr_id}"

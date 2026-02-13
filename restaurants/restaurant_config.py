"""
Restaurant configuration and metadata management.
"""
from dataclasses import dataclass, field
from typing import Optional, Dict
from pathlib import Path
from datetime import datetime


@dataclass
class RestaurantConfig:
    """Configuration for a restaurant's sommelier system."""

    restaurant_id: str
    name: str
    location: Optional[str] = None
    qr_id: str = field(init=False)
    namespace: str = field(init=False)
    menu_namespace: str = field(init=False)
    producers_namespace: str = "producers"

    # Display settings
    logo_path: Optional[Path] = None
    primary_color: str = "#8B0000"  # Default wine red
    accent_color: str = "#DAA520"  # Default gold

    # Recommendation settings
    max_recommendations: int = 2  # Always return exactly 2 wines
    enable_food_pairing: bool = True
    enable_menu_pairing: bool = False  # Enable after menu is ingested into Pinecone
    enable_price_filtering: bool = True

    # Contact info
    phone: Optional[str] = None
    website: Optional[str] = None
    hours: Optional[str] = None

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    wine_count: int = 0

    def __post_init__(self):
        """Initialize computed fields."""
        self.qr_id = f"qr_{self.restaurant_id}"
        self.namespace = f"{self.restaurant_id}_wine_list"
        self.menu_namespace = f"{self.restaurant_id}_menu"

    @property
    def qr_code_path(self) -> Path:
        """Path to QR code image."""
        return Path(f"restaurants/{self.restaurant_id}/static/{self.restaurant_id}_qr.png")

    @property
    def wine_list_path(self) -> Path:
        """Path to wine list file."""
        return Path(f"restaurants/{self.restaurant_id}/data/wine_list.csv")

    def to_dict(self) -> Dict:
        """Convert to dictionary for storage."""
        return {
            "restaurant_id": self.restaurant_id,
            "name": self.name,
            "location": self.location,
            "qr_id": self.qr_id,
            "namespace": self.namespace,
            "primary_color": self.primary_color,
            "accent_color": self.accent_color,
            "max_recommendations": self.max_recommendations,
            "phone": self.phone,
            "website": self.website,
            "hours": self.hours,
            "wine_count": self.wine_count,
        }


# Pre-configured restaurants
MAASS_CONFIG = RestaurantConfig(
    restaurant_id="maass",
    name="MAASS Beverage List",
    location=None,  # Location not displayed in header
    primary_color="#000000",  # Black
    accent_color="#4A4A4A",  # Gray accent
    enable_menu_pairing=True,  # Menu embedded in Pinecone (maass_menu namespace)
    phone=None,
    website=None,
    hours=None,
)


def get_restaurant_config(restaurant_id: str) -> Optional[RestaurantConfig]:
    """Get configuration for a restaurant by ID."""
    configs = {
        "maass": MAASS_CONFIG,
    }
    return configs.get(restaurant_id)

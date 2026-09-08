"""Restaurant configuration and metadata management."""
from dataclasses import dataclass, field
from typing import Optional, Dict, List
from pathlib import Path
from datetime import datetime
import json

from data.sommelier_knowledge import BODY_CUES, FOOD_CUES, PROFILE_CUES


ROOT = Path(__file__).resolve().parent.parent
PRODUCT_NAME = "Jarvis"
PRODUCT_LOGO = ROOT / "logo" / "03-spine-ring.png"


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

    logo_path: Optional[Path] = None
    primary_color: str = "#7A8A78"
    accent_color: str = "#C4B7A6"
    background_color: str = "#F3EEE6"
    ink_color: str = "#1C1A16"

    max_recommendations: int = 2
    enable_food_pairing: bool = True
    enable_menu_pairing: bool = True
    enable_price_filtering: bool = True
    cellar_min: int = 250

    phone: Optional[str] = None
    website: Optional[str] = None
    hours: Optional[str] = None

    created_at: datetime = field(default_factory=datetime.utcnow)
    wine_count: int = 0

    price_bands: List[Dict[str, str]] = field(default_factory=list)
    food_cues: List[Dict[str, str]] = field(default_factory=list)
    body_cues: List[Dict[str, str]] = field(default_factory=list)
    profile_cues: List[Dict[str, str]] = field(default_factory=list)
    # When False, guests see Jarvis + Agenthaus. Set True per customer to use restaurant name/logo.
    branded: bool = False

    def __post_init__(self):
        self.qr_id = f"qr_{self.restaurant_id}"
        self.namespace = f"{self.restaurant_id}_wine_list"
        self.menu_namespace = f"{self.restaurant_id}_menu"

    @property
    def qr_code_path(self) -> Path:
        return Path(f"restaurants/{self.restaurant_id}/static/{self.restaurant_id}_qr.png")

    @property
    def wine_list_path(self) -> Path:
        return Path(f"restaurants/{self.restaurant_id}/data/wine_list.csv")

    @property
    def menu_path(self) -> Path:
        return ROOT / "restaurants" / self.restaurant_id / "menu.json"

    def _merged_food_cues(self) -> List[Dict[str, str]]:
        from data.sommelier_knowledge import menu_dish_cues
        cues = list(self.food_cues or [])
        seen = {c.get("label", "").lower() for c in cues}
        extras = 0
        overlap = ("oyster", "steak", "chicken", "burrata", "pasta")
        for dish in menu_dish_cues(self.load_menu()):
            label = dish["label"].lower()
            if label in seen or any(w in label for w in overlap):
                continue
            cues.append(dish)
            seen.add(label)
            extras += 1
            if extras >= 8:
                break
        return cues

    def load_menu(self) -> List[Dict]:
        path = self.menu_path
        if not path.exists():
            return []
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def to_public_dict(self) -> Dict:
        if self.branded and self.logo_path and Path(self.logo_path).exists():
            display_name = self.name
            logo = f"/api/restaurants/{self.restaurant_id}/logo"
        else:
            display_name = PRODUCT_NAME
            logo = "/api/brand/logo" if PRODUCT_LOGO.exists() else "/brand-logo.png"
        return {
            "id": self.restaurant_id,
            "name": display_name,
            "restaurant_name": self.name,
            "location": self.location,
            "wine_count": self.wine_count,
            "primary_color": self.primary_color,
            "accent_color": self.accent_color,
            "background_color": self.background_color,
            "ink_color": self.ink_color,
            "logo": logo,
            "price_bands": self.price_bands,
            "food_cues": self._merged_food_cues(),
            "body_cues": self.body_cues,
            "profile_cues": self.profile_cues,
            "credit": PRODUCT_NAME,
        }


MAASS_CONFIG = RestaurantConfig(
    restaurant_id="maass",
    name="MAASS",
    location=None,
    logo_path=ROOT / "restaurants" / "maass" / "maass_logo.jpg",
    primary_color="#7A8A78",
    accent_color="#C4B7A6",
    background_color="#F3EEE6",
    ink_color="#1C1A16",
    enable_menu_pairing=True,
    cellar_min=250,
    price_bands=[
        {"label": "Under $75", "query": "under $75"},
        {"label": "$75–$150", "query": "between $75 and $150"},
        {"label": "$150–$250", "query": "between $150 and $250"},
        {"label": "Cellar", "query": "cellar"},
        {"label": "Any price", "query": ""},
    ],
    food_cues=list(FOOD_CUES),
    body_cues=list(BODY_CUES),
    profile_cues=list(PROFILE_CUES),
)


GUEST_ID = "demo"
_ALIASES = {
    "demo": "maass",
    "maass": "maass",
    "": "maass",
}


def resolve_restaurant_id(restaurant_id: Optional[str]) -> str:
    key = (restaurant_id or GUEST_ID).strip().lower()
    return _ALIASES.get(key, key)


def get_restaurant_config(restaurant_id: str) -> Optional[RestaurantConfig]:
    configs = {
        "maass": MAASS_CONFIG,
        "demo": MAASS_CONFIG,
    }
    return configs.get(resolve_restaurant_id(restaurant_id))


def list_restaurant_configs() -> List[RestaurantConfig]:
    return [MAASS_CONFIG]

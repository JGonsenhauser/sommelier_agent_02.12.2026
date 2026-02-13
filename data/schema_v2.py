"""
Schema V2 - Standardized metadata format for all Pinecone namespaces.

This schema defines:
1. Core metadata (shared across all namespaces)
2. Restaurant-specific metadata (only in restaurant namespaces)
3. Vector ID conventions
4. Embedding source conventions
"""
import hashlib
from typing import Optional, Dict
from dataclasses import dataclass, field


@dataclass
class CoreWineMetadata:
    """
    Core metadata shared across all namespaces (master, restaurant, producers).
    """
    # Required fields
    producer: str
    grapes: str
    region: str
    country: str
    text: str  # Standardized embedding text (no price, no restaurant info)

    # Optional fields
    label: str = ""  # Specific wine label/cuvée name
    major_region: str = ""  # Broader region (often same as region)
    sync_version: int = 2  # Schema version for migrations

    def to_dict(self) -> Dict:
        """Convert to dictionary for Pinecone metadata."""
        return {
            "producer": self.producer,
            "label": self.label,
            "grapes": self.grapes,
            "region": self.region,
            "major_region": self.major_region or self.region,
            "country": self.country,
            "text": self.text,
            "sync_version": self.sync_version
        }

    @classmethod
    def generate_text(
        cls,
        producer: str,
        label: str,
        grapes: str,
        region: str,
        major_region: str,
        country: str
    ) -> str:
        """
        Generate standardized text for embedding.
        NEVER include price, tasting notes, or restaurant info.
        """
        parts = [
            f"Producer: {producer}",
            f"Label: {label}" if label else None,
            f"Grapes: {grapes}",
            f"Region: {region}",
            f"Major Region: {major_region or region}",
            f"Country: {country}"
        ]
        return " | ".join(filter(None, parts))

    @classmethod
    def generate_master_id(
        cls,
        producer: str,
        label: str,
        grapes: str,
        region: str,
        country: str
    ) -> str:
        """
        Generate deterministic master ID from core identity.
        Format: 32-character lowercase hex (MD5).
        """
        identity = f"{producer}_{label}_{grapes}_{region}_{country}"
        return hashlib.md5(identity.encode('utf-8')).hexdigest()


@dataclass
class RestaurantWineMetadata(CoreWineMetadata):
    """
    Restaurant-specific metadata (only in restaurant namespaces).
    Includes all core metadata plus restaurant-specific fields.
    """
    # Restaurant-specific required fields
    price_range: str = ""  # e.g. "<$50", "$75-$100"
    list_id: str = ""
    qr_id: str = ""
    restaurant: str = ""

    # Restaurant-specific optional fields
    price: Optional[float] = None  # Exact price if available
    tasting_keywords: str = ""  # Free-text tasting note
    vintage: str = ""  # Optional vintage
    wine_type: str = ""  # Optional wine type classification

    def to_dict(self) -> Dict:
        """Convert to dictionary for Pinecone metadata."""
        base = super().to_dict()
        restaurant_fields = {
            "price_range": self.price_range,
            "list_id": self.list_id,
            "qr_id": self.qr_id,
            "restaurant": self.restaurant,
            "tasting_keywords": self.tasting_keywords,
        }

        # Add optional fields if they exist
        if self.price is not None:
            restaurant_fields["price"] = self.price
        if self.vintage:
            restaurant_fields["vintage"] = self.vintage
        if self.wine_type:
            restaurant_fields["wine_type"] = self.wine_type

        return {**base, **restaurant_fields}

    @classmethod
    def generate_restaurant_id(
        cls,
        restaurant: str,
        list_id: str,
        qr_id: str,
        master_id: str
    ) -> str:
        """
        Generate restaurant-specific vector ID.
        Format: {restaurant}_{list_id}_{qr_id}_wine_{master_id_short}
        """
        master_id_short = master_id[:8]
        return f"{restaurant}_{list_id}_{qr_id}_wine_{master_id_short}"


def get_price_range(price: float) -> str:
    """Categorize price into range bucket."""
    if price < 50:
        return "<$50"
    elif price < 100:
        return "$50-100"
    elif price < 200:
        return "$100-200"
    else:
        return "$200+"


# Schema validation
CORE_REQUIRED_FIELDS = {"producer", "grapes", "region", "country", "text"}
RESTAURANT_REQUIRED_FIELDS = CORE_REQUIRED_FIELDS | {"price_range", "list_id", "qr_id", "restaurant"}


def validate_core_metadata(metadata: Dict) -> bool:
    """Validate that metadata has all required core fields."""
    return CORE_REQUIRED_FIELDS.issubset(set(metadata.keys()))


def validate_restaurant_metadata(metadata: Dict) -> bool:
    """Validate that metadata has all required restaurant fields."""
    return RESTAURANT_REQUIRED_FIELDS.issubset(set(metadata.keys()))


if __name__ == "__main__":
    # Example usage
    print("Schema V2 - Core + Restaurant Metadata")
    print("=" * 60)

    # Example core metadata
    core = CoreWineMetadata(
        producer="Del Dotto",
        label="The Beast",
        grapes="Cabernet Sauvignon",
        region="Napa Valley",
        major_region="Napa Valley",
        country="United States",
        text=CoreWineMetadata.generate_text(
            producer="Del Dotto",
            label="The Beast",
            grapes="Cabernet Sauvignon",
            region="Napa Valley",
            major_region="Napa Valley",
            country="United States"
        )
    )

    master_id = CoreWineMetadata.generate_master_id(
        producer="Del Dotto",
        label="The Beast",
        grapes="Cabernet Sauvignon",
        region="Napa Valley",
        country="United States"
    )

    print(f"\nMaster ID: {master_id}")
    print(f"Core metadata: {core.to_dict()}")

    # Example restaurant metadata
    restaurant = RestaurantWineMetadata(
        producer="Del Dotto",
        label="The Beast",
        grapes="Cabernet Sauvignon",
        region="Napa Valley",
        major_region="Napa Valley",
        country="United States",
        text=core.text,
        price_range="$100-200",
        price=125.00,
        list_id="maass_wine_list",
        qr_id="qr_maass",
        restaurant="maass",
        tasting_keywords="Bold, rich, full-bodied",
        vintage="2020"
    )

    restaurant_id = RestaurantWineMetadata.generate_restaurant_id(
        restaurant="maass",
        list_id="maass_wine_list",
        qr_id="qr_maass",
        master_id=master_id
    )

    print(f"\nRestaurant ID: {restaurant_id}")
    print(f"Restaurant metadata: {restaurant.to_dict()}")
    print("\n" + "=" * 60)

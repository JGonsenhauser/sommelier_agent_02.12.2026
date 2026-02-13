"""
Wine taxonomy data models for the wine regions scraper.
"""
from dataclasses import dataclass, asdict
from typing import List, Optional
import json


@dataclass
class WineTaxonomy:
    """Schema for wine region and grape taxonomy entries."""
    world_type: str  # "old" (Europe) or "new" (rest of world)
    country: str
    region: str
    sub_region: Optional[str]  # Village, commune, or sub-region
    larger_region: Optional[str]  # Province, state, or larger region
    wine_type: str  # "red", "white", "rosé", "sparkling", "dessert"
    primary_grape: str
    common_blends: List[str]
    typical_styles: str  # Descriptors: body, acidity, aromas, tannins
    food_pairings: str
    source_url: Optional[str] = None
    
    def to_dict(self):
        """Convert to dictionary for storage."""
        return asdict(self)
    
    def to_json(self):
        """Convert to JSON string."""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_dict(cls, data: dict):
        """Create instance from dictionary."""
        return cls(**data)


def validate_taxonomy(entry: WineTaxonomy) -> bool:
    """Validate taxonomy entry has required fields."""
    required_fields = [
        'world_type', 'country', 'region', 'wine_type', 'primary_grape',
        'typical_styles', 'food_pairings'
    ]
    # Check required fields are not None/empty (except common_blends which can be empty list)
    for field in required_fields:
        value = getattr(entry, field, None)
        if not value:
            return False
    # wine_type must be valid (accept both Rose and rosé)
    valid_types = ['red', 'white', 'rosé', 'Rose', 'rose', 'sparkling', 'dessert', 'fortified']
    if entry.wine_type not in valid_types:
        return False
    # common_blends must exist and be a list (but can be empty)
    return isinstance(entry.common_blends, list)

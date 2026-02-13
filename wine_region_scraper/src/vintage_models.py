"""
Wine vintage data models for the wine regions scraper.
"""
from dataclasses import dataclass, asdict
from typing import Optional
import json


@dataclass
class WineVintage:
    """Schema for wine vintage entries."""
    region: str  # Wine region name (e.g., "Bordeaux (France)")
    vintage: int  # Year of the vintage
    rating: Optional[int]  # Numeric rating (e.g., 90, 95, etc.)
    notes: str  # Tasting notes and vintage characteristics
    
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


def validate_vintage(entry: WineVintage) -> bool:
    """Validate vintage entry has required fields."""
    # Check required fields
    if not entry.region or not entry.vintage or not entry.notes:
        return False
    
    # Vintage must be a valid year
    if not isinstance(entry.vintage, int) or entry.vintage < 1900 or entry.vintage > 2100:
        return False
    
    # Rating must be valid if present
    if entry.rating is not None:
        if not isinstance(entry.rating, int) or entry.rating < 0 or entry.rating > 100:
            return False
    
    return True

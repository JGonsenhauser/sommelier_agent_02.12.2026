"""
Data model for restaurant menu dishes.
Used for embedding menu items into Pinecone for wine-dish pairing.
"""
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
import uuid


class MenuDish(BaseModel):
    """A single dish from a restaurant's menu."""

    dish_id: str = Field(default_factory=lambda: f"dish_{uuid.uuid4().hex[:8]}")
    name: str = Field(..., description="Dish name (e.g., 'Pan-Seared Branzino')")
    description: str = Field(default="", description="Dish description or ingredients")
    category: str = Field(default="", description="Category (e.g., 'Seafood', 'Meat', 'Pasta')")
    price: Optional[float] = Field(None, description="Dish price")
    restaurant_id: str = Field(..., description="Restaurant identifier")

    def to_embedding_text(self) -> str:
        """Generate text for embedding."""
        parts = [self.name]
        if self.description:
            parts.append(f"- {self.description}")
        if self.category:
            parts.append(f"Category: {self.category}")
        return ". ".join(parts)

    def to_pinecone_metadata(self) -> Dict[str, Any]:
        """Convert to Pinecone metadata."""
        metadata = {
            "dish_id": self.dish_id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "restaurant_id": self.restaurant_id,
        }
        if self.price is not None:
            metadata["price"] = self.price
        return metadata

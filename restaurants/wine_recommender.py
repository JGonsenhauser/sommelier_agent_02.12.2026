"""
Wine recommendation engine for restaurant-specific wine lists.
Returns exactly 2 wine recommendations with detailed tasting notes.
"""
from typing import List, Dict, Optional
import logging
import re
from openai import OpenAI

from data.embedding_pipeline import EmbeddingPipeline
from restaurants.restaurant_config import RestaurantConfig
from config import settings

logger = logging.getLogger(__name__)


class WineRecommender:
    """Recommends wines from restaurant-specific lists with Jarvis personality."""

    def __init__(self, config: RestaurantConfig):
        """Initialize recommender for a specific restaurant."""
        self.config = config
        self.pipeline = EmbeddingPipeline()

        # Initialize Grok client for conversational responses
        xai_api_key = settings.get_decrypted_xai_key()
        self.grok_client = OpenAI(
            api_key=xai_api_key,
            base_url="https://api.x.ai/v1"
        )

    def extract_price_filter(self, user_query: str) -> Optional[Dict]:
        """Extract price constraints from user query."""
        query_lower = user_query.lower()

        # Check for specific price mentions
        price_patterns = [
            r'under\s*\$?(\d+)',
            r'less than\s*\$?(\d+)',
            r'below\s*\$?(\d+)',
            r'around\s*\$?(\d+)',
            r'about\s*\$?(\d+)',
            r'\$?(\d+)\s*or less',
            r'\$?(\d+)-\$?(\d+)',  # Range
        ]

        for pattern in price_patterns:
            match = re.search(pattern, query_lower)
            if match:
                if len(match.groups()) == 2:  # Range
                    min_price = int(match.group(1))
                    max_price = int(match.group(2))
                    if max_price < 50:
                        return {"price_range": "<$50"}
                    elif max_price < 100:
                        return {"price_range": {"$in": ["<$50", "$50-100"]}}
                    elif max_price < 200:
                        return {"price_range": {"$in": ["<$50", "$50-100", "$100-200"]}}
                else:
                    price = int(match.group(1))
                    # For "around" or "about", give +/- $25 range
                    if 'around' in query_lower or 'about' in query_lower:
                        if price < 75:
                            return {"price_range": {"$in": ["<$50", "$50-100"]}}
                        elif price < 150:
                            return {"price_range": {"$in": ["$50-100", "$100-200"]}}
                        else:
                            return {"price_range": {"$in": ["$100-200", "$200+"]}}
                    else:
                        if price < 50:
                            return {"price_range": "<$50"}
                        elif price < 100:
                            return {"price_range": {"$in": ["<$50", "$50-100"]}}
                        elif price < 200:
                            return {"price_range": {"$in": ["<$50", "$50-100", "$100-200"]}}

        # Check for budget/affordable/premium keywords
        if any(word in query_lower for word in ['budget', 'affordable', 'cheap', 'inexpensive']):
            return {"price_range": "<$50"}
        elif any(word in query_lower for word in ['premium', 'expensive', 'luxury', 'high-end', 'special occasion']):
            return {"price_range": {"$in": ["$100-200", "$200+"]}}

        return None

    def get_tasting_note_from_master(self, producer: str, region: str) -> Optional[str]:
        """Fetch tasting note from master list or producers namespace."""
        try:
            # Search in producers namespace
            query = f"{producer} {region}"
            results = self.pipeline.search_similar_wines(
                query_text=query,
                top_k=3,
                namespace="producers"
            )

            for wine_id, score, metadata in results:
                if producer.lower() in metadata.get('producer', '').lower():
                    tasting_note = metadata.get('tasting_note', '')
                    if tasting_note and len(tasting_note) > 20:
                        return tasting_note

            # Fallback: search in master list
            results = self.pipeline.search_similar_wines(
                query_text=query,
                list_id="master",
                top_k=3
            )

            for wine_id, score, metadata in results:
                if producer.lower() in metadata.get('producer', '').lower():
                    tasting_keywords = metadata.get('tasting_keywords', '')
                    if tasting_keywords:
                        return tasting_keywords

        except Exception as e:
            logger.error(f"Error fetching tasting note from master: {e}")

        return None

    def generate_detailed_tasting_note(
        self,
        producer: str,
        wine_name: str,
        region: str,
        grapes: str,
        wine_type: str
    ) -> str:
        """Generate detailed tasting note using LLM."""
        try:
            prompt = f"""Generate a detailed, professional tasting note for this wine. Be specific and descriptive.

Producer: {producer}
Wine: {wine_name or region}
Region: {region}
Grapes: {grapes}
Type: {wine_type}

Write 2-3 sentences describing:
1. Aromas and flavors
2. Structure and body
3. Finish

Be specific and elegant. Do not use generic phrases."""

            response = self.grok_client.chat.completions.create(
                model=settings.xai_chat_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=200
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"Error generating tasting note: {e}")
            return f"A {wine_type} from {region} featuring {grapes}."

    def get_food_pairing_suggestion(self, wine_type: str, region: str, grapes: str) -> str:
        """Generate food pairing suggestion using LLM."""
        try:
            prompt = f"""Suggest 2-3 food pairings for this wine. Be brief and specific.

Wine: {wine_type} from {region}
Grapes: {grapes}

Format: "Pairs well with [food 1], [food 2], and [food 3]."
"""
            response = self.grok_client.chat.completions.create(
                model=settings.xai_chat_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=100
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"Error generating food pairing: {e}")
            if 'red' in wine_type.lower():
                return "Pairs well with grilled meats, hearty stews, and aged cheeses."
            elif 'white' in wine_type.lower():
                return "Pairs well with seafood, poultry, and light pasta dishes."
            else:
                return "Versatile pairing options available."

    def get_recommendations(
        self,
        user_query: str,
        top_k: int = 20,
        filters: Optional[Dict] = None
    ) -> List[Dict]:
        """Get exactly 2 wine recommendations based on user query."""
        logger.info(f"Getting recommendations for: {user_query}")

        # Extract price filter from query
        price_filter = self.extract_price_filter(user_query)
        if price_filter:
            logger.info(f"Extracted price filter: {price_filter}")
            if filters:
                filters.update(price_filter)
            else:
                filters = price_filter

        # Search for similar wines
        matches = self.pipeline.search_similar_wines(
            query_text=user_query,
            qr_id=self.config.qr_id,
            list_id=self.config.namespace,
            top_k=top_k,
            filters=filters,
            namespace=self.config.namespace
        )

        if not matches:
            logger.warning("No wines found matching query")
            return []

        # Get full details for each wine
        enriched_wines = []
        for wine_id, score, metadata in matches:
            # Extract all details
            producer = metadata.get("producer", "Unknown")
            wine_name = metadata.get("wine_name", "")
            region = metadata.get("region", "Unknown")
            country = metadata.get("country", "")
            grapes = metadata.get("grapes", "")
            wine_type = metadata.get("wine_type", "unknown")
            price_range = metadata.get("price_range", "")
            vintage = metadata.get("vintage", "")

            # Try to get actual price from metadata
            price = metadata.get("price", "")
            if not price:
                # Extract from price_range as fallback
                if "$50-100" in price_range:
                    price = "75"
                elif "$100-200" in price_range:
                    price = "150"
                elif "$200+" in price_range:
                    price = "250"
                elif "<$50" in price_range:
                    price = "40"

            # Get or generate detailed tasting note
            tasting_note = metadata.get("tasting_note", "")
            if not tasting_note or len(tasting_note) < 20:
                # Try master list first
                master_note = self.get_tasting_note_from_master(producer, region)
                if master_note:
                    tasting_note = master_note
                else:
                    # Generate detailed tasting note
                    tasting_note = self.generate_detailed_tasting_note(
                        producer, wine_name, region, grapes, wine_type
                    )

            # Get or generate food pairing
            food_pairing = self.get_food_pairing_suggestion(wine_type, region, grapes)

            enriched_wines.append({
                "wine_id": wine_id,
                "score": score,
                "producer": producer,
                "wine_name": wine_name,
                "region": region,
                "country": country,
                "vintage": vintage,
                "price": price,
                "grapes": grapes,
                "wine_type": wine_type,
                "price_range": price_range,
                "tasting_note": tasting_note,
                "food_pairing": food_pairing,
                "metadata": metadata
            })

        # Use LLM to select best 2 wines
        selected_wines = self._select_best_two_wines(user_query, enriched_wines)

        logger.info(f"Selected {len(selected_wines)} wines for recommendation")
        return selected_wines[:2]

    def _select_best_two_wines(
        self,
        user_query: str,
        candidates: List[Dict]
    ) -> List[Dict]:
        """Use LLM to select the best 2 wines from candidates."""
        if len(candidates) <= 2:
            return candidates

        # Build candidate descriptions
        candidate_text = "\n\n".join([
            f"Wine {i+1}:\n"
            f"- Producer: {wine['producer']}\n"
            f"- Wine Name: {wine.get('wine_name', 'N/A')}\n"
            f"- Region: {wine['region']}, {wine.get('country', '')}\n"
            f"- Grapes: {wine['grapes']}\n"
            f"- Type: {wine['wine_type']}\n"
            f"- Price: ${wine.get('price', wine['price_range'])}\n"
            f"- Vintage: {wine.get('vintage', 'NV')}\n"
            f"- Similarity Score: {wine['score']:.2f}"
            for i, wine in enumerate(candidates[:15])
        ])

        prompt = f"""You are Jarvis, an expert sommelier. A customer asked: "{user_query}"

Here are the top wine options:

{candidate_text}

Select the BEST 2 wines that perfectly match this request.
Consider:
1. How well they match the customer's preferences (price, grape, region, body)
2. Variety - select wines that offer different experiences
3. Value and quality

Respond with ONLY the wine numbers (e.g., "1,7" or "3,12") separated by a comma.
"""

        try:
            response = self.grok_client.chat.completions.create(
                model=settings.xai_chat_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=50
            )

            selection = response.choices[0].message.content.strip()
            logger.info(f"LLM selected wines: {selection}")

            # Parse response
            selected_indices = []
            for part in selection.split(","):
                try:
                    idx = int(part.strip()) - 1
                    if 0 <= idx < len(candidates):
                        selected_indices.append(idx)
                except ValueError:
                    continue

            if len(selected_indices) >= 2:
                return [candidates[i] for i in selected_indices[:2]]

        except Exception as e:
            logger.error(f"Error selecting wines with LLM: {e}")

        # Fallback: return top 2 by score
        return candidates[:2]

    def get_full_recommendation(self, user_query: str, filters: Optional[Dict] = None) -> List[Dict]:
        """
        Get wine recommendations without intro text.

        Args:
            user_query: User's wine preference query
            filters: Optional filters

        Returns:
            List of 2 wine dictionaries with full details
        """
        # Get wine recommendations with full details
        wines = self.get_recommendations(user_query, filters=filters)

        # Return wines directly, no intro text
        return wines


def test_recommender():
    """Test the recommendation engine."""
    from restaurants.restaurant_config import MAASS_CONFIG

    recommender = WineRecommender(MAASS_CONFIG)

    test_queries = [
        "Bold red wine for steak under $100",
        "Full body Chianti around 125"
    ]

    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"Query: {query}")
        print('='*60)

        wines = recommender.get_full_recommendation(query)

        if wines:
            for i, wine in enumerate(wines, 1):
                print(f"\n{i}. {wine.get('vintage', '')} {wine['producer']} {wine.get('wine_name', '')}")
                print(f"   Region: {wine['region']}, {wine.get('country', '')}")
                print(f"   Price: ${wine.get('price', wine['price_range'])}")
                print(f"   Tasting Note: {wine.get('tasting_note', 'N/A')}")
                print(f"   Food Pairing: {wine.get('food_pairing', 'N/A')}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_recommender()

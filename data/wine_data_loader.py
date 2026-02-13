"""
Wine data loader for Wine Sommelier Agent.
Loads business wine lists into Redis from Excel/CSV files.
"""
import redis
import pandas as pd
import logging
from typing import List, Dict, Optional
from pathlib import Path
import uuid
import unicodedata

from data.schema_definitions import Wine, Business, RedisKeys, WineType, PriceRange
from config import settings

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)


class WineDataLoader:
    """Handles loading wine data from various sources into Redis."""
    
    def __init__(self, redis_required: bool = True):
        """Initialize Redis connection."""
        self.redis_client = None
        if redis_required:
            self.redis_client = redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                db=settings.redis_db,
                password=settings.redis_password,
                decode_responses=True
            )
            logger.info(f"Connected to Redis at {settings.redis_host}:{settings.redis_port}")
    
    def load_business_wine_list(
        self,
        business_id: str,
        business_name: str,
        wine_list_file: Path,
        location: Optional[str] = None
    ) -> int:
        """
        Load a business's wine list from Excel/CSV file into Redis.
        
        Args:
            business_id: Unique identifier for the business
            business_name: Name of the restaurant/wine bar
            wine_list_file: Path to Excel/CSV file with wine data
            location: Optional physical address
            
        Returns:
            Number of wines loaded
            
        Expected file columns:
            - producer (required)
            - wine_name (optional)
            - region (required)
            - country (required)
            - vintage (optional)
            - price (required)
            - grapes (required - comma separated)
            - wine_type (required - red/white/rosé/sparkling/dessert)
            - tasting_note (required)
            - alcohol_content (optional)
        """
        if not self.redis_client:
            raise RuntimeError("Redis is required to load a business wine list.")

        logger.info(f"Loading wine list for {business_name} from {wine_list_file}")
        
        df = self._read_wine_list(wine_list_file)
        
        # Generate QR code identifier
        qr_id = f"qr_{business_id}"
        
        # Store business information
        business = Business(
            business_id=business_id,
            name=business_name,
            location=location,
            qr_code=qr_id,
            wine_list_count=len(df)
        )
        self._store_business(business)
        
        wines, wine_ids = self._wines_from_dataframe(df, qr_id)
        wines_loaded = 0
        for wine in wines:
            self._store_wine(wine)
            wines_loaded += 1
        
        # Store wine list index (set of wine IDs for this business)
        wine_list_key = RedisKeys.wine_list_index(qr_id)
        self.redis_client.sadd(wine_list_key, *wine_ids)
        
        logger.info(f"Successfully loaded {wines_loaded} wines for {business_name}")
        return wines_loaded

    def parse_wine_list(self, wine_list_file: Path, qr_id: str) -> List[Wine]:
        """Parse a wine list file into Wine objects without using Redis."""
        df = self._read_wine_list(wine_list_file)
        wines, _ = self._wines_from_dataframe(df, qr_id)
        return wines

    def _read_wine_list(self, wine_list_file: Path) -> pd.DataFrame:
        if wine_list_file.suffix == '.xlsx':
            df = pd.read_excel(wine_list_file)
        elif wine_list_file.suffix == '.csv':
            df = pd.read_csv(wine_list_file)
        else:
            raise ValueError(f"Unsupported file format: {wine_list_file.suffix}")

        df = self._normalize_columns(df)
        optional_columns = {
            "grapes",
            "wine_name",
            "tasting_note",
            "alcohol_content",
            "vintage",
        }
        for col in optional_columns:
            if col not in df.columns:
                df[col] = ""
        required_columns = {"producer", "region", "country", "price", "wine_type"}
        missing_columns = required_columns - set(df.columns)
        if missing_columns:
            raise ValueError(
                f"Missing required columns after normalization: {', '.join(sorted(missing_columns))}"
            )
        return df

    def _wines_from_dataframe(self, df: pd.DataFrame, qr_id: str) -> tuple[List[Wine], List[str]]:
        wines: List[Wine] = []
        wine_ids: List[str] = []
        for idx, row in df.iterrows():
            try:
                wine_id = f"wine_{uuid.uuid4().hex[:8]}"
                wine_ids.append(wine_id)

                grapes_value = self._get_optional_value(row, "grapes") or ""
                grapes = [g.strip() for g in grapes_value.split(',') if g.strip()]

                wine = Wine(
                    wine_id=wine_id,
                    qr_id=qr_id,
                    producer=self._get_value(row, "producer"),
                    wine_name=self._get_optional_value(row, "wine_name"),
                    region=self._get_value(row, "region"),
                    country=self._get_value(row, "country"),
                    vintage=self._safe_int(self._get_optional_value(row, "vintage")),
                    price=self._safe_float(self._get_value(row, "price")),
                    grapes=grapes,
                    wine_type=self._parse_wine_type(self._get_value(row, "wine_type")),
                    tasting_note=self._get_optional_value(row, "tasting_note") or "No tasting note provided.",
                    alcohol_content=self._safe_float(self._get_optional_value(row, "alcohol_content"))
                )
                wines.append(wine)
            except Exception as e:
                logger.error(f"Error loading wine at row {idx}: {e}")
                continue
        return wines, wine_ids

    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize column names and common aliases for predictable access."""
        normalized = {col: self._slugify(col) for col in df.columns}
        df = df.rename(columns=normalized)

        aliases = {
            "winename": "wine_name",
            "wine": "wine_name",
            "winetype": "wine_type",
            "type": "wine_type",
            "varietal": "grapes",
            "varietals": "grapes",
            "variety": "grapes",
            "grape": "grapes",
            "notes": "tasting_note",
            "tastingnotes": "tasting_note",
            "description": "tasting_note",
            "abv": "alcohol_content",
            "alcohol": "alcohol_content",
        }
        df = df.rename(columns={col: aliases.get(col, col) for col in df.columns})
        return df

    def _slugify(self, value: str) -> str:
        normalized = unicodedata.normalize("NFKD", str(value))
        cleaned = "".join(ch for ch in normalized if ch.isalnum())
        return cleaned.lower()

    def _get_value(self, row: pd.Series, key: str) -> str:
        if key not in row:
            raise KeyError(f"Missing required column: {key}")
        value = row.get(key)
        if pd.isna(value):
            raise ValueError(f"Missing required value for: {key}")
        return str(value).strip()

    def _get_optional_value(self, row: pd.Series, key: str) -> Optional[str]:
        if key not in row:
            return None
        value = row.get(key)
        if pd.isna(value):
            return None
        return str(value).strip()

    def _safe_float(self, value: Optional[str]) -> Optional[float]:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except ValueError:
            return None

    def _safe_int(self, value: Optional[str]) -> Optional[int]:
        if value is None or value == "":
            return None
        try:
            return int(float(value))
        except ValueError:
            return None

    def _parse_wine_type(self, value: str) -> WineType:
        normalized = value.strip().lower()
        normalized = normalized.replace("rose", "rosé")
        mapping = {
            "red": WineType.RED,
            "white": WineType.WHITE,
            "rosé": WineType.ROSE,
            "rose": WineType.ROSE,
            "sparkling": WineType.SPARKLING,
            "dessert": WineType.DESSERT,
        }
        return mapping.get(normalized, WineType.UNKNOWN)
    
    def _store_business(self, business: Business) -> None:
        """Store business data in Redis."""
        if not self.redis_client:
            raise RuntimeError("Redis client is not initialized.")
        key = RedisKeys.business(business.business_id)
        self.redis_client.hset(key, mapping=business.to_redis_hash())
        logger.debug(f"Stored business: {business.business_id}")
    
    def _store_wine(self, wine: Wine) -> None:
        """Store wine data in Redis."""
        if not self.redis_client:
            raise RuntimeError("Redis client is not initialized.")
        key = RedisKeys.wine(wine.qr_id, wine.wine_id)
        self.redis_client.hset(key, mapping=wine.to_redis_hash())
        logger.debug(f"Stored wine: {wine.wine_id}")
    
    def get_business_wines(self, qr_id: str) -> List[Wine]:
        """
        Retrieve all wines for a business.
        
        Args:
            qr_id: QR code identifier for the business
            
        Returns:
            List of Wine objects
        """
        if not self.redis_client:
            raise RuntimeError("Redis client is not initialized.")

        wine_list_key = RedisKeys.wine_list_index(qr_id)
        wine_ids = self.redis_client.smembers(wine_list_key)
        
        wines = []
        for wine_id in wine_ids:
            key = RedisKeys.wine(qr_id, wine_id)
            wine_data = self.redis_client.hgetall(key)
            if wine_data:
                wines.append(Wine.from_redis_hash(wine_data))
        
        return wines
    
    def get_business(self, business_id: str) -> Optional[Business]:
        """
        Retrieve business information.
        
        Args:
            business_id: Business identifier
            
        Returns:
            Business object or None if not found
        """
        if not self.redis_client:
            raise RuntimeError("Redis client is not initialized.")

        key = RedisKeys.business(business_id)
        business_data = self.redis_client.hgetall(key)
        
        if business_data:
            return Business.from_redis_hash(business_data)
        return None
    
    def clear_business_wines(self, business_id: str) -> None:
        """
        Remove all wines for a business from Redis.
        
        Args:
            business_id: Business identifier
        """
        if not self.redis_client:
            raise RuntimeError("Redis client is not initialized.")

        business = self.get_business(business_id)
        if not business:
            logger.warning(f"Business {business_id} not found")
            return
        
        qr_id = business.qr_code
        wine_list_key = RedisKeys.wine_list_index(qr_id)
        wine_ids = self.redis_client.smembers(wine_list_key)
        
        # Delete all wine records
        for wine_id in wine_ids:
            key = RedisKeys.wine(qr_id, wine_id)
            self.redis_client.delete(key)
        
        # Delete wine list index
        self.redis_client.delete(wine_list_key)
        
        # Delete business record
        self.redis_client.delete(RedisKeys.business(business_id))
        
        logger.info(f"Cleared {len(wine_ids)} wines for business {business_id}")


def load_sample_wine_list():
    """
    Example function to load a sample wine list.
    Replace with actual file path and business details.
    """
    loader = WineDataLoader()
    
    # Example usage
    wine_list_path = Path("data/raw/sample_wine_list.xlsx")
    
    if wine_list_path.exists():
        loader.load_business_wine_list(
            business_id="biz_001",
            business_name="The Vineyard Restaurant",
            wine_list_file=wine_list_path,
            location="123 Main St, San Francisco, CA"
        )
    else:
        logger.warning(f"Sample wine list not found at {wine_list_path}")


if __name__ == "__main__":
    load_sample_wine_list()

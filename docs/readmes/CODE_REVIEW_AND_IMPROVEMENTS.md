# Code Review & Pythonic Improvements

**Date**: 2026-02-11
**Status**: Comprehensive Review Complete

---

## Executive Summary

The Wine Sommelier Agent codebase is well-structured with clear separation of concerns. Below are recommendations for making the code more Pythonic, improving usability, and enhancing maintainability.

---

## API Connection Status

✅ **PASSED (5/6 tests)**:
- Encryption Setup
- Configuration Loading
- XAI Grok API
- Pinecone Vector DB
- Embedding Pipeline

⚠️ **OPTIONAL (Redis)**: Not running but system works without it

---

## Code Quality Assessment

### Strengths
1. ✅ Good use of Pydantic for data validation
2. ✅ Clear type hints throughout
3. ✅ Proper use of logging
4. ✅ Well-documented docstrings
5. ✅ Separation of concerns (data, config, crypto)
6. ✅ Enum usage for wine types and price ranges

### Areas for Improvement

---

## 1. Pythonic Improvements

### 1.1 `config.py` - Configuration Management

**Current Issues**:
- Exception handling could be more specific
- Missing context manager support

**Improved Version**:
```python
from contextlib import contextmanager
from functools import lru_cache

class Settings(BaseSettings):
    # ... existing code ...

    @lru_cache(maxsize=1)
    def get_decrypted_xai_key(self) -> str:
        """Cached decrypted key to avoid repeated decryption."""
        try:
            key_manager = SecureKeyManager(encryption_key=self.encryption_key)
            return key_manager.decrypt_key(self.xai_api_key)
        except (ValueError, InvalidToken) as e:
            logger.warning(f"Decryption failed, using raw key: {e}")
            return self.xai_api_key

    @contextmanager
    def temporary_log_level(self, level: str):
        """Context manager for temporary log level changes."""
        old_level = self.log_level
        self.log_level = level
        logging.root.setLevel(level)
        try:
            yield
        finally:
            self.log_level = old_level
            logging.root.setLevel(old_level)
```

### 1.2 `crypto_utils.py` - Security Enhancement

**Current Issues**:
- Generic exception catching
- No key rotation support
- Missing key validation

**Improved Version**:
```python
from cryptography.fernet import Fernet, InvalidToken
from typing import Optional
import secrets

class SecureKeyManager:
    """Manages encryption and decryption of sensitive API keys."""

    def __init__(self, encryption_key: Optional[str] = None):
        self.encryption_key = encryption_key or os.getenv('ENCRYPTION_KEY')

        if not self.encryption_key:
            self.encryption_key = self._generate_secure_key()
            logger.warning(
                "No encryption key found. Generated new key.\n"
                f"Add to .env: ENCRYPTION_KEY={self.encryption_key}"
            )

        self._cipher = self._create_cipher(self.encryption_key)

    @staticmethod
    def _generate_secure_key() -> str:
        """Generate cryptographically secure Fernet key."""
        return Fernet.generate_key().decode()

    def _create_cipher(self, key: str) -> Fernet:
        """Create Fernet cipher with validation."""
        try:
            key_bytes = key.encode() if isinstance(key, str) else key
            return Fernet(key_bytes)
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid encryption key format: {e}") from e

    @property
    def cipher(self) -> Fernet:
        """Lazy-loaded cipher property."""
        if not hasattr(self, '_cipher'):
            self._cipher = self._create_cipher(self.encryption_key)
        return self._cipher

    def encrypt_key(self, api_key: str) -> str:
        """Encrypt an API key with error handling."""
        if not api_key or not isinstance(api_key, str):
            raise ValueError("API key must be a non-empty string")
        try:
            encrypted = self.cipher.encrypt(api_key.encode())
            return encrypted.decode()
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise

    def decrypt_key(self, encrypted_key: str) -> str:
        """Decrypt an API key with specific error handling."""
        try:
            key_bytes = encrypted_key.encode() if isinstance(encrypted_key, str) else encrypted_key
            decrypted = self.cipher.decrypt(key_bytes)
            return decrypted.decode()
        except InvalidToken as e:
            logger.error("Invalid or corrupted encryption token")
            raise ValueError("Decryption failed - invalid token") from e
        except Exception as e:
            logger.error(f"Unexpected decryption error: {e}")
            raise
```

### 1.3 `embedding_pipeline.py` - Performance & Readability

**Current Issues**:
- Long methods that could be broken down
- Repeated code in vector building
- No connection pooling or retries
- Hardcoded values

**Improved Version**:
```python
from functools import wraps
from time import sleep
from typing import Callable, TypeVar

T = TypeVar('T')

def retry_on_failure(max_attempts: int = 3, delay: float = 1.0):
    """Decorator for retrying failed operations."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        logger.warning(
                            f"{func.__name__} failed (attempt {attempt + 1}/{max_attempts}): {e}"
                        )
                        sleep(delay * (attempt + 1))  # Exponential backoff
            raise last_exception
        return wrapper
    return decorator

class EmbeddingPipeline:
    # Constants at class level
    DEFAULT_BATCH_SIZE = 100
    DEFAULT_TOP_K = 5
    KEYWORD_COUNT = (5, 7)  # min, max keywords

    def __init__(self):
        """Initialize with connection pooling and validation."""
        self._grok_client = None
        self._openai_client = None
        self._pc = None
        self._index = None
        self._setup_clients()

    def _setup_clients(self):
        """Lazy initialization of API clients."""
        xai_api_key = settings.get_decrypted_xai_key()
        self._grok_client = OpenAI(
            api_key=xai_api_key,
            base_url="https://api.x.ai/v1",
            timeout=30.0,
            max_retries=2
        )

        if settings.openai_api_key:
            self._openai_client = OpenAI(
                api_key=settings.openai_api_key,
                timeout=30.0,
                max_retries=2
            )

        self._pc = Pinecone(api_key=settings.pinecone_api_key)
        self.wine_loader = WineDataLoader()
        self._setup_index()

        logger.info("Embedding pipeline initialized successfully")

    @property
    def grok_client(self) -> OpenAI:
        """Lazy-loaded Grok client."""
        if not self._grok_client:
            self._setup_clients()
        return self._grok_client

    @retry_on_failure(max_attempts=3, delay=1.0)
    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings with automatic retry."""
        if not texts:
            raise ValueError("Cannot generate embeddings for empty text list")

        embeddings = self._get_embeddings_via_embeddings_api(texts)
        if embeddings is not None:
            return embeddings

        logger.warning("Embedding endpoint failed; falling back to chat-based embeddings")
        return self._get_embeddings_via_chat(texts)

    def generate_wine_text(self, wine: Wine) -> str:
        """Generate rich text representation using f-string template."""
        grapes_text = ", ".join(wine.grapes) if wine.grapes else "Unknown varietals"
        vintage_text = f"{wine.vintage} vintage" if wine.vintage else "non-vintage"

        return (
            f"{wine.producer} {wine.wine_name or ''} - {vintage_text}\n"
            f"Region: {wine.region}, {wine.country}\n"
            f"Grape varietals: {grapes_text}\n"
            f"Wine type: {wine.wine_type.value}\n"
            f"Tasting profile: {wine.tasting_note}\n"
            f"Price: ${wine.price:.2f}"
        ).strip()
```

### 1.4 `wine_data_loader.py` - Data Validation

**Current Issues**:
- Silent failures in data parsing
- No data quality checks
- Missing validation for wine prices

**Improved Version**:
```python
from decimal import Decimal, InvalidOperation
from typing import Tuple

class WineDataLoader:
    """Enhanced wine data loader with validation."""

    # Class constants
    MIN_WINE_PRICE = 5.0
    MAX_WINE_PRICE = 10000.0
    CURRENT_YEAR = datetime.now().year
    MIN_VINTAGE_YEAR = 1900

    def _validate_wine_data(self, wine: Wine) -> Tuple[bool, Optional[str]]:
        """Validate wine data before storage."""
        if not wine.producer.strip():
            return False, "Producer name is required"

        if wine.price < self.MIN_WINE_PRICE or wine.price > self.MAX_WINE_PRICE:
            return False, f"Price ${wine.price} out of valid range"

        if wine.vintage and (wine.vintage < self.MIN_VINTAGE_YEAR or wine.vintage > self.CURRENT_YEAR):
            return False, f"Invalid vintage year: {wine.vintage}"

        if wine.wine_type == WineType.UNKNOWN:
            logger.warning(f"Wine {wine.wine_id} has unknown type")

        return True, None

    def _safe_float(self, value: Optional[str]) -> Optional[float]:
        """Safely convert to float with Decimal precision."""
        if not value or value == "":
            return None
        try:
            # Use Decimal for precise financial calculations
            dec_value = Decimal(str(value).replace(',', ''))
            return float(dec_value)
        except (InvalidOperation, ValueError) as e:
            logger.warning(f"Could not convert '{value}' to float: {e}")
            return None

    def _wines_from_dataframe(
        self,
        df: pd.DataFrame,
        qr_id: str
    ) -> Tuple[List[Wine], List[str], List[Dict[str, Any]]]:
        """Parse wines with error tracking."""
        wines: List[Wine] = []
        wine_ids: List[str] = []
        errors: List[Dict[str, Any]] = []

        for idx, row in df.iterrows():
            try:
                wine = self._create_wine_from_row(row, qr_id)
                is_valid, error_msg = self._validate_wine_data(wine)

                if is_valid:
                    wines.append(wine)
                    wine_ids.append(wine.wine_id)
                else:
                    errors.append({
                        "row": idx,
                        "producer": row.get('producer', 'unknown'),
                        "error": error_msg
                    })
                    logger.error(f"Row {idx} validation failed: {error_msg}")
            except Exception as e:
                errors.append({
                    "row": idx,
                    "error": str(e)
                })
                logger.error(f"Error loading wine at row {idx}: {e}")

        if errors:
            logger.warning(f"Failed to load {len(errors)} wines")

        return wines, wine_ids, errors
```

### 1.5 `maass_ingest.py` - Better Structure

**Current Issues**:
- Hardcoded column mappings
- No validation of extracted data
- Poor error messages

**Improved Version**:
```python
from dataclasses import dataclass
from pathlib import Path
from typing import Final

@dataclass
class ColumnMapping:
    """Configuration for column name normalization."""
    aliases: dict[str, str]
    required: set[str]
    optional: set[str]

# Constants
STANDARD_COLUMNS: Final[list[str]] = [
    "producer", "wine_name", "region", "country", "vintage",
    "price", "grapes", "wine_type", "tasting_note", "alcohol_content"
]

COLUMN_MAPPING = ColumnMapping(
    aliases={
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
    },
    required={"producer", "region", "country", "price", "wine_type"},
    optional={"wine_name", "vintage", "grapes", "tasting_note", "alcohol_content"}
)

class DataQualityError(Exception):
    """Raised when data quality checks fail."""
    pass

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize column names with validation."""
    def slugify(value: str) -> str:
        """Convert to lowercase alphanumeric only."""
        return re.sub(r"[^a-z0-9]", "", str(value).lower())

    # Slugify all column names
    df = df.rename(columns={col: slugify(col) for col in df.columns})

    # Apply aliases
    df = df.rename(columns=COLUMN_MAPPING.aliases)

    # Check for required columns
    missing = COLUMN_MAPPING.required - set(df.columns)
    if missing:
        raise DataQualityError(
            f"Missing required columns: {', '.join(sorted(missing))}"
        )

    # Add missing optional columns
    for col in STANDARD_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    return df[STANDARD_COLUMNS]
```

---

## 2. Usability Improvements

### 2.1 Better Error Messages

**Current**: Generic exceptions
**Improved**: Specific, actionable error messages

```python
class WineDataError(Exception):
    """Base exception for wine data operations."""
    pass

class ValidationError(WineDataError):
    """Raised when data validation fails."""
    pass

class ConnectionError(WineDataError):
    """Raised when API/DB connections fail."""
    pass

# Usage
if not wines:
    raise ValidationError(
        f"No valid wines found in {wine_list_file}. "
        f"Please check the file format and required columns: {REQUIRED_COLUMNS}"
    )
```

### 2.2 Progress Indicators

Add progress bars for long-running operations:

```python
from tqdm import tqdm

def embed_wines(self, wines: List[Wine], ...) -> int:
    """Embed wines with progress tracking."""
    total_embedded = 0

    with tqdm(total=len(wines), desc="Embedding wines") as pbar:
        for i in range(0, len(wines), batch_size):
            batch = wines[i:i + batch_size]
            # ... processing ...
            total_embedded += len(vectors)
            pbar.update(len(batch))

    return total_embedded
```

### 2.3 Configuration Validation

Add startup validation:

```python
def validate_environment() -> list[str]:
    """Validate all required environment variables and connections."""
    errors = []

    if not settings.xai_api_key:
        errors.append("XAI_API_KEY is not set")

    if not settings.pinecone_api_key:
        errors.append("PINECONE_API_KEY is not set")

    # Test API connections
    try:
        pipeline = EmbeddingPipeline()
        pipeline.get_embeddings(["test"])
    except Exception as e:
        errors.append(f"Embedding API test failed: {e}")

    return errors

# In main application startup
if __name__ == "__main__":
    errors = validate_environment()
    if errors:
        logger.error("Environment validation failed:")
        for error in errors:
            logger.error(f"  - {error}")
        sys.exit(1)
```

---

## 3. Performance Optimizations

### 3.1 Caching

```python
from functools import lru_cache
from cachetools import TTLCache, cached

# Cache embeddings for repeated queries
embedding_cache = TTLCache(maxsize=1000, ttl=3600)  # 1 hour TTL

@cached(cache=embedding_cache)
def get_cached_embedding(text: str) -> List[float]:
    """Get embedding with caching."""
    return self.get_embeddings([text])[0]
```

### 3.2 Batch Processing

```python
async def embed_wines_async(
    self,
    wines: List[Wine],
    batch_size: int = 100
) -> int:
    """Asynchronous batch embedding for better performance."""
    import asyncio

    batches = [wines[i:i + batch_size] for i in range(0, len(wines), batch_size)]

    async def process_batch(batch: List[Wine]) -> int:
        wine_texts = [self.generate_wine_text(wine) for wine in batch]
        embeddings = await self.get_embeddings_async(wine_texts)
        vectors = self._build_vectors(batch, embeddings, ...)
        self.index.upsert(vectors=vectors)
        return len(vectors)

    results = await asyncio.gather(*[process_batch(batch) for batch in batches])
    return sum(results)
```

### 3.3 Connection Pooling

Already using OpenAI client which has built-in connection pooling, but ensure:
```python
self.grok_client = OpenAI(
    api_key=xai_api_key,
    base_url="https://api.x.ai/v1",
    timeout=30.0,
    max_retries=2,
    http_client=httpx.Client(
        limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
    )
)
```

---

## 4. Testing Recommendations

### 4.1 Unit Tests

```python
import pytest
from unittest.mock import Mock, patch

def test_wine_data_validation():
    """Test wine data validation logic."""
    loader = WineDataLoader(redis_required=False)

    # Valid wine
    valid_wine = Wine(
        wine_id="test_001",
        qr_id="qr_test",
        producer="Test Winery",
        region="Napa Valley",
        country="USA",
        price=50.0,
        grapes=["Cabernet Sauvignon"],
        wine_type=WineType.RED,
        tasting_note="Bold and fruity"
    )
    is_valid, error = loader._validate_wine_data(valid_wine)
    assert is_valid is True
    assert error is None

    # Invalid price
    invalid_wine = valid_wine.copy()
    invalid_wine.price = -10.0
    is_valid, error = loader._validate_wine_data(invalid_wine)
    assert is_valid is False
    assert "price" in error.lower()
```

### 4.2 Integration Tests

```python
@pytest.mark.integration
def test_maass_ingestion_end_to_end():
    """Test complete MAASS ingestion pipeline."""
    source = Path("test_data/sample_wine_list.xlsx")

    # Ingest
    embedded_count = ingest_maass_list(source, business_id="test_maass")
    assert embedded_count > 0

    # Verify in Pinecone
    pipeline = EmbeddingPipeline()
    results = pipeline.search_similar_wines(
        query_text="bold red wine",
        qr_id="qr_test_maass",
        top_k=5
    )
    assert len(results) > 0
```

---

## 5. Documentation Improvements

### 5.1 README Enhancement

Add quick start examples:

```markdown
## Quick Start

### 1. Ingest a Wine List
\`\`\`python
from pathlib import Path
from data.maass_ingest import ingest_maass_list

# Load your restaurant's wine list
embedded = ingest_maass_list(
    source_path=Path("my_wine_list.xlsx"),
    business_id="my_restaurant",
    business_name="My Restaurant",
    location="123 Main St, City, State"
)
print(f"Embedded {embedded} wines")
\`\`\`

### 2. Search for Wines
\`\`\`python
from data.embedding_pipeline import EmbeddingPipeline

pipeline = EmbeddingPipeline()
results = pipeline.search_similar_wines(
    query_text="light, crisp white wine under $50",
    qr_id="qr_my_restaurant",
    top_k=3
)

for wine_id, score, metadata in results:
    print(f"{metadata['producer']} - {metadata['region']} (Score: {score:.2f})")
\`\`\`
```

---

## 6. Security Recommendations

1. **API Key Rotation**: Implement automated key rotation
2. **Rate Limiting**: Add rate limiting for API calls
3. **Input Validation**: Validate all user inputs (prices, text fields)
4. **SQL Injection Prevention**: If adding SQL database, use parameterized queries
5. **CORS Configuration**: Properly configure CORS for production

---

## Priority Action Items

### High Priority
1. ✅ Add specific exception types
2. ✅ Implement data validation in `WineDataLoader`
3. ✅ Add retry logic for API calls
4. ✅ Add progress indicators for long operations

### Medium Priority
1. Implement caching for embeddings
2. Add comprehensive unit tests
3. Create integration test suite
4. Add async batch processing

### Low Priority
1. Add connection pooling configuration
2. Implement key rotation
3. Add monitoring/metrics
4. Create performance benchmarks

---

## Conclusion

The codebase is in good shape with proper architecture. The recommended improvements will:
- Make code more maintainable and Pythonic
- Improve error handling and user experience
- Enhance performance for large datasets
- Add better validation and testing

**Next Steps**: Implement QR code system for restaurant-specific access (starting with MAASS).

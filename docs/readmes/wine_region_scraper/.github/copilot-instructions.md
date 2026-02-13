# Copilot Instructions for Wine Regions & Grapes Taxonomy Scraper

## Project Context

**Wine Regions & Grapes Taxonomy Scraper** is a one-time data curation agent that builds a comprehensive reference database of wine regions, grape varieties, and their characteristics. The taxonomy is stored in Pinecone for metadata-filtered queries and rule-based wine recommendation inference.

**Goal:** Build 200-400 taxonomy entries mapping regions → primary grapes → styles/pairings, sourced from Wine Folly, Wine-Searcher, Wikipedia, and manual curation.

## Architecture Overview

### Core Data Model
- **WineTaxonomy** (`src/models.py`): Dataclass with 9 required fields
  - `world_type`: "old" (Europe) or "new" (rest of world)
  - `primary_grape`, `common_blends`, `typical_styles`, `food_pairings`
  - Validated by `validate_taxonomy()` before storage

### Three Main Components

1. **TaxonomyBuilder** (`src/taxonomy_builder.py`)
   - Orchestrator class managing in-memory entry list
   - Methods: `load_from_csv()`, `load_from_json_lines()`, `save_as_jsonl()`, `push_to_pinecone(namespace="taxonomy")`
   - Each entry gets id format: `{country}_{region}_{index}`

2. **Scrapers** (`src/scrapers.py`)
   - `get_session_with_retries()`: HTTP client with exponential backoff for rate limiting
   - `scrape_wine_folly()`, `scrape_wine_searcher_regions()`: WIP implementations
   - Manual sources noted (Jancis Robinson, GuildSomm PDFs)

3. **Pinecone Client** (`src/pinecone_client.py`)
   - Single index: `pc.index("wineregionscrape")`
   - Namespace: `"taxonomy"` for all entries
   - Metadata contains full taxonomy object; vectors are 384-dim placeholders

### Data Flow

```
CSV/Manual Input
    ↓
TaxonomyBuilder.load_from_csv()
    ↓
WineTaxonomy instances + validate_taxonomy()
    ↓
TaxonomyBuilder.push_to_pinecone(namespace="taxonomy")
    ↓
Pinecone: Vectors with full metadata + region_key filtering
```

## Development Patterns & Conventions

### Entry Addition Pattern
Always use `TaxonomyBuilder` for consistency:
```python
entry = WineTaxonomy(world_type="old", country="Italy", region="Chianti Classico", ...)
builder.add_entry(entry)  # Validates before adding
```

### CSV Input Format
Expect CSV with columns: `world_type, country, region, larger_region, primary_grape, common_blends, typical_styles, food_pairings, source_url`
- `common_blends`: comma-separated string, auto-converted to list by `load_from_csv()`
- All fields required except `larger_region`

### Pinecone Query Pattern
Metadata-first approach; filter by region attributes:
```python
index.query(vector=[0.0]*384, top_k=10, namespace="taxonomy", 
            filter={"country": "Italy", "world_type": "old"})
```

### File Output Convention
- **JSONL** (primary): One taxonomy object per line, human-readable for streaming
- **CSV** (secondary): For Excel/spreadsheet review
- Both in `data/` directory, created by `TaxonomyBuilder.save_as_*()`

## Critical Workflow Commands

### Local Development
```bash
# Activate environment (required before any Python work)
.venv\Scripts\Activate.ps1

# Load and validate from CSV
python -c "from src.taxonomy_builder import TaxonomyBuilder; b = TaxonomyBuilder(); b.load_from_csv('data/wine_taxonomy.csv'); print(b.get_stats())"

# Push to Pinecone (requires .env with API key)
python -c "from src.taxonomy_builder import TaxonomyBuilder; b = TaxonomyBuilder(); b.load_from_csv('data/wine_taxonomy.csv'); b.push_to_pinecone()"
```

### Data Validation
Before pushing to Pinecone:
- Run `TaxonomyBuilder.load_from_csv()` to catch schema errors early
- Check `get_stats()` output: count and variety of countries/regions
- Verify `source_url` fields are populated (important for attribution)

## Integration Points & Dependencies

### External Services
- **Pinecone:** Index `wineregionscrape`, env vars: `PINECONE_API_KEY`, `PINECONE_ENVIRONMENT`, `PINECONE_INDEX_NAME`
- **Wine Folly, Wine-Searcher, Wikipedia:** Scraping targets; BeautifulSoup parsers WIP
- **Jancis Robinson, GuildSomm:** Manual reference sources (no automated scraping planned)

### Import Patterns
```python
# Always use absolute imports from src/
from src.models import WineTaxonomy, validate_taxonomy
from src.taxonomy_builder import TaxonomyBuilder
from src.pinecone_client import get_index, pc
from src.scrapers import scrape_wine_folly, get_session_with_retries
```

### Environment Requirements
- Python 3.8+
- `.env` file with `PINECONE_API_KEY` (required for `pinecone_client.py`)
- Pinecone index `wineregionscrape` must exist pre-deployment

## Common Tasks & How-Tos

### Add a Single Wine Region
```python
from src.taxonomy_builder import TaxonomyBuilder
from src.models import WineTaxonomy

builder = TaxonomyBuilder()
builder.add_entry(WineTaxonomy(
    world_type="old", country="Spain", region="Rioja",
    larger_region="La Rioja", primary_grape="Tempranillo",
    common_blends=["Garnacha"], 
    typical_styles="medium-bodied, oak, vanilla, plum",
    food_pairings="beef, roasted vegetables",
    source_url="https://..."
))
builder.save_as_jsonl()
```

### Bulk Load from CSV and Push
```python
builder = TaxonomyBuilder()
builder.load_from_csv("wine_data.csv")
print(f"Loaded {len(builder.entries)} entries")
builder.push_to_pinecone(namespace="taxonomy")
```

### Query Taxonomy by Filters
```python
from src.pinecone_client import get_index

index = get_index()
results = index.query(vector=[0.0]*384, top_k=20, namespace="taxonomy",
                      filter={"world_type": "new", "country": {"$in": ["USA", "Australia"]}})
for match in results.matches:
    print(match.metadata)
```

### Scraping New Wine Data
- Check `scrapers.py` for incomplete `scrape_*()` functions
- Use `get_session_with_retries()` to avoid rate limiting
- Parse HTML with BeautifulSoup; test on small samples first
- Convert results to `WineTaxonomy` objects before adding to builder

## Project-Specific Gotchas

1. **Namespace matters:** All Pinecone operations default to `namespace="taxonomy"`. Other namespaces will be ignored by the default index.query() setup.

2. **Metadata vs. Vectors:** Current implementation stores metadata but uses placeholder vectors. Real embeddings (sentence-transformers) would improve semantic search.

3. **CSV parsing:** The `common_blends` field in CSV is a comma-separated string; `load_from_csv()` auto-converts it to a list. Manual JSON entries should already be lists.

4. **Validation is strict:** `validate_taxonomy()` requires non-None/non-empty values for most fields. Missing `source_url` will fail.

5. **Large imports:** Scrapy is installed but not yet used; BeautifulSoup is the primary scraper.

## Testing & Validation

- No formal test suite; validation happens during `load_from_csv()` and `add_entry()`
- Manual spot-checks: Run `TaxonomyBuilder.get_stats()` to verify counts
- Pinecone push is silent; verify manually: `index.describe_index_stats()`

## Files to Reference

- **Schema & Models:** [src/models.py](src/models.py)
- **Data Orchestration:** [src/taxonomy_builder.py](src/taxonomy_builder.py)
- **Pinecone Setup:** [src/pinecone_client.py](src/pinecone_client.py)
- **Data Input:** [data/](data/) for CSV/JSONL files
- **Example Entry:** README.md has sample wine entry

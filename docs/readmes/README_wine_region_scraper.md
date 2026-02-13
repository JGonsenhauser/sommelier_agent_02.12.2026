# Wine Regions & Grapes Taxonomy Scraper

A Python agent for building a comprehensive wine regions and grape varieties taxonomy database.

## Project Overview

**Purpose:** Build a one-time, comprehensive reference taxonomy of wine regions globally with associated grape varieties, styles, and characteristics. Designed to support rule-based wine recommendation inference before LLM processing.

**Output Schema:**
```json
{
  "world_type": "old|new",
  "country": "string",
  "region": "string",
  "larger_region": "string",
  "primary_grape": "string",
  "common_blends": ["string"],
  "typical_styles": "string",
  "food_pairings": "string",
  "source_url": "string"
}
```

## Project Structure

```
wine_region_scraper/
├── .venv/                    # Python virtual environment
├── src/
│   ├── __init__.py
│   ├── models.py             # WineTaxonomy dataclass and validation
│   ├── scrapers.py           # Web scrapers (Wine Folly, Wine-Searcher, etc.)
│   ├── pinecone_client.py    # Pinecone index initialization and utilities
│   └── taxonomy_builder.py   # Core orchestrator for building and storing taxonomy
├── data/                     # Output directory
│   ├── wine_taxonomy.jsonl   # JSON Lines format (main output)
│   └── wine_taxonomy.csv     # CSV format (secondary output)
├── requirements.txt          # Python dependencies
├── .env.example              # Pinecone config template
└── README.md                 # This file
```

## Setup

### 1. Create Virtual Environment
```bash
python -m venv .venv
.venv\Scripts\Activate.ps1  # Windows
source .venv/bin/activate   # macOS/Linux
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Pinecone
- Copy `.env.example` to `.env`
- Add your Pinecone API key and environment
- Ensure index `wineregionscrape` exists in your Pinecone project

### 4. Run Taxonomy Builder
```bash
python -m src.taxonomy_builder
```

## Strategy

**Data Collection (200-400 entries):**
1. **Primary curation sources:**
   - Wine Folly (regions, grapes, maps)
   - Wine-Searcher region pages
   - Wikipedia lists (wine-producing regions, grape varieties)
   
2. **Secondary reference sources:**
   - Jancis Robinson / Oxford Companion to Wine
   - GuildSomm study guides (public PDFs)

3. **Approach:**
   - Mostly manual curation with light scraping (BeautifulSoup)
   - Parse CSV/JSON templates for bulk entry
   - Validation and deduplication before Pinecone storage

## Usage

### Loading Data
```python
from src.taxonomy_builder import TaxonomyBuilder

builder = TaxonomyBuilder()
builder.load_from_csv("wine_data.csv")  # Or load_from_json_lines()
builder.push_to_pinecone(namespace="taxonomy")
```

### Adding Entries Programmatically
```python
from src.models import WineTaxonomy
from src.taxonomy_builder import TaxonomyBuilder

builder = TaxonomyBuilder()

entry = WineTaxonomy(
    world_type="old",
    country="France",
    region="Burgundy",
    larger_region="Bourgogne",
    primary_grape="Pinot Noir",
    common_blends=["Chardonnay"],
    typical_styles="light-bodied, high acidity, red fruit, earthy",
    food_pairings="duck, salmon, mushroom dishes",
    source_url="https://winefolly.com/..."
)

builder.add_entry(entry)
builder.push_to_pinecone()
```

## Pinecone Integration

- **Index Name:** `wineregionscrape`
- **Namespace:** `taxonomy` (default)
- **Metadata Storage:** Full taxonomy object stored as metadata
- **Vectors:** Placeholder embeddings (384-dim) for metadata filtering and hybrid search

### Query Example
```python
from src.pinecone_client import get_index

index = get_index()
results = index.query(
    vector=[0.0] * 384,  # Placeholder
    top_k=10,
    namespace="taxonomy",
    filter={"country": "Italy"}
)
```

## Development Workflow

1. **Data Collection:** Manual curation into `data/wine_taxonomy.csv`
2. **Validation:** Run `TaxonomyBuilder.load_from_csv()` to validate schema
3. **Storage:** `builder.push_to_pinecone()` to index taxonomy
4. **Verification:** Query Pinecone to confirm metadata is indexed

## Dependencies

- `pinecone-client` - Pinecone vector DB access
- `beautifulsoup4` - Web scraping
- `requests` - HTTP client
- `scrapy` - Advanced web scraping (optional)
- `pandas` - CSV handling
- `python-dotenv` - Environment variables

## Notes

- Metadata is indexed in Pinecone; actual embeddings are TBD
- Consider using sentence-transformers for wine description embeddings
- Filter queries by `world_type` for Old World vs New World distinction

# Wine Vintages Data Scraper & Uploader

Extract wine vintage ratings and notes from Excel files and upload to Pinecone vector database for metadata-filtered queries.

## Overview

This tool parses wine vintage data from Excel spreadsheets and uploads it to Pinecone, enabling efficient queries for vintage ratings, tasting notes, and regional characteristics.

## Features

- **Excel Parsing**: Reads multi-column vintage data (region → vintage year → rating & notes)
- **Data Validation**: Ensures vintage years, ratings, and notes meet quality standards
- **Pinecone Integration**: Uploads to vector database with metadata for filtering
- **Export Options**: Save as JSONL or CSV for inspection

## Data Structure

### Input Format (Excel)
```
| Baden (Germany) |                 | Napa (USA) |                 |
|-----------------|-----------------|------------|-----------------|
| Vintage         | Rating & Notes  | Vintage    | Rating & Notes  |
| 2025            | 90: Excellent   | 2025       | 95: Outstanding |
| 2024            | 91: Very good   | 2024       | 93: Excellent   |
```

### WineVintage Model
```python
region: str           # "Baden (Germany)"
vintage: int          # 2025, 2024, etc.
rating: int | None    # 90-100 scale (optional)
notes: str            # Tasting notes and characteristics
```

## Installation

1. Clone the repository:
```bash
git clone https://github.com/JGonsenhauser/wine_vintage_scrape.git
cd wine_vintage_scrape
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
Create a `.env` file in the root directory:
```
PINECONE_API_KEY=your_api_key_here
PINECONE_INDEX_NAME=your_index_name
```

## Usage

### Load and Upload Vintages

```python
from src.vintage_builder import VintageBuilder

vb = VintageBuilder()
vb.load_from_excel('data/wine_vintages_notes.xlsx')

# View statistics
stats = vb.get_stats()
print(f"Loaded {stats['count']} entries")
print(f"Regions: {stats['regions']}")
print(f"Vintage range: {stats['vintage_range']}")

# Push to Pinecone
vb.push_to_pinecone(namespace='vintages')
```

### Run Upload Script

```bash
python upload_vintages.py
```

### Export Data

```python
vb.save_as_jsonl()  # → data/wine_vintages.jsonl
vb.save_as_csv()    # → data/wine_vintages.csv
```

## Querying Pinecone

### Find Vintages for a Region

```python
from src.pinecone_client import get_index

index = get_index()

results = index.query(
    vector=[0.0]*1024,  # Dummy vector for metadata-only query
    top_k=100,
    namespace='vintages',
    filter={"region": "Baden (Germany)"}
)

for match in results.matches:
    print(f"{match.metadata['vintage']}: {match.metadata['notes']}")
```

### Find High-Rated Recent Vintages

```python
results = index.query(
    vector=[0.0]*1024,
    top_k=50,
    namespace='vintages',
    filter={
        "vintage": {"$gte": 2020},
        "rating": {"$gte": 95}
    }
)
```

### Find Vintages by Year Range

```python
results = index.query(
    vector=[0.0]*1024,
    top_k=100,
    namespace='vintages',
    filter={
        "region": "Bordeaux (France)",
        "vintage": {"$gte": 2015, "$lte": 2020}
    }
)
```

## File Structure

```
wine_vintage_scrape/
├── src/
│   ├── vintage_models.py      # WineVintage dataclass & validation
│   ├── vintage_builder.py     # Excel parser & Pinecone uploader
│   └── pinecone_client.py     # Pinecone connection utilities
├── data/
│   └── wine_vintages_notes.xlsx  # (Your Excel file here)
├── upload_vintages.py         # Main upload script
├── requirements.txt           # Python dependencies
├── .env.example              # Environment variables template
└── README.md                 # This file
```

## Implementation Details

### Excel Parsing
- Each region occupies 2 columns (vintage year, rating & notes)
- Ratings extracted via regex: `^(\d+):\s*(.+)$`
- Empty rows and invalid vintages are skipped
- Region names cleaned for vector ID generation

### Pinecone Upload
- **Vector IDs**: `{region}_{vintage}` (e.g., `Baden_Germany_2025`)
- **Embeddings**: 1024-dim random placeholders (replace with real embeddings)
- **Metadata**: All vintage fields (None values excluded)
- **Batch size**: 100 vectors per upsert

### Data Validation
- Vintage year must be 1900-2100
- Rating must be 0-100 (if present)
- Region and notes must be non-empty
- Invalid entries are skipped with warnings

## Upgrading to Real Embeddings

Replace placeholder embeddings with semantic embeddings:

1. Install sentence-transformers:
```bash
pip install sentence-transformers
```

2. Update `vintage_builder.py`:
```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')

# In push_to_pinecone():
embedding = model.encode(entry.notes).tolist()
```

## Requirements

- Python 3.8+
- pandas
- pinecone-client
- python-dotenv
- openpyxl (for Excel reading)

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PINECONE_API_KEY` | Your Pinecone API key | *Required* |
| `PINECONE_INDEX_NAME` | Name of Pinecone index | `wine_vintages` |

## License

MIT

## Contributing

Contributions welcome! Please open an issue or submit a pull request.

## Author

JGonsenhauser

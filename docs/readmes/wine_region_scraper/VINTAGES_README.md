# Wine Vintages Integration

Successfully integrated wine vintage data into the same Pinecone index as the taxonomy data.

## What Was Added

### New Files

1. **[src/vintage_models.py](src/vintage_models.py)** - Data model for wine vintages
   - `WineVintage` dataclass with region, vintage year, rating, and notes
   - Validation function to ensure data quality

2. **[src/vintage_builder.py](src/vintage_builder.py)** - Loader and uploader for vintage data
   - Parses Excel file with region columns (left to right format)
   - Extracts ratings from notes (format: "90: Description...")
   - Uploads to Pinecone with unique IDs (`{region}_{year}`)

3. **[upload_vintages.py](upload_vintages.py)** - Upload script for vintage data
   - Loads from `data/wine_vintages_notes.xlsx`
   - Shows statistics and sample data
   - Pushes to Pinecone namespace `vintages`

### Data Structure

**Source Excel Format:**
- Row 1: Region names (e.g., "Baden (Germany)", "Napa, USA")
- Row 2: Column headers ("Vintage", "Rating & Notes")
- Rows 3+: Vintage years and rating/notes

**WineVintage Model:**
```python
region: str           # "Baden (Germany)"
vintage: int          # 2025, 2024, etc.
rating: int | None    # 90-100 scale (optional)
notes: str            # Tasting notes and characteristics
```

## Uploaded Data Stats

- **Total vintage entries:** 2,839
- **Regions covered:** 134
- **Vintage range:** 1985 - 2025
- **Entries with ratings:** 2,690 / 2,839

## Pinecone Organization

**Index:** `wineregionscrape`

**Namespaces:**
- `wine_taxonomy` - 355 vectors (wine regions, grapes, styles)
- `vintages` - 2,839 vectors (vintage ratings and notes)

**Total:** 3,194 vectors

## Usage Examples

### Load and Upload Vintages
```python
from src.vintage_builder import VintageBuilder

vb = VintageBuilder()
vb.load_from_excel('data/wine_vintages_notes.xlsx')
vb.push_to_pinecone(namespace='vintages')
```

### Query Vintage Data from Pinecone
```python
from src.pinecone_client import get_index

index = get_index()

# Find all vintages for a specific region
results = index.query(
    vector=[0.0]*1024,  # Dummy vector
    top_k=100,
    namespace='vintages',
    filter={"region": "Baden (Germany)"}
)

# Find high-rated recent vintages
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

### Export to JSONL/CSV
```python
vb.save_as_jsonl()  # → data/wine_vintages.jsonl
vb.save_as_csv()    # → data/wine_vintages.csv
```

## Implementation Details

### Excel Parsing Logic
- Each region occupies 2 columns (vintage year, rating & notes)
- Ratings are extracted using regex: `^(\d+):\s*(.+)$`
- Empty rows and invalid vintages are skipped
- Region names are cleaned for use in vector IDs

### Pinecone Upload
- Vector IDs: `{region}_{vintage}` (e.g., `Baden_Germany_2025`)
- Embeddings: 1024-dim random placeholders (replace with real embeddings in production)
- Metadata: All vintage fields except None values (Pinecone requirement)
- Batch size: 100 vectors per upsert

## Next Steps

To use real embeddings instead of placeholders:

1. Install sentence-transformers: `pip install sentence-transformers`
2. Update `vintage_builder.py` to generate embeddings:
```python
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('all-MiniLM-L6-v2')

# In push_to_pinecone():
embedding = model.encode(entry.notes).tolist()
```

# Schema V2 Update - Complete Summary

**Date**: 2026-02-11
**Status**: ✅ Successfully Completed

---

## What Was Done

### 1. Created Standardized Schema V2
✅ **Core Metadata** (shared across all namespaces):
- `producer`, `label`, `grapes`, `region`, `major_region`, `country`
- **`text`** - Standardized embedding text (NO price, NO restaurant info)
- `sync_version` - Schema version tracking

✅ **Restaurant-Specific Metadata** (only in restaurant namespaces):
- `price_range`, `price`, `tasting_keywords`, `list_id`, `qr_id`, `restaurant`
- `vintage`, `wine_type` (optional)

### 2. Updated Vector ID Conventions
✅ **Master Namespace** (producers):
- Format: 32-character MD5 hash
- Example: `0a88e2d504a8b10866a4677a7110c8ca`
- Deterministic based on: `producer + label + grapes + region + country`

✅ **Restaurant Namespace** (e.g., maass_wine_list):
- Format: `{restaurant}_{list_id}_{qr_id}_wine_{hash[:8]}`
- Example: `maass_maass_wine_list_qr_maass_wine_0a88e2d5`
- Human-readable + traceable

### 3. Re-embedded All Data
✅ **MAASS Wine List**: 282 wines → `maass_wine_list` namespace
✅ **Producer List**: 904 wines → `producers` namespace
✅ **Total**: 1,186 wine vectors with new Schema V2 format

### 4. Updated Embedding Source
✅ Embeddings now generated ONLY from `text` field
✅ Text field contains: Producer | Label | Grapes | Region | Major Region | Country
✅ **Excluded**: Price, restaurant, tasting notes (restaurant-specific info)

---

## Key Changes

### Before (Old Schema):
```json
{
  "wine_id": "abc123",
  "producer": "Del Dotto",
  "wine_name": "The Beast",
  "region": "Napa Valley",
  "grapes": "Cabernet Sauvignon",
  "price_range": "$100-200"
}
```
- Mixed metadata (core + restaurant)
- Price included in embedding
- Non-deterministic IDs

### After (Schema V2):
```json
{
  "producer": "Del Dotto",
  "label": "The Beast",
  "grapes": "Cabernet Sauvignon",
  "region": "Napa Valley",
  "major_region": "Napa Valley",
  "country": "United States",
  "text": "Producer: Del Dotto | Label: The Beast | Grapes: Cabernet Sauvignon...",
  "sync_version": 2,
  "price_range": "$100-200",
  "price": 125.00,
  "restaurant": "maass",
  "list_id": "maass_wine_list",
  "qr_id": "qr_maass"
}
```
- Clear core + restaurant separation
- Standardized text (no price)
- Deterministic master hash IDs
- Schema versioning

---

## Files Created

| File | Purpose |
|------|---------|
| `data/schema_v2.py` | Schema definitions, ID generators, validation |
| `migrate_to_schema_v2.py` | Migration script to re-embed with new schema |
| `verify_schema_v2.py` | Verification script to test migration |
| `SCHEMA_V2_MIGRATION_COMPLETE.md` | Detailed migration documentation |
| `SCHEMA_UPDATE_SUMMARY.md` | This summary document |

## Files Modified

| File | Changes |
|------|---------|
| `data/embedding_pipeline.py` | Updated `search_similar_wines()` to use vector ID instead of metadata wine_id (Schema V2 compatible) |

---

## Benefits

### 1. Deterministic IDs ✓
- Same wine always gets same master ID
- Easy to check for duplicates
- Cross-list wine identity

### 2. Pure Embeddings ✓
- No price/restaurant info in embeddings
- Better semantic search
- Consistent embeddings across all lists

### 3. Clear Namespace Separation ✓
- Restaurant namespaces: Core + Restaurant metadata
- Master namespace: Core metadata only
- Easy to understand data structure

### 4. Schema Versioning ✓
- `sync_version: 2` tracks schema
- Easy to identify old vs new format
- Enables future migrations

### 5. Flexible Price Handling ✓
- `price_range` (string) for categories
- `price` (number) for exact amounts
- Both available for filtering

---

## Verification Results

### ✅ MAASS Restaurant List
```
Namespace: maass_wine_list
Vectors: 282
Vector ID Format: maass_maass_wine_list_qr_maass_wine_{hash8} ✓
Metadata: Core + Restaurant fields ✓
Text Field: Present (no price/restaurant) ✓
sync_version: 2 ✓
```

### ✅ Producers Master List
```
Namespace: producers
Vectors: 904
Vector ID Format: 32-char MD5 hash ✓
Metadata: Core fields only ✓
Text Field: Present (no price/restaurant) ✓
No Restaurant Fields: Confirmed ✓
```

---

## Example Usage

### Search with New Schema:
```python
from data.embedding_pipeline import EmbeddingPipeline

pipeline = EmbeddingPipeline()

results = pipeline.search_similar_wines(
    query_text="Bold Cabernet Sauvignon from Napa Valley",
    namespace="maass_wine_list",
    top_k=5
)

for wine_id, score, metadata in results:
    print(f"Producer: {metadata['producer']}")
    print(f"Label: {metadata['label']}")
    print(f"Region: {metadata['region']}")
    print(f"Price Range: {metadata['price_range']}")
    print(f"Schema: v{metadata['sync_version']}")
```

### Generate Master ID:
```python
from data.schema_v2 import CoreWineMetadata

master_id = CoreWineMetadata.generate_master_id(
    producer="Del Dotto",
    label="The Beast",
    grapes="Cabernet Sauvignon",
    region="Napa Valley",
    country="United States"
)
# Returns: "0a88e2d504a8b10866a4677a7110c8ca"
```

---

## Testing Commands

### Verify Migration:
```bash
python verify_schema_v2.py
```

### Test Search:
```bash
python -c "
from data.embedding_pipeline import EmbeddingPipeline

pipeline = EmbeddingPipeline()
results = pipeline.search_similar_wines(
    query_text='Malbec Argentina',
    namespace='producers',
    top_k=3
)

for wine_id, score, metadata in results:
    print(f'{wine_id[:16]}... - {metadata[\"producer\"]} {metadata[\"label\"]}')
    print(f'  Version: {metadata.get(\"sync_version\", \"old\")}')
"
```

---

## Migration Summary

| Metric | Value |
|--------|-------|
| **Total Wines Migrated** | 1,186 |
| **MAASS Restaurant** | 282 wines |
| **Producers Master** | 904 wines |
| **Schema Version** | 2 |
| **Namespaces Updated** | 2 |
| **Vector ID Format** | Deterministic (MD5 hash) |
| **Embedding Source** | Standardized (no price) |
| **Status** | ✅ Complete |

---

## Next Steps

### Immediate:
1. ✅ Schema V2 implemented
2. ✅ Data migrated and embedded
3. ✅ Search function updated
4. ✅ Verification complete

### Optional:
1. ⏳ Update wine recommender to use new field names (currently still works)
2. ⏳ Clean up any old vectors if needed
3. ⏳ Add more restaurants with new schema
4. ⏳ Update Streamlit UI to show new metadata fields

---

## Documentation

📄 **Detailed Documentation**: See [SCHEMA_V2_MIGRATION_COMPLETE.md](SCHEMA_V2_MIGRATION_COMPLETE.md)

📄 **Schema Reference**: See [data/schema_v2.py](data/schema_v2.py)

📄 **Verification Results**: Run `python verify_schema_v2.py`

---

**Status**: ✅ Schema V2 successfully implemented and all data migrated!

The system now uses standardized metadata with:
- Deterministic vector IDs
- Pure wine characteristic embeddings
- Clear core/restaurant metadata separation
- Schema versioning for future migrations

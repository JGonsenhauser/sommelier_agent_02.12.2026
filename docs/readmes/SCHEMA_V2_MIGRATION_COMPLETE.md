# Schema V2 Migration Complete

**Date**: 2026-02-11
**Status**: ✅ Successfully Migrated

---

## Migration Summary

### Wines Migrated:
- **MAASS Restaurant List**: 282 wines → `maass_wine_list` namespace
- **Producer Master List**: 904 wines → `producers` namespace
- **Total**: 1,186 wine vectors with new Schema V2 format

---

## Schema V2 Changes

### Core Metadata (Shared Across All Namespaces)

| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `producer` | string | Yes | Wine producer/winery name | "Del Dotto" |
| `label` | string | No | Specific wine label/cuvée | "The Beast" |
| `grapes` | string | Yes | Primary grape variety or blend | "Cabernet Sauvignon" |
| `region` | string | Yes | Sub-region/appellation | "Napa Valley" |
| `major_region` | string | No | Broader region | "Napa Valley" |
| `country` | string | Yes | Country of origin | "United States" |
| **`text`** | string | Yes | **Standardized embedding text (NO price, NO restaurant)** | "Producer: Del Dotto \| Label: The Beast \| Grapes: Cabernet Sauvignon \| Region: Napa Valley \| Major Region: Napa Valley \| Country: United States" |
| `sync_version` | integer | No | Schema version (2 for new format) | 2 |

### Restaurant-Specific Metadata (Only in Restaurant Namespaces)

| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `price_range` | string | Yes | Price category | "<$50", "$100-200" |
| `price` | number | No | Exact price in USD | 125.00 |
| `tasting_keywords` | string | No | Tasting note or keywords | "Bold, rich, full-bodied" |
| `list_id` | string | Yes | Wine list identifier | "maass_wine_list" |
| `qr_id` | string | Yes | QR code identifier | "qr_maass" |
| `restaurant` | string | Yes | Restaurant short name | "maass" |
| `vintage` | string | No | Vintage year | "2020" |
| `wine_type` | string | No | Wine type classification | "Red Wine" |

---

## Vector ID Conventions

### Master Namespace (producers)
**Format**: 32-character lowercase MD5 hash

**Generation**:
```python
md5(producer + "_" + label + "_" + grapes + "_" + region + "_" + country)
```

**Example**:
```
0a88e2d504a8b10866a4677a7110c8ca
```

### Restaurant Namespace (e.g., maass_wine_list)
**Format**: `{restaurant}_{list_id}_{qr_id}_wine_{master_hash[:8]}`

**Generation**:
```python
master_hash = md5(producer + "_" + label + "_" + grapes + "_" + region + "_" + country)
restaurant_id = f"{restaurant}_{list_id}_{qr_id}_wine_{master_hash[:8]}"
```

**Example**:
```
maass_maass_wine_list_qr_maass_wine_0a88e2d5
```

---

## Embedding Source

**CRITICAL**: Embeddings are ONLY generated from the `text` field

### What's Included in `text`:
✅ Producer
✅ Label (wine name)
✅ Grapes
✅ Region
✅ Major Region
✅ Country

### What's EXCLUDED from `text`:
❌ Price
❌ Price Range
❌ Restaurant Name
❌ Tasting Notes
❌ List ID
❌ QR ID

**Why?** This ensures embeddings are based purely on wine characteristics, not restaurant-specific information. The same wine can appear in multiple restaurant lists with different prices, but will have the same embedding.

---

## Migration Process

### Step 1: Schema Definition
Created `data/schema_v2.py` with:
- `CoreWineMetadata` dataclass (core fields)
- `RestaurantWineMetadata` dataclass (core + restaurant fields)
- Vector ID generation methods
- Standardized text generation (no price/restaurant)

### Step 2: Migration Script
Created `migrate_to_schema_v2.py` to:
1. Read existing wine data from Excel/CSV
2. Normalize column names
3. Generate standardized `text` field
4. Generate new vector IDs (master hash format)
5. Create Schema V2 metadata
6. Re-embed to Pinecone with new structure

### Step 3: Verification
Created `verify_schema_v2.py` to test:
- Schema V2 fields present in metadata
- Vector ID formats correct
- Restaurant fields only in restaurant namespace
- Core fields only in producers namespace
- Search functionality working

---

## Verification Results

### ✅ MAASS Wine List (Restaurant Namespace)
- **Namespace**: `maass_wine_list`
- **Vector Count**: 282
- **Vector ID Format**: `maass_maass_wine_list_qr_maass_wine_{hash8}`
- **Metadata**: Core + Restaurant fields ✓
- **Text Field**: Present (no price/restaurant) ✓
- **sync_version**: 2 ✓

### ✅ Producers List (Master Namespace)
- **Namespace**: `producers`
- **Vector Count**: 904
- **Vector ID Format**: 32-char MD5 hash ✓
- **Metadata**: Core fields only ✓
- **Text Field**: Present (no price/restaurant) ✓
- **No Restaurant Fields**: Confirmed ✓

---

## Example Metadata Comparison

### Before (Old Schema):
```json
{
  "wine_id": "abc123",
  "qr_id": "qr_maass",
  "list_id": "maass_wine_list",
  "producer": "Del Dotto",
  "wine_name": "The Beast",
  "region": "Napa Valley",
  "country": "United States",
  "grapes": "Cabernet Sauvignon",
  "wine_type": "red",
  "price_range": "$100-200",
  "tasting_keywords": "Bold, rich, tannic"
}
```

**Vector ID**: `maass_wine_list_qr_maass_abc123`

### After (Schema V2):
```json
{
  "producer": "Del Dotto",
  "label": "The Beast",
  "grapes": "Cabernet Sauvignon",
  "region": "Napa Valley",
  "major_region": "Napa Valley",
  "country": "United States",
  "text": "Producer: Del Dotto | Label: The Beast | Grapes: Cabernet Sauvignon | Region: Napa Valley | Major Region: Napa Valley | Country: United States",
  "sync_version": 2,
  "price_range": "$100-200",
  "price": 125.00,
  "list_id": "maass_wine_list",
  "qr_id": "qr_maass",
  "restaurant": "maass",
  "tasting_keywords": "Bold, rich, tannic",
  "vintage": "2020"
}
```

**Master ID**: `0a88e2d504a8b10866a4677a7110c8ca`
**Vector ID**: `maass_maass_wine_list_qr_maass_wine_0a88e2d5`

---

## Key Improvements

### 1. Deterministic IDs
- Master IDs are deterministic MD5 hashes
- Same wine always gets same master ID
- Easy to check for duplicates across lists

### 2. Standardized Embedding Text
- No price information in embeddings
- No restaurant-specific info in embeddings
- Pure wine characteristics only
- Consistent embeddings across all lists

### 3. Clear Namespace Separation
- **Restaurant namespaces**: Full metadata (core + restaurant)
- **Master namespace**: Core metadata only
- Easy to understand what belongs where

### 4. Schema Versioning
- `sync_version` field tracks schema version
- Easy to identify old vs new format
- Enables future migrations

### 5. Flexible Price Handling
- `price_range` (string) for categories
- `price` (number) for exact prices
- Both available for filtering

---

## Updated Code

### Files Created:
1. **data/schema_v2.py** - Schema definitions and helpers
2. **migrate_to_schema_v2.py** - Migration script
3. **verify_schema_v2.py** - Verification script
4. **SCHEMA_V2_MIGRATION_COMPLETE.md** - This documentation

### Files Modified:
1. **data/embedding_pipeline.py**
   - Updated `search_similar_wines()` to use vector ID instead of metadata wine_id
   - Now compatible with both old and new schema

---

## Usage Examples

### Generate Master ID
```python
from data.schema_v2 import CoreWineMetadata

master_id = CoreWineMetadata.generate_master_id(
    producer="Del Dotto",
    label="The Beast",
    grapes="Cabernet Sauvignon",
    region="Napa Valley",
    country="United States"
)
# Result: "0a88e2d504a8b10866a4677a7110c8ca"
```

### Generate Standardized Text
```python
text = CoreWineMetadata.generate_text(
    producer="Del Dotto",
    label="The Beast",
    grapes="Cabernet Sauvignon",
    region="Napa Valley",
    major_region="Napa Valley",
    country="United States"
)
# Result: "Producer: Del Dotto | Label: The Beast | Grapes: Cabernet Sauvignon | Region: Napa Valley | Major Region: Napa Valley | Country: United States"
```

### Generate Restaurant Vector ID
```python
from data.schema_v2 import RestaurantWineMetadata

vector_id = RestaurantWineMetadata.generate_restaurant_id(
    restaurant="maass",
    list_id="maass_wine_list",
    qr_id="qr_maass",
    master_id="0a88e2d504a8b10866a4677a7110c8ca"
)
# Result: "maass_maass_wine_list_qr_maass_wine_0a88e2d5"
```

### Search with New Schema
```python
from data.embedding_pipeline import EmbeddingPipeline

pipeline = EmbeddingPipeline()

# Search restaurant namespace
results = pipeline.search_similar_wines(
    query_text="Bold Cabernet Sauvignon from Napa",
    namespace="maass_wine_list",
    top_k=5
)

# Results automatically include new schema fields
for wine_id, score, metadata in results:
    print(f"Producer: {metadata['producer']}")
    print(f"Label: {metadata['label']}")
    print(f"Price Range: {metadata['price_range']}")
    print(f"Text: {metadata['text']}")
```

---

## Testing Commands

### Run Verification
```bash
python verify_schema_v2.py
```

### Re-run Migration (if needed)
```bash
python migrate_to_schema_v2.py
```

### Test Search
```bash
python -c "
from data.embedding_pipeline import EmbeddingPipeline

pipeline = EmbeddingPipeline()
results = pipeline.search_similar_wines(
    query_text='Cabernet Sauvignon Napa',
    namespace='maass_wine_list',
    top_k=3
)

for wine_id, score, metadata in results:
    print(f'{metadata[\"producer\"]} - {metadata[\"label\"]} ({metadata[\"region\"]})')
    print(f'  Schema Version: {metadata.get(\"sync_version\", \"old\")}')
    print()
"
```

---

## Next Steps

### Immediate:
1. ✅ ~~Migrate MAASS wine list~~ - DONE
2. ✅ ~~Migrate producers list~~ - DONE
3. ✅ ~~Verify new schema~~ - DONE
4. ✅ ~~Update search function~~ - DONE

### Optional:
1. ⏳ Clean up old vectors with old schema (if any remain)
2. ⏳ Update wine recommender to use new field names
3. ⏳ Add more restaurants with new schema
4. ⏳ Update Streamlit app to display new metadata

---

## Schema V2 Benefits Summary

| Feature | Before | After | Benefit |
|---------|--------|-------|---------|
| **Vector IDs** | Random/sequential | Deterministic hash | Deduplication, consistency |
| **Embedding Source** | Mixed (with price) | Standardized (no price) | Better semantic search |
| **Metadata Structure** | Flat, mixed | Core + Restaurant | Clear separation |
| **Schema Version** | None | `sync_version: 2` | Migration tracking |
| **Master IDs** | None | MD5 hash | Cross-list identity |
| **Price Handling** | String only | String + number | Flexible filtering |
| **Major Region** | Missing | Added | Better geo-hierarchy |

---

## Troubleshooting

### If search returns no results:
1. Check namespace name is correct
2. Verify vectors were uploaded: use Pinecone console
3. Check `sync_version` field in results

### If old schema vectors still appear:
1. Old vectors may coexist with new ones
2. Filter by `sync_version: 2` if needed
3. Or run cleanup script to remove old vectors

### If vector IDs look wrong:
1. Check that master hash is being generated correctly
2. Verify input fields are not empty
3. Ensure MD5 hash function is working

---

**Migration Status**: ✅ Complete and Verified

**Total Vectors Migrated**: 1,186 wines
**Schema Version**: 2
**Namespaces Updated**: 2 (maass_wine_list, producers)

# Sommelier Agent - Architecture & Data Flow

## System Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                        USER (Mobile/Desktop)                     │
│                     Scans QR code or opens URL                   │
└───────────────────────────┬──────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│                   STREAMLIT FRONTEND (:8501)                     │
│                   app_fastapi_hybrid.py                          │
│                                                                  │
│  - Displays MAASS logo header                                    │
│  - Chat interface (user <-> Jarvis)                              │
│  - Caches API results (st.cache_data, 1hr TTL)                  │
│  - Handles errors with friendly messages                         │
└───────────────────────────┬──────────────────────────────────────┘
                            │ POST /api/recommend
                            │ {query, restaurant_id}
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│                   FASTAPI BACKEND (:8000)                        │
│                   api/mobile_api.py                               │
│                                                                  │
│  - REST API with CORS enabled                                    │
│  - Creates OptimizedWineRecommender per request                  │
│  - Returns JSON: {wines[], query, restaurant_name, time}         │
│  - Catches EmbeddingError -> friendly error message              │
└───────────────────────────┬──────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│              OPTIMIZED WINE RECOMMENDER                          │
│              restaurants/wine_recommender_optimized.py            │
│                                                                  │
│  Step 1: EXTRACT PRICE FILTER                                    │
│  ├── "around 90"    -> {price: {$gte: 63, $lte: 117}}          │
│  ├── "under 80"     -> {price: {$lte: 80}}                     │
│  ├── "$100-$200"    -> {price: {$gte: 100, $lte: 200}}         │
│  ├── "budget"       -> {price: {$lte: 50}}                     │
│  └── "premium"      -> {price: {$gte: 100}}                    │
│                                                                  │
│  Step 2: GENERATE QUERY EMBEDDING                                │
│  └── OpenAI text-embedding-3-small (1024 dimensions)             │
│                                                                  │
│  Step 3: VECTOR SEARCH (Pinecone)                                │
│  ├── Index: wineregionscrape                                     │
│  ├── Namespace: maass_wine_list (282 wines)                      │
│  ├── Filter: price range + list_id                               │
│  └── Returns: Top 10 matches with metadata                       │
│                                                                  │
│  Step 4: ENRICH METADATA (parallel ThreadPoolExecutor)           │
│  └── Extract producer, region, grapes, price, text from each     │
│                                                                  │
│  Step 5: LLM SELECT BEST 2 WINES                                │
│  ├── Sends all 10 candidates to Grok                             │
│  ├── Grok evaluates match quality, variety, value                │
│  └── Returns "1,7" -> picks wine 1 and wine 7                   │
│                                                                  │
│  Step 6: GENERATE TASTING NOTES (for 2 wines only)              │
│  ├── Check 1: Existing metadata note valid?                      │
│  ├── Check 2: Redis cache hit?                                   │
│  ├── Check 3: Pinecone producers namespace?                      │
│  └── Check 4: Generate via Grok LLM (3-4 sentences)             │
│       └── Cache result in Redis                                  │
└──────────────────────────────────────────────────────────────────┘
```

## External Services

```
┌─────────────────────────────────────────────────────────────────┐
│                      EXTERNAL SERVICES                           │
│                                                                  │
│  ┌─────────────────────┐  ┌──────────────────────────────────┐  │
│  │   OpenAI API        │  │   XAI Grok API                   │  │
│  │                     │  │                                  │  │
│  │   EMBEDDINGS ONLY   │  │   ALL LLM CHAT                   │  │
│  │   text-embedding-   │  │   grok-4-fast-reasoning          │  │
│  │   3-small           │  │                                  │  │
│  │   1024 dimensions   │  │   - Wine selection (best 2)      │  │
│  │   10s timeout       │  │   - Tasting note generation      │  │
│  │                     │  │   - Food pairing (on request)    │  │
│  └─────────────────────┘  └──────────────────────────────────┘  │
│                                                                  │
│  ┌─────────────────────┐  ┌──────────────────────────────────┐  │
│  │   Pinecone          │  │   Redis Cloud                    │  │
│  │                     │  │                                  │  │
│  │   VECTOR SEARCH     │  │   CACHING LAYER                  │  │
│  │   Index:            │  │                                  │  │
│  │   wineregionscrape  │  │   Host: redis-11062.c261.       │  │
│  │                     │  │   us-east-1-4.ec2.cloud.        │  │
│  │   Namespaces:       │  │   redislabs.com:11062           │  │
│  │   - maass_wine_list │  │                                  │  │
│  │     (282 vectors)   │  │   Caches:                        │  │
│  │   - producers       │  │   - Tasting notes                │  │
│  │     (2079 vectors)  │  │   - Food pairings                │  │
│  │   - vintages        │  │   - Query results                │  │
│  │     (2839 vectors)  │  │                                  │  │
│  │   - wine_taxonomy   │  │   TTL: 24 hours                  │  │
│  │     (355 vectors)   │  │   Timeout: 10 seconds            │  │
│  └─────────────────────┘  └──────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Request Flow Example

```
USER: "light pinot noir around 90"
  │
  ▼
STREAMLIT (:8501)
  │ POST http://localhost:8000/api/recommend
  │ Body: {"query": "light pinot noir around 90", "restaurant_id": "maass"}
  ▼
FASTAPI (:8000)
  │
  ├─► STEP 1: Price Filter
  │   "around 90" → {price: {$gte: 63, $lte: 117}}
  │
  ├─► STEP 2: Embed Query
  │   "light pinot noir around 90"
  │     → OpenAI text-embedding-3-small
  │     → [0.023, -0.441, 0.187, ...] (1024 floats)
  │
  ├─► STEP 3: Pinecone Search
  │   namespace: maass_wine_list
  │   filter: {price: {$gte: 63, $lte: 117}, list_id: "maass_wine_list"}
  │   top_k: 10
  │     → 10 wines with similarity scores
  │
  ├─► STEP 4: Enrich (parallel)
  │   Extract metadata for all 10 wines
  │
  ├─► STEP 5: LLM Selection
  │   Grok evaluates 10 candidates
  │     → "Wine 1,4" (best 2 matches)
  │
  ├─► STEP 6: Tasting Notes
  │   Wine 1: Redis cache HIT → use cached note
  │   Wine 4: Redis cache MISS → Grok generates 3-4 sentences → cache
  │
  └─► RESPONSE
      {
        wines: [
          {producer, region, price, text, tasting_note, ...},
          {producer, region, price, text, tasting_note, ...}
        ],
        processing_time: 3.2s
      }
```

## Error Handling Flow

```
USER QUERY
  │
  ├─► OpenAI Embeddings OK (200)
  │   └── Normal flow → 2 wine recommendations
  │
  └─► OpenAI Embeddings FAIL (500/503)
      │   10-second timeout, no retries to garbage fallbacks
      │
      └── EmbeddingError raised
          │
          ├─► FastAPI catches → returns {error: "...", wines: []}
          │
          └─► Streamlit displays friendly message:
              "Our wine search is momentarily refreshing —
               like a good decant! Please try again in a few seconds."
```

## Key Files

```
sommelier_agent/
├── .env                              # API keys, config (encrypted XAI key)
├── config.py                         # Settings, Fernet key decryption
├── api/
│   └── mobile_api.py                 # FastAPI backend (port 8000)
├── data/
│   ├── embedding_pipeline.py         # OpenAI embeddings + Pinecone search
│   ├── wine_data_loader.py           # Redis data loader
│   └── schema_definitions.py         # Wine/Embedding data models
├── restaurants/
│   ├── app_fastapi_hybrid.py         # Streamlit frontend (port 8501)
│   ├── wine_recommender_optimized.py # Core recommendation engine
│   ├── restaurant_config.py          # Per-restaurant settings
│   └── maass/
│       ├── maass_logo.jpg            # Restaurant logo
│       └── setup_maass.py            # MAASS-specific setup
└── .streamlit/
    └── config.toml                   # Streamlit theme (black & white)
```

## Running the App

```bash
# Terminal 1: Start FastAPI backend
python -m uvicorn api.mobile_api:app --reload --port 8000

# Terminal 2: Start Streamlit frontend
streamlit run restaurants/app_fastapi_hybrid.py --server.port 8501

# Access: http://localhost:8501
```

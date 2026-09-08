# Jarvis — Restaurant-Branded AI Sommelier

AI wine sommelier for restaurants and hotels. Guests scan a QR code (no signup), describe what they want, and get **exactly two** bottles from that property’s list — with a short reason, tasting note, and a pairing from tonight’s menu. They can email the two bottles to themselves; the sommelier desk keeps a report.

**Primary restaurant:** MAASS (`restaurant_id=maass`, ~282 wines)

---

## What It Does

| Capability | Detail |
|---|---|
| Natural-language wine search | “light pinot noir around 90”, “bold red for steak”, “under $50” |
| Price-aware filtering | Parses budget / under / around / ranges before vector search |
| List-only matching | Wine-aware search over the property catalog, then Grok picks 2 |
| Tasting notes | Grounded in grape/region; cached per wine |
| Food pairing | Tonight’s menu when the dish is on the list |
| Email + CRM | Guest emails the two bottles; admin report at `/admin` |
| Multi-restaurant | `/?r={id}`, per-property namespace, branding, QR |
| Guest UI | Phone PWA (`mobile/index.html`) served by FastAPI |

---

## High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  Guest (phone)                                                   │
│  QR code → PWA  /?r={restaurant_id}  (mobile/index.html)         │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                             ▼
                             │  POST /api/recommend
                             │  { "query", "restaurant_id" }
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│  FASTAPI  :8000  api/mobile_api.py                               │
│  Guest PWA, email capture, admin report                          │
│  Returns wines[] (no scores) + recommendation_id                 │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│  RECOMMENDATION ENGINE                                           │
│  restaurants/wine_recommender_optimized.py                       │
│                                                                  │
│  1. Extract price filter from query                              │
│  2. Embed query (OpenAI text-embedding-3-small, 1024-d)          │
│  3. Pinecone vector search (restaurant namespace + filters)       │
│  4. Enrich top matches (metadata)                                │
│  5. Grok selects best 2 wines                                    │
│  6. Tasting notes: metadata → Redis → producers NS → Grok        │
└──────────────────────────────────────────────────────────────────┘
```

### How services connect

```
                    ┌─────────────────────┐
                    │   OpenAI API        │
                    │   Embeddings only   │
                    │   text-embedding-   │
                    │   3-small (1024)    │
                    └──────────▲──────────┘
                               │ query / wine vectors
┌──────────────┐    ┌──────────┴──────────┐    ┌─────────────────────┐
│ Streamlit UI │───▶│ FastAPI + Engine    │───▶│ XAI Grok API        │
│ :8501        │    │ :8000               │    │ Chat / selection /  │
└──────────────┘    └──────────┬──────────┘    │ tasting notes       │
                               │               └─────────────────────┘
                    ┌──────────┼──────────┐
                    ▼                     ▼
           ┌────────────────┐    ┌────────────────┐
           │ Pinecone       │    │ Redis (opt.)   │
           │ Vector search  │    │ Tasting notes, │
           │ + namespaces   │    │ pairings, etc. │
           └────────────────┘    └────────────────┘
```

| Service | Role | Used for |
|---|---|---|
| **OpenAI** | Embeddings | Query + wine list vectors (`text-embedding-3-small`, 1024 dims) |
| **XAI Grok** | LLM | Pick best 2 wines, tasting notes, pairings |
| **Pinecone** | Vector DB | Semantic search over restaurant wine lists + enrichment namespaces |
| **Redis** | Cache | Tasting notes / pairings / repeated results (optional; degrades gracefully) |
| **Streamlit** | Frontend | Guest chat UI |
| **FastAPI** | Backend | Recommendation API for UI, mobile, future clients |

Config is loaded from `.env` via [`config.py`](config.py). XAI keys may be Fernet-encrypted (`crypto_utils.py` / `key_management.py`).

---

## Recommendation Pipeline (one request)

Example query: **“light pinot noir around 90”**

1. **Price filter** — `around 90` → roughly `$63–$117` (and similar rules for under/range/budget/premium)
2. **Embed** — OpenAI turns the query into a 1024-d vector
3. **Search** — Pinecone in the restaurant namespace (e.g. `maass_wine_list`), filtered by price / list id, top ~10
4. **Enrich** — producer, region, grapes, price, display text
5. **Select** — Grok ranks candidates and returns the best **2**
6. **Notes** — reuse stored note → Redis hit → producer context in Pinecone → else generate with Grok and cache
7. **Respond** — JSON with two wines + processing time

Typical first-hit latency is a few seconds; cached paths are much faster (Streamlit cache + Redis).

---

## Project layout (runtime-critical)

```
.
├── README.md                          ← this file
├── ARCHITECTURE.md                    ← detailed data-flow diagrams
├── config.py                          ← env settings + key decryption
├── crypto_utils.py / key_management.py
├── requirements.txt
├── start_api.bat / start_frontend.bat # Windows helpers
├── .env                               ← secrets (not committed)
│
├── api/
│   └── mobile_api.py                  # FastAPI app (:8000)
│
├── restaurants/
│   ├── app_fastapi_hybrid.py          # Streamlit UI (:8501) → calls API
│   ├── app.py                         # alternate Streamlit entry
│   ├── wine_recommender_optimized.py  # core engine
│   ├── restaurant_config.py           # per-restaurant branding / namespaces
│   ├── qr_generator.py
│   └── maass/                         # MAASS assets, QR, setup
│
├── data/
│   ├── embedding_pipeline.py          # embeddings + Pinecone
│   ├── schema_v2.py / schema_definitions.py
│   ├── maass_ingest.py / menu_ingest.py
│   └── raw/                           # source wine lists
│
├── mobile/                            # lightweight PWA client for the API
├── wine_data_enricher/                # enrichment tooling
├── wine_producer_scaper/              # producer data pipeline
├── wine_region_scraper/               # region / vintage / taxonomy pipelines
└── docs/readmes/                      # historical guides & indexes
```

### Pinecone namespaces (typical)

| Namespace | Purpose |
|---|---|
| `{restaurant}_wine_list` (e.g. `maass_wine_list`) | That restaurant’s sellable list |
| `producers` | Producer context for richer notes |
| `vintages` | Vintage / year enrichment |
| `wine_taxonomy` | Style / type taxonomy |

Exact index name comes from env (`PINECONE_INDEX_NAME` / host). See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the live layout used in this deployment.

---

## Prerequisites

- Python 3.10+ recommended  
- Accounts / keys:
  - **XAI_API_KEY** (Grok)
  - **OPENAI_API_KEY** (embeddings; `USE_OPENAI_EMBEDDINGS=true` by default)
  - **PINECONE_API_KEY** (+ environment / host / index name)
  - **REDIS_URL** or host/port/password (optional but recommended)
- Wine list ingested into the restaurant’s Pinecone namespace

---

## Setup

```bash
# 1. Clone / open repo root
cd restaurant_branded_ai_sommelier_agent_jarvis

# 2. Virtual environment
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

# 3. Dependencies
pip install -r requirements.txt

# 4. Environment
# Create .env in the repo root (do not commit). Minimum:
```

```env
XAI_API_KEY=your_xai_key
# ENCRYPTION_KEY=...          # only if XAI key is stored encrypted
OPENAI_API_KEY=your_openai_key
USE_OPENAI_EMBEDDINGS=true
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

PINECONE_API_KEY=your_pinecone_key
PINECONE_ENVIRONMENT=your_env
PINECONE_INDEX_NAME=your_index
# PINECONE_HOST=...           # if using serverless host URL

REDIS_URL=redis://default:password@host:port
# or REDIS_HOST / REDIS_PORT / REDIS_PASSWORD

ENVIRONMENT=development
LOG_LEVEL=INFO
```

Validate connectivity:

```bash
python test_api_connections.py
# or
python setup_check.py
```

---

## How to run (local)

Guest path is **one process**: the FastAPI app serves the phone PWA.

### Windows

```bat
start_api.bat
```

### Cross-platform

```bash
python -m uvicorn api.mobile_api:app --host 0.0.0.0 --port 8000
```

| Endpoint | URL |
|---|---|
| Guest PWA | http://localhost:8000/?r=maass |
| Table QR | http://localhost:8000/showcase |
| Admin desk | http://localhost:8000/admin (dev password `maass-admin`) |
| Recommend | `POST /api/recommend` |
| Email bottles | `POST /api/email-wine` |

Streamlit (`start_frontend.bat`) is an optional staff kiosk, not the QR target.

Set `PUBLIC_BASE_URL` to the HTTPS origin before printing QR codes. Optional SMTP: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`. Without SMTP, emailed bottles are stored for the desk (`data/outbox/` + CRM).

### Example API call

```bash
curl -X POST http://localhost:8000/api/recommend ^
  -H "Content-Type: application/json" ^
  -d "{\"query\": \"light pinot noir around 90\", \"restaurant_id\": \"maass\"}"
```

Response shape (simplified):

```json
{
  "wines": [
    {
      "wine_id": "...",
      "producer": "...",
      "region": "...",
      "price": "...",
      "wine_type": "...",
      "tasting_note": "...",
      "why": "...",
      "food_pairing": "Prime NY Strip Gratin — ..."
    }
  ],
  "recommendation_id": "...",
  "intro": "For a steak at this table, I would start here.",
  "query": "light pinot noir around 90",
  "restaurant_name": "MAASS"
}
```

The phone app is already on port 8000. Do not serve `mobile/` from a second HTTP server.

---

## Restaurant branding & QR

- Config: [`restaurants/restaurant_config.py`](restaurants/restaurant_config.py)  
  - `restaurant_id`, display name, colors, logo  
  - Pinecone namespace: `{restaurant_id}_wine_list`  
  - Always returns `max_recommendations = 2`
- MAASS assets / QR: `restaurants/maass/`
- QR generation: [`restaurants/qr_generator.py`](restaurants/qr_generator.py)

Guest flow: **scan QR → branded chat → 2 wines from that list only**.

---

## Data & ingest (overview)

Wine lists are normalized to the project schema, embedded, and upserted into Pinecone under the restaurant namespace. Supporting pipelines live under:

- `data/` — schema, embedding pipeline, MAASS/menu ingest  
- `run_maass_ingest.py`, `embed_maass_schema_v2.py`, `migrate_to_schema_v2.py`  
- `wine_producer_scaper/`, `wine_region_scraper/`, `wine_data_enricher/`

After changing a list, re-ingest/embed so the API searches current inventory.

---

## Error handling (guest-facing)

If embeddings or upstream search fail, FastAPI returns an empty `wines` list plus an `error` field. The Streamlit UI shows a friendly retry message rather than a stack trace (see [`ARCHITECTURE.md`](ARCHITECTURE.md)).

---

## Security notes

- Keep `.env` out of git  
- Prefer encrypted storage for long-lived API keys (`key_management.py`)  
- Tighten CORS (`allow_origins`) before public deploy  
- Do not expose Pinecone/OpenAI/XAI keys to the browser — only the FastAPI backend should hold them  

---

## Tests & smoke checks

```bash
python test_api_connections.py   # external services
python test_api_quick.py         # quick API smoke
python test_hybrid.py            # hybrid path
python test_user_queries.py      # sample guest queries
python test_maass_wines.py       # MAASS list checks
```

---

## Deployment sketch

| Layer | Typical host | Notes |
|---|---|---|
| Streamlit UI | Streamlit Community Cloud | Free tier; set API base URL to backend |
| FastAPI | Railway / Fly.io / similar | Holds secrets; scales independently |
| Redis | Redis Cloud | Shared cache across instances |
| Pinecone / OpenAI / XAI | Vendor SaaS | Managed |

See [`docs/readmes/HYBRID_ARCHITECTURE_SUMMARY.md`](docs/readmes/HYBRID_ARCHITECTURE_SUMMARY.md) and [`docs/readmes/STREAMLIT_CLOUD_DEPLOYMENT.md`](docs/readmes/STREAMLIT_CLOUD_DEPLOYMENT.md) for longer deploy notes.

---

## More documentation

| Doc | Contents |
|---|---|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Full request/error flow diagrams |
| [`docs/readmes/DOCUMENTATION_INDEX.md`](docs/readmes/DOCUMENTATION_INDEX.md) | Index of historical guides |
| [`docs/readmes/START_HERE.md`](docs/readmes/START_HERE.md) | XAI/Grok migration summary |
| [`docs/readmes/QUICK_START_MAASS.md`](docs/readmes/QUICK_START_MAASS.md) | MAASS-focused quick start |
| [`docs/readmes/MOBILE_QUICKSTART.md`](docs/readmes/MOBILE_QUICKSTART.md) | PWA + API mobile path |
| [`docs/readmes/XAI_GROK_INTEGRATION.md`](docs/readmes/XAI_GROK_INTEGRATION.md) | Grok integration details |

---

## Status

- Hybrid **Streamlit + FastAPI** sommelier path is the primary runtime  
- **MAASS** wine list is the reference restaurant integration  
- LLM: **XAI Grok** · Embeddings: **OpenAI** · Search: **Pinecone** · Cache: **Redis**

# Performance Optimization & Cost Analysis

**Date**: 2026-02-11
**Current Performance**: ~25 seconds per query
**Target Performance**: <2 seconds per query

---

## Current Cost Per Query

### API Pricing (2026 rates):

**XAI Grok API:**
- Input: $2.00 per 1M tokens
- Output: $10.00 per 1M tokens

**OpenAI Embeddings (text-embedding-3-small):**
- $0.02 per 1M tokens

**Pinecone (Serverless):**
- Read: $0.30 per 1M read units
- Write: $2.00 per 1M write units
- Storage: $0.25/GB/month

---

## Cost Breakdown Per Query (Typical Case)

### 1. Embedding Generation (1 call)
- User query: ~50 tokens
- **Cost**: $0.000001

### 2. Pinecone Searches
- Initial search (top_k=20): 1 read unit
- Master list searches: ~40 read units (2 per wine × 20 wines)
- **Total**: 41 read units = **$0.0000123**

### 3. Grok LLM Calls (42 total)

#### Tasting Note Generation (20 wines):
- Input: ~100 tokens/wine × 20 = 2,000 tokens
- Output: ~100 tokens/wine × 20 = 2,000 tokens
- **Cost**: (2,000 × $2/1M) + (2,000 × $10/1M) = **$0.024**

#### Food Pairing Generation (20 wines):
- Input: ~80 tokens/wine × 20 = 1,600 tokens
- Output: ~50 tokens/wine × 20 = 1,000 tokens
- **Cost**: (1,600 × $2/1M) + (1,000 × $10/1M) = **$0.0132**

#### Wine Selection (1 call):
- Input: ~800 tokens (15 wine candidates)
- Output: ~10 tokens
- **Cost**: (800 × $2/1M) + (10 × $10/1M) = **$0.0017**

---

## **Total Cost Per Query: ~$0.039 (4 cents)**

### Cost Per 1,000 Queries: **$39**
### Cost Per 10,000 Queries: **$390**

### With 90% Caching (optimized): **$0.004 per query (0.4 cents)**

---

## Major Performance Bottlenecks

### 1. **Sequential API Calls** ⚠️ CRITICAL
- 42 API calls executed one-by-one
- Each call waits for previous to complete
- **Impact**: ~25 second latency

### 2. **Over-fetching** ⚠️ HIGH
- Enriches 20 wines, returns 2
- 90% of API calls wasted on discarded wines
- **Impact**: 18x unnecessary API calls

### 3. **No Caching** ⚠️ HIGH
- Same wines queried repeatedly
- Same food pairings regenerated
- **Impact**: 10x cost increase for repeat queries

### 4. **Always Generate Food Pairings** ⚠️ MEDIUM
- Generates for all 20 wines
- Even wines that will be discarded
- **Impact**: 18 unnecessary Grok calls

---

## Optimization Solutions

### Priority 1: Add Caching (90% cost reduction)

#### Recommended: Redis Cache

**Install Redis:**
```bash
pip install redis hiredis
```

**Cache Strategy:**

1. **Tasting Notes Cache**
   - Key: `tasting_note:{producer}_{region}_{wine_name}`
   - TTL: 30 days (notes don't change)
   - **Saves**: 20 Grok calls per cached wine

2. **Food Pairing Cache**
   - Key: `food_pairing:{wine_type}_{region}_{grapes}`
   - TTL: 30 days
   - **Saves**: 20 Grok calls per cached pairing

3. **Embedding Cache**
   - Key: `embedding:{hash(query)}`
   - TTL: 7 days
   - **Saves**: 1 OpenAI call per repeat query

4. **Wine Metadata Cache**
   - Key: `wine:{wine_id}`
   - TTL: 1 day
   - **Saves**: Pinecone lookups for repeated wines

---

### Priority 2: Parallel Processing (10x speed improvement)

**Use asyncio for concurrent API calls:**

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

async def enrich_wines_parallel(self, wines: List[Dict]):
    """Enrich multiple wines concurrently."""
    async with ThreadPoolExecutor(max_workers=10) as executor:
        tasks = [
            self._enrich_single_wine_async(wine)
            for wine in wines
        ]
        return await asyncio.gather(*tasks)
```

**Impact:**
- Reduce 42 sequential calls to ~3 seconds of parallel execution
- 8x faster response time

---

### Priority 3: Reduce Over-fetching (50% cost reduction)

**Strategy: Two-stage retrieval**

```python
# Stage 1: Fast search (no enrichment)
candidates = self.pipeline.search_similar_wines(
    top_k=10,  # Reduced from 20
    include_metadata=False  # Faster
)

# Stage 2: LLM selects best 2 based on metadata only
selected_ids = self._quick_select_two(candidates)

# Stage 3: Enrich ONLY the 2 selected wines
enriched = [self._enrich_wine(id) for id in selected_ids]
```

**Impact:**
- Enrich 2 wines instead of 20
- Reduce from 40 to 4 Grok calls
- 10x cost reduction

---

### Priority 4: Lazy Food Pairing Generation

**Generate only for final 2 wines:**

```python
# Before selection: Don't generate food pairings
candidates = self.get_candidates(query)

# After selection: Generate for 2 wines only
selected = self._select_best_two(candidates)
for wine in selected:
    wine['food_pairing'] = self.get_food_pairing_suggestion(...)
```

**Impact:**
- 20 food pairing calls → 2 calls
- 10x reduction in pairing generation cost

---

### Priority 5: Use Faster Models

**Current**: Grok-3 for all tasks

**Optimized**:
- **Wine selection**: Grok-3 (needs reasoning)
- **Tasting notes**: Grok-2 or Claude Haiku (faster, cheaper)
- **Food pairings**: Claude Haiku (3x faster, 10x cheaper)

**Claude Haiku pricing**:
- Input: $0.25 per 1M tokens (8x cheaper)
- Output: $1.25 per 1M tokens (8x cheaper)
- Latency: ~500ms vs 2s for Grok

---

## Mobile Interface Alternatives

### Issue with Streamlit:
- ❌ Slow on mobile
- ❌ Not responsive by default
- ❌ Heavy JavaScript bundle
- ❌ Poor offline support
- ❌ No native app features

### **Recommended: FastAPI + React Native**

#### Option 1: Progressive Web App (PWA) ⭐ BEST
**Tech Stack:**
- Backend: FastAPI (Python)
- Frontend: React or Vue.js
- Mobile: PWA (installable, offline support)

**Advantages:**
- ✅ Fast, responsive mobile UI
- ✅ Native-like experience
- ✅ Installable on iOS/Android
- ✅ Push notifications
- ✅ Offline caching
- ✅ Single codebase

**Cost**: Free, open-source

---

#### Option 2: React Native App ⭐ PREMIUM
**Tech Stack:**
- Backend: FastAPI (Python)
- Mobile: React Native (iOS + Android)

**Advantages:**
- ✅ True native performance
- ✅ App Store presence
- ✅ Full native features (camera for wine label scanning)
- ✅ Offline support

**Cost**: $99/year (Apple), $25 one-time (Google)

---

#### Option 3: Telegram/WhatsApp Bot ⭐ FASTEST TO BUILD
**Tech Stack:**
- Backend: FastAPI + Telegram Bot API
- Interface: Chat-based

**Advantages:**
- ✅ No app installation needed
- ✅ Instant access via messaging app
- ✅ Built-in authentication
- ✅ Easy to build (2-3 hours)

**Cost**: Free

---

#### Option 4: Flutter App
**Tech Stack:**
- Backend: FastAPI
- Mobile: Flutter (Dart)

**Advantages:**
- ✅ Beautiful UI
- ✅ Fast performance
- ✅ Single codebase (iOS + Android + Web)

**Cost**: Same as React Native

---

## Implementation Priority

### Phase 1: Quick Wins (1 day)
1. ✅ Add Redis caching for tasting notes and food pairings
2. ✅ Reduce top_k from 20 to 10
3. ✅ Lazy food pairing generation (only for final 2 wines)

**Expected**:
- Cost reduction: 70%
- Speed improvement: 2x faster (~12 seconds)

---

### Phase 2: Architecture Changes (3 days)
1. ✅ Two-stage retrieval (fast search → select → enrich)
2. ✅ Parallel API calls with asyncio
3. ✅ Switch food pairings to Claude Haiku

**Expected**:
- Cost reduction: 90%
- Speed improvement: 10x faster (~2 seconds)

---

### Phase 3: Mobile Interface (1 week)
1. ✅ Build FastAPI REST API backend
2. ✅ Create React PWA frontend
3. ✅ Deploy to Vercel/Netlify (frontend) + Railway/Fly.io (backend)

**Expected**:
- Mobile-optimized interface
- <1 second load time
- Offline support

---

## Cost Comparison

| Scenario | Cost/Query | Speed | Cache Hit Rate |
|----------|------------|-------|----------------|
| **Current** | $0.039 | 25s | 0% |
| **Phase 1** | $0.012 | 12s | 70% |
| **Phase 2** | $0.004 | 2s | 90% |
| **Optimal** | $0.001 | 1s | 95% |

---

## Recommended Mobile Tech Stack

### For Quick Launch (2-3 days):
**Telegram Bot** with FastAPI backend

### For Production (1-2 weeks):
**PWA (Progressive Web App)**
- Frontend: React + Vite + TailwindCSS
- Backend: FastAPI
- Hosting: Vercel (frontend) + Railway (backend)
- Cost: ~$5-10/month

### For Premium Experience (3-4 weeks):
**React Native App**
- Full native iOS/Android apps
- App Store presence
- Camera integration for wine label scanning
- Cost: ~$15/month + $124/year (app store fees)

---

**Next Steps**: Choose optimization phase and mobile platform

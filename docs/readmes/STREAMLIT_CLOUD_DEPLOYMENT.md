# Streamlit Cloud Deployment Guide

**FastAPI Backend + Streamlit Frontend Hybrid Architecture**

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│  Streamlit Cloud (Frontend)                     │
│  ├─ Chat UI                                     │
│  ├─ Caching (@st.cache_data)                   │
│  └─ calls →                                     │
└────────────────┬────────────────────────────────┘
                 │
                 │ HTTP POST
                 │
┌────────────────▼────────────────────────────────┐
│  Railway/Fly.io (Backend)                       │
│  ├─ FastAPI API                                 │
│  ├─ Optimized Recommender                       │
│  ├─ Redis Cache                                 │
│  └─ Pinecone + OpenAI                          │
└─────────────────────────────────────────────────┘
```

**Benefits**:
- ✅ Streamlit Cloud: Free hosting, instant QR codes
- ✅ FastAPI: Heavy lifting (embeddings, LLM, Pinecone)
- ✅ Caching: Both layers cached for speed
- ✅ Mobile-ready: Streamlit responsive + fast
- ✅ Easy deployment: Push to GitHub → Auto-deploy

---

## Quick Setup (5 minutes)

### Step 1: Deploy FastAPI Backend

**Option A: Railway.app (Recommended)**

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Initialize project
railway init

# Create railway.json
cat > railway.json << EOF
{
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "uvicorn api.mobile_api:app --host 0.0.0.0 --port $PORT",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
EOF

# Deploy
railway up
```

**Option B: Fly.io**

```bash
# Install Fly CLI
curl -L https://fly.io/install.sh | sh

# Login
fly auth login

# Create fly.toml
cat > fly.toml << EOF
app = "jarvis-sommelier-api"

[http_service]
  internal_port = 8000
  force_https = true
  auto_stop_machines = false
  auto_start_machines = true
  min_machines_running = 1

[[vm]]
  cpu_kind = "shared"
  cpus = 1
  memory_mb = 512
EOF

# Deploy
fly deploy
```

**Your API will be at**: `https://your-app.railway.app` or `https://jarvis-sommelier-api.fly.dev`

---

### Step 2: Deploy Streamlit Frontend

**On Streamlit Cloud:**

1. **Push to GitHub**:
   ```bash
   git add .
   git commit -m "Add FastAPI + Streamlit hybrid"
   git push origin main
   ```

2. **Go to**: https://share.streamlit.io

3. **Click "New app"**:
   - Repository: `your-username/sommelier_agent`
   - Branch: `main`
   - Main file: `restaurants/app_fastapi_hybrid.py`

4. **Add secrets** (click Advanced → Secrets):
   ```toml
   API_URL = "https://your-app.railway.app"
   ```

5. **Click "Deploy"**

**Your app will be at**: `https://your-app.streamlit.app`

---

### Step 3: Generate QR Code

```python
import qrcode

# Your Streamlit Cloud URL
url = "https://your-app.streamlit.app/?restaurant=maass"

# Generate QR
qr = qrcode.QRCode(version=1, box_size=10, border=5)
qr.add_data(url)
qr.make(fit=True)

img = qr.make_image(fill_color="black", back_color="white")
img.save("maass_qr_streamlit.png")

print(f"QR Code saved! Users can scan to access: {url}")
```

---

## File Structure

```
sommelier_agent/
├── api/
│   └── mobile_api.py              # FastAPI backend
├── restaurants/
│   ├── app_fastapi_hybrid.py      # Streamlit frontend (NEW)
│   ├── wine_recommender_optimized.py
│   └── restaurant_config.py
├── data/
│   ├── schema_v2.py
│   └── embedding_pipeline.py
├── requirements.txt               # Python dependencies
├── .streamlit/
│   └── config.toml               # Streamlit config
└── railway.json                   # Railway deployment config
```

---

## Configuration Files

### `.streamlit/config.toml`

```toml
[theme]
primaryColor = "#000000"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F8F9FA"
textColor = "#1F1F1F"
font = "sans serif"

[server]
headless = true
enableCORS = false
enableXsrfProtection = true
```

### `requirements.txt`

```txt
# Core dependencies
streamlit>=1.30.0
requests>=2.31.0

# Backend (only needed for Railway/Fly.io)
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
openai>=1.0.0
pinecone-client>=3.0.0
redis>=5.0.0
pandas>=2.0.0
python-dotenv>=1.0.0
cryptography>=41.0.0
```

### `railway.json`

```json
{
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "uvicorn api.mobile_api:app --host 0.0.0.0 --port $PORT",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

---

## Performance Optimization

### Streamlit Caching

```python
@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_wine_recommendations(query: str, restaurant_id: str):
    # Calls FastAPI
    # Cached results avoid duplicate API calls
    pass

@st.cache_data(ttl=86400)  # Cache for 24 hours
def get_restaurant_info(restaurant_id: str):
    # Restaurant info rarely changes
    pass
```

**Cache Hit Performance**:
- First query: ~2-10s (FastAPI + LLM)
- Cached query: <100ms (Streamlit cache)

---

## Cost Breakdown

### Free Tier (Perfect for Testing):

| Service | Cost | Limits |
|---------|------|--------|
| **Streamlit Cloud** | Free | Unlimited public apps |
| **Railway** | $5/mo credit | 500 hours/month |
| **Fly.io** | Free | 3 VMs (shared CPU) |
| **Upstash Redis** | Free | 10k commands/day |
| **Total** | **$0-5/month** | Good for 1,000-5,000 requests |

### Production Tier:

| Service | Cost | Scale |
|---------|------|-------|
| **Streamlit Cloud** | Free | Still free! |
| **Railway** | ~$10-20/mo | Auto-scaling |
| **Upstash Redis** | ~$10/mo | 1M commands/day |
| **OpenAI API** | Pay-per-use | ~$20/10k queries |
| **Total** | **~$40-50/month** | 10k-50k requests |

---

## Testing Locally

### Terminal 1: Start FastAPI Backend
```bash
python -m uvicorn api.mobile_api:app --reload --port 8000
```

### Terminal 2: Start Streamlit Frontend
```bash
streamlit run restaurants/app_fastapi_hybrid.py
```

### Visit:
- Frontend: http://localhost:8501
- Backend API: http://localhost:8000/docs

---

## Deployment Checklist

### Before Deploying:

- [ ] Test locally (both FastAPI + Streamlit)
- [ ] Add environment variables to Railway/Fly.io
- [ ] Update `API_URL` in Streamlit secrets
- [ ] Push to GitHub
- [ ] Deploy backend first (Railway/Fly.io)
- [ ] Deploy frontend (Streamlit Cloud)
- [ ] Test production URLs
- [ ] Generate QR codes
- [ ] Print/display QR codes at restaurant

### Environment Variables (Backend):

**Railway/Fly.io Secrets:**
```bash
OPENAI_API_KEY=sk-...
XAI_API_KEY=xai-...
PINECONE_API_KEY=...
PINECONE_ENVIRONMENT=...
PINECONE_INDEX=wineregionscrape
REDIS_URL=redis://...  # Optional
```

### Streamlit Cloud Secrets:

```toml
API_URL = "https://your-backend.railway.app"
```

---

## QR Code Generation

### For Each Restaurant:

```python
import qrcode

def generate_restaurant_qr(restaurant_id: str, streamlit_url: str):
    """Generate QR code for restaurant."""
    url = f"{streamlit_url}/?restaurant={restaurant_id}"

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    filename = f"{restaurant_id}_qr_streamlit.png"
    img.save(filename)

    print(f"QR Code saved: {filename}")
    print(f"URL: {url}")

# Generate QR codes
streamlit_url = "https://your-app.streamlit.app"
generate_restaurant_qr("maass", streamlit_url)
```

---

## Performance Metrics

### Expected Performance:

| Scenario | Streamlit | FastAPI | Total | Cache |
|----------|-----------|---------|-------|-------|
| **First Query** | 100ms | 2-10s | 2-10s | Miss |
| **Cached Query** | <100ms | 0s | <100ms | Hit |
| **Mobile Load** | <500ms | - | <500ms | - |

### Optimization Layers:

1. **Streamlit Cache** (@st.cache_data, TTL=1h)
   - Caches API responses
   - Avoids duplicate FastAPI calls
   - ~100ms response for cached queries

2. **FastAPI Cache** (Redis, TTL=30d)
   - Caches tasting notes
   - Caches food pairings
   - ~1-2s response for cached enrichment

3. **LLM Selection** (Grok/Haiku)
   - Fast wine selection
   - Parallel API calls
   - ~2-3s for new queries

---

## Monitoring

### Streamlit Cloud Dashboard:
- View app logs
- Monitor usage
- See deployment status
- https://share.streamlit.io/[your-app]

### Railway/Fly.io Dashboard:
- API logs
- Resource usage
- Cost tracking
- Deployment history

### Custom Analytics:

```python
# Add to app_fastapi_hybrid.py
import logging

logging.info(f"Query: {user_query}")
logging.info(f"Restaurant: {restaurant_id}")
logging.info(f"Processing time: {processing_time}s")
logging.info(f"Cache hit: {result is not None}")
```

---

## Troubleshooting

### Issue: "Cannot connect to backend API"
**Solution**:
- Check `API_URL` in Streamlit secrets
- Verify FastAPI is deployed and running
- Test backend URL directly: `https://your-backend.railway.app/`

### Issue: "Slow response times"
**Solution**:
- Check Redis is connected (backend logs)
- Monitor cache hit rate
- Consider upgrading backend resources

### Issue: "Out of memory"
**Solution**:
- Upgrade Railway plan (more RAM)
- Reduce top_k in searches
- Clear old cache entries

---

## Scaling Guide

### 100 users/day:
- ✅ Free tier works perfectly
- Estimated cost: $0-5/month

### 1,000 users/day:
- ✅ Streamlit Cloud (still free)
- ✅ Railway Hobby ($10/mo)
- ✅ Upstash Redis ($10/mo)
- Estimated cost: $20-30/month

### 10,000 users/day:
- ✅ Streamlit Cloud (still free!)
- ⬆️ Railway Pro ($20-40/mo)
- ⬆️ Upstash Pro ($20-30/mo)
- Estimated cost: $40-70/month

---

## Next Steps

1. **Test locally** with both FastAPI + Streamlit
2. **Deploy backend** to Railway/Fly.io
3. **Deploy frontend** to Streamlit Cloud
4. **Generate QR codes** for each restaurant
5. **Print and display** at restaurant tables
6. **Monitor usage** and optimize as needed

---

## Support

- **Streamlit Docs**: https://docs.streamlit.io
- **Railway Docs**: https://docs.railway.app
- **Fly.io Docs**: https://fly.io/docs
- **FastAPI Docs**: https://fastapi.tiangolo.com

---

**Status**: Ready to deploy! 🚀

**Total setup time**: 15-20 minutes
**Monthly cost**: $0-50 depending on usage
**Mobile-ready**: ✅ Yes, with QR codes

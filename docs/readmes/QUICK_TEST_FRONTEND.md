# 🚀 Quick Frontend Test - 5 Minutes

## ⚡ Super Fast Start

### 1️⃣ Run Setup Check (30 seconds)
```bash
python test_frontend_setup.py
```

✅ If all checks pass → Continue to step 2
❌ If checks fail → See [FRONTEND_TESTING_GUIDE.md](FRONTEND_TESTING_GUIDE.md)

---

### 2️⃣ Start Backend (Terminal 1)
```bash
python -m uvicorn api.mobile_api:app --reload --port 8000
```

Wait for: `Uvicorn running on http://127.0.0.1:8000`

---

### 3️⃣ Test Backend (Terminal 2)
```bash
python test_hybrid.py
```

Expected: `✓ Backend Test Complete!`

---

### 4️⃣ Start Frontend (Terminal 3)
```bash
streamlit run restaurants/app_fastapi_hybrid.py
```

Browser auto-opens: http://localhost:8501

---

## ✅ Test These 3 Queries

### Query 1: Price + Type
```
Bold red wine for steak under $100
```
**Expect**: 2 red wines, prices <$100, detailed tasting notes

### Query 2: Region + Price
```
Full body Chianti around $125
```
**Expect**: 2 Italian Chianti wines, ~$100-150

### Query 3: Grape Varietal
```
Pinot Noir from Burgundy under $200
```
**Expect**: 2 French Burgundy Pinot Noir wines

---

## ✓ Success Criteria

Each wine should show:
- ✅ Vintage + Producer + Wine Name
- ✅ Region + Country
- ✅ Price
- ✅ **Tasting Note** (XAI Grok generated)
- ✅ **Food Pairing** (XAI Grok generated)
- ✅ Response time: 2-10s (first), <200ms (cached)

---

## 🎯 Verify XAI Grok is Working

### Check 1: Look at Terminal 1 logs
Should see:
```
INFO: Getting recommendations for: Bold red wine...
INFO: LLM selected wines: 3,7
```

### Check 2: Read the tasting notes
Should be detailed and specific:
- ❌ Generic: "A bold red wine from Italy"
- ✅ Grok: "This Tuscan blend opens with aromas of dark cherry and violet..."

### Check 3: Code confirmation
XAI Grok is used in 3 places:
1. **Tasting notes** ([wine_recommender_optimized.py:227](restaurants/wine_recommender_optimized.py#L227))
2. **Food pairings** ([wine_recommender_optimized.py:264](restaurants/wine_recommender_optimized.py#L264))
3. **Wine selection** ([wine_recommender_optimized.py:364](restaurants/wine_recommender_optimized.py#L364))

All use `self.grok_client` with model `grok-3` ✅

---

## 🐛 Common Issues

### "Cannot connect to backend"
```bash
# Make sure Terminal 1 is running
python -m uvicorn api.mobile_api:app --reload --port 8000
```

### "No wines found"
```bash
# Check Pinecone has data
python check_pinecone_status.py
```

### "XAI API error"
```bash
# Verify API key
python -c "from config import settings; print(settings.get_decrypted_xai_key()[:20])"
```

### "Redis not running" ⚠️
**This is OK!** Redis is optional. Your app works without it.
- **Without Redis**: Uses in-memory cache (works fine for testing)
- **With Redis**: 10-50x faster cached responses

**Want to add Redis?** See [REDIS_SETUP_GUIDE.md](REDIS_SETUP_GUIDE.md)

---

## 📱 Test on Mobile (Optional)

### 1. Get your local IP
```bash
ipconfig  # Windows
```

### 2. Open on phone
```
http://YOUR_IP:8501/?restaurant=maass
```

### 3. Test mobile responsiveness
- [ ] UI is readable
- [ ] Chat works
- [ ] No horizontal scrolling

---

## 🎉 Success!

If all tests pass, you're ready for:
- ✅ Production deployment
- ✅ QR code generation
- ✅ Restaurant rollout

**Next**: See [STREAMLIT_CLOUD_DEPLOYMENT.md](STREAMLIT_CLOUD_DEPLOYMENT.md)

---

## 📚 Full Documentation

- **Complete guide**: [FRONTEND_TESTING_GUIDE.md](FRONTEND_TESTING_GUIDE.md)
- **Architecture**: [HYBRID_ARCHITECTURE_SUMMARY.md](HYBRID_ARCHITECTURE_SUMMARY.md)
- **Deployment**: [STREAMLIT_CLOUD_DEPLOYMENT.md](STREAMLIT_CLOUD_DEPLOYMENT.md)
- **XAI Integration**: [XAI_GROK_INTEGRATION.md](XAI_GROK_INTEGRATION.md)

---

**Testing time**: ~5 minutes
**XAI Grok**: ✅ Already integrated
**Cost**: $5/month (Railway) + FREE (Streamlit Cloud)

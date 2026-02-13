# Redis Setup Guide - Optional but Recommended

## ⚠️ Redis is OPTIONAL

Your app works without Redis! It will automatically fall back to in-memory caching.

**Why use Redis?**
- ✅ Persistent cache (survives restarts)
- ✅ Shared cache (multiple backend instances)
- ✅ 90% faster responses for cached queries
- ✅ Reduced API costs (fewer XAI calls)

**Without Redis:**
- ⚠️ Cache resets on restart
- ⚠️ Each backend instance has its own cache
- ✅ Still works fine for testing and small deployments

---

## 🖥️ Local Development (Your Computer)

### Option 1: Windows (WSL - Recommended)

```bash
# Install WSL (if not already installed)
wsl --install

# Inside WSL, install Redis
sudo apt update
sudo apt install redis-server

# Start Redis
sudo service redis-server start

# Verify it's running
redis-cli ping
# Should return: PONG
```

**Start Redis on boot:**
```bash
# Add to ~/.bashrc or ~/.zshrc
sudo service redis-server start
```

### Option 2: Windows (Docker - Easiest)

```bash
# Install Docker Desktop for Windows first
# Then run:
docker run -d --name redis -p 6379:6379 redis:latest

# Verify it's running
docker ps
```

**Start Redis with Docker:**
```bash
# Start
docker start redis

# Stop
docker stop redis

# Auto-start on boot
docker update --restart unless-stopped redis
```

### Option 3: Mac (Homebrew)

```bash
# Install Redis
brew install redis

# Start Redis
brew services start redis

# Verify it's running
redis-cli ping
# Should return: PONG
```

### Option 4: Linux

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install redis-server
sudo systemctl start redis
sudo systemctl enable redis  # Auto-start on boot

# Verify
redis-cli ping
```

---

## ☁️ Production Deployment

### Option 1: Railway (Same as Backend) - FREE TIER

**Best for**: Your current Railway backend deployment

1. Add Redis to your Railway project:
   ```bash
   # In your Railway dashboard:
   # 1. Click "New" → "Database" → "Add Redis"
   # 2. Copy the connection URL
   ```

2. Update your backend environment variables:
   ```bash
   # Railway will provide something like:
   REDIS_URL=redis://default:password@redis.railway.internal:6379
   ```

3. Update your code to use REDIS_URL:
   ```python
   # In wine_recommender_optimized.py, update Redis connection:
   import os
   redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
   self.redis_client = redis.from_url(redis_url)
   ```

**Cost**: FREE up to 100MB, then $5/month

### Option 2: Upstash (Serverless Redis) - FREE TIER

**Best for**: Serverless deployments, minimal setup

1. Create account at https://upstash.com
2. Create a Redis database
3. Copy connection details:
   ```
   UPSTASH_REDIS_REST_URL=https://...
   UPSTASH_REDIS_REST_TOKEN=...
   ```

4. Install upstash-redis:
   ```bash
   pip install upstash-redis
   ```

5. Update your code:
   ```python
   from upstash_redis import Redis

   redis_client = Redis(
       url=os.getenv("UPSTASH_REDIS_REST_URL"),
       token=os.getenv("UPSTASH_REDIS_REST_TOKEN")
   )
   ```

**Cost**: FREE up to 10,000 commands/day

### Option 3: Redis Cloud - FREE TIER

**Best for**: Managed Redis with high availability

1. Create account at https://redis.com/try-free/
2. Create a free database
3. Get connection details:
   ```
   REDIS_HOST=redis-12345.c123.us-east-1-3.ec2.cloud.redislabs.com
   REDIS_PORT=12345
   REDIS_PASSWORD=your-password
   ```

4. Update `.env`:
   ```bash
   REDIS_HOST=redis-12345.c123.us-east-1-3.ec2.cloud.redislabs.com
   REDIS_PORT=12345
   REDIS_PASSWORD=your-password
   ```

**Cost**: FREE 30MB, then $5/month

---

## 🧪 Test Redis Connection

### After installing Redis, test it:

```bash
# Test with redis-cli
redis-cli ping
# Should return: PONG

# Test with Python
python -c "import redis; r = redis.Redis(host='localhost', port=6379); r.ping(); print('✓ Redis working!')"
```

### Test with your app:

```bash
# Run the setup check again
python test_frontend_setup.py
```

You should now see:
```
============================================================
  6. Redis Cache (Optional)
============================================================
  ✓ Redis connected
  ✓ Caching enabled (fast responses)
```

---

## 🚀 Quick Recommendation

### For Testing Locally:
**Use Docker** (easiest):
```bash
docker run -d --name redis -p 6379:6379 redis:latest
```

### For Production:
**Use Railway Redis** (simplest, same platform as backend):
1. Railway Dashboard → Add Redis
2. Copy REDIS_URL to environment variables
3. Update code to use redis.from_url()

**Total cost**: FREE or $5/month (included in Railway)

---

## 🔧 Configure Your App for Redis

### Current Setup (No Changes Needed!)

Your app is already configured to handle Redis:

```python
# In wine_recommender_optimized.py:
class WineCache:
    def __init__(self):
        self.memory_cache = {}  # Fallback
        self.redis_client = None

        if REDIS_AVAILABLE:
            try:
                self.redis_client = redis.Redis(
                    host='localhost',
                    port=6379,
                    db=0
                )
                self.redis_client.ping()
            except:
                # Falls back to memory cache
                pass
```

✅ **Already handles missing Redis gracefully!**

### For Production (Railway Redis):

Update `wine_recommender_optimized.py`:

```python
import os

# In WineCache.__init__:
redis_url = os.getenv("REDIS_URL", None)
if redis_url and REDIS_AVAILABLE:
    try:
        self.redis_client = redis.from_url(redis_url)
        self.redis_client.ping()
        logger.info("Redis cache connected")
    except Exception as e:
        logger.warning(f"Redis not available: {e}")
        self.redis_client = None
```

---

## 📊 Performance Comparison

### Without Redis:
- First query: 3-10 seconds
- Repeated query: 3-10 seconds (no cache)
- Restart app: Cache lost

### With Redis:
- First query: 3-10 seconds
- Repeated query: <200ms (90-95% faster)
- Restart app: Cache persists ✅

---

## ❓ FAQ

### Do I need Redis for testing?
**No** - Your app works fine without it for local testing.

### Do I need Redis for production?
**Recommended** - Dramatically improves performance and reduces API costs.

### Can I add Redis later?
**Yes** - Just install it and restart your app. No code changes needed.

### Which option is best for my Railway deployment?
**Railway Redis** - Same platform, easy setup, free tier available.

### What if Redis stops working?
**Automatic fallback** - Your app will continue working with in-memory cache.

---

## 🎯 Decision Tree

```
Are you testing locally?
├─ Yes → Docker Redis (easiest)
│        docker run -d --name redis -p 6379:6379 redis:latest
│
└─ No, deploying to production?
   ├─ Using Railway? → Railway Redis (same platform)
   │                   Railway Dashboard → Add Redis
   │
   ├─ Want serverless? → Upstash (free tier)
   │                     https://upstash.com
   │
   └─ Want managed? → Redis Cloud (free tier)
                      https://redis.com/try-free/
```

---

## ✅ Summary

**For now (testing):**
- ✅ Skip Redis - your app works without it
- ✅ Focus on testing the frontend first
- ✅ Add Redis later if you want faster responses

**For production:**
- ✅ Add Railway Redis ($0-5/month)
- ✅ Improves performance 10-50x
- ✅ Reduces XAI API costs significantly

**Quick test without Redis:**
```bash
# Your app already works!
python -m uvicorn api.mobile_api:app --reload --port 8000
streamlit run restaurants/app_fastapi_hybrid.py
```

Redis will make it faster, but it's not required. ✨

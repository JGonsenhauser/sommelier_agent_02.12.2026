# Restaurant-Specific Wine Sommelier System

This system provides QR code-based access to restaurant-specific wine lists with AI-powered recommendations.

## Overview

Each restaurant gets:
- ✅ Unique QR code linking to their wine list
- ✅ Dedicated wine list namespace in Pinecone
- ✅ AI sommelier that returns exactly **2 wine recommendations**
- ✅ Natural language conversation interface
- ✅ Mobile-friendly Streamlit app

---

## Quick Start: MAASS Restaurant

### 1. Complete Setup (One Command)

```bash
python restaurants/maass/setup_maass.py
```

This will:
- ✅ Ingest the MAASS wine list into Pinecone
- ✅ Generate QR code
- ✅ Test recommendations
- ✅ Validate everything works

### 2. Run the App

**Option A: Universal App** (handles all restaurants)
```bash
streamlit run restaurants/app.py
```
Then navigate to: `http://localhost:8501/?restaurant=maass`

**Option B: MAASS-Specific App**
```bash
streamlit run restaurants/maass/maass_app.py
```

### 3. Scan QR Code

- Open `restaurants/maass/static/maass_qr.png`
- Scan with your phone
- Start chatting with the sommelier!

---

## Architecture

```
restaurants/
├── app.py                          # Universal app (all restaurants)
├── restaurant_config.py            # Restaurant configurations
├── qr_generator.py                 # QR code generation
├── wine_recommender.py             # AI recommendation engine
│
└── maass/                          # MAASS restaurant
    ├── setup_maass.py              # Complete setup script
    ├── maass_app.py                # MAASS-specific app
    ├── static/                     # QR codes, images
    └── data/                       # Wine list data
```

---

## How It Works

### 1. User Scans QR Code
QR code contains URL: `https://your-app.com/?restaurant=maass`

### 2. User Asks for Wine
"I want a bold red wine for steak dinner"

### 3. AI Sommelier Process
1. **Embed query** using OpenAI/Grok embeddings
2. **Search Pinecone** for similar wines (filtered by restaurant)
3. **LLM selects best 2** wines from candidates
4. **Generate recommendation** with natural language explanation

### 4. User Gets 2 Perfect Wines
Each with:
- Producer & region
- Grape varietals
- Wine type
- Price range
- Tasting notes
- Why it matches their request

---

## Adding a New Restaurant

### 1. Create Configuration

Edit `restaurant_config.py`:

```python
NEW_RESTAURANT_CONFIG = RestaurantConfig(
    restaurant_id="new_restaurant",
    name="New Restaurant Name",
    location="123 Main St, City, State",
    primary_color="#3498db",
    accent_color="#e74c3c",
    phone="(555) 123-4567",
    website="https://restaurant.com",
    hours="5pm-10pm Daily"
)
```

### 2. Prepare Wine List

Create Excel/CSV file with columns:
- `producer` (required)
- `wine_name` (optional)
- `region` (required)
- `country` (required)
- `vintage` (optional)
- `price` (required)
- `grapes` (required - comma separated)
- `wine_type` (required - red/white/rosé/sparkling/dessert)
- `tasting_note` (required)
- `alcohol_content` (optional)

### 3. Ingest Wine List

```python
from data.maass_ingest import ingest_maass_list

embedded = ingest_maass_list(
    source_path=Path("restaurant_wine_list.xlsx"),
    business_id="new_restaurant",
    business_name="New Restaurant Name",
    location="123 Main St",
    namespace="new_restaurant_wine_list"
)
```

### 4. Generate QR Code

```python
from restaurants.qr_generator import RestaurantQRGenerator
from restaurants.restaurant_config import NEW_RESTAURANT_CONFIG

generator = RestaurantQRGenerator(base_url="https://your-domain.com")
qr_path = generator.generate_qr_code(NEW_RESTAURANT_CONFIG)
print(f"QR code saved to: {qr_path}")
```

### 5. Deploy

```bash
streamlit run restaurants/app.py
```

Access at: `https://your-domain.com/?restaurant=new_restaurant`

---

## API Reference

### WineRecommender

```python
from restaurants.wine_recommender import WineRecommender
from restaurants.restaurant_config import MAASS_CONFIG

# Initialize
recommender = WineRecommender(MAASS_CONFIG)

# Get recommendations
recommendation_text, wines = recommender.get_full_recommendation(
    user_query="Bold red wine for steak"
)

# Returns:
# - recommendation_text: Natural language explanation
# - wines: List of exactly 2 wine dictionaries
```

### Wine Dictionary Structure

```python
{
    "wine_id": "wine_abc123",
    "score": 0.92,  # Similarity score (0-1)
    "producer": "Caymus Vineyards",
    "region": "Napa Valley",
    "grapes": "Cabernet Sauvignon",
    "wine_type": "red",
    "price_range": "$100-200",
    "tasting_keywords": "bold, dark fruit, oak, tannic",
    "metadata": {...}  # Full Pinecone metadata
}
```

---

## Customization

### Change Number of Recommendations

Default is 2 wines. To change:

```python
config = RestaurantConfig(
    restaurant_id="my_restaurant",
    name="My Restaurant",
    max_recommendations=3  # Return 3 wines instead
)
```

Update logic in `wine_recommender.py` accordingly.

### Customize Colors

```python
config = RestaurantConfig(
    restaurant_id="my_restaurant",
    name="My Restaurant",
    primary_color="#1e3a8a",  # Navy blue
    accent_color="#fbbf24"    # Amber
)
```

### Add Logo to QR Code

```python
generator.generate_styled_qr_code(
    config=MY_CONFIG,
    logo_path=Path("restaurants/my_restaurant/logo.png")
)
```

---

## Testing

### Test Recommendations

```bash
python restaurants/wine_recommender.py
```

This runs test queries against MAASS and shows results.

### Test QR Generation

```bash
python restaurants/qr_generator.py
```

### Manual Testing

```python
from restaurants.wine_recommender import WineRecommender
from restaurants.restaurant_config import MAASS_CONFIG

recommender = WineRecommender(MAASS_CONFIG)

# Test different queries
queries = [
    "Bold red for steak",
    "Light white wine",
    "Affordable wine under $50",
    "Special occasion"
]

for query in queries:
    text, wines = recommender.get_full_recommendation(query)
    print(f"\nQuery: {query}")
    print(f"Response: {text}")
    for wine in wines:
        print(f"  - {wine['producer']} ({wine['region']})")
```

---

## Production Deployment

### 1. Update QR Code URLs

```python
# In qr_generator.py
generator = RestaurantQRGenerator(
    base_url="https://your-production-domain.com"
)
```

### 2. Regenerate QR Codes

```bash
python restaurants/qr_generator.py
```

### 3. Deploy Streamlit App

**Streamlit Cloud:**
```bash
streamlit run restaurants/app.py
```

**Docker:**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["streamlit", "run", "restaurants/app.py", "--server.port=8501"]
```

**Environment Variables:**
```bash
# .env (production)
XAI_API_KEY=your_encrypted_key
ENCRYPTION_KEY=your_encryption_key
OPENAI_API_KEY=your_openai_key
PINECONE_API_KEY=your_pinecone_key
PINECONE_INDEX_NAME=wineregionscrape
PINECONE_ENVIRONMENT=us-east-1
```

### 4. Print QR Codes

- Print high-resolution QR codes
- Place on restaurant tables
- Include call-to-action: "Scan for wine recommendations"

---

## Troubleshooting

### No Wines Found

**Issue:** Search returns 0 wines

**Solutions:**
1. Check wine list was ingested: `python test_api_connections.py`
2. Verify namespace: Should match `config.namespace`
3. Check QR ID: Should be `qr_{restaurant_id}`
4. Verify Pinecone filter: `list_id` should match namespace

### QR Code Doesn't Work

**Issue:** Scanning QR code doesn't open app

**Solutions:**
1. Regenerate with correct base URL
2. Ensure app is running and accessible
3. Test URL in browser first
4. Check firewall/network settings

### Recommendations Not Relevant

**Issue:** Wines don't match user query

**Solutions:**
1. Check embedding quality - embeddings should be semantic
2. Try different queries to test
3. Increase `top_k` in search to get more candidates
4. Review wine metadata (grapes, tasting notes, etc.)

### Slow Performance

**Issue:** Recommendations take too long

**Solutions:**
1. Use OpenAI embeddings (`USE_OPENAI_EMBEDDINGS=true`)
2. Reduce keyword extraction (skip if using OpenAI)
3. Cache embeddings
4. Optimize Pinecone index

---

## Advanced Features

### Food Pairing

Enable in config:
```python
config.enable_food_pairing = True
```

Ask: "Wine to pair with salmon" or "What wine goes with steak?"

### Price Filtering

Users can specify: "Under $50" or "Premium wines"

System automatically filters by `price_range` metadata.

### Multi-Language Support

Add translation in recommendation generation:
```python
# In wine_recommender.py
prompt += f"\nRespond in {user_language}"
```

---

## Support

For issues or questions:
1. Check this README
2. Review code comments
3. Check `CODE_REVIEW_AND_IMPROVEMENTS.md` for best practices
4. Test with `test_api_connections.py`

---

## License

Proprietary - Wine Sommelier Agent Project

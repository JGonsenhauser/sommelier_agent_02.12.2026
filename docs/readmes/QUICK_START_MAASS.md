# Quick Start Guide - MAASS Restaurant

## ✅ Setup Complete!

Your MAASS restaurant sommelier system is **fully operational**.

---

## What's Ready

- ✅ **282 wines** from MAASS wine list loaded
- ✅ **QR code** generated at: `restaurants/maass/static/maass_qr.png`
- ✅ **AI sommelier** returns exactly 2 wine recommendations
- ✅ **Streamlit app** ready to launch

---

## Start the App (3 Options)

### Option 1: Universal App (Recommended)
```bash
streamlit run restaurants/app.py
```
Open: http://localhost:8501/?restaurant=maass

### Option 2: MAASS-Specific App
```bash
streamlit run restaurants/maass/maass_app.py
```
Open: http://localhost:8501

### Option 3: Python Import
```python
from restaurants.wine_recommender import WineRecommender
from restaurants.restaurant_config import MAASS_CONFIG

recommender = WineRecommender(MAASS_CONFIG)
text, wines = recommender.get_full_recommendation("Bold red wine for steak")

print(text)
for wine in wines:
    print(f"- {wine['producer']} ({wine['region']})")
```

---

## Test Queries

Try these in the chat:

1. **"Bold red wine for steak dinner"**
   - Returns: Powerful reds perfect for meat

2. **"Light white wine for seafood"**
   - Returns: Crisp, refreshing whites

3. **"Wine under $50"**
   - Returns: Budget-friendly options

4. **"Special occasion wine"**
   - Returns: Premium selections

---

## QR Code Usage

### For Testing
1. Open: `restaurants/maass/static/maass_qr.png`
2. Scan with phone camera
3. Chat with AI sommelier

### For Production
1. Print QR code at high resolution
2. Place on restaurant tables
3. Customers scan and get instant wine recommendations

---

## File Locations

```
restaurants/maass/
├── setup_maass.py          # Setup script (already run ✅)
├── maass_app.py            # Streamlit app
└── static/
    └── maass_qr.png        # QR code (ready to print ✅)
```

---

## Next Steps

### 1. Test Locally
```bash
streamlit run restaurants/app.py
```

### 2. Print QR Code
- Open `restaurants/maass/static/maass_qr.png`
- Print at 300 DPI or higher
- Size: 3"×3" or larger recommended

### 3. Deploy to Production
- Update base URL in `restaurants/qr_generator.py`
- Regenerate QR code
- Deploy Streamlit app to cloud
- See [restaurants/README.md](restaurants/README.md) for details

---

## Support

- **Full Documentation**: [restaurants/README.md](restaurants/README.md)
- **Code Review**: [CODE_REVIEW_AND_IMPROVEMENTS.md](CODE_REVIEW_AND_IMPROVEMENTS.md)
- **Implementation Summary**: [IMPLEMENTATION_COMPLETE_QR_SYSTEM.md](IMPLEMENTATION_COMPLETE_QR_SYSTEM.md)

---

**Status**: ✅ Ready to Launch!

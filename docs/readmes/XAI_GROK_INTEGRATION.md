
# XAI Grok Integration Guide

## Overview

This document details the migration from Anthropic Claude to **XAI Grok LLM** for the Wine Sommelier Agent.

## Changes Made

### 1. **LLM Provider Migration**
   - **Removed**: Anthropic Claude API client
   - **Added**: XAI Grok API (OpenAI-compatible)
   - **Benefits**: 
     - Grok's advanced reasoning for wine analysis
     - OpenAI-compatible API reduces compatibility issues
     - Real-time information capabilities

### 2. **Encryption & Security**
   - **New Module**: `crypto_utils.py`
   - **Features**:
     - Fernet symmetric encryption for API keys
     - Encryption key management via environment variable (`ENCRYPTION_KEY`)
     - Methods: `encrypt_key()`, `decrypt_key()`, `generate_encryption_key()`
   - **Usage**: API keys can be stored encrypted in `.env` and decrypted at runtime

### 3. **Configuration Changes**

#### config.py
```python
# Old
anthropic_api_key: str

# New  
xai_api_key: str
encryption_key: Optional[str] = None
```

**New Method**:
```python
def get_decrypted_xai_key(self) -> str:
    """Get decrypted XAI API key"""
```

#### .env File
```dotenv
# XAI Grok API Configuration
XAI_API_KEY=YOUR_XAI_API_KEY
ENCRYPTION_KEY=YOUR_ENCRYPTION_KEY

# Pinecone Configuration (Unchanged)
PINECONE_API_KEY=YOUR_PINECONE_API_KEY
PINECONE_INDEX_NAME=wineregionscrape
PINECONE_ENVIRONMENT=us-east-1

# Redis Configuration (Unchanged)
REDIS_HOST=localhost
REDIS_PORT=6379
```

### 4. **Embedding Pipeline Updates**

#### Dependencies
- **Removed**: `anthropic>=0.18.0`
- **Added**: `openai>=1.3.0`
- **Added**: `cryptography>=41.0.0`

#### Client Initialization
```python
# Old
from anthropic import Anthropic
self.anthropic_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

# New
from openai import OpenAI
xai_api_key = settings.get_decrypted_xai_key()
self.grok_client = OpenAI(
    api_key=xai_api_key,
    base_url="https://api.x.ai/v1"
)
```

#### Key Methods Updated

1. **get_embeddings()** - Now uses Grok for semantic embedding generation
   - Model: `grok-latest`
   - Dimension: 1536 (OpenAI standard)
   - Uses Grok's reasoning for semantic understanding

2. **extract_tasting_keywords()** - Now uses Grok for keyword extraction
   - Faster processing with Grok
   - Better contextual understanding of wine terminology

### 5. **API Connections Included**

The integration includes connections to:
- ✅ **XAI Grok API** - Primary LLM
- ✅ **Pinecone** - Vector database for semantic search
- ✅ **Redis** - Caching layer (optional)

### 6. **Testing & Verification**

**New Script**: `test_api_connections.py`

Runs comprehensive tests for:
1. Encryption setup and key management
2. Configuration loading
3. XAI Grok API connectivity
4. Pinecone vector database
5. Redis connection (optional)
6. Embedding pipeline initialization

**Usage**:
```bash
python test_api_connections.py
```

## Installation & Setup

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Set Up Environment Variables

Edit `.env` and ensure you have:
```dotenv
XAI_API_KEY=<your-xai-api-key>
ENCRYPTION_KEY=<your-encryption-key>
PINECONE_API_KEY=<your-pinecone-key>
PINECONE_ENVIRONMENT=us-east-1
REDIS_HOST=localhost
REDIS_PORT=6379
```

To generate a new encryption key:
```python
from crypto_utils import SecureKeyManager
print(SecureKeyManager.generate_encryption_key())
```

### Step 3: Verify Connections
```bash
python test_api_connections.py
```

Expected output:
```
✓ PASS: Encryption Setup
✓ PASS: Configuration Loading
✓ PASS: XAI Grok API
✓ PASS: Pinecone Vector DB
✓ PASS: Redis Cache (or FAIL if Redis not running - optional)
✓ PASS: Embedding Pipeline
```

## API Key Encryption

### Why Encrypt API Keys?

API keys are sensitive credentials that should never be stored in plain text in version control or logs. The encryption utility provides:

- **Secure Storage**: Keys are encrypted at rest
- **Symmetric Encryption**: Uses Fernet (AES-based) for reliability
- **Easy Decryption**: Automatic decryption via `get_decrypted_xai_key()`

### How to Encrypt Existing Keys

```python
from crypto_utils import SecureKeyManager

manager = SecureKeyManager()
api_key = "xai-your-api-key-here"
encrypted_key = manager.encrypt_key(api_key)
print(f"Encrypted: {encrypted_key}")
```

Add the encrypted key to `.env`:
```dotenv
XAI_API_KEY=gAAAAABn...encrypted-value...
ENCRYPTION_KEY=your-generated-key
```

## XAI Grok API Documentation

### Models Available
- `grok-latest` - Latest stable Grok model
- `grok-vision-beta` - Vision capabilities (experimental)

### API Endpoint
```
https://api.x.ai/v1
```

### Example Usage
```python
from openai import OpenAI

client = OpenAI(
    api_key="xai-...",
    base_url="https://api.x.ai/v1"
)

response = client.chat.completions.create(
    model="grok-latest",
    messages=[
        {"role": "system", "content": "You are a wine expert."},
        {"role": "user", "content": "Describe a Cabernet Sauvignon..."}
    ],
    temperature=0.3,
    max_tokens=500
)

print(response.choices[0].message.content)
```

## Pinecone Integration

### Vector Dimensions
- **Current**: 1536 (OpenAI standard)
- **Reason**: Compatible with Grok embeddings generation

### Index Configuration
```python
spec=ServerlessSpec(
    cloud='aws',
    region='us-east-1'
)
```

### Metadata Fields
Wine embeddings include:
- `wine_id`: Unique wine identifier
- `qr_id`: Business QR code
- `producer`: Winery/producer name
- `region`: Wine region
- `grapes`: Grape varieties (comma-separated)
- `wine_type`: red, white, sparkling, dessert
- `price_range`: budget, mid, premium, luxury
- `tasting_keywords`: Extracted flavor descriptors

## Troubleshooting

### "Invalid encryption key format"
```
Solution: Regenerate encryption key with SecureKeyManager.generate_encryption_key()
```

### "XAI API connection failed"
```
Solution: Verify XAI_API_KEY is set correctly in .env
         Check: https://console.x.ai/ for API key status
```

### "Pinecone connection failed"
```
Solution: Verify PINECONE_API_KEY and PINECONE_ENVIRONMENT are correct
         Check: https://app.pinecone.io/ for your API credentials
```

### "Redis connection failed"
```
Solution: Redis is optional. If not needed, this can be ignored.
         To fix: Install and run Redis
         macOS: brew install redis && redis-server
         Windows: Use Windows Subsystem for Linux (WSL) or Docker
```

## Migration Checklist

- [x] Replace Anthropic with XAI Grok client
- [x] Create encryption utility (`crypto_utils.py`)
- [x] Update configuration (`config.py`)
- [x] Update embedding pipeline (`embedding_pipeline.py`)
- [x] Update requirements.txt
- [x] Create API connection tester (`test_api_connections.py`)
- [x] Clean up setup checks
- [x] Document integration (this file)

## Next Steps

1. ✅ Complete the setup by running: `python test_api_connections.py`
2. 🚀 Use the embedding pipeline to generate wine embeddings:
   ```python
   from data.embedding_pipeline import EmbeddingPipeline
   pipeline = EmbeddingPipeline()
   count = pipeline.embed_business_wines(qr_id="your-qr-id")
   ```
3. 🔍 Search for similar wines:
   ```python
   results = pipeline.search_similar_wines(
       query_text="Bold red wine with fruit forward flavors",
       qr_id="your-qr-id",
       top_k=5
   )
   ```

## Support

For issues with:
- **XAI Grok**: See https://docs.x.ai/
- **Pinecone**: See https://docs.pinecone.io/
- **Cryptography**: See https://cryptography.io/
- **OpenAI Python Client**: See https://github.com/openai/openai-python

---

**Last Updated**: January 29, 2026  
**Version**: 2.0 (XAI Grok)

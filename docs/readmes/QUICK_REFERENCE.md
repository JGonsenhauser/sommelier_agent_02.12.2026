# Quick Reference Guide - XAI Grok Integration

## 📁 File Structure

```
sommelier_agent/
├── config.py                          [MODIFIED] XAI config + encryption support
├── crypto_utils.py                    [NEW] Encryption utility
├── key_management.py                  [NEW] Key management tool
├── test_api_connections.py            [NEW] API connection tests
├── setup_check.py                     [MODIFIED] Updated dependencies
├── .env                               [MODIFIED] Cleaned + XAI key
├── requirements.txt                   [MODIFIED] Removed anthropic, added openai
├── XAI_GROK_INTEGRATION.md           [NEW] Full integration guide
├── IMPLEMENTATION_SUMMARY.md          [NEW] Change summary
├── data/
│   ├── embedding_pipeline.py         [MODIFIED] Uses Grok instead of Claude
│   ├── schema_definitions.py         [UNCHANGED]
│   ├── wine_data_loader.py           [UNCHANGED]
│   └── __init__.py                   [UNCHANGED]
└── ...other files
```

## 🔑 API Keys & Encryption

### Check Your Current Keys
```bash
# View current .env configuration
cat .env
```

### Generate Encryption Key
```bash
python key_management.py
# Select option 1
```

### Encrypt API Key
```bash
python key_management.py
# Select option 2
# Paste your XAI_API_KEY
# Paste your encryption key
```

### Decrypt API Key (if needed)
```bash
python key_management.py
# Select option 3
```

## ✅ Verification Commands

### Test All APIs
```bash
python test_api_connections.py
```

Expected: All tests should PASS ✓

### Test Individually

**Test Encryption:**
```python
python -c "
from crypto_utils import SecureKeyManager
m = SecureKeyManager()
e = m.encrypt_key('test')
d = m.decrypt_key(e)
print(f'✓ Encryption works' if e != 'test' and d == 'test' else '✗ Failed')
"
```

**Test XAI Grok:**
```python
python -c "
from config import settings
from openai import OpenAI
client = OpenAI(api_key=settings.get_decrypted_xai_key(), base_url='https://api.x.ai/v1')
r = client.chat.completions.create(model='grok-latest', messages=[{'role':'user', 'content':'Hi'}])
print('✓ XAI Grok works')
"
```

**Test Pinecone:**
```python
python -c "
from pinecone import Pinecone
from config import settings
pc = Pinecone(api_key=settings.pinecone_api_key)
indexes = pc.list_indexes()
print(f'✓ Pinecone works - {len(indexes)} indexes')
"
```

## 🚀 Common Usage Patterns

### Initialize Embedding Pipeline
```python
from data.embedding_pipeline import EmbeddingPipeline

pipeline = EmbeddingPipeline()
print(f"Connected to: {pipeline.index_name}")
```

### Generate Wine Embeddings
```python
count = pipeline.embed_business_wines(qr_id="qr_biz_001", batch_size=100)
print(f"Embedded {count} wines")
```

### Search Similar Wines
```python
results = pipeline.search_similar_wines(
    query_text="Full-bodied red wine with dark fruit",
    qr_id="qr_biz_001",
    top_k=5
)

for wine_id, score, metadata in results:
    print(f"{metadata['producer']} - Score: {score:.3f}")
```

### Extract Wine Keywords
```python
tasting_note = "Crisp and bright with notes of lemon and green apple"
keywords = pipeline.extract_tasting_keywords(tasting_note)
print(f"Keywords: {keywords}")
```

## 🔧 Configuration Reference

### config.py
```python
from config import settings

# Access settings
print(settings.xai_api_key)           # Raw (encrypted) key
print(settings.get_decrypted_xai_key())  # Decrypted key
print(settings.pinecone_api_key)      # Pinecone key
print(settings.pinecone_index_name)   # Index name
print(settings.redis_host)             # Redis host
print(settings.environment)            # dev/prod
```

### .env Example
```dotenv
XAI_API_KEY=gAAAAABn...encrypted...
ENCRYPTION_KEY=your-encryption-key-from-generate
PINECONE_API_KEY=pcsk_...
PINECONE_ENVIRONMENT=us-east-1
REDIS_HOST=localhost
REDIS_PORT=6379
ENVIRONMENT=development
LOG_LEVEL=INFO
```

## 📊 Embedding Dimensions

| Service | Dimension | Reason |
|---------|-----------|--------|
| Grok (XAI) | 1536 | OpenAI standard, better compatibility |
| Old Claude | 1024 | Anthropic specific |

**Migration Note**: Pinecone index was updated to 1536 dimensions.

## 🐛 Troubleshooting

### "ModuleNotFoundError: No module named 'openai'"
```bash
pip install openai>=1.3.0
```

### "Invalid encryption key format"
```python
from crypto_utils import SecureKeyManager
key = SecureKeyManager.generate_encryption_key()
# Add to .env: ENCRYPTION_KEY={key}
```

### "XAI API rate limited"
- Add delay between requests
- Check usage at https://console.x.ai/

### "Pinecone index not found"
```python
# Check existing indexes
from config import settings
from pinecone import Pinecone
pc = Pinecone(api_key=settings.pinecone_api_key)
print([idx['name'] for idx in pc.list_indexes()])
```

### "Redis connection refused"
```bash
# Start Redis (if installed)
redis-server

# Or skip Redis if not needed
# (It's optional for caching only)
```

## 📞 API Documentation

### XAI Grok
- **Docs**: https://docs.x.ai/
- **Models**: grok-latest, grok-vision-beta
- **Endpoint**: https://api.x.ai/v1
- **Usage**: OpenAI-compatible interface

### Pinecone
- **Docs**: https://docs.pinecone.io/
- **Dashboard**: https://app.pinecone.io/
- **Index Dimension**: 1536

### OpenAI Python SDK
- **Docs**: https://github.com/openai/openai-python
- **Works with**: XAI, OpenAI, Azure OpenAI

## 🎯 Feature Checklist

- [x] LLM: Switched from Claude to Grok
- [x] Encryption: Added crypto_utils.py
- [x] Configuration: Updated config.py
- [x] Embeddings: Updated pipeline to use Grok
- [x] Testing: Created test_api_connections.py
- [x] Documentation: Created guides
- [x] Key Management: Created key_management.py
- [x] Dependencies: Updated requirements.txt

## 📝 Useful Commands

```bash
# Install all dependencies
pip install -r requirements.txt

# Test everything
python test_api_connections.py

# Manage keys
python key_management.py

# Check setup
python setup_check.py

# Run embedding pipeline
python -c "from data.embedding_pipeline import EmbeddingPipeline; EmbeddingPipeline()"
```

## 🔄 Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Pre-Jan 29 | Original with Anthropic Claude |
| 2.0 | Jan 29, 2026 | Migrated to XAI Grok, added encryption |

## 💡 Tips

1. **Security**: Keep encryption key separate from API keys
2. **Backup**: Save your encryption key securely
3. **Testing**: Run tests before deploying changes
4. **Monitoring**: Check API usage and limits regularly
5. **Logging**: Set LOG_LEVEL=DEBUG for troubleshooting

---

**Last Updated**: January 29, 2026  
**Questions?** See XAI_GROK_INTEGRATION.md or IMPLEMENTATION_SUMMARY.md

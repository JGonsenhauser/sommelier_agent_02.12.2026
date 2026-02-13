review this folder # Phase 1: Core Infrastructure - Complete! ✓

## What We've Built

### 1. Project Structure
```
sommelier_agent/
├── venv/                          # Virtual environment
├── data/                          # Data pipeline
│   ├── __init__.py
│   ├── schema_definitions.py     # Redis & Pinecone schemas
│   ├── wine_data_loader.py       # Wine list → Redis pipeline
│   ├── embedding_pipeline.py     # Pinecone embedding generation
│   └── raw/                      # Raw data files
├── config.py                      # Settings & environment config
├── requirements.txt               # Dependencies
├── .env.example                   # Environment template
└── README.md                      # Documentation
```

### 2. Core Components

#### Schema Definitions (`data/schema_definitions.py`)
- **Wine**: Individual wine data model with Redis serialization
- **Business**: Restaurant/bar details and wine list references
- **Session**: User session with preferences and conversation history
- **WineEmbedding**: Pinecone metadata schema for semantic search
- **RedisKeys**: Standardized key patterns for Redis storage

#### Wine Data Loader (`data/wine_data_loader.py`)
- Load wine lists from Excel/CSV files
- Store wines in Redis with structured schema
- Create business records and QR code mappings
- Batch processing support
- Retrieve wines by business/QR code

#### Embedding Pipeline (`data/embedding_pipeline.py`)
- Generate wine embeddings for semantic search
- Extract tasting note keywords using Claude
- Store vectors in Pinecone with metadata
- Search similar wines based on preferences
- Filter by business, price, wine type, etc.

## Next Steps

### Immediate Actions

1. **Set up Redis**
   ```bash
   # Windows (using Chocolatey)
   choco install redis-64
   redis-server
   
   # Or use Docker
   docker run -d -p 6379:6379 redis:latest
   ```

2. **Configure Environment**
   ```bash
   # Copy template and add your API keys
   cp .env.example .env
   
   # Edit .env with:
   # - ANTHROPIC_API_KEY
   # - PINECONE_API_KEY
   # - PINECONE_ENVIRONMENT
   ```

3. **Run Setup Check**
   ```bash
   python setup_check.py
   ```

### Testing the Pipeline

Once Redis is running and .env is configured:

```python
# Create sample wine list
python setup_check.py  # Select 'y' to create sample data

# Load wines into Redis
from data.wine_data_loader import WineDataLoader
from pathlib import Path

loader = WineDataLoader()
loader.load_business_wine_list(
    business_id="biz_001",
    business_name="The Vineyard Restaurant",
    wine_list_file=Path("data/raw/sample_wine_list.xlsx"),
    location="123 Main St, San Francisco, CA"
)

# Generate embeddings (requires Pinecone setup)
from data.embedding_pipeline import EmbeddingPipeline

pipeline = EmbeddingPipeline()
pipeline.embed_business_wines("qr_biz_001")
```

## Moving to Phase 2

Ready to build the Chat Engine? Phase 2 includes:
- Conversational flow manager
- Prompt templates for sommelier personality
- Wine matching algorithm
- LLM integration with Claude Haiku

Let me know when you're ready to proceed!

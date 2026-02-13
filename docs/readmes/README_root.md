# Wine Sommelier Agent

An AI-powered sommelier that provides personalized wine recommendations for restaurants and wine bars.

## Setup

1. Create virtual environment:
```bash
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment:
```bash
cp .env.example .env
# Edit .env with your API keys
```

## Architecture

- **Chat Engine**: Claude Haiku 4.5 for conversational sommelier
- **Vector DB**: Pinecone for wine embeddings and semantic search
- **Session Cache**: Redis for fast session and wine list lookups
- **Frontend**: Streamlit with upmarket design
- **Backend API**: FastAPI

## Project Structure

```
sommelier_agent/
├── data/               # Data pipeline and schemas
├── agents/             # Chat engine and wine matching logic
├── app/                # Streamlit frontend
└── api/                # FastAPI backend (Phase 4)
```

## Development Phases

- Phase 1: Core Infrastructure (Database & Data Pipeline)
- Phase 2: Chat Engine (Conversational Flow & LLM Integration)
- Phase 3: Frontend (Streamlit UI)
- Phase 4: Integration & Deployment

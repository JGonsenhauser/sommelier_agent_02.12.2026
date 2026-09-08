"""Vercel Python entry: guest PWA (local list + Grok notes, no Pinecone)."""
try:
    from api.demo_api import app
except ImportError:
    from demo_api import app

__all__ = ["app"]

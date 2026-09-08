"""
Configuration management for Wine Sommelier Agent.
Loads settings from environment variables with encrypted API key support.
"""
from pydantic_settings import BaseSettings
from typing import Optional
from crypto_utils import SecureKeyManager


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # XAI/Grok API
    xai_api_key: str
    encryption_key: Optional[str] = None
    xai_chat_model: str = "grok-4-fast-reasoning"
    xai_embedding_model: str = "grok-embedding"
    embedding_dimensions: int = 1024
    master_list_id: str = "master"
    master_namespace: str = "master"
    
    # Optional OpenAI embeddings (xAI has no public embedding model)
    openai_api_key: Optional[str] = None
    openai_embedding_model: str = "text-embedding-3-small"
    use_openai_embeddings: bool = False
    
    # Pinecone Configuration
    pinecone_api_key: str
    pinecone_environment: str
    pinecone_index_name: str = "wine-sommelier"
    pinecone_host: Optional[str] = None
    
    # Redis Configuration
    redis_url: Optional[str] = None  # Full Redis URL (e.g., for Redis Cloud)
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None
    
    # Application Settings
    environment: str = "development"
    log_level: str = "INFO"
    public_base_url: Optional[str] = None  # HTTPS URL for guest QR / PWA
    cors_origins: str = "http://localhost:8000,http://127.0.0.1:8000,http://localhost:8501"
    admin_password: Optional[str] = None
    admin_secret: Optional[str] = None
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from: Optional[str] = None

    def cors_origin_list(self) -> list:
        origins = [o.strip() for o in (self.cors_origins or "").split(",") if o.strip()]
        public = (self.public_base_url or "").strip().rstrip("/")
        if public and public not in origins:
            origins.append(public)
        return origins or ["http://localhost:8000"]

    def resolved_admin_password(self) -> Optional[str]:
        if self.admin_password:
            return self.admin_password
        if (self.environment or "").lower() == "development":
            return "maass-admin"
        return None
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"
    
    def get_decrypted_xai_key(self) -> str:
        """Return the xAI key, decrypting only if it is Fernet-encrypted."""
        raw = (self.xai_api_key or "").strip()
        if raw.startswith("xai-"):
            return raw
        try:
            key_manager = SecureKeyManager(encryption_key=self.encryption_key)
            return key_manager.decrypt_key(raw)
        except Exception:
            return raw


# Global settings instance
settings = Settings()

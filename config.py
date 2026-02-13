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
    xai_chat_model: str = "grok-3"
    xai_embedding_model: str = "grok-embedding"
    embedding_dimensions: int = 1024  # OpenAI text-embedding-3-small dimension
    master_list_id: str = "master"
    master_namespace: str = "master"
    
    # OpenAI API (alternative for embeddings)
    openai_api_key: Optional[str] = None
    openai_embedding_model: str = "text-embedding-3-small"
    use_openai_embeddings: bool = True
    
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
    
    class Config:
        env_file = ".env"
        case_sensitive = False
    
    def get_decrypted_xai_key(self) -> str:
        """
        Get decrypted XAI API key.
        
        Returns:
            Decrypted XAI API key string
        """
        try:
            key_manager = SecureKeyManager(encryption_key=self.encryption_key)
            return key_manager.decrypt_key(self.xai_api_key)
        except Exception:
            # If decryption fails, assume key is not encrypted
            return self.xai_api_key


# Global settings instance
settings = Settings()

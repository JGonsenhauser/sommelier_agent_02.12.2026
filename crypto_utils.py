"""
Cryptographic utilities for secure API key management.
Provides encryption/decryption for sensitive credentials.
"""
from cryptography.fernet import Fernet
from typing import Optional
import logging
import os

logger = logging.getLogger(__name__)


class SecureKeyManager:
    """Manages encryption and decryption of sensitive API keys."""
    
    def __init__(self, encryption_key: Optional[str] = None):
        """
        Initialize SecureKeyManager.
        
        Args:
            encryption_key: Encryption key for Fernet cipher. 
                          If None, will look for ENCRYPTION_KEY env var.
                          If not found, will generate a new key.
        """
        self.encryption_key = encryption_key or os.getenv('ENCRYPTION_KEY')
        
        if not self.encryption_key:
            # Generate a new key if none exists
            self.encryption_key = Fernet.generate_key().decode()
            logger.warning(
                "No encryption key found. Generated new key. "
                "Set ENCRYPTION_KEY environment variable to use the same key."
            )
        
        try:
            # Ensure key is bytes
            if isinstance(self.encryption_key, str):
                key_bytes = self.encryption_key.encode()
            else:
                key_bytes = self.encryption_key
            
            self.cipher = Fernet(key_bytes)
        except Exception as e:
            logger.error(f"Invalid encryption key format: {e}")
            raise ValueError("Encryption key must be a valid Fernet key")
    
    def encrypt_key(self, api_key: str) -> str:
        """
        Encrypt an API key.
        
        Args:
            api_key: The API key to encrypt
            
        Returns:
            Encrypted key as string
        """
        try:
            encrypted = self.cipher.encrypt(api_key.encode())
            return encrypted.decode()
        except Exception as e:
            logger.error(f"Error encrypting key: {e}")
            raise
    
    def decrypt_key(self, encrypted_key: str) -> str:
        """
        Decrypt an API key.
        
        Args:
            encrypted_key: The encrypted API key
            
        Returns:
            Decrypted API key as string
        """
        try:
            if isinstance(encrypted_key, str):
                encrypted_key = encrypted_key.encode()
            decrypted = self.cipher.decrypt(encrypted_key)
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Error decrypting key: {e}")
            raise
    
    @staticmethod
    def generate_encryption_key() -> str:
        """
        Generate a new Fernet encryption key.
        
        Returns:
            New encryption key as string
        """
        return Fernet.generate_key().decode()


def get_secure_key_manager() -> SecureKeyManager:
    """Get or create a SecureKeyManager instance."""
    return SecureKeyManager()

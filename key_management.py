"""
Key Management Utility for Wine Sommelier Agent.
Provides easy encryption/decryption of API keys.
"""
import sys
from pathlib import Path
from crypto_utils import SecureKeyManager


def generate_and_save_encryption_key():
    """Generate a new encryption key and display it."""
    print("=" * 70)
    print("Encryption Key Generator")
    print("=" * 70)
    
    key = SecureKeyManager.generate_encryption_key()
    
    print("\n✓ New encryption key generated:")
    print(f"\n{key}\n")
    
    print("ADD THIS TO YOUR .env FILE:")
    print(f"ENCRYPTION_KEY={key}\n")
    
    print("⚠️  IMPORTANT:")
    print("  - Keep this key secure and back it up safely")
    print("  - Never commit this key to version control")
    print("  - Use the same key to decrypt API keys encrypted with it")
    
    return key


def encrypt_api_key(api_key: str, encryption_key: str = None):
    """Encrypt an API key and display it."""
    print("=" * 70)
    print("API Key Encryptor")
    print("=" * 70)
    
    manager = SecureKeyManager(encryption_key=encryption_key)
    encrypted = manager.encrypt_key(api_key)
    
    print(f"\n✓ API Key encrypted:")
    print(f"\nOriginal:  {api_key[:20]}...{api_key[-20:]}")
    print(f"Encrypted: {encrypted[:50]}...{encrypted[-50:]}\n")
    
    print("ADD THIS TO YOUR .env FILE:")
    print(f"XAI_API_KEY={encrypted}\n")
    
    return encrypted


def decrypt_api_key(encrypted_key: str, encryption_key: str = None):
    """Decrypt an API key."""
    print("=" * 70)
    print("API Key Decryptor")
    print("=" * 70)
    
    try:
        manager = SecureKeyManager(encryption_key=encryption_key)
        decrypted = manager.decrypt_key(encrypted_key)
        
        print(f"\n✓ API Key decrypted:")
        print(f"\nDecrypted: {decrypted[:20]}...{decrypted[-20:]}\n")
        
        return decrypted
        
    except Exception as e:
        print(f"\n✗ Failed to decrypt: {e}")
        print("   - Check that the encryption key is correct")
        print("   - Verify the encrypted key is valid")
        return None


def main():
    """Main menu for key management."""
    print("\n" + "=" * 70)
    print("Wine Sommelier Agent - Key Management Tool")
    print("=" * 70 + "\n")
    
    print("Options:")
    print("  1. Generate new encryption key")
    print("  2. Encrypt an API key")
    print("  3. Decrypt an API key")
    print("  4. Exit")
    
    choice = input("\nSelect option (1-4): ").strip()
    
    if choice == "1":
        generate_and_save_encryption_key()
        
    elif choice == "2":
        api_key = input("\nEnter API key to encrypt: ").strip()
        encryption_key = input("Enter encryption key (or press Enter for env var): ").strip()
        
        if not encryption_key:
            encryption_key = None
        
        encrypt_api_key(api_key, encryption_key)
        
    elif choice == "3":
        encrypted_key = input("\nEnter encrypted key: ").strip()
        encryption_key = input("Enter encryption key (or press Enter for env var): ").strip()
        
        if not encryption_key:
            encryption_key = None
        
        decrypt_api_key(encrypted_key, encryption_key)
        
    elif choice == "4":
        print("\nGoodbye!")
        sys.exit(0)
    else:
        print("\n✗ Invalid option")
    
    # Ask to continue
    print("\n" + "-" * 70)
    again = input("Run another operation? (y/n): ").strip().lower()
    
    if again == "y":
        main()
    else:
        print("Goodbye!")


if __name__ == "__main__":
    main()

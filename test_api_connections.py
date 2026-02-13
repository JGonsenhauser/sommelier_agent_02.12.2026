"""
API Connection Tester for Wine Sommelier Agent.
Tests connectivity to all required APIs: XAI Grok, Pinecone, Redis, and encryption utilities.
"""
import sys
import logging
from typing import Dict, Tuple

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_encryption_setup() -> Tuple[bool, str]:
    """Test encryption utility and key generation."""
    try:
        from crypto_utils import SecureKeyManager
        
        # Test key manager initialization
        key_manager = SecureKeyManager()
        logger.info("✓ Encryption utility initialized successfully")
        
        # Test encrypt/decrypt
        test_key = "test-api-key-12345"
        encrypted = key_manager.encrypt_key(test_key)
        decrypted = key_manager.decrypt_key(encrypted)
        
        if decrypted == test_key:
            logger.info("✓ Encryption/Decryption test passed")
            return True, "Encryption working correctly"
        else:
            logger.error("✗ Decryption mismatch")
            return False, "Decryption verification failed"
            
    except Exception as e:
        logger.error(f"✗ Encryption setup failed: {e}")
        return False, str(e)


def test_config_loading() -> Tuple[bool, str]:
    """Test configuration loading from environment."""
    try:
        from config import settings
        
        # Check required settings
        required_settings = {
            'xai_api_key': 'XAI API Key',
            'pinecone_api_key': 'Pinecone API Key',
            'pinecone_environment': 'Pinecone Environment',
            'redis_host': 'Redis Host'
        }
        
        missing = []
        for attr, label in required_settings.items():
            if not getattr(settings, attr, None):
                missing.append(label)
        
        if missing:
            logger.error(f"✗ Missing configuration: {', '.join(missing)}")
            return False, f"Missing: {', '.join(missing)}"
        
        logger.info("✓ All configuration settings loaded successfully")
        logger.info(f"  - Environment: {settings.environment}")
        logger.info(f"  - Log Level: {settings.log_level}")
        logger.info(f"  - Pinecone Index: {settings.pinecone_index_name}")
        logger.info(f"  - Redis: {settings.redis_host}:{settings.redis_port}")
        
        return True, "Configuration loaded successfully"
        
    except Exception as e:
        logger.error(f"✗ Configuration loading failed: {e}")
        return False, str(e)


def test_xai_connection() -> Tuple[bool, str]:
    """Test XAI Grok API connection."""
    try:
        from openai import OpenAI
        from config import settings
        
        # Initialize Grok client
        xai_api_key = settings.get_decrypted_xai_key()
        client = OpenAI(
            api_key=xai_api_key,
            base_url="https://api.x.ai/v1"
        )
        
        # Test connection with simple request
        response = client.chat.completions.create(
            model="grok-3",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful wine expert assistant. Be concise."
                },
                {
                    "role": "user",
                    "content": "What is a Pinot Noir wine? Answer in one sentence."
                }
            ],
            temperature=0.3,
            max_tokens=100
        )
        
        answer = response.choices[0].message.content
        logger.info(f"✓ XAI Grok API connection successful")
        logger.info(f"  - Model: grok-3")
        logger.info(f"  - Response: {answer[:100]}...")
        
        return True, "XAI Grok API connection successful"
        
    except Exception as e:
        logger.error(f"✗ XAI Grok API connection failed: {e}")
        return False, str(e)


def test_pinecone_connection() -> Tuple[bool, str]:
    """Test Pinecone vector database connection."""
    try:
        from pinecone import Pinecone
        from config import settings
        
        # Initialize Pinecone
        pc = Pinecone(api_key=settings.pinecone_api_key)
        
        # List indexes to verify connection
        indexes = pc.list_indexes()
        
        logger.info(f"✓ Pinecone connection successful")
        logger.info(f"  - Available indexes: {len(indexes)}")
        
        if indexes:
            for idx in indexes:
                logger.info(f"    - {idx['name']}")
        
        return True, f"Pinecone connection successful ({len(indexes)} indexes found)"
        
    except Exception as e:
        logger.error(f"✗ Pinecone connection failed: {e}")
        return False, str(e)


def test_redis_connection() -> Tuple[bool, str]:
    """Test Redis connection."""
    try:
        import redis
        from config import settings
        
        # Initialize Redis connection
        redis_client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            password=settings.redis_password,
            decode_responses=True
        )
        
        # Test connection with ping
        redis_client.ping()
        
        # Test set/get
        test_key = "wine_agent_test"
        test_value = "test_value"
        redis_client.set(test_key, test_value)
        retrieved = redis_client.get(test_key)
        redis_client.delete(test_key)
        
        if retrieved == test_value:
            logger.info(f"✓ Redis connection successful")
            logger.info(f"  - Host: {settings.redis_host}:{settings.redis_port}")
            logger.info(f"  - Database: {settings.redis_db}")
            return True, "Redis connection successful"
        else:
            logger.error("✗ Redis test set/get failed")
            return False, "Redis set/get test failed"
            
    except Exception as e:
        logger.error(f"✗ Redis connection failed: {e}")
        logger.warning("  Note: Redis is optional. Continue without it if not needed.")
        return False, str(e)


def test_embedding_pipeline() -> Tuple[bool, str]:
    """Test embedding pipeline initialization."""
    try:
        from data.embedding_pipeline import EmbeddingPipeline
        
        # Initialize pipeline
        pipeline = EmbeddingPipeline()
        
        logger.info(f"✓ Embedding pipeline initialized successfully")
        logger.info(f"  - Pinecone Index: {pipeline.index_name}")
        logger.info(f"  - LLM: Grok (XAI)")
        logger.info(f"  - Embedding Dimension: 1536")
        
        return True, "Embedding pipeline initialized successfully"
        
    except Exception as e:
        logger.error(f"✗ Embedding pipeline initialization failed: {e}")
        return False, str(e)


def run_all_tests() -> Dict[str, Tuple[bool, str]]:
    """Run all connection tests."""
    tests = [
        ("Encryption Setup", test_encryption_setup),
        ("Configuration Loading", test_config_loading),
        ("XAI Grok API", test_xai_connection),
        ("Pinecone Vector DB", test_pinecone_connection),
        ("Redis Cache", test_redis_connection),
        ("Embedding Pipeline", test_embedding_pipeline),
    ]
    
    results = {}
    logger.info("=" * 70)
    logger.info("Starting API Connection Tests")
    logger.info("=" * 70)
    
    for test_name, test_func in tests:
        logger.info(f"\nTesting: {test_name}")
        logger.info("-" * 70)
        success, message = test_func()
        results[test_name] = (success, message)
    
    # Print summary
    logger.info("\n" + "=" * 70)
    logger.info("Test Summary")
    logger.info("=" * 70)
    
    passed = sum(1 for success, _ in results.values() if success)
    total = len(results)
    
    for test_name, (success, message) in results.items():
        status = "✓ PASS" if success else "✗ FAIL"
        logger.info(f"{status}: {test_name}")
        if not success:
            logger.info(f"       Error: {message}")
    
    logger.info("-" * 70)
    logger.info(f"Total: {passed}/{total} tests passed")
    logger.info("=" * 70)
    
    return results


if __name__ == "__main__":
    results = run_all_tests()
    
    # Exit with error code if any critical test failed
    critical_tests = [
        "Configuration Loading",
        "XAI Grok API",
        "Pinecone Vector DB"
    ]
    
    critical_failed = any(
        not success 
        for test_name, (success, _) in results.items() 
        if test_name in critical_tests
    )
    
    sys.exit(1 if critical_failed else 0)

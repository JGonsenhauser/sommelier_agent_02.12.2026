import os
from dotenv import load_dotenv
from pinecone import Pinecone

# Load environment variables from .env file in the current directory
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

# Initialize Pinecone client
api_key = os.getenv("PINECONE_API_KEY")
if not api_key:
    raise ValueError("PINECONE_API_KEY not found in .env file")

pc = Pinecone(api_key=api_key)

# Get index name from environment
index_name = os.getenv("PINECONE_INDEX_NAME", "wine_list_test")

def get_index():
    """Get the Pinecone index for wine regions."""
    try:
        return pc.Index(index_name)
    except Exception as e:
        print(f"Error connecting to index '{index_name}': {e}")
        raise

def get_pinecone_client():
    """Get the Pinecone client instance."""
    return pc

def list_indexes():
    """List all available Pinecone indexes."""
    return pc.list_indexes()

if __name__ == "__main__":
    print("Pinecone client initialized successfully")
    print(f"API Key: {api_key[:20]}...")
    print(f"Index Name: {index_name}")
    
    try:
        print("\nAvailable indexes:")
        indexes = pc.list_indexes()
        for idx in indexes:
            print(f"  - {idx.name}")
        
        index = get_index()
        stats = index.describe_index_stats()
        print(f"\nIndex '{index_name}' Stats:")
        print(f"  {stats}")
    except Exception as e:
        print(f"\nError: {e}")
        print(f"Index '{index_name}' not found or connection failed.")

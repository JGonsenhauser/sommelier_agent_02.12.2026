"""
Embedding pipeline for Wine Sommelier Agent.
Generates embeddings for wine data and stores in Pinecone for semantic search.
Uses Grok LLM from XAI for semantic processing.
"""
from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec
import logging
from typing import List, Dict, Tuple, Optional
import hashlib
import time
import re

from data.schema_definitions import Wine, WineEmbedding, PriceRange
from data.wine_data_loader import WineDataLoader
from config import settings

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)


class EmbeddingError(Exception):
    """Raised when embedding generation fails (e.g. OpenAI outage)."""
    pass


class EmbeddingPipeline:
    """Generates and manages wine embeddings in Pinecone using Grok LLM."""
    
    def __init__(self):
        """Initialize Grok/XAI and Pinecone clients."""
        # Initialize XAI Grok client (OpenAI-compatible)
        xai_api_key = settings.get_decrypted_xai_key()
        self.grok_client = OpenAI(
            api_key=xai_api_key,
            base_url="https://api.x.ai/v1"
        )
        
        # Initialize OpenAI client if available
        self.openai_client = None
        if settings.openai_api_key:
            self.openai_client = OpenAI(api_key=settings.openai_api_key)
        
        # Initialize Pinecone
        self.pc = Pinecone(api_key=settings.pinecone_api_key)
        self.wine_loader = WineDataLoader()
        self.index_name = settings.pinecone_index_name
        self.chat_model = settings.xai_chat_model
        self.embedding_model = settings.xai_embedding_model
        self.embedding_dimensions = settings.embedding_dimensions
        self.master_list_id = settings.master_list_id
        
        # Initialize or connect to Pinecone index
        self._setup_index()
        
        logger.info("Embedding pipeline initialized with Grok LLM and Pinecone")
    
    def _setup_index(self):
        """Create or connect to Pinecone index."""
        # Check if index exists
        existing_indexes = self.pc.list_indexes()
        existing_names = {
            idx["name"] if isinstance(idx, dict) else idx.name
            for idx in existing_indexes
        }
        
        if self.index_name not in existing_names:
            logger.info(f"Creating new Pinecone index: {self.index_name}")
            self.pc.create_index(
                name=self.index_name,
                dimension=self.embedding_dimensions,
                metric='cosine',
                spec=ServerlessSpec(
                    cloud='aws',
                    region=settings.pinecone_environment
                )
            )
            # Wait for index to be ready
            time.sleep(1)
        
        self.index = self.pc.Index(self.index_name)
        logger.info(f"Connected to Pinecone index: {self.index_name}")
    
    def generate_wine_text(self, wine: Wine) -> str:
        """
        Generate rich text representation of wine for embedding.
        
        Combines producer, region, grapes, and tasting notes into
        a descriptive text that captures the wine's characteristics.
        """
        grapes_text = ", ".join(wine.grapes)
        vintage_text = f"{wine.vintage} vintage" if wine.vintage else "non-vintage"
        
        text = f"""
        {wine.producer} {wine.wine_name or ""} - {vintage_text}
        Region: {wine.region}, {wine.country}
        Grape varietals: {grapes_text}
        Wine type: {wine.wine_type.value}
        Tasting profile: {wine.tasting_note}
        Price: ${wine.price}
        """.strip()
        
        return text
    
    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings using OpenAI text-embedding-3-small (1024 dims).

        Raises EmbeddingError if the service is unavailable so callers
        can return a friendly message instead of garbage results.
        """
        if not (settings.use_openai_embeddings and self.openai_client):
            raise EmbeddingError("No embedding provider configured. Set USE_OPENAI_EMBEDDINGS=true.")

        try:
            response = self.openai_client.embeddings.create(
                model=settings.openai_embedding_model,
                input=texts,
                dimensions=self.embedding_dimensions,
                timeout=10  # Fail fast — 10 seconds max per call
            )
            vectors = [item.embedding for item in response.data]
            return vectors
        except Exception as e:
            logger.error(f"OpenAI embedding error: {e}")
            raise EmbeddingError(f"Embedding service temporarily unavailable. Please try again in a moment.")
    
    def extract_tasting_keywords(self, tasting_note: str) -> str:
        """
        Use Grok to extract semantic keywords from tasting notes.
        
        Args:
            tasting_note: Raw tasting note text
            
        Returns:
            Comma-separated keywords
        """
        prompt = f"""Extract 5-7 key flavor and aroma descriptors from this wine tasting note.
        Return only the keywords, comma-separated, no explanation.
        
        Tasting note: {tasting_note}
        
        Keywords:"""
        
        try:
            response = self.grok_client.chat.completions.create(
                model=self.chat_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=100
            )
            
            keywords = response.choices[0].message.content.strip()
            return keywords
            
        except Exception as e:
            logger.error(f"Error extracting keywords with Grok: {e}")
            return tasting_note[:100]  # Fallback to truncated note
    
    def get_price_range(self, price: float) -> str:
        """Categorize price into range bucket."""
        if price < 50:
            return PriceRange.BUDGET.value
        elif price < 100:
            return PriceRange.MID.value
        elif price < 200:
            return PriceRange.PREMIUM.value
        else:
            return PriceRange.LUXURY.value
    
    def embed_business_wines(
        self,
        qr_id: str,
        batch_size: int = 100,
        list_id: Optional[str] = None,
        also_add_to_master: bool = False,
        namespace: Optional[str] = None,
        also_add_to_producers: bool = False,
        producers_namespace: str = "producers"
    ) -> int:
        """
        Generate and store embeddings for all wines of a business.
        
        Args:
            qr_id: QR code identifier for the business
            batch_size: Number of wines to process per batch
            
        Returns:
            Number of wines embedded
        """
        logger.info(f"Embedding wines for business: {qr_id}")
        
        # Get all wines for this business
        wines = self.wine_loader.get_business_wines(qr_id)

        return self.embed_wines(
            wines=wines,
            qr_id=qr_id,
            batch_size=batch_size,
            list_id=list_id,
            also_add_to_master=also_add_to_master,
            namespace=namespace,
            also_add_to_producers=also_add_to_producers,
            producers_namespace=producers_namespace
        )

    def embed_wines(
        self,
        wines: List[Wine],
        qr_id: str,
        batch_size: int = 100,
        list_id: Optional[str] = None,
        also_add_to_master: bool = False,
        namespace: Optional[str] = None,
        also_add_to_producers: bool = False,
        producers_namespace: str = "producers"
    ) -> int:
        """Embed a list of Wine objects without relying on Redis."""
        
        if not wines:
            logger.warning(f"No wines found for {qr_id}")
            return 0
        
        logger.info(f"Processing {len(wines)} wines")
        
        # Process in batches
        total_embedded = 0
        for i in range(0, len(wines), batch_size):
            batch = wines[i:i + batch_size]
            
            # Generate text representations
            wine_texts = [self.generate_wine_text(wine) for wine in batch]
            
            # Generate embeddings (replace with actual embedding service)
            embeddings = self.get_embeddings(wine_texts)
            
            vectors = self._build_vectors(
                wines=batch,
                embeddings=embeddings,
                list_id=list_id,
                also_add_to_master=also_add_to_master
            )

            producer_vectors = []
            if also_add_to_producers:
                producer_vectors = self._build_producer_vectors(
                    wines=batch,
                    embeddings=embeddings,
                    list_id=list_id
                )
            
            # Upload to Pinecone
            try:
                self.index.upsert(vectors=vectors, namespace=namespace)
                total_embedded += len(vectors)
                if producer_vectors:
                    self.index.upsert(vectors=producer_vectors, namespace=producers_namespace)
                logger.info(f"Embedded batch {i//batch_size + 1}: {len(vectors)} wines")
            except Exception as e:
                logger.error(f"Error upserting batch: {e}")
        
        logger.info(f"Successfully embedded {total_embedded} wines for {qr_id}")
        return total_embedded

    def _build_vectors(
        self,
        wines: List[Wine],
        embeddings: List[List[float]],
        list_id: Optional[str],
        also_add_to_master: bool
    ) -> List[Dict]:
        vectors = []
        effective_list_id = list_id or (wines[0].qr_id if wines else "")
        for wine, embedding in zip(wines, embeddings):
            # Skip slow keyword extraction when using OpenAI embeddings
            if settings.use_openai_embeddings and self.openai_client:
                keywords = wine.tasting_note[:100]  # Use truncated tasting note
            else:
                keywords = self.extract_tasting_keywords(wine.tasting_note)

            metadata = WineEmbedding(
                wine_id=wine.wine_id,
                qr_id=wine.qr_id,
                list_id=effective_list_id,
                producer=wine.producer,
                region=wine.region,
                grapes=",".join(wine.grapes),
                wine_type=wine.wine_type.value,
                price_range=self.get_price_range(wine.price),
                tasting_keywords=keywords
            ).to_pinecone_metadata()

            vector_id = f"{effective_list_id}_{wine.qr_id}_{wine.wine_id}"
            vectors.append({
                "id": vector_id,
                "values": embedding,
                "metadata": metadata
            })

            if also_add_to_master:
                master_metadata = WineEmbedding(
                    wine_id=wine.wine_id,
                    qr_id=wine.qr_id,
                    list_id=self.master_list_id,
                    producer=wine.producer,
                    region=wine.region,
                    grapes=",".join(wine.grapes),
                    wine_type=wine.wine_type.value,
                    price_range=self.get_price_range(wine.price),
                    tasting_keywords=keywords
                ).to_pinecone_metadata()
                master_vector_id = f"{self.master_list_id}_{wine.qr_id}_{wine.wine_id}"
                vectors.append({
                    "id": master_vector_id,
                    "values": embedding,
                    "metadata": master_metadata
                })

        return vectors

    def _build_producer_vectors(
        self,
        wines: List[Wine],
        embeddings: List[List[float]],
        list_id: Optional[str]
    ) -> List[Dict]:
        vectors = []
        effective_list_id = list_id or (wines[0].qr_id if wines else "")
        for wine, embedding in zip(wines, embeddings):
            text = self.generate_wine_text(wine)
            producer_id = hashlib.md5(
                f"{wine.producer}|{wine.wine_name or ''}|{wine.region}|{wine.country}|{wine.qr_id}|{effective_list_id}".encode("utf-8")
            ).hexdigest()
            metadata = {
                "producer": wine.producer,
                "wine_name": wine.wine_name or "",
                "region": wine.region,
                "country": wine.country,
                "grapes": ",".join(wine.grapes),
                "wine_type": wine.wine_type.value,
                "tasting_note": wine.tasting_note,
                "price": wine.price,
                "wine_id": wine.wine_id,
                "qr_id": wine.qr_id,
                "list_id": effective_list_id,
                "source": "wine_list",
                "text": text
            }
            vectors.append({
                "id": f"producer_{producer_id}",
                "values": embedding,
                "metadata": metadata
            })
        return vectors
    
    def search_similar_wines(
        self,
        query_text: str,
        qr_id: Optional[str] = None,
        list_id: Optional[str] = None,
        top_k: int = 5,
        filters: Dict = None,
        namespace: Optional[str] = None
    ) -> List[Tuple[str, float, Dict]]:
        """
        Search for similar wines based on query text.
        
        Args:
            query_text: Natural language wine preference query
            qr_id: Filter to specific business
            top_k: Number of results to return
            filters: Additional metadata filters
            
        Returns:
            List of (wine_id, score, metadata) tuples
        """
        # Generate embedding for query
        query_embedding = self.get_embeddings([query_text])[0]
        
        # Build filter
        query_filter: Dict = {}
        effective_list_id = list_id or qr_id
        if effective_list_id:
            query_filter["list_id"] = effective_list_id
        if qr_id and list_id:
            query_filter["qr_id"] = qr_id
        if filters:
            query_filter.update(filters)
        
        # Search Pinecone
        results = self.index.query(
            vector=query_embedding,
            top_k=top_k,
            filter=query_filter,
            include_metadata=True,
            namespace=namespace
        )
        
        # Parse results
        matches = []
        for match in results['matches']:
            # Use vector ID instead of metadata wine_id (Schema V2 compatible)
            wine_id = match.get('id', match['metadata'].get('wine_id', 'unknown'))
            score = match['score']
            metadata = match['metadata']
            matches.append((wine_id, score, metadata))

        return matches
    
    def search_menu_items(
        self,
        query_text: str,
        restaurant_id: str,
        top_k: int = 3,
        namespace: Optional[str] = None
    ) -> List[Tuple[str, float, Dict]]:
        """Search for menu dishes that pair well with a wine description.

        Args:
            query_text: Wine description (grapes, type, region, tasting keywords).
            restaurant_id: Restaurant whose menu to search.
            top_k: Number of dish candidates to return.
            namespace: Override namespace (default: {restaurant_id}_menu).

        Returns:
            List of (dish_id, score, metadata) tuples.
        """
        menu_namespace = namespace or f"{restaurant_id}_menu"
        query_embedding = self.get_embeddings([query_text])[0]

        results = self.index.query(
            vector=query_embedding,
            top_k=top_k,
            include_metadata=True,
            namespace=menu_namespace,
        )

        matches = []
        for match in results["matches"]:
            dish_id = match["metadata"].get("dish_id", match.get("id", "unknown"))
            score = match["score"]
            metadata = match["metadata"]
            matches.append((dish_id, score, metadata))

        return matches

    def delete_business_embeddings(self, qr_id: str, namespace: Optional[str] = None) -> None:
        """
        Delete all embeddings for a business.
        
        Args:
            qr_id: QR code identifier
        """
        # Pinecone delete by metadata filter
        self.index.delete(filter={"qr_id": qr_id}, namespace=namespace)
        logger.info(f"Deleted embeddings for {qr_id}")


def embed_sample_business():
    """Example function to embed a sample business's wines."""
    pipeline = EmbeddingPipeline()
    
    # Replace with actual QR ID from your data
    qr_id = "qr_biz_001"
    
    count = pipeline.embed_business_wines(qr_id)
    logger.info(f"Embedded {count} wines")


if __name__ == "__main__":
    embed_sample_business()

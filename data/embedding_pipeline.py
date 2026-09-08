"""
Embedding pipeline for Wine Sommelier Agent.
Generates embeddings for wine data and stores in Pinecone for semantic search.
Uses Grok LLM from XAI for semantic processing.
"""
from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec
import logging
from typing import List, Dict, Tuple, Optional, Any
import hashlib
import time
import re
from pathlib import Path

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
        xai_api_key = settings.get_decrypted_xai_key()
        self.grok_client = OpenAI(
            api_key=xai_api_key,
            base_url="https://api.x.ai/v1",
            timeout=20.0,
        )
        self.openai_client = None
        
        # Initialize Pinecone
        self.pc = Pinecone(api_key=settings.pinecone_api_key)
        self.wine_loader = WineDataLoader()
        self.index_name = settings.pinecone_index_name
        self.chat_model = settings.xai_chat_model
        self.embedding_model = settings.xai_embedding_model
        self.embedding_dimensions = settings.embedding_dimensions
        self.master_list_id = settings.master_list_id
        self._namespace_catalog: Dict[str, List[Tuple[str, Dict]]] = {}
        
        # Initialize or connect to Pinecone index
        self._setup_index()
        try:
            self._load_namespace_catalog("maass_wine_list")
        except Exception as e:
            logger.warning("Catalog warmup skipped: %s", e)
        
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
        """Embed texts. xAI has no public embedding model; OpenAI is optional."""
        if settings.use_openai_embeddings and settings.openai_api_key:
            if self.openai_client is None:
                self.openai_client = OpenAI(api_key=settings.openai_api_key, timeout=20.0)
            response = self.openai_client.embeddings.create(
                model=settings.openai_embedding_model,
                input=texts,
                dimensions=settings.embedding_dimensions,
            )
            by_index = {item.index: item.embedding for item in response.data}
            return [by_index[i] for i in range(len(texts))]
        raise EmbeddingError("xAI embeddings are not available; using catalog search.")
    
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
            keywords = (wine.tasting_note or "")[:100]

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
        query_filter: Dict = {}
        effective_list_id = list_id or qr_id
        if effective_list_id:
            query_filter["list_id"] = effective_list_id
        if filters:
            query_filter.update(filters)

        if settings.use_openai_embeddings:
            try:
                query_embedding = self.get_embeddings([query_text])[0]
                results = self.index.query(
                    vector=query_embedding,
                    top_k=top_k,
                    filter=query_filter or None,
                    include_metadata=True,
                    namespace=namespace
                )
                matches = self._parse_query_matches(results)
                if matches:
                    return matches
                logger.warning("Vector search returned no matches; trying lexical fallback")
            except EmbeddingError as e:
                logger.warning("Embeddings unavailable (%s); using catalog search", e)
            except Exception as e:
                logger.warning("Vector search failed (%s); using catalog search", e)

        return self._lexical_search_wines(
            query_text=query_text,
            query_filter=query_filter,
            top_k=top_k,
            namespace=namespace,
        )

    @staticmethod
    def _parse_query_matches(results: Any) -> List[Tuple[str, float, Dict]]:
        raw = results.matches if hasattr(results, "matches") else results.get("matches", [])
        matches = []
        for match in raw:
            if hasattr(match, "id"):
                wine_id = match.id or "unknown"
                score = float(match.score or 0)
                metadata = dict(match.metadata or {})
            else:
                metadata = match.get("metadata") or {}
                wine_id = match.get("id", metadata.get("wine_id", "unknown"))
                score = float(match.get("score") or 0)
            matches.append((wine_id, score, metadata))
        return matches

    def _iter_namespace_ids(self, namespace: str):
        for page in self.index.list(namespace=namespace):
            vectors = getattr(page, "vectors", None)
            items = vectors if vectors is not None else page
            for item in items:
                yield item.id if hasattr(item, "id") else item

    def _load_namespace_catalog(self, namespace: str) -> List[Tuple[str, Dict]]:
        if namespace in self._namespace_catalog:
            return self._namespace_catalog[namespace]

        catalog: List[Tuple[str, Dict]] = []
        batch: List[str] = []
        try:
            for wine_id in self._iter_namespace_ids(namespace):
                batch.append(str(wine_id))
                if len(batch) >= 100:
                    catalog.extend(self._fetch_metadata_batch(batch, namespace))
                    batch = []
            if batch:
                catalog.extend(self._fetch_metadata_batch(batch, namespace))
        except Exception as e:
            logger.warning("Pinecone catalog load failed for %s: %s", namespace, e)

        if not catalog and namespace == "maass_wine_list":
            catalog = self._load_maass_csv_catalog()

        self._namespace_catalog[namespace] = catalog
        logger.info("Loaded %s wines for lexical search in %s", len(catalog), namespace)
        return catalog

    def _fetch_metadata_batch(self, ids: List[str], namespace: str) -> List[Tuple[str, Dict]]:
        fetched = self.index.fetch(ids=ids, namespace=namespace)
        vectors = fetched.vectors if hasattr(fetched, "vectors") else fetched.get("vectors", {})
        rows = []
        for wine_id, vec in (vectors or {}).items():
            metadata = vec.metadata if hasattr(vec, "metadata") else (vec.get("metadata") if isinstance(vec, dict) else {})
            rows.append((wine_id, dict(metadata or {})))
        return rows

    def _load_maass_csv_catalog(self) -> List[Tuple[str, Dict]]:
        csv_path = Path(__file__).parent / "raw" / "maass_wine_list_schema_compliant.csv"
        if not csv_path.exists():
            return []
        import csv
        catalog = []
        with csv_path.open(newline="", encoding="utf-8") as handle:
            for i, row in enumerate(csv.DictReader(handle)):
                wine_id = f"maass_csv_{i}"
                metadata = {
                    "producer": row.get("producer", ""),
                    "label": row.get("label", ""),
                    "wine_name": row.get("label", ""),
                    "grapes": row.get("grapes", ""),
                    "region": row.get("region", ""),
                    "major_region": row.get("major_region", ""),
                    "country": row.get("country", ""),
                    "text": row.get("text", ""),
                    "price": row.get("price", ""),
                    "price_range": row.get("price_range", ""),
                    "wine_style": (row.get("Wine Style") or "").lower(),
                    "wine_type": (row.get("Wine Style") or "").lower(),
                    "list_id": row.get("list_id", "maass_wine_list"),
                    "qr_id": row.get("qr_id", "qr_maass"),
                    "tasting_note": row.get("tasting_keywords", ""),
                }
                catalog.append((wine_id, metadata))
        return catalog

    @staticmethod
    def _style_aliases(value: str) -> set:
        v = (value or "").lower().strip()
        if v in {"rose", "rosé"}:
            return {"rose", "rosé"}
        if v in {"sparkling", "champagne"}:
            return {"sparkling", "champagne"}
        return {v} if v else set()

    @classmethod
    def _metadata_matches_filter(cls, metadata: Dict, query_filter: Dict) -> bool:
        if not query_filter:
            return True
        for key, expected in query_filter.items():
            if key in {"wine_style", "wine_type"}:
                actual = str(
                    metadata.get("wine_style") or metadata.get("wine_type") or ""
                ).lower()
                wanted = cls._style_aliases(str(expected))
                if not wanted.intersection(cls._style_aliases(actual)):
                    return False
                continue
            actual = metadata.get(key)
            if isinstance(expected, dict):
                try:
                    numeric = float(actual)
                except (TypeError, ValueError):
                    return False
                if "$gte" in expected and numeric < float(expected["$gte"]):
                    return False
                if "$lte" in expected and numeric > float(expected["$lte"]):
                    return False
                if "$eq" in expected and numeric != float(expected["$eq"]):
                    return False
            elif str(actual) != str(expected):
                return False
        return True

    LIGHT_GRAPES = {
        "pinot", "gamay", "riesling", "gris", "grigio", "arneis", "muscadet",
        "albariño", "albarino", "chenin", "glera",
    }
    FULL_GRAPES = {
        "cabernet", "syrah", "shiraz", "malbec", "nebbiolo", "sangiovese",
        "tempranillo", "zinfandel", "grenache", "mourvedre",
    }
    FOOD_AFFINITY = {
        "steak": {"styles": {"red"}, "grapes": {"cabernet", "syrah", "malbec", "nebbiolo", "sangiovese", "tempranillo"}},
        "strip": {"styles": {"red"}, "grapes": {"cabernet", "syrah", "nebbiolo", "sangiovese"}},
        "oyster": {"styles": {"white", "sparkling", "champagne"}, "grapes": {"chablis", "muscadet", "sauvignon", "champagne", "chardon"}},
        "oysters": {"styles": {"white", "sparkling", "champagne"}, "grapes": {"chablis", "muscadet", "sauvignon", "champagne"}},
        "branzino": {"styles": {"white", "sparkling"}, "grapes": {"chablis", "sauvignon", "vermentino", "pinot gris"}},
        "seafood": {"styles": {"white", "sparkling", "rose", "rosé"}, "grapes": {"sauvignon", "chablis", "riesling", "vermentino"}},
        "chicken": {"styles": {"white", "red", "rose", "rosé"}, "grapes": {"chardonnay", "pinot", "chenin"}},
        "cream": {"styles": {"white", "red"}, "grapes": {"chardonnay", "pinot", "chenin"}},
        "tomato": {"styles": {"red"}, "grapes": {"sangiovese", "barbera", "nebbiolo"}},
        "pork": {"styles": {"white", "red", "sparkling"}, "grapes": {"pinot", "riesling", "chenin", "nebbiolo"}},
        "cheese": {"styles": {"red", "white", "sparkling"}, "grapes": {"chardonnay", "pinot", "sauvignon", "nebbiolo"}},
        "cod": {"styles": {"white"}, "grapes": {"chardonnay", "chenin", "riesling"}},
        "caviar": {"styles": {"sparkling", "champagne", "white"}, "grapes": {"chardon", "pinot"}},
    }

    @classmethod
    def _lexical_score(cls, query_text: str, metadata: Dict) -> float:
        stop = {
            "a", "an", "the", "for", "and", "with", "from", "around", "about",
            "under", "over", "than", "less", "more", "wine", "wines", "please",
            "something", "looking", "want", "need", "me", "my", "i", "to",
            "drink", "preferences", "between", "any", "price",
        }
        tokens = [
            t for t in re.findall(r"[a-zA-Z]+", query_text.lower())
            if t not in stop and len(t) > 2
        ]
        grapes = str(metadata.get("grapes", "")).lower()
        style = str(metadata.get("wine_style") or metadata.get("wine_type") or "").lower()
        haystack = " ".join([
            str(metadata.get("producer", "")),
            str(metadata.get("label", "")),
            str(metadata.get("wine_name", "")),
            grapes,
            str(metadata.get("region", "")),
            str(metadata.get("major_region", "")),
            str(metadata.get("country", "")),
            style,
            str(metadata.get("text", "")),
        ]).lower()
        if not tokens:
            return 0.05
        hits = sum(1 for token in tokens if token in haystack)
        score = hits / max(len(tokens), 1)
        joined = " ".join(tokens)
        if joined in haystack:
            score += 0.4
        grape_tokens = [t for t in tokens if t not in {"light", "crisp", "bold", "dry", "full", "medium"}]
        if grape_tokens and all(token in grapes or token in haystack for token in grape_tokens[:2]):
            score += 0.35
        q = query_text.lower()
        sparkling_query = any(word in q for word in ("sparkling", "champagne", "bubbly", "prosecco"))
        if not sparkling_query and style in {"sparkling", "champagne"}:
            score -= 0.55
        light_query = any(word in q for word in ("light", "fresh", "summer", "refreshing"))
        bold_query = any(word in q for word in ("bold", "heavy", "tannin", "full"))
        grape_blob = grapes + " " + haystack
        if light_query:
            if any(g in grape_blob for g in cls.LIGHT_GRAPES) or style in {"white", "rose", "rosé", "sparkling"}:
                score += 0.4
            if any(g in grape_blob for g in cls.FULL_GRAPES) and "pinot" not in grape_blob:
                score -= 0.45
        if bold_query:
            if any(g in grape_blob for g in cls.FULL_GRAPES) or style == "red":
                score += 0.4
            if any(g in grape_blob for g in cls.LIGHT_GRAPES) and style != "red":
                score -= 0.2
        if re.search(r"\bred\b", q) and style == "red":
            score += 0.45
        if re.search(r"\bwhite\b", q) and style == "white":
            score += 0.45
        if ("rosé" in q or re.search(r"\brose\b", q)) and style in {"rose", "rosé"}:
            score += 0.45
        if sparkling_query and style in {"sparkling", "champagne"}:
            score += 0.55
        for word, affinity in cls.FOOD_AFFINITY.items():
            if word in q:
                if style in affinity["styles"]:
                    score += 0.35
                if any(g in grape_blob for g in affinity["grapes"]):
                    score += 0.4
                elif style and style not in affinity["styles"]:
                    score -= 0.35
        from data.sommelier_knowledge import sommelier_score
        return sommelier_score(query_text, metadata, base=score)

    def _lexical_search_wines(
        self,
        query_text: str,
        query_filter: Dict,
        top_k: int,
        namespace: Optional[str],
    ) -> List[Tuple[str, float, Dict]]:
        ns = namespace or "maass_wine_list"
        catalog = self._load_namespace_catalog(ns)
        scored = []
        for wine_id, metadata in catalog:
            if not self._metadata_matches_filter(metadata, query_filter):
                continue
            score = self._lexical_score(query_text, metadata)
            if score <= 0:
                continue
            scored.append((wine_id, score, metadata))
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:top_k]
    
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
        if settings.use_openai_embeddings and settings.openai_api_key:
            try:
                query_embedding = self.get_embeddings([query_text])[0]
                results = self.index.query(
                    vector=query_embedding,
                    top_k=top_k,
                    include_metadata=True,
                    namespace=menu_namespace,
                )
                matches = self._parse_query_matches(results)
                if matches:
                    return matches
            except Exception as e:
                logger.debug("Menu vector search skipped: %s", e)

        from restaurants.restaurant_config import get_restaurant_config

        config = get_restaurant_config(restaurant_id)
        dishes = config.load_menu() if config else []
        scored = []
        for i, dish in enumerate(dishes):
            metadata = {
                "dish_id": f"dish_{i}",
                "name": dish.get("name", ""),
                "description": dish.get("description", ""),
                "category": dish.get("category", ""),
            }
            haystack = " ".join(
                str(metadata[k]) for k in ("name", "description", "category")
            ).lower()
            tokens = re.findall(r"[a-zA-Z]+", query_text.lower())
            hits = sum(1 for t in tokens if len(t) > 3 and t in haystack)
            score = hits / max(len(tokens), 1)
            scored.append((metadata["dish_id"], score, metadata))
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:top_k]

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

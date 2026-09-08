"""Wine recommendation engine: list-only search, then a sommelier pick."""
from typing import List, Dict, Optional, Tuple
import logging
import re
import hashlib
import json
import sys
from pathlib import Path

from openai import OpenAI

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.embedding_pipeline import EmbeddingPipeline
from restaurants.restaurant_config import RestaurantConfig
from config import settings
from data.sommelier_knowledge import (
    parse_intent,
    sommelier_score,
    grok_system_prompt,
    approachable_note,
    complementary_picks,
    grape_family,
    named_miss_intro,
)

logger = logging.getLogger(__name__)

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis not available - install with: pip install redis")


class WineCache:
    """Redis with in-memory fallback."""

    def __init__(self):
        self.memory_cache = {}
        self.redis_client = None
        if REDIS_AVAILABLE:
            try:
                import os
                redis_url = os.getenv("REDIS_URL") or settings.redis_url
                if redis_url:
                    self.redis_client = redis.from_url(
                        redis_url, decode_responses=True, socket_connect_timeout=5
                    )
                else:
                    self.redis_client = redis.Redis(
                        host=settings.redis_host,
                        port=settings.redis_port,
                        db=settings.redis_db,
                        password=settings.redis_password,
                        decode_responses=True,
                        socket_connect_timeout=2,
                    )
                self.redis_client.ping()
            except Exception as e:
                logger.warning("Redis not available, using memory cache: %s", e)
                self.redis_client = None

    def get(self, key: str) -> Optional[str]:
        if self.redis_client:
            try:
                return self.redis_client.get(key)
            except Exception:
                pass
        return self.memory_cache.get(key)

    def set(self, key: str, value: str, ttl: int = 2592000):
        if self.redis_client:
            try:
                self.redis_client.setex(key, ttl, value)
                return
            except Exception:
                pass
        self.memory_cache[key] = value


class OptimizedWineRecommender:
    """Search the restaurant list, then let Grok pick two bottles."""

    def __init__(self, config: RestaurantConfig):
        self.config = config
        self.pipeline = EmbeddingPipeline()
        self.cache = WineCache()
        xai_api_key = settings.get_decrypted_xai_key()
        self.grok_client = OpenAI(
            api_key=xai_api_key,
            base_url="https://api.x.ai/v1",
            timeout=45.0,
            max_retries=0,
        )
        self._llm_ok = True

    def _chat_completion(self, **kwargs):
        if not self._llm_ok:
            raise RuntimeError("Grok disabled after previous auth failure")
        model = str(kwargs.get("model") or settings.xai_chat_model)
        if model.startswith("grok-4.6") or model.startswith("grok-4.5"):
            extra = dict(kwargs.get("extra_body") or {})
            extra.setdefault("reasoning_effort", "low")
            kwargs["extra_body"] = extra
        try:
            return self.grok_client.chat.completions.create(**kwargs)
        except Exception as e:
            err = str(e).lower()
            if any(token in err for token in ("incorrect api key", "invalid_api_key", "unauthorized", "401")):
                self._llm_ok = False
                logger.warning("Disabling Grok calls after auth failure")
            raise

    def _cache_key(self, prefix: str, *args) -> str:
        key_str = f"{self.config.restaurant_id}:{prefix}:{':'.join(str(arg) for arg in args)}"
        return hashlib.md5(key_str.encode()).hexdigest()[:16]

    def extract_price_filter(self, user_query: str) -> Optional[Dict]:
        query_lower = user_query.lower()
        between = re.search(
            r"between\s*\$?(\d+)\s*and\s*\$?(\d+)", query_lower
        )
        if between:
            low, high = int(between.group(1)), int(between.group(2))
            return {"price": {"$gte": min(low, high), "$lte": max(low, high)}}

        price_patterns = [
            r"\$?(\d+)\s*[–-]\s*\$?(\d+)",
            r"under\s*\$?(\d+)",
            r"less than\s*\$?(\d+)",
            r"below\s*\$?(\d+)",
            r"around\s*\$?(\d+)",
            r"about\s*\$?(\d+)",
            r"\$?(\d+)\s*or less",
        ]
        for pattern in price_patterns:
            match = re.search(pattern, query_lower)
            if match:
                if len(match.groups()) == 2 and match.group(2):
                    min_price = int(match.group(1))
                    max_price = int(match.group(2))
                    return {"price": {"$gte": min_price, "$lte": max_price}}
                price = int(match.group(1))
                if "around" in query_lower or "about" in query_lower:
                    return {"price": {"$gte": int(price * 0.7), "$lte": int(price * 1.3)}}
                return {"price": {"$lte": price}}

        if any(word in query_lower for word in ("cellar", "splurge", "vertical")):
            return {"price": {"$gte": self.config.cellar_min}}
        if any(word in query_lower for word in ("budget", "affordable", "inexpensive")):
            return {"price": {"$lte": 75}}
        if any(word in query_lower for word in ("premium", "expensive", "luxury", "high-end", "special occasion")):
            return {"price": {"$gte": 100}}
        return None

    def extract_style_filter(self, user_query: str) -> Optional[str]:
        intent = parse_intent(user_query)
        if intent.color == "sparkling":
            return "sparkling"
        if intent.color == "rose":
            return "rose"
        if intent.color == "white":
            return "white"
        if intent.color == "red":
            return "red"
        return None

    def enrich_wine_metadata(self, wine_data: Tuple) -> Dict:
        wine_id, score, metadata = wine_data
        producer = metadata.get("producer", "Unknown")
        wine_name = metadata.get("wine_name") or metadata.get("label", "")
        region = metadata.get("region", "Unknown")
        grapes = metadata.get("grapes", "")
        wine_type = metadata.get("wine_type") or metadata.get("wine_style", "unknown")
        price = metadata.get("price", "")
        if isinstance(price, (int, float)):
            price = str(int(price))
        else:
            price = str(price).strip() if price else ""
        return {
            "wine_id": wine_id,
            "score": score,
            "producer": producer,
            "wine_name": wine_name,
            "region": region,
            "country": metadata.get("country", ""),
            "vintage": metadata.get("vintage", ""),
            "price": price,
            "text": metadata.get("text", ""),
            "grapes": grapes,
            "wine_type": wine_type,
            "price_range": metadata.get("price_range", ""),
            "metadata": metadata,
        }

    def _search(self, query: str, filters: Optional[Dict], top_k: int = 10) -> List[Dict]:
        matches = self.pipeline.search_similar_wines(
            query_text=query,
            top_k=top_k,
            filters=filters,
            namespace=self.config.namespace,
        )
        return [self.enrich_wine_metadata(m) for m in matches]

    def _relax_search(self, query: str, filters: Optional[Dict]) -> Tuple[List[Dict], str]:
        """Widen one constraint rather than returning random bottles."""
        matches = self._search(query, filters)
        if len(matches) >= 2:
            return matches, ""

        relaxed = ""
        widened = dict(filters or {})
        price = dict(widened.get("price") or {})
        floor_only = "$gte" in price and "$lte" not in price
        if price and not floor_only:
            if "$lte" in price:
                price["$lte"] = int(float(price["$lte"]) * 1.4)
            if "$gte" in price:
                price["$gte"] = int(float(price["$gte"]) * 0.7)
            widened["price"] = price
            matches = self._search(query, widened)
            if len(matches) >= 2:
                return matches, "Nothing sat in that exact price band; these are the closest on the list."

        intent = parse_intent(query)
        style_only_dropped = dict(widened)
        if "wine_style" in style_only_dropped and not intent.lock_color:
            style_only_dropped.pop("wine_style")
            matches = self._search(query, style_only_dropped or None)
            if matches:
                return matches, "I loosened the color filter to stay on this list."
            relaxed = "I loosened the color filter to stay on this list."

        if "price" in (filters or {}) and not floor_only:
            no_price = dict(filters or {})
            no_price.pop("price", None)
            # Keep implied color (crisp/clean → white). Never fall back to reds.
            if not intent.lock_color:
                no_price.pop("wine_style", None)
            matches = self._search(query, no_price or None)
            if matches:
                return matches, "Nothing matched that budget; these are the nearest bottles we pour."
        return matches, relaxed

    def _fallback_note(self, wine: Dict) -> str:
        _why, note = approachable_note(wine, "")
        return note

    def _select_and_note(
        self,
        user_query: str,
        candidates: List[Dict],
        menu: List[Dict],
    ) -> Tuple[List[Dict], str]:
        pool = candidates[:8]
        if not pool:
            return [], ""
        if not self._llm_ok or len(pool) == 1:
            return pool[:2], ""

        candidate_text = "\n".join(
            f"{i+1}. {wine.get('vintage', '')} {wine['producer']} {wine.get('wine_name', '')} "
            f"| {wine.get('grapes', '')} | {wine['wine_type']} | {wine['region']} | "
            f"{'$' + wine['price'] if wine.get('price') else 'price on request'}"
            for i, wine in enumerate(pool)
        )
        menu_text = "\n".join(
            f"- {d.get('name')}: {d.get('description', '')} ({d.get('category', '')})"
            for d in menu[:24]
        ) or "(menu not loaded — omit pairing)"

        prompt = (
            f'The guest said: "{user_query}"\n\n'
            "Choose ONLY from these numbered wines. Never invent a bottle, vintage, or price.\n"
            f"{candidate_text}\n\n"
            "Tonight's menu (pair only from this list, or leave dish empty):\n"
            f"{menu_text}\n\n"
            "Pick two complementary bottles that actually match the guest's language. "
            "If they asked for crisp/clean, do not pick oaky California Chardonnay.\n"
            "JSON only, no markdown:\n"
            '{"intro":"one sentence to the guest, everyday words",'
            '"picks":[{"n":1,"why":"one sentence tying this bottle to what they asked",'
            '"note":"two short everyday sentences","dish":"exact menu dish or empty","pair":"one sentence or empty"},'
            '{"n":2,"why":"...","note":"...","dish":"","pair":""}]}'
        )
        try:
            response = self._chat_completion(
                model=settings.xai_chat_model,
                messages=[
                    {
                        "role": "system",
                        "content": grok_system_prompt(self.config.name),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.4,
                max_tokens=520,
            )
            raw = (response.choices[0].message.content or "").strip()
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            payload = json.loads(match.group(0) if match else raw)
            intro = str(payload.get("intro") or "").strip()
            selected = []
            for item in payload.get("picks", [])[:2]:
                idx = int(item.get("n", 0)) - 1
                if 0 <= idx < len(pool):
                    wine = pool[idx]
                    note = str(item.get("note") or "").strip()
                    why = str(item.get("why") or "").strip()
                    if note:
                        wine["_grok_note"] = note
                    if why:
                        wine["_grok_why"] = why
                    dish = str(item.get("dish") or "").strip()
                    pair = str(item.get("pair") or "").strip()
                    if dish:
                        wine["_grok_pair"] = f"{dish} — {pair}".strip(" —") if pair else dish
                    selected.append(wine)
            if selected:
                return selected[:2], intro
        except Exception as e:
            logger.error("Combined Grok pick/note failed: %s", e)
        return pool[:2], ""

    def get_recommendations(
        self,
        user_query: str,
        top_k: int = 10,
        filters: Optional[Dict] = None,
    ) -> List[Dict]:
        wines, _intro, _relaxed = self.recommend(user_query, filters=filters)
        return wines

    def recommend(
        self,
        user_query: str,
        filters: Optional[Dict] = None,
    ) -> Tuple[List[Dict], str, str]:
        logger.info("Getting recommendations for: %s", user_query)
        price_filter = self.extract_price_filter(user_query)
        if price_filter:
            filters = dict(filters or {})
            filters.update(price_filter)
        style_filter = self.extract_style_filter(user_query)
        if style_filter:
            filters = dict(filters or {})
            filters["wine_style"] = style_filter

        enriched, relaxed = self._relax_search(user_query, filters)
        for wine in enriched:
            wine["score"] = sommelier_score(
                user_query, wine, base=float(wine.get("score") or 0)
            )
        enriched.sort(key=lambda w: w["score"], reverse=True)
        enriched = [w for w in enriched if w["score"] > -1]
        if not enriched:
            miss = named_miss_intro(user_query) or (
                "Nothing on this list matched what you asked for. I won't substitute a random bottle."
            )
            return [], miss, miss

        diverse = []
        fam_n = {}
        for wine in enriched:
            fam = grape_family(wine)
            if fam_n.get(fam, 0) >= 2:
                continue
            diverse.append(wine)
            fam_n[fam] = fam_n.get(fam, 0) + 1
            if len(diverse) >= 8:
                break
        menu = self.config.load_menu() if self.config.enable_menu_pairing else []
        selected, intro = self._select_and_note(user_query, diverse or enriched, menu)
        if len(selected) >= 2 and grape_family(selected[0]) == grape_family(selected[1]):
            selected = complementary_picks(diverse or enriched, query=user_query) or selected
        menu_names = [d.get("name", "").lower() for d in menu if d.get("name")]

        for wine in selected:
            tasting_note = (wine.get("metadata") or {}).get("tasting_note", "")
            invalid = (
                not tasting_note
                or len(tasting_note) < 20
                or "No tasting note" in tasting_note
                or "not provided" in tasting_note
                or "not available" in tasting_note.lower()
            )
            cache_key = self._cache_key("tasting", wine["wine_id"])
            if invalid:
                cached = self.cache.get(cache_key)
                tasting_note = cached if cached and len(cached) > 20 else (
                    wine.get("_grok_note") or self._fallback_note(wine)
                )
                if tasting_note and len(tasting_note) > 40:
                    self.cache.set(cache_key, tasting_note)
            wine["tasting_note"] = tasting_note
            wine["why"] = wine.get("_grok_why") or ""
            pairing = wine.get("_grok_pair") or ""
            if pairing and not any(name and name in pairing.lower() for name in menu_names):
                pairing = ""
            wine["food_pairing"] = pairing or None
            wine.pop("metadata", None)

        logger.info("Selected %s wines", len(selected))
        return selected[:2], intro, relaxed

    def get_full_recommendation(
        self,
        user_query: str,
        filters: Optional[Dict] = None,
    ) -> List[Dict]:
        wines, _, _ = self.recommend(user_query, filters=filters)
        return wines

import json
import time
from typing import Any, Dict, List, Optional

from structlog import get_logger

from app.config import settings

logger = get_logger(__name__)

try:
    import redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis not available, using in-memory cache")


class CacheManager:
    """Advanced caching manager with Redis and fallback to in-memory."""

    def __init__(self):
        self.redis_client = None
        self.use_redis = False

        if REDIS_AVAILABLE and settings.redis_url:
            try:
                self.redis_client = redis.from_url(settings.redis_url)
                # Test connection
                self.redis_client.ping()
                self.use_redis = True
                logger.info("Using Redis for caching")
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}, using in-memory cache")

        # In-memory fallback
        self._memory_cache: Dict[str, Dict[str, Any]] = {}

    def _get_cache_key(self, prefix: str, key: str) -> str:
        """Generate cache key with prefix."""
        return f"schema_registry:{prefix}:{key}"

    def get(self, prefix: str, key: str) -> Optional[Any]:
        """Get value from cache."""
        cache_key = self._get_cache_key(prefix, key)

        if self.use_redis:
            try:
                value = self.redis_client.get(cache_key)
                if value:
                    return json.loads(value)
            except Exception as e:
                logger.error(f"Redis get error: {e}")

        # Fallback to memory cache
        if cache_key in self._memory_cache:
            item = self._memory_cache[cache_key]
            if time.time() < item["expires_at"]:
                return item["value"]
            else:
                del self._memory_cache[cache_key]

        return None

    def set(self, prefix: str, key: str, value: Any, ttl: int = None) -> bool:
        """Set value in cache with TTL."""
        cache_key = self._get_cache_key(prefix, key)
        ttl = ttl or settings.cache_ttl_seconds

        if self.use_redis:
            try:
                self.redis_client.setex(cache_key, ttl, json.dumps(value))
                return True
            except Exception as e:
                logger.error(f"Redis set error: {e}")

        # Fallback to memory cache
        self._memory_cache[cache_key] = {
            "value": value,
            "expires_at": time.time() + ttl,
        }
        return True

    def delete(self, prefix: str, key: str) -> bool:
        """Delete value from cache."""
        cache_key = self._get_cache_key(prefix, key)

        if self.use_redis:
            try:
                self.redis_client.delete(cache_key)
                return True
            except Exception as e:
                logger.error(f"Redis delete error: {e}")

        # Fallback to memory cache
        if cache_key in self._memory_cache:
            del self._memory_cache[cache_key]
            return True

        return False

    def clear_prefix(self, prefix: str) -> bool:
        """Clear all keys with a specific prefix."""
        if self.use_redis:
            try:
                pattern = self._get_cache_key(prefix, "*")
                keys = self.redis_client.keys(pattern)
                if keys:
                    self.redis_client.delete(*keys)
                return True
            except Exception as e:
                logger.error(f"Redis clear prefix error: {e}")

        # Fallback to memory cache
        pattern = self._get_cache_key(prefix, "")
        keys_to_delete = [
            key for key in self._memory_cache.keys() if key.startswith(pattern)
        ]
        for key in keys_to_delete:
            del self._memory_cache[key]

        return True

    def get_many(self, prefix: str, keys: List[str]) -> Dict[str, Any]:
        """Get multiple values from cache."""
        result = {}

        if self.use_redis:
            try:
                cache_keys = [self._get_cache_key(prefix, key) for key in keys]
                values = self.redis_client.mget(cache_keys)

                for key, value in zip(keys, values):
                    if value:
                        result[key] = json.loads(value)
            except Exception as e:
                logger.error(f"Redis get_many error: {e}")

        # Fallback to memory cache
        for key in keys:
            value = self.get(prefix, key)
            if value is not None:
                result[key] = value

        return result

    def set_many(self, prefix: str, data: Dict[str, Any], ttl: int = None) -> bool:
        """Set multiple values in cache."""
        ttl = ttl or settings.cache_ttl_seconds

        if self.use_redis:
            try:
                pipeline = self.redis_client.pipeline()
                for key, value in data.items():
                    cache_key = self._get_cache_key(prefix, key)
                    pipeline.setex(cache_key, ttl, json.dumps(value))
                pipeline.execute()
                return True
            except Exception as e:
                logger.error(f"Redis set_many error: {e}")

        # Fallback to memory cache
        for key, value in data.items():
            self.set(prefix, key, value, ttl)

        return True

    def increment(self, prefix: str, key: str, amount: int = 1) -> Optional[int]:
        """Increment a counter in cache."""
        cache_key = self._get_cache_key(prefix, key)

        if self.use_redis:
            try:
                return self.redis_client.incr(cache_key, amount)
            except Exception as e:
                logger.error(f"Redis increment error: {e}")

        # Fallback to memory cache
        current = self.get(prefix, key) or 0
        new_value = current + amount
        self.set(prefix, key, new_value, 3600)  # 1 hour TTL for counters
        return new_value

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        stats = {
            "use_redis": self.use_redis,
            "memory_cache_size": len(self._memory_cache),
        }

        if self.use_redis:
            try:
                info = self.redis_client.info()
                stats.update(
                    {
                        "redis_connected_clients": info.get("connected_clients", 0),
                        "redis_used_memory": info.get("used_memory_human", "0B"),
                        "redis_keyspace_hits": info.get("keyspace_hits", 0),
                        "redis_keyspace_misses": info.get("keyspace_misses", 0),
                    }
                )
            except Exception as e:
                logger.error(f"Redis info error: {e}")

        return stats


# Global cache instance
cache = CacheManager()


class SchemaCache:
    """Schema-specific caching utilities."""

    @staticmethod
    def get_schema(
        schema_id: str, version: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get schema from cache."""
        key = f"{schema_id}:{version or 'latest'}"
        return cache.get("schema", key)

    @staticmethod
    def set_schema(
        schema_id: str, version: Optional[str], schema_data: Dict[str, Any]
    ) -> bool:
        """Set schema in cache."""
        key = f"{schema_id}:{version or 'latest'}"
        return cache.set("schema", key, schema_data)

    @staticmethod
    def clear_schema(schema_id: str) -> bool:
        """Clear all cached versions of a schema."""
        return cache.clear_prefix(f"schema:{schema_id}")

    @staticmethod
    def get_schema_list() -> Optional[List[str]]:
        """Get cached schema list."""
        return cache.get("meta", "schema_list")

    @staticmethod
    def set_schema_list(schema_list: List[str]) -> bool:
        """Set cached schema list."""
        return cache.set("meta", "schema_list", schema_list, ttl=300)  # 5 minutes

    @staticmethod
    def get_version_list(schema_id: str) -> Optional[List[str]]:
        """Get cached version list for a schema."""
        return cache.get("versions", schema_id)

    @staticmethod
    def set_version_list(schema_id: str, versions: List[str]) -> bool:
        """Set cached version list for a schema."""
        return cache.set("versions", schema_id, versions, ttl=300)  # 5 minutes


class MetricsCache:
    """Metrics-specific caching utilities."""

    @staticmethod
    def increment_schema_fetch(schema_id: str, version: str = "latest") -> int:
        """Increment schema fetch counter."""
        key = f"fetch:{schema_id}:{version}"
        return cache.increment("metrics", key) or 0

    @staticmethod
    def increment_schema_create(schema_id: str) -> int:
        """Increment schema create counter."""
        key = f"create:{schema_id}"
        return cache.increment("metrics", key) or 0

    @staticmethod
    def increment_compatibility_check(schema_id: str) -> int:
        """Increment compatibility check counter."""
        key = f"compat:{schema_id}"
        return cache.increment("metrics", key) or 0

    @staticmethod
    def get_daily_stats() -> Dict[str, Any]:
        """Get daily statistics."""
        today = time.strftime("%Y-%m-%d")
        return cache.get("stats", f"daily:{today}") or {}

    @staticmethod
    def set_daily_stats(stats: Dict[str, Any]) -> bool:
        """Set daily statistics."""
        today = time.strftime("%Y-%m-%d")
        return cache.set("stats", f"daily:{today}", stats, ttl=86400)  # 24 hours

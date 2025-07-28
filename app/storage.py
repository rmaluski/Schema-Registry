import json
import time
from typing import Any, Dict, List, Optional

import etcd3
from structlog import get_logger

from app.config import settings
from app.models import SchemaDocument

logger = get_logger(__name__)


class EtcdStorage:
    """Etcd-based storage backend for schema documents."""

    def __init__(self):
        self.client = None
        self._connect()
        self._cache: Dict[str, Any] = {}
        self._cache_ttl = settings.cache_ttl_seconds
        # In-memory storage fallback when etcd is not available
        self._memory_storage: Dict[str, Any] = {}

    def _connect(self):
        """Establish connection to Etcd."""
        try:
            kwargs = {
                "host": settings.etcd_host,
                "port": settings.etcd_port,
            }

            if settings.etcd_username and settings.etcd_password:
                kwargs["username"] = settings.etcd_username
                kwargs["password"] = settings.etcd_password

            if settings.etcd_ca_cert:
                kwargs["ca_cert"] = settings.etcd_ca_cert

            if settings.etcd_cert_cert and settings.etcd_cert_key:
                kwargs["cert_cert"] = settings.etcd_cert_cert
                kwargs["cert_key"] = settings.etcd_cert_key

            self.client = etcd3.client(**kwargs)
            logger.info(
                "Connected to Etcd", host=settings.etcd_host, port=settings.etcd_port
            )

        except Exception as e:
            logger.warning(
                "Failed to connect to Etcd, using in-memory storage", error=str(e)
            )
            self.client = None

    def _get_key(self, schema_id: str, version: Optional[str] = None) -> str:
        """Generate Etcd key for schema storage."""
        if version:
            return f"/schemas/{schema_id}/{version}"
        return f"/schemas/{schema_id}/latest"

    def _get_cache_key(self, schema_id: str, version: Optional[str] = None) -> str:
        """Generate cache key."""
        return f"{schema_id}:{version or 'latest'}"

    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached item is still valid."""
        if cache_key not in self._cache:
            return False

        cached_time = self._cache[cache_key].get("timestamp", 0)
        return time.time() - cached_time < self._cache_ttl

    def _set_cache(self, cache_key: str, data: Any):
        """Set cache with timestamp."""
        self._cache[cache_key] = {"data": data, "timestamp": time.time()}

    def _get_cache(self, cache_key: str) -> Optional[Any]:
        """Get cached data if valid."""
        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]["data"]
        return None

    def _clear_cache(self, schema_id: str):
        """Clear all cache entries for a schema."""
        keys_to_remove = [
            k for k in self._cache.keys() if k.startswith(f"{schema_id}:")
        ]
        for key in keys_to_remove:
            del self._cache[key]

    async def store_schema(self, schema: SchemaDocument) -> bool:
        """Store a new schema version."""
        try:
            schema_data = schema.dict()
            schema_data["created_at"] = time.time()
            schema_data["updated_at"] = time.time()

            if self.client is not None:
                # Store the specific version
                version_key = self._get_key(schema.id, schema.version)
                self.client.put(version_key, json.dumps(schema_data))

                # Update latest pointer
                latest_key = self._get_key(schema.id)
                self.client.put(latest_key, json.dumps(schema_data))
            else:
                # Use in-memory storage
                version_key = self._get_key(schema.id, schema.version)
                latest_key = self._get_key(schema.id)
                self._memory_storage[version_key] = schema_data
                self._memory_storage[latest_key] = schema_data

            # Clear cache for this schema
            self._clear_cache(schema.id)

            logger.info(
                "Schema stored successfully",
                schema_id=schema.id,
                version=schema.version,
            )
            return True

        except Exception as e:
            logger.error(
                "Failed to store schema",
                schema_id=schema.id,
                version=schema.version,
                error=str(e),
            )
            return False

    async def get_schema(
        self, schema_id: str, version: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Retrieve a schema by ID and optional version."""
        try:
            cache_key = self._get_cache_key(schema_id, version)
            cached = self._get_cache(cache_key)
            if cached:
                return cached

            key = self._get_key(schema_id, version)

            if self.client is not None:
                value, _ = self.client.get(key)
                if value is None:
                    logger.warning(
                        "Schema not found", schema_id=schema_id, version=version
                    )
                    return None
                schema_data = json.loads(value.decode("utf-8"))
            else:
                # Use in-memory storage
                schema_data = self._memory_storage.get(key)
                if schema_data is None:
                    logger.warning(
                        "Schema not found", schema_id=schema_id, version=version
                    )
                    return None

            self._set_cache(cache_key, schema_data)
            return schema_data

        except Exception as e:
            logger.error(
                "Failed to retrieve schema",
                schema_id=schema_id,
                version=version,
                error=str(e),
            )
            return None

    async def list_schemas(self) -> List[str]:
        """List all schema IDs."""
        try:
            schemas = set()
            prefix = "/schemas/"

            if self.client is not None:
                for value, _ in self.client.get_prefix(prefix):
                    # Extract schema ID from key
                    key = value.decode("utf-8")
                    if key.endswith("/latest"):
                        schema_id = key[len(prefix) : -len("/latest")]
                        schemas.add(schema_id)
            else:
                # Use in-memory storage
                for key in self._memory_storage.keys():
                    if key.startswith(prefix) and key.endswith("/latest"):
                        schema_id = key[len(prefix) : -len("/latest")]
                        schemas.add(schema_id)

            return list(schemas)

        except Exception as e:
            logger.error("Failed to list schemas", error=str(e))
            return []

    async def list_versions(self, schema_id: str) -> List[str]:
        """List all versions for a schema."""
        try:
            versions = []
            prefix = f"/schemas/{schema_id}/"

            if self.client is not None:
                for value, _ in self.client.get_prefix(prefix):
                    key = value.decode("utf-8")
                    if not key.endswith("/latest"):
                        version = key[len(prefix) :]
                        versions.append(version)
            else:
                # Use in-memory storage
                for key in self._memory_storage.keys():
                    if key.startswith(prefix) and not key.endswith("/latest"):
                        version = key[len(prefix) :]
                        versions.append(version)

            return sorted(versions, key=lambda v: [int(x) for x in v.split(".")])

        except Exception as e:
            logger.error("Failed to list versions", schema_id=schema_id, error=str(e))
            return []

    async def delete_schema(
        self, schema_id: str, version: Optional[str] = None
    ) -> bool:
        """Delete a schema version or entire schema."""
        try:
            if self.client is not None:
                if version:
                    # Delete specific version
                    key = self._get_key(schema_id, version)
                    self.client.delete(key)
                    self._clear_cache(schema_id)
                    logger.info(
                        "Schema version deleted", schema_id=schema_id, version=version
                    )
                else:
                    # Delete all versions and latest pointer
                    prefix = f"/schemas/{schema_id}/"
                    for value, _ in self.client.get_prefix(prefix):
                        key = value.decode("utf-8")
                        self.client.delete(key)
                    self._clear_cache(schema_id)
                    logger.info("Schema deleted", schema_id=schema_id)
            else:
                # Use in-memory storage
                if version:
                    # Delete specific version
                    key = self._get_key(schema_id, version)
                    if key in self._memory_storage:
                        del self._memory_storage[key]
                    self._clear_cache(schema_id)
                    logger.info(
                        "Schema version deleted", schema_id=schema_id, version=version
                    )
                else:
                    # Delete all versions and latest pointer
                    prefix = f"/schemas/{schema_id}/"
                    keys_to_delete = [
                        k for k in self._memory_storage.keys() if k.startswith(prefix)
                    ]
                    for key in keys_to_delete:
                        del self._memory_storage[key]
                    self._clear_cache(schema_id)
                    logger.info("Schema deleted", schema_id=schema_id)

            return True

        except Exception as e:
            logger.error(
                "Failed to delete schema",
                schema_id=schema_id,
                version=version,
                error=str(e),
            )
            return False

    async def health_check(self) -> bool:
        """Check if Etcd connection is healthy."""
        try:
            if self.client is not None:
                # Try to get a simple key to test connection
                self.client.get("/health")
                return True
            else:
                # In-memory storage is always healthy
                return True
        except Exception as e:
            logger.error("Etcd health check failed", error=str(e))
            return False


# Global storage instance
storage = EtcdStorage()

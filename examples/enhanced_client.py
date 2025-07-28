#!/usr/bin/env python3
"""
Enhanced Schema Registry Client Example

Demonstrates all the new features:
- GraphQL queries
- WebSocket real-time updates
- Advanced caching
- Authentication
- Rate limiting
"""
import asyncio
import json
import time
import websockets
import httpx
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class SchemaRegistryConfig:
    """Configuration for Schema Registry client."""
    base_url: str = "http://localhost:8000"
    ws_url: str = "ws://localhost:8000"
    auth_token: Optional[str] = None
    timeout: int = 30


class EnhancedSchemaRegistryClient:
    """Enhanced client with all new features."""
    
    def __init__(self, config: SchemaRegistryConfig):
        self.config = config
        self.client = httpx.AsyncClient(
            timeout=config.timeout,
            headers={"Authorization": f"Bearer {config.auth_token}"} if config.auth_token else {}
        )
        self.ws_connections = {}
    
    async def close(self):
        """Close all connections."""
        await self.client.aclose()
        for ws in self.ws_connections.values():
            await ws.close()
    
    # REST API Methods
    async def get_schema(self, schema_id: str, version: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get schema via REST API."""
        try:
            url = f"{self.config.base_url}/schema/{schema_id}"
            if version:
                url += f"?version={version}"
            
            response = await self.client.get(url)
            response.raise_for_status()
            return response.json()["schema"]
        except Exception as e:
            logger.error(f"Error getting schema {schema_id}: {e}")
            return None
    
    async def create_schema(self, schema_id: str, schema_data: Dict[str, Any]) -> bool:
        """Create schema via REST API."""
        try:
            url = f"{self.config.base_url}/schema/{schema_id}"
            response = await self.client.post(url, json={"schema": schema_data})
            response.raise_for_status()
            logger.info(f"Created schema {schema_id}")
            return True
        except Exception as e:
            logger.error(f"Error creating schema {schema_id}: {e}")
            return False
    
    async def check_compatibility(self, schema_id: str, data: Dict[str, Any]) -> bool:
        """Check data compatibility via REST API."""
        try:
            url = f"{self.config.base_url}/schema/{schema_id}/compat"
            response = await self.client.post(url, json={"data": data})
            response.raise_for_status()
            result = response.json()
            return result["compatible"]
        except Exception as e:
            logger.error(f"Error checking compatibility: {e}")
            return False
    
    # GraphQL Methods
    async def graphql_query(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute GraphQL query."""
        try:
            url = f"{self.config.base_url}/graphql"
            payload = {"query": query}
            if variables:
                payload["variables"] = variables
            
            response = await self.client.post(url, json=payload)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"GraphQL query error: {e}")
            return {"data": None, "errors": [str(e)]}
    
    async def search_schemas(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search schemas using GraphQL."""
        graphql_query = """
        query SearchSchemas($query: String!, $limit: Int) {
            searchSchemas(query: $query, limit: $limit) {
                id
                version
                title
                field_count
                has_arrow_schema
            }
        }
        """
        
        result = await self.graphql_query(graphql_query, {
            "query": query,
            "limit": limit
        })
        
        return result.get("data", {}).get("searchSchemas", [])
    
    async def get_schema_versions(self, schema_id: str) -> List[Dict[str, Any]]:
        """Get all versions of a schema using GraphQL."""
        graphql_query = """
        query GetSchemaVersions($id: String!) {
            schemaVersions(id: $id) {
                version
                is_latest
                schema {
                    id
                    title
                    field_count
                }
            }
        }
        """
        
        result = await self.graphql_query(graphql_query, {"id": schema_id})
        return result.get("data", {}).get("schemaVersions", [])
    
    async def get_compatible_schemas(self, schema_id: str, version: str) -> List[Dict[str, Any]]:
        """Find schemas compatible with given schema version."""
        graphql_query = """
        query GetCompatibleSchemas($schema_id: String!, $version: String!) {
            compatibleSchemas(schema_id: $schema_id, version: $version) {
                id
                version
                title
                field_count
            }
        }
        """
        
        result = await self.graphql_query(graphql_query, {
            "schema_id": schema_id,
            "version": version
        })
        
        return result.get("data", {}).get("compatibleSchemas", [])
    
    # WebSocket Methods
    async def connect_websocket(self, channel: str) -> bool:
        """Connect to WebSocket channel."""
        try:
            ws_url = f"{self.config.ws_url}/ws/{channel}"
            websocket = await websockets.connect(ws_url)
            self.ws_connections[channel] = websocket
            
            # Send authentication if available
            if self.config.auth_token:
                auth_message = {
                    "type": "auth",
                    "token": self.config.auth_token
                }
                await websocket.send(json.dumps(auth_message))
            
            logger.info(f"Connected to WebSocket channel: {channel}")
            return True
        except Exception as e:
            logger.error(f"WebSocket connection error: {e}")
            return False
    
    async def listen_schema_updates(self, callback=None):
        """Listen for schema updates via WebSocket."""
        if "schema-updates" not in self.ws_connections:
            await self.connect_websocket("schema-updates")
        
        websocket = self.ws_connections["schema-updates"]
        
        try:
            async for message in websocket:
                data = json.loads(message)
                logger.info(f"Schema update received: {data}")
                
                if callback:
                    await callback(data)
        except Exception as e:
            logger.error(f"WebSocket listen error: {e}")
    
    async def listen_compatibility_alerts(self, callback=None):
        """Listen for compatibility alerts via WebSocket."""
        if "compatibility-alerts" not in self.ws_connections:
            await self.connect_websocket("compatibility-alerts")
        
        websocket = self.ws_connections["compatibility-alerts"]
        
        try:
            async for message in websocket:
                data = json.loads(message)
                logger.info(f"Compatibility alert received: {data}")
                
                if callback:
                    await callback(data)
        except Exception as e:
            logger.error(f"WebSocket listen error: {e}")
    
    # Cache Management
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        try:
            response = await self.client.get(f"{self.config.base_url}/cache/stats")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {}
    
    async def clear_cache(self) -> bool:
        """Clear all caches (requires admin privileges)."""
        try:
            response = await self.client.post(f"{self.config.base_url}/cache/clear")
            response.raise_for_status()
            logger.info("Cache cleared successfully")
            return True
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return False
    
    async def get_websocket_stats(self) -> Dict[str, Any]:
        """Get WebSocket connection statistics."""
        try:
            response = await self.client.get(f"{self.config.base_url}/ws/stats")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error getting WebSocket stats: {e}")
            return {}


# Example usage and demonstration
async def schema_update_callback(data: Dict[str, Any]):
    """Callback for schema updates."""
    logger.info(f"Schema update: {data['schema_id']} v{data['version']} - {data['action']}")


async def compatibility_alert_callback(data: Dict[str, Any]):
    """Callback for compatibility alerts."""
    logger.warning(f"Compatibility alert: {data['schema_id']} {data['old_version']} -> {data['new_version']}")
    if data.get('breaking_changes'):
        logger.error(f"Breaking changes: {data['breaking_changes']}")


async def main():
    """Main demonstration function."""
    config = SchemaRegistryConfig(
        base_url="http://localhost:8000",
        ws_url="ws://localhost:8000"
    )
    
    client = EnhancedSchemaRegistryClient(config)
    
    try:
        # 1. Basic REST API operations
        logger.info("=== REST API Operations ===")
        
        # Get a schema
        schema = await client.get_schema("ticks_v1")
        if schema:
            logger.info(f"Retrieved schema: {schema['title']}")
        
        # Check compatibility
        test_data = {
            "ts": "2023-01-01T10:00:00Z",
            "symbol": "AAPL",
            "price": 150.50,
            "size": 100
        }
        
        is_compatible = await client.check_compatibility("ticks_v1", test_data)
        logger.info(f"Data compatibility: {is_compatible}")
        
        # 2. GraphQL operations
        logger.info("\n=== GraphQL Operations ===")
        
        # Search schemas
        search_results = await client.search_schemas("ticks", limit=5)
        logger.info(f"Search results: {len(search_results)} schemas found")
        
        # Get schema versions
        versions = await client.get_schema_versions("ticks_v1")
        logger.info(f"Schema versions: {len(versions)} versions found")
        
        # Get compatible schemas
        compatible = await client.get_compatible_schemas("ticks_v1", "1.0.0")
        logger.info(f"Compatible schemas: {len(compatible)} found")
        
        # 3. WebSocket operations
        logger.info("\n=== WebSocket Operations ===")
        
        # Connect to WebSocket channels
        await client.connect_websocket("schema-updates")
        await client.connect_websocket("compatibility-alerts")
        
        # Start listening in background
        schema_task = asyncio.create_task(
            client.listen_schema_updates(schema_update_callback)
        )
        alert_task = asyncio.create_task(
            client.listen_compatibility_alerts(compatibility_alert_callback)
        )
        
        # 4. Cache management
        logger.info("\n=== Cache Management ===")
        
        cache_stats = await client.get_cache_stats()
        logger.info(f"Cache stats: {cache_stats}")
        
        ws_stats = await client.get_websocket_stats()
        logger.info(f"WebSocket stats: {ws_stats}")
        
        # 5. Wait for some WebSocket messages
        logger.info("\nWaiting for WebSocket messages (30 seconds)...")
        await asyncio.sleep(30)
        
        # Cancel WebSocket tasks
        schema_task.cancel()
        alert_task.cancel()
        
    except Exception as e:
        logger.error(f"Error in main: {e}")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main()) 
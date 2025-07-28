#!/usr/bin/env python3
"""
Enhanced Dataset Cleaner Integration with Schema Registry

This demonstrates how the Dataset Cleaner would integrate with the enhanced
Schema Registry features including caching, WebSocket notifications, and GraphQL.
"""
import asyncio
import json
import time
import csv
from typing import Dict, Any, Optional, List, Set
from dataclasses import dataclass
from pathlib import Path
import logging
import httpx
import websockets
from app.cache import SchemaCache, MetricsCache
from app.websocket import websocket_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ProcessingStats:
    """Statistics for data processing."""
    total_rows: int = 0
    valid_rows: int = 0
    invalid_rows: int = 0
    quarantined_rows: int = 0
    processing_time: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0


class EnhancedDatasetCleaner:
    """Enhanced Dataset Cleaner with Schema Registry integration."""
    
    def __init__(self, registry_url: str = "http://localhost:8000", ws_url: str = "ws://localhost:8000"):
        self.registry_url = registry_url.rstrip('/')
        self.ws_url = ws_url.rstrip('/')
        self.client = httpx.AsyncClient(timeout=30.0)
        self.quarantine_dir = Path("quarantine")
        self.quarantine_dir.mkdir(exist_ok=True)
        
        # Processing statistics
        self.stats = ProcessingStats()
        
        # Schema cache and subscriptions
        self.schema_cache = {}
        self.subscribed_schemas: Set[str] = set()
        self.websocket_connections = {}
        
        # Real-time schema update handling
        self.schema_update_queue = asyncio.Queue()
        self.processing_tasks = set()
    
    async def initialize(self):
        """Initialize the Dataset Cleaner with Schema Registry."""
        logger.info("Initializing Enhanced Dataset Cleaner...")
        
        # Connect to WebSocket for real-time updates
        await self._connect_websockets()
        
        # Start background tasks
        asyncio.create_task(self._process_schema_updates())
        asyncio.create_task(self._monitor_schema_changes())
        
        logger.info("Dataset Cleaner initialized successfully")
    
    async def _connect_websockets(self):
        """Connect to Schema Registry WebSocket channels."""
        try:
            # Connect to schema updates
            schema_ws = await websockets.connect(f"{self.ws_url}/ws/schema-updates")
            self.websocket_connections["schema-updates"] = schema_ws
            
            # Connect to compatibility alerts
            compat_ws = await websockets.connect(f"{self.ws_url}/ws/compatibility-alerts")
            self.websocket_connections["compatibility-alerts"] = compat_ws
            
            # Start listening for messages
            asyncio.create_task(self._listen_schema_updates(schema_ws))
            asyncio.create_task(self._listen_compatibility_alerts(compat_ws))
            
            logger.info("Connected to Schema Registry WebSocket channels")
        except Exception as e:
            logger.error(f"Failed to connect to WebSocket channels: {e}")
    
    async def _listen_schema_updates(self, websocket):
        """Listen for schema updates from WebSocket."""
        try:
            async for message in websocket:
                data = json.loads(message)
                await self.schema_update_queue.put(data)
        except Exception as e:
            logger.error(f"WebSocket schema updates error: {e}")
    
    async def _listen_compatibility_alerts(self, websocket):
        """Listen for compatibility alerts from WebSocket."""
        try:
            async for message in websocket:
                data = json.loads(message)
                logger.warning(f"Compatibility alert: {data}")
                
                # Handle breaking changes
                if data.get('breaking_changes'):
                    await self._handle_breaking_changes(data)
        except Exception as e:
            logger.error(f"WebSocket compatibility alerts error: {e}")
    
    async def _handle_breaking_changes(self, alert_data: Dict[str, Any]):
        """Handle breaking schema changes."""
        schema_id = alert_data['schema_id']
        old_version = alert_data['old_version']
        new_version = alert_data['new_version']
        breaking_changes = alert_data['breaking_changes']
        
        logger.error(f"Breaking changes detected for {schema_id}: {old_version} -> {new_version}")
        logger.error(f"Breaking changes: {breaking_changes}")
        
        # Clear cache for this schema
        SchemaCache.clear_schema(schema_id)
        
        # Notify processing tasks
        for task in self.processing_tasks:
            if not task.done():
                task.cancel()
        
        # Update subscribed schemas
        if schema_id in self.subscribed_schemas:
            await self._refresh_schema(schema_id)
    
    async def _process_schema_updates(self):
        """Process schema updates from the queue."""
        while True:
            try:
                update = await self.schema_update_queue.get()
                schema_id = update['schema_id']
                action = update['action']
                
                logger.info(f"Processing schema update: {schema_id} - {action}")
                
                if action in ['created', 'updated']:
                    # Clear cache and refresh schema
                    SchemaCache.clear_schema(schema_id)
                    await self._refresh_schema(schema_id)
                elif action == 'deleted':
                    # Remove from cache
                    SchemaCache.clear_schema(schema_id)
                    if schema_id in self.schema_cache:
                        del self.schema_cache[schema_id]
                
                self.schema_update_queue.task_done()
            except Exception as e:
                logger.error(f"Error processing schema update: {e}")
    
    async def _monitor_schema_changes(self):
        """Monitor for schema changes and update processing."""
        while True:
            try:
                # Check for schema updates every 30 seconds
                await asyncio.sleep(30)
                
                # Refresh all subscribed schemas
                for schema_id in self.subscribed_schemas:
                    await self._refresh_schema(schema_id)
                    
            except Exception as e:
                logger.error(f"Error monitoring schema changes: {e}")
    
    async def _refresh_schema(self, schema_id: str):
        """Refresh schema from registry."""
        try:
            # Try cache first
            cached_schema = SchemaCache.get_schema(schema_id)
            if cached_schema:
                self.schema_cache[schema_id] = cached_schema
                self.stats.cache_hits += 1
                return
            
            # Fetch from registry
            response = await self.client.get(f"{self.registry_url}/schema/{schema_id}")
            if response.status_code == 200:
                schema_data = response.json()['schema']
                self.schema_cache[schema_id] = schema_data
                SchemaCache.set_schema(schema_id, None, schema_data)
                self.stats.cache_misses += 1
                logger.info(f"Refreshed schema: {schema_id}")
            else:
                logger.error(f"Failed to refresh schema {schema_id}: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error refreshing schema {schema_id}: {e}")
    
    async def load_raw_data(self, file_path: str, schema_id: str, version: Optional[str] = None) -> bool:
        """Load and process raw data with enhanced schema validation."""
        start_time = time.time()
        
        try:
            # Subscribe to schema updates
            self.subscribed_schemas.add(schema_id)
            
            # Get schema (with caching)
            schema_data = await self._get_schema(schema_id, version)
            if not schema_data:
                logger.error(f"Schema {schema_id} not found")
                return False
            
            # Parse schema
            properties = schema_data.get('properties', {})
            required_fields = set(schema_data.get('required', []))
            additional_properties = schema_data.get('additionalProperties', False)
            
            # Process file
            valid_rows = []
            invalid_rows = []
            
            with open(file_path, 'r') as f:
                reader = csv.DictReader(f)
                
                for line_num, row in enumerate(reader, 1):
                    # Validate row
                    validation_result = await self._validate_row(
                        row, schema_id, required_fields, properties, additional_properties
                    )
                    
                    if validation_result['valid']:
                        valid_rows.append(row)
                        self.stats.valid_rows += 1
                    else:
                        invalid_rows.append(row)
                        self.stats.invalid_rows += 1
                        
                        # Quarantine invalid row
                        await self._handle_invalid_row(
                            row, line_num, file_path, schema_id, validation_result['errors']
                        )
                    
                    self.stats.total_rows += 1
            
            # Process valid rows
            if valid_rows:
                await self._process_valid_rows(valid_rows, schema_id)
            
            # Update processing statistics
            self.stats.processing_time = time.time() - start_time
            
            # Log statistics
            logger.info(f"Processing complete for {file_path}")
            logger.info(f"Total: {self.stats.total_rows}, Valid: {self.stats.valid_rows}, "
                       f"Invalid: {self.stats.invalid_rows}, Quarantined: {self.stats.quarantined_rows}")
            logger.info(f"Cache hits: {self.stats.cache_hits}, misses: {self.stats.cache_misses}")
            logger.info(f"Processing time: {self.stats.processing_time:.2f}s")
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")
            return False
    
    async def _get_schema(self, schema_id: str, version: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get schema with caching."""
        # Try cache first
        cached_schema = SchemaCache.get_schema(schema_id, version)
        if cached_schema:
            self.stats.cache_hits += 1
            return cached_schema
        
        # Fetch from registry
        try:
            url = f"{self.registry_url}/schema/{schema_id}"
            if version:
                url += f"?version={version}"
            
            response = await self.client.get(url)
            if response.status_code == 200:
                schema_data = response.json()['schema']
                SchemaCache.set_schema(schema_id, version, schema_data)
                self.stats.cache_misses += 1
                return schema_data
            else:
                logger.error(f"Failed to get schema {schema_id}: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error getting schema {schema_id}: {e}")
            return None
    
    async def _validate_row(self, data: Dict[str, Any], schema_id: str,
                           required_fields: Set[str], properties: Dict[str, Any],
                           additional_properties: bool) -> Dict[str, Any]:
        """Validate a data row against schema."""
        errors = []
        
        # Check required fields
        missing_fields = required_fields - set(data.keys())
        if missing_fields:
            errors.append(f"Missing required fields: {missing_fields}")
        
        # Check for unknown fields
        if not additional_properties:
            unknown_fields = set(data.keys()) - set(properties.keys())
            if unknown_fields:
                errors.append(f"Unknown fields: {unknown_fields}")
        
        # Type validation (simplified)
        for field, value in data.items():
            if field in properties:
                field_schema = properties[field]
                field_type = field_schema.get('type')
                
                if field_type == 'integer' and not isinstance(value, int):
                    try:
                        int(value)
                    except (ValueError, TypeError):
                        errors.append(f"Field '{field}' must be integer, got {type(value).__name__}")
                
                elif field_type == 'number' and not isinstance(value, (int, float)):
                    try:
                        float(value)
                    except (ValueError, TypeError):
                        errors.append(f"Field '{field}' must be number, got {type(value).__name__}")
                
                elif field_type == 'string' and not isinstance(value, str):
                    errors.append(f"Field '{field}' must be string, got {type(value).__name__}")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }
    
    async def _handle_invalid_row(self, data: Dict[str, Any], line_num: int,
                                 file_path: str, schema_id: str, errors: List[str]):
        """Handle invalid row by quarantining it."""
        quarantine_file = self.quarantine_dir / f"{schema_id}_{Path(file_path).stem}_quarantine.jsonl"
        
        quarantine_entry = {
            'timestamp': time.time(),
            'file_path': file_path,
            'line_number': line_num,
            'schema_id': schema_id,
            'data': data,
            'errors': errors
        }
        
        with open(quarantine_file, 'a') as f:
            f.write(json.dumps(quarantine_entry) + '\n')
        
        self.stats.quarantined_rows += 1
        logger.warning(f"Quarantined row {line_num} from {file_path}: {errors}")
    
    async def _process_valid_rows(self, rows: List[Dict[str, Any]], schema_id: str):
        """Process valid rows (placeholder for actual processing logic)."""
        # This would integrate with your actual data processing pipeline
        logger.info(f"Processing {len(rows)} valid rows for schema {schema_id}")
        
        # Example: Send to downstream systems
        # await self._send_to_latency_tick_store(rows, schema_id)
        # await self._send_to_analytics_pipeline(rows, schema_id)
    
    async def get_processing_stats(self) -> Dict[str, Any]:
        """Get processing statistics."""
        return {
            'total_rows': self.stats.total_rows,
            'valid_rows': self.stats.valid_rows,
            'invalid_rows': self.stats.invalid_rows,
            'quarantined_rows': self.stats.quarantined_rows,
            'processing_time': self.stats.processing_time,
            'cache_hits': self.stats.cache_hits,
            'cache_misses': self.stats.cache_misses,
            'cache_hit_ratio': self.stats.cache_hits / (self.stats.cache_hits + self.stats.cache_misses) if (self.stats.cache_hits + self.stats.cache_misses) > 0 else 0,
            'subscribed_schemas': list(self.subscribed_schemas),
            'active_websocket_connections': len(self.websocket_connections)
        }
    
    async def close(self):
        """Clean up resources."""
        await self.client.aclose()
        
        # Close WebSocket connections
        for ws in self.websocket_connections.values():
            await ws.close()
        
        # Cancel background tasks
        for task in self.processing_tasks:
            if not task.done():
                task.cancel()


# Example usage
async def main():
    """Example usage of enhanced Dataset Cleaner."""
    cleaner = EnhancedDatasetCleaner()
    
    try:
        await cleaner.initialize()
        
        # Process data files
        await cleaner.load_raw_data("data/ticks.csv", "ticks_v1")
        await cleaner.load_raw_data("data/ticks_v2.csv", "ticks_v1", version="1.1.0")
        
        # Get statistics
        stats = await cleaner.get_processing_stats()
        print("Processing Statistics:")
        print(json.dumps(stats, indent=2))
        
        # Keep running to receive WebSocket updates
        print("Listening for schema updates... (Press Ctrl+C to stop)")
        await asyncio.sleep(300)  # Run for 5 minutes
        
    except KeyboardInterrupt:
        print("Shutting down...")
    finally:
        await cleaner.close()


if __name__ == "__main__":
    asyncio.run(main()) 
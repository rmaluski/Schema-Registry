#!/usr/bin/env python3
"""
Example integration of Dataset Cleaner with Schema Registry.

This demonstrates how the loader would:
1. Fetch schemas from the registry
2. Validate data against schemas
3. Handle schema mismatches
4. Cache schemas for performance
"""

import json
import time
import httpx
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class SchemaCache:
    """Schema cache with TTL."""
    schema: Dict[str, Any]
    timestamp: float
    ttl: int = 600  # 10 minutes
    
    def is_valid(self) -> bool:
        """Check if cache entry is still valid."""
        return time.time() - self.timestamp < self.ttl


class SchemaRegistryClient:
    """Client for interacting with Schema Registry."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
        self.client = httpx.AsyncClient(timeout=30.0)
        self._cache: Dict[str, SchemaCache] = {}
    
    async def get_schema(self, schema_id: str, version: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get schema from registry with caching."""
        cache_key = f"{schema_id}:{version or 'latest'}"
        
        # Check cache first
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            if cached.is_valid():
                logger.info(f"Using cached schema for {schema_id}")
                return cached.schema
        
        # Fetch from registry
        try:
            url = f"{self.base_url}/schema/{schema_id}"
            if version:
                url += f"/{version}"
            
            response = await self.client.get(url)
            response.raise_for_status()
            
            schema_data = response.json()
            schema = schema_data['schema']
            
            # Cache the result
            self._cache[cache_key] = SchemaCache(schema=schema, timestamp=time.time())
            
            logger.info(f"Fetched schema {schema_id} from registry")
            return schema
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.error(f"Schema {schema_id} not found in registry")
            else:
                logger.error(f"Failed to fetch schema {schema_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error fetching schema {schema_id}: {e}")
            return None
    
    async def check_compatibility(self, schema_id: str, data: Dict[str, Any]) -> bool:
        """Check if data is compatible with schema."""
        try:
            url = f"{self.base_url}/schema/{schema_id}/compat"
            response = await self.client.post(url, json={"data": data})
            response.raise_for_status()
            
            result = response.json()
            return result['compatible']
            
        except Exception as e:
            logger.error(f"Error checking compatibility: {e}")
            return False
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


class DatasetCleaner:
    """Example Dataset Cleaner with Schema Registry integration."""
    
    def __init__(self, registry_url: str = "http://localhost:8000"):
        self.registry = SchemaRegistryClient(registry_url)
        self.quarantine_dir = Path("quarantine")
        self.quarantine_dir.mkdir(exist_ok=True)
    
    async def load_raw_data(self, file_path: str, schema_id: str, version: Optional[str] = None) -> bool:
        """
        Load raw data with schema validation.
        
        Args:
            file_path: Path to the data file
            schema_id: Schema identifier
            version: Optional schema version (uses latest if not specified)
        
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Loading {file_path} with schema {schema_id}")
        
        # Fetch schema from registry
        schema = await self.registry.get_schema(schema_id, version)
        if not schema:
            logger.error(f"Failed to fetch schema {schema_id}")
            return False
        
        # Parse schema for validation
        required_fields = set(schema.get('required', []))
        properties = schema.get('properties', {})
        additional_properties = schema.get('additionalProperties', False)
        
        # Read and validate data
        try:
            with open(file_path, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        # Parse JSON line
                        data = json.loads(line.strip())
                        
                        # Validate against schema
                        validation_result = await self._validate_row(
                            data, schema_id, required_fields, properties, additional_properties
                        )
                        
                        if not validation_result['valid']:
                            await self._handle_invalid_row(
                                data, line_num, file_path, schema_id, validation_result['errors']
                            )
                        else:
                            # Process valid row
                            await self._process_valid_row(data, schema_id)
                    
                    except json.JSONDecodeError as e:
                        logger.error(f"Invalid JSON at line {line_num}: {e}")
                        await self._handle_invalid_row(
                            {"raw_line": line.strip()}, line_num, file_path, schema_id, 
                            [f"Invalid JSON: {e}"]
                        )
            
            logger.info(f"Successfully processed {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")
            return False
    
    async def _validate_row(self, data: Dict[str, Any], schema_id: str, 
                           required_fields: set, properties: Dict[str, Any], 
                           additional_properties: bool) -> Dict[str, Any]:
        """Validate a single row against the schema."""
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
        
        # Check field types and constraints
        for field_name, field_value in data.items():
            if field_name in properties:
                field_schema = properties[field_name]
                field_errors = self._validate_field(field_name, field_value, field_schema)
                errors.extend(field_errors)
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }
    
    def _validate_field(self, field_name: str, value: Any, field_schema: Dict[str, Any]) -> List[str]:
        """Validate a single field against its schema."""
        errors = []
        
        # Type validation
        expected_type = field_schema.get('type')
        if expected_type:
            if expected_type == 'string':
                if not isinstance(value, str):
                    errors.append(f"Field '{field_name}' must be string, got {type(value).__name__}")
            elif expected_type == 'number':
                if not isinstance(value, (int, float)):
                    errors.append(f"Field '{field_name}' must be number, got {type(value).__name__}")
            elif expected_type == 'integer':
                if not isinstance(value, int):
                    errors.append(f"Field '{field_name}' must be integer, got {type(value).__name__}")
            elif expected_type == 'boolean':
                if not isinstance(value, bool):
                    errors.append(f"Field '{field_name}' must be boolean, got {type(value).__name__}")
        
        # Enum validation
        enum_values = field_schema.get('enum')
        if enum_values and value not in enum_values:
            errors.append(f"Field '{field_name}' value '{value}' not in enum {enum_values}")
        
        # Format validation
        if field_schema.get('format') == 'date-time':
            # Simple date-time validation (could be more sophisticated)
            if not isinstance(value, str) or 'T' not in value:
                errors.append(f"Field '{field_name}' must be ISO 8601 date-time format")
        
        return errors
    
    async def _handle_invalid_row(self, data: Dict[str, Any], line_num: int, 
                                 file_path: str, schema_id: str, errors: List[str]):
        """Handle invalid rows by moving them to quarantine."""
        quarantine_file = self.quarantine_dir / f"{Path(file_path).stem}_quarantine.jsonl"
        
        quarantine_record = {
            'original_file': file_path,
            'line_number': line_num,
            'schema_id': schema_id,
            'timestamp': time.time(),
            'errors': errors,
            'data': data
        }
        
        with open(quarantine_file, 'a') as f:
            f.write(json.dumps(quarantine_record) + '\n')
        
        logger.warning(f"schema_mismatch: {errors[0]} (schema {schema_id}) - moved to quarantine")
    
    async def _process_valid_row(self, data: Dict[str, Any], schema_id: str):
        """Process a valid row (placeholder for actual processing logic)."""
        # This would contain the actual data processing logic
        # For now, just log that we processed it
        pass
    
    async def close(self):
        """Clean up resources."""
        await self.registry.close()


# Example usage
async def main():
    """Example usage of Dataset Cleaner with Schema Registry."""
    
    # Initialize the cleaner
    cleaner = DatasetCleaner("http://localhost:8000")
    
    try:
        # Example 1: Load with latest schema
        success = await cleaner.load_raw_data(
            file_path="data/ticks.csv",
            schema_id="ticks_v1"
        )
        
        # Example 2: Load with specific version
        success = await cleaner.load_raw_data(
            file_path="data/ticks_v2.csv",
            schema_id="ticks_v1",
            version="1.1.0"
        )
        
        # Example 3: Check compatibility before processing
        test_data = {
            "ts": "2023-01-01T10:00:00Z",
            "symbol": "AAPL",
            "price": 150.50,
            "size": 100,
            "side": "B"
        }
        
        is_compatible = await cleaner.registry.check_compatibility("ticks_v1", test_data)
        if is_compatible:
            logger.info("Data is compatible with schema")
        else:
            logger.warning("Data is not compatible with schema")
    
    finally:
        await cleaner.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main()) 
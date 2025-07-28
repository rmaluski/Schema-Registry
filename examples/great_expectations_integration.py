#!/usr/bin/env python3
"""
Great Expectations Integration with Schema Registry.

This demonstrates how Great Expectations can use the Schema Registry
for validation, ensuring both parsing and validation use the same schema.
"""

import json
import httpx
from typing import Dict, Any, Optional, List
from great_expectations.core.batch import BatchRequest
from great_expectations.data_context import BaseDataContext
from great_expectations.execution_engine import PandasExecutionEngine
from great_expectations.validator.validator import Validator
import pandas as pd
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SchemaRegistryGEIntegration:
    """Great Expectations integration with Schema Registry."""
    
    def __init__(self, registry_url: str = "http://localhost:8000"):
        self.registry_url = registry_url.rstrip('/')
        self.client = httpx.AsyncClient(timeout=30.0)
        self.context = BaseDataContext()
    
    async def get_schema_for_validation(self, schema_id: str, version: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get schema from registry for Great Expectations validation."""
        try:
            url = f"{self.registry_url}/schema/{schema_id}"
            if version:
                url += f"/{version}"
            
            response = await self.client.get(url)
            response.raise_for_status()
            
            schema_data = response.json()
            return schema_data['schema']
            
        except Exception as e:
            logger.error(f"Failed to fetch schema {schema_id}: {e}")
            return None
    
    def create_ge_expectations_from_schema(self, schema: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convert JSON Schema to Great Expectations expectations."""
        expectations = []
        properties = schema.get('properties', {})
        required_fields = set(schema.get('required', []))
        
        # Create expectations for each field
        for field_name, field_schema in properties.items():
            field_type = field_schema.get('type')
            is_required = field_name in required_fields
            
            # Expect column to exist
            expectations.append({
                "expectation_type": "expect_column_to_exist",
                "kwargs": {"column": field_name}
            })
            
            # Expect column not to be null if required
            if is_required:
                expectations.append({
                    "expectation_type": "expect_column_values_to_not_be_null",
                    "kwargs": {"column": field_name}
                })
            
            # Type-specific expectations
            if field_type == "string":
                expectations.append({
                    "expectation_type": "expect_column_values_to_be_of_type",
                    "kwargs": {"column": field_name, "type_": "str"}
                })
                
                # Check for enum values if specified
                if "enum" in field_schema:
                    expectations.append({
                        "expectation_type": "expect_column_values_to_be_in_set",
                        "kwargs": {
                            "column": field_name,
                            "value_set": field_schema["enum"]
                        }
                    })
                    
            elif field_type == "integer":
                expectations.append({
                    "expectation_type": "expect_column_values_to_be_of_type",
                    "kwargs": {"column": field_name, "type_": "int64"}
                })
                
            elif field_type == "number":
                expectations.append({
                    "expectation_type": "expect_column_values_to_be_of_type",
                    "kwargs": {"column": field_name, "type_": "float64"}
                })
            
            # Check for additional constraints
            if "minimum" in field_schema:
                expectations.append({
                    "expectation_type": "expect_column_values_to_be_between",
                    "kwargs": {
                        "column": field_name,
                        "min_value": field_schema["minimum"]
                    }
                })
            
            if "maximum" in field_schema:
                expectations.append({
                    "expectation_type": "expect_column_values_to_be_between",
                    "kwargs": {
                        "column": field_name,
                        "max_value": field_schema["maximum"]
                    }
                })
        
        # Expect no additional columns if additionalProperties is false
        if not schema.get('additionalProperties', True):
            expected_columns = list(properties.keys())
            expectations.append({
                "expectation_type": "expect_table_columns_to_match_set",
                "kwargs": {"column_set": expected_columns}
            })
        
        return expectations
    
    async def validate_dataframe(self, df: pd.DataFrame, schema_id: str, version: Optional[str] = None) -> Dict[str, Any]:
        """Validate a DataFrame against a schema from the registry."""
        # Get schema from registry
        schema = await self.get_schema_for_validation(schema_id, version)
        if not schema:
            return {
                "success": False,
                "error": f"Failed to fetch schema {schema_id}"
            }
        
        # Create expectations from schema
        expectations = self.create_ge_expectations_from_schema(schema)
        
        # Create validator
        batch_request = BatchRequest(
            datasource_name="pandas",
            data_connector_name="default_runtime_data_connector_name",
            data_asset_name="my_data",
            runtime_parameters={"batch_data": df},
            batch_identifiers={"default_identifier_name": "default_identifier"}
        )
        
        validator = self.context.get_validator(
            batch_request=batch_request,
            expectation_suite_name="schema_validation"
        )
        
        # Run expectations
        results = []
        for expectation in expectations:
            result = validator.expect(**expectation)
            results.append({
                "expectation_type": expectation["expectation_type"],
                "success": result.success,
                "kwargs": expectation["kwargs"]
            })
        
        # Calculate overall success
        success = all(r["success"] for r in results)
        
        return {
            "success": success,
            "schema_id": schema_id,
            "version": version,
            "results": results,
            "total_expectations": len(results),
            "passed_expectations": sum(1 for r in results if r["success"]),
            "failed_expectations": sum(1 for r in results if not r["success"])
        }
    
    async def create_validation_suite(self, schema_id: str, version: Optional[str] = None) -> str:
        """Create a Great Expectations validation suite from a schema."""
        schema = await self.get_schema_for_validation(schema_id, version)
        if not schema:
            raise ValueError(f"Failed to fetch schema {schema_id}")
        
        expectations = self.create_ge_expectations_from_schema(schema)
        
        # Create expectation suite
        suite_name = f"{schema_id}_validation"
        suite = self.context.create_expectation_suite(
            expectation_suite_name=suite_name,
            overwrite_existing=True
        )
        
        # Add expectations to suite
        for expectation in expectations:
            suite.add_expectation(expectation)
        
        # Save suite
        self.context.save_expectation_suite(suite)
        
        logger.info(f"Created validation suite: {suite_name}")
        return suite_name
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


# Example usage
async def main():
    """Example of using Great Expectations with Schema Registry."""
    ge_integration = SchemaRegistryGEIntegration()
    
    # Create sample data
    data = {
        "ts": ["2023-01-01T10:00:00Z", "2023-01-01T10:01:00Z"],
        "symbol": ["AAPL", "GOOGL"],
        "price": [150.50, 2800.75],
        "size": [100, 50],
        "side": ["B", "S"]
    }
    df = pd.DataFrame(data)
    
    # Validate against ticks_v1 schema
    result = await ge_integration.validate_dataframe(df, "ticks_v1")
    
    print("Validation Result:")
    print(json.dumps(result, indent=2))
    
    # Create validation suite
    suite_name = await ge_integration.create_validation_suite("ticks_v1")
    print(f"Created validation suite: {suite_name}")
    
    await ge_integration.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main()) 
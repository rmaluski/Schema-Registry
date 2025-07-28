from typing import List, Optional, Dict, Any
from graphql import GraphQLSchema, GraphQLObjectType, GraphQLField, GraphQLString, GraphQLList, GraphQLNonNull, GraphQLInt, GraphQLBoolean
from graphql import graphql_sync
from structlog import get_logger
from app.storage import storage
from app.validation import SchemaValidator

logger = get_logger(__name__)


class GraphQLSchemaRegistry:
    """GraphQL API for Schema Registry."""
    
    def __init__(self):
        self.schema = self._build_schema()
    
    def _build_schema(self) -> GraphQLSchema:
        """Build GraphQL schema."""
        
        # Schema Type
        SchemaType = GraphQLObjectType(
            'Schema',
            fields={
                'id': GraphQLField(GraphQLNonNull(GraphQLString)),
                'version': GraphQLField(GraphQLNonNull(GraphQLString)),
                'title': GraphQLField(GraphQLNonNull(GraphQLString)),
                'properties': GraphQLField(GraphQLNonNull(GraphQLString), resolver=self._resolve_properties),
                'required_fields': GraphQLField(GraphQLList(GraphQLString), resolver=self._resolve_required_fields),
                'field_count': GraphQLField(GraphQLInt, resolver=self._resolve_field_count),
                'has_arrow_schema': GraphQLField(GraphQLBoolean, resolver=self._resolve_has_arrow),
                'created_at': GraphQLField(GraphQLString, resolver=self._resolve_created_at),
                'updated_at': GraphQLField(GraphQLString, resolver=self._resolve_updated_at)
            }
        )
        
        # Schema Version Type
        SchemaVersionType = GraphQLObjectType(
            'SchemaVersion',
            fields={
                'version': GraphQLField(GraphQLNonNull(GraphQLString)),
                'schema': GraphQLField(SchemaType, resolver=self._resolve_schema_version),
                'is_latest': GraphQLField(GraphQLBoolean, resolver=self._resolve_is_latest),
                'is_compatible_with': GraphQLField(
                    GraphQLBoolean,
                    args={'target_version': GraphQLNonNull(GraphQLString)},
                    resolver=self._resolve_compatibility
                )
            }
        )
        
        # Query Type
        QueryType = GraphQLObjectType(
            'Query',
            fields={
                'schemas': GraphQLField(
                    GraphQLList(SchemaType),
                    resolver=self._resolve_schemas
                ),
                'schema': GraphQLField(
                    SchemaType,
                    args={
                        'id': GraphQLNonNull(GraphQLString),
                        'version': GraphQLString
                    },
                    resolver=self._resolve_schema
                ),
                'schemaVersions': GraphQLField(
                    GraphQLList(SchemaVersionType),
                    args={'id': GraphQLNonNull(GraphQLString)},
                    resolver=self._resolve_schema_versions
                ),
                'searchSchemas': GraphQLField(
                    GraphQLList(SchemaType),
                    args={
                        'query': GraphQLNonNull(GraphQLString),
                        'limit': GraphQLInt
                    },
                    resolver=self._resolve_search_schemas
                ),
                'compatibleSchemas': GraphQLField(
                    GraphQLList(SchemaType),
                    args={
                        'schema_id': GraphQLNonNull(GraphQLString),
                        'version': GraphQLNonNull(GraphQLString)
                    },
                    resolver=self._resolve_compatible_schemas
                ),
                'schemaStats': GraphQLField(
                    GraphQLString,
                    args={'id': GraphQLNonNull(GraphQLString)},
                    resolver=self._resolve_schema_stats
                )
            }
        )
        
        return GraphQLSchema(query=QueryType)
    
    def _resolve_schemas(self, info) -> List[Dict[str, Any]]:
        """Resolve all schemas."""
        try:
            schema_ids = storage.list_schemas()
            schemas = []
            for schema_id in schema_ids:
                schema_data = storage.get_schema(schema_id)
                if schema_data:
                    schemas.append(schema_data)
            return schemas
        except Exception as e:
            logger.error(f"Error resolving schemas: {e}")
            return []
    
    def _resolve_schema(self, info, id: str, version: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Resolve a specific schema."""
        try:
            return storage.get_schema(id, version)
        except Exception as e:
            logger.error(f"Error resolving schema {id}: {e}")
            return None
    
    def _resolve_schema_versions(self, info, id: str) -> List[Dict[str, Any]]:
        """Resolve all versions of a schema."""
        try:
            versions = storage.list_versions(id)
            latest_schema = storage.get_schema(id)
            latest_version = latest_schema['version'] if latest_schema else None
            
            schema_versions = []
            for version in versions:
                schema_data = storage.get_schema(id, version)
                if schema_data:
                    schema_versions.append({
                        'version': version,
                        'schema': schema_data,
                        'is_latest': version == latest_version
                    })
            return schema_versions
        except Exception as e:
            logger.error(f"Error resolving schema versions for {id}: {e}")
            return []
    
    def _resolve_search_schemas(self, info, query: str, limit: Optional[int] = 10) -> List[Dict[str, Any]]:
        """Search schemas by query."""
        try:
            schema_ids = storage.list_schemas()
            matching_schemas = []
            
            for schema_id in schema_ids:
                if query.lower() in schema_id.lower():
                    schema_data = storage.get_schema(schema_id)
                    if schema_data and len(matching_schemas) < (limit or 10):
                        matching_schemas.append(schema_data)
            
            return matching_schemas
        except Exception as e:
            logger.error(f"Error searching schemas: {e}")
            return []
    
    def _resolve_compatible_schemas(self, info, schema_id: str, version: str) -> List[Dict[str, Any]]:
        """Find schemas compatible with the given schema version."""
        try:
            target_schema = storage.get_schema(schema_id, version)
            if not target_schema:
                return []
            
            schema_ids = storage.list_schemas()
            compatible_schemas = []
            
            for other_id in schema_ids:
                if other_id == schema_id:
                    continue
                
                other_schema = storage.get_schema(other_id)
                if other_schema:
                    is_compatible, _, _ = SchemaValidator.check_compatibility(
                        target_schema, other_schema
                    )
                    if is_compatible:
                        compatible_schemas.append(other_schema)
            
            return compatible_schemas
        except Exception as e:
            logger.error(f"Error finding compatible schemas: {e}")
            return []
    
    def _resolve_schema_stats(self, info, id: str) -> str:
        """Get schema statistics."""
        try:
            versions = storage.list_versions(id)
            latest_schema = storage.get_schema(id)
            
            stats = {
                'total_versions': len(versions),
                'latest_version': latest_schema['version'] if latest_schema else None,
                'field_count': len(latest_schema.get('properties', {})) if latest_schema else 0,
                'has_arrow_schema': bool(latest_schema.get('arrow')) if latest_schema else False
            }
            
            return str(stats)
        except Exception as e:
            logger.error(f"Error getting schema stats for {id}: {e}")
            return "{}"
    
    # Field resolvers
    def _resolve_properties(self, schema, info) -> str:
        """Resolve properties as JSON string."""
        import json
        return json.dumps(schema.get('properties', {}))
    
    def _resolve_required_fields(self, schema, info) -> List[str]:
        """Resolve required fields."""
        return schema.get('required', [])
    
    def _resolve_field_count(self, schema, info) -> int:
        """Resolve field count."""
        return len(schema.get('properties', {}))
    
    def _resolve_has_arrow(self, schema, info) -> bool:
        """Resolve if schema has Arrow definition."""
        return bool(schema.get('arrow'))
    
    def _resolve_created_at(self, schema, info) -> str:
        """Resolve created at timestamp."""
        return str(schema.get('created_at', ''))
    
    def _resolve_updated_at(self, schema, info) -> str:
        """Resolve updated at timestamp."""
        return str(schema.get('updated_at', ''))
    
    def _resolve_schema_version(self, version_info, info) -> Dict[str, Any]:
        """Resolve schema for version."""
        return version_info['schema']
    
    def _resolve_is_latest(self, version_info, info) -> bool:
        """Resolve if version is latest."""
        return version_info['is_latest']
    
    def _resolve_compatibility(self, version_info, info, target_version: str) -> bool:
        """Resolve compatibility with target version."""
        try:
            schema_id = version_info['schema']['id']
            current_schema = storage.get_schema(schema_id, version_info['version'])
            target_schema = storage.get_schema(schema_id, target_version)
            
            if current_schema and target_schema:
                is_compatible, _, _ = SchemaValidator.check_compatibility(
                    current_schema, target_schema
                )
                return is_compatible
            
            return False
        except Exception as e:
            logger.error(f"Error checking compatibility: {e}")
            return False
    
    def execute_query(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute GraphQL query."""
        try:
            result = graphql_sync(self.schema, query, variable_values=variables)
            return {
                'data': result.data,
                'errors': [str(error) for error in result.errors] if result.errors else None
            }
        except Exception as e:
            logger.error(f"GraphQL query execution error: {e}")
            return {
                'data': None,
                'errors': [str(e)]
            }


# Global GraphQL instance
graphql_api = GraphQLSchemaRegistry() 
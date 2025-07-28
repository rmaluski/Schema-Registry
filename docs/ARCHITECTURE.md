# Schema Registry Architecture

## Overview

The Schema Registry is a critical service that provides versioned, auditable schema management for data pipelines. It ensures data consistency across producers and consumers by maintaining a single source of truth for data schemas.

## Core Components

### 1. FastAPI Application (`app/main.py`)

The main application provides a RESTful API with the following endpoints:

- `GET /schema/{id}` - Retrieve latest schema version
- `GET /schema/{id}/{version}` - Retrieve specific schema version
- `POST /schema/{id}` - Create new schema version
- `POST /schema/{id}/compat` - Check data compatibility
- `GET /compat/{id}/{ver_from}/{ver_to}` - Check version compatibility
- `GET /schemas` - List all schemas
- `GET /schema/{id}/versions` - List schema versions
- `GET /health` - Health check
- `GET /metrics` - Prometheus metrics

### 2. Etcd Storage Backend (`app/storage.py`)

- **Persistent Storage**: Schemas are stored in Etcd with keys like `/schemas/{id}/{version}`
- **Caching**: In-memory cache with TTL (10 minutes default)
- **Latest Pointer**: Each schema maintains a `/schemas/{id}/latest` pointer
- **Health Checks**: Connection monitoring and error handling

### 3. Schema Validation (`app/validation.py`)

- **JSON Schema Validation**: Uses Draft-07 for schema validation
- **Compatibility Checking**: Detects breaking vs. compatible changes
- **Type Safety**: Validates semantic versioning and type widening
- **Arrow Schema Support**: Optional Arrow type definitions for C++ integration

### 4. Configuration Management (`app/config.py`)

- **Environment Variables**: All configuration via environment variables
- **Pydantic Settings**: Type-safe configuration with validation
- **Security**: TLS, authentication, and authorization settings

## Schema Document Format

```json
{
  "id": "ticks_v1",
  "schema": "http://json-schema.org/draft-07/schema#",
  "title": "Level-1 Tick Data",
  "type": "object",
  "properties": {
    "ts": {
      "type": "string",
      "format": "date-time"
    },
    "symbol": {
      "type": "string"
    },
    "price": {
      "type": "number"
    },
    "size": {
      "type": "integer"
    },
    "side": {
      "type": "string",
      "enum": ["B", "S"]
    }
  },
  "required": ["ts", "symbol", "price", "size"],
  "additionalProperties": false,
  "arrow": {
    "fields": [
      {
        "name": "ts",
        "type": {
          "name": "timestamp",
          "unit": "us"
        }
      }
    ]
  },
  "version": "1.0.0"
}
```

## Schema Evolution Rules

### Compatible Changes (Minor/Patch Version Bump)

- Adding optional fields
- Widening numeric types (int32 → int64, int → float)
- Adding enum values
- Relaxing constraints

### Breaking Changes (Major Version Bump)

- Removing fields
- Removing required fields
- Narrowing types (string → int)
- Removing enum values
- Making optional fields required

## GitHub Integration

### Schema-Diff Bot (`scripts/diff_schemas.py`)

1. **Detects Changes**: Compares schema files between commits
2. **Validates Compatibility**: Uses `SchemaValidator.check_compatibility()`
3. **Enforces Versioning**: Ensures breaking changes bump major version
4. **Labels PRs**: Adds `schema:breaking` or `schema:compatible` labels
5. **Blocks Merges**: Prevents breaking changes without proper versioning

### Validation Pipeline (`.github/workflows/schema-validation.yml`)

1. **Schema Validation**: Validates all schema files
2. **Compatibility Check**: Runs schema diff analysis
3. **PR Comments**: Provides detailed change summaries
4. **Version Enforcement**: Blocks invalid version bumps

## Integration Patterns

### Dataset Cleaner Integration

```python
# Fetch schema from registry
schema = await registry_client.get_schema("ticks_v1")

# Validate data
is_valid = await registry_client.check_compatibility("ticks_v1", data)

# Handle schema mismatches
if not is_valid:
    # Move to quarantine
    await quarantine_row(data, errors)
```

### C++ Integration

```cpp
// Fetch Arrow schema
auto schema = registry_client.get_latest("ticks_v1");
arrow::SchemaPtr arrow_schema = ArrowSchemaFromJson(schema["arrow"]);

// Use for CSV parsing
auto reader = arrow::csv::TableReader::Make(pool, input, arrow_schema, opts);
```

### Great Expectations Integration

```python
# Load schema for validation
schema = registry_client.get_schema("ticks_v1")

# Use in Great Expectations suite
expectation_suite = {
    "data_asset_type": "Dataset",
    "expectations": [
        {
            "expectation_type": "expect_column_to_exist",
            "kwargs": {"column": "ts"}
        }
    ]
}
```

## Security & Operations

### Authentication & Authorization

- **mTLS**: Mutual TLS for internal service communication
- **GitHub OIDC**: For CI/CD bot authentication
- **Etcd JWT**: Short-lived tokens for registry access
- **RBAC**: Kubernetes role-based access control

### Monitoring & Observability

- **Prometheus Metrics**: Request counts, latencies, error rates
- **Structured Logging**: JSON logs with correlation IDs
- **Health Checks**: Etcd connectivity and service health
- **Grafana Dashboards**: Schema usage and performance metrics

### Backup & Recovery

- **Etcd Snapshots**: Nightly backups to S3
- **Git Versioning**: All schemas versioned in Git
- **Disaster Recovery**: Multi-region Etcd clusters
- **Schema Migration**: Automated schema deployment

## Deployment Architecture

### Kubernetes Deployment

```yaml
# High availability with 3 replicas
replicas: 3

# Resource limits and requests
resources:
  requests:
    memory: "256Mi"
    cpu: "250m"
  limits:
    memory: "512Mi"
    cpu: "500m"

# Health checks
livenessProbe:
  httpGet:
    path: /health
    port: 8000
```

### Etcd Cluster

- **3-node cluster** for high availability
- **Persistent volumes** for data durability
- **TLS encryption** for data in transit
- **Regular snapshots** for backup

### Load Balancing

- **Ingress controller** for external access
- **Service mesh** for internal communication
- **Circuit breakers** for fault tolerance
- **Rate limiting** for API protection

## Performance Considerations

### Caching Strategy

- **Schema Cache**: 10-minute TTL for frequently accessed schemas
- **HTTP Cache**: ETags and conditional requests
- **CDN**: For static schema documentation
- **Redis**: Optional distributed cache for high-traffic deployments

### Scalability

- **Horizontal Scaling**: Multiple API instances
- **Database Sharding**: Schema partitioning by domain
- **CDN**: Global schema distribution
- **Load Balancing**: Round-robin and health-based routing

## Testing Strategy

### Unit Tests

- **Schema Validation**: Test all validation rules
- **Compatibility Logic**: Test breaking vs. compatible changes
- **API Endpoints**: Test all HTTP endpoints
- **Error Handling**: Test edge cases and failures

### Integration Tests

- **Etcd Integration**: Test storage operations
- **GitHub Integration**: Test PR validation
- **Client Libraries**: Test Python and C++ clients
- **End-to-End**: Test complete workflows

### Performance Tests

- **Load Testing**: High-throughput schema requests
- **Stress Testing**: Memory and CPU limits
- **Concurrency**: Multiple simultaneous operations
- **Failover**: Etcd cluster failure scenarios

## Migration Guide

### From Hard-coded Schemas

1. **Extract Schemas**: Move hard-coded schemas to JSON files
2. **Register Schemas**: Upload to Schema Registry
3. **Update Clients**: Modify code to fetch from registry
4. **Validate Data**: Ensure all data conforms to schemas
5. **Monitor**: Watch for schema mismatches

### From Other Schema Registries

1. **Export Schemas**: Export from existing registry
2. **Transform Format**: Convert to our JSON Schema format
3. **Import Schemas**: Register in new system
4. **Update Dependencies**: Point clients to new registry
5. **Verify Compatibility**: Test all integrations

## Troubleshooting

### Common Issues

1. **Schema Not Found**: Check schema ID and version
2. **Validation Errors**: Review schema format and constraints
3. **Compatibility Issues**: Check breaking change rules
4. **Performance Problems**: Monitor cache hit rates and Etcd latency

### Debug Commands

```bash
# Check service health
curl http://localhost:8000/health

# View metrics
curl http://localhost:8000/metrics

# Validate schema
python scripts/validate_all.py schemas/

# Check compatibility
python scripts/diff_schemas.py v1.0.0 v1.1.0
```

## Future Enhancements

### Planned Features

- **GraphQL API**: For complex schema queries
- **Schema Templates**: Reusable schema components
- **Automated Testing**: Schema-driven test generation
- **Data Lineage**: Track schema usage across systems
- **Schema Analytics**: Usage patterns and impact analysis

### Scalability Improvements

- **Multi-tenancy**: Support for multiple organizations
- **Schema Federation**: Cross-registry schema sharing
- **Real-time Updates**: WebSocket notifications for schema changes

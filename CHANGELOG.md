# Changelog

All notable changes to the Schema Registry project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Initial project setup and documentation

## [1.0.0] - 2025-01-XX

### Added

- **Core Schema Registry Service**

  - FastAPI-based REST API with comprehensive endpoints
  - Etcd storage backend with caching and health checks
  - Schema validation using JSON Schema Draft-07
  - Compatibility checking for schema evolution
  - Semantic versioning enforcement

- **Schema Management**

  - Create, read, update, and delete schemas
  - Version management with latest pointers
  - Schema compatibility checking
  - Arrow schema support for C++ integration

- **GitHub Integration**

  - Schema-Diff Bot for PR validation
  - GitHub Actions workflow for automated checks
  - Breaking change detection and enforcement
  - Automatic PR labeling and commenting

- **Developer Tools**

  - Schema validation scripts
  - Schema diff analysis tools
  - Comprehensive test suite
  - Docker and Kubernetes deployment manifests

- **Documentation**

  - Complete API documentation
  - Architecture guide
  - Contributing guidelines
  - Integration examples

- **Monitoring & Observability**
  - Prometheus metrics
  - Structured logging
  - Health checks
  - Performance monitoring

### Features

- **Schema Evolution Rules**

  - Compatible changes: adding optional fields, widening types
  - Breaking changes: removing fields, narrowing types
  - Automatic version bump enforcement

- **Integration Examples**

  - Dataset Cleaner integration with quarantine handling
  - C++ Arrow schema integration
  - Great Expectations validation integration

- **Security & Operations**
  - mTLS support for internal communication
  - GitHub OIDC for CI/CD authentication
  - RBAC for Kubernetes deployments
  - Etcd backup and recovery

### Technical Details

- **Performance**: 10-minute schema caching with TTL
- **Scalability**: Horizontal scaling with Kubernetes
- **Reliability**: Health checks and circuit breakers
- **Observability**: Comprehensive metrics and logging

## [0.1.0] - 2025-01-XX

### Added

- Initial project structure
- Basic FastAPI application
- Etcd storage integration
- Schema validation framework

---

## Version History

- **1.0.0**: Production-ready Schema Registry with full feature set
- **0.1.0**: Initial development version with core functionality

## Migration Guide

### From 0.1.0 to 1.0.0

1. **Update Dependencies**: Install new requirements
2. **Database Migration**: No breaking changes to storage format
3. **API Changes**: All endpoints remain backward compatible
4. **Configuration**: Update environment variables for new features

## Deprecation Notices

No deprecations in current version.

## Breaking Changes

No breaking changes in current version.

---

For detailed information about each release, see the [GitHub releases page](https://github.com/rmaluski/Schema-Registry/releases).

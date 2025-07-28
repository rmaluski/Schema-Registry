from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import time
from typing import Optional
import structlog

from app.config import settings
from app.models import (
    SchemaCreateRequest, SchemaResponse, CompatibilityRequest, 
    CompatibilityResponse, CompatibilityCheckResponse, ErrorResponse,
    SchemaListResponse, VersionListResponse
)
from app.storage import storage
from app.validation import SchemaValidator

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Schema Registry API for managing versioned data schemas",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Metrics
schema_fetch_counter = Counter('schema_fetch_total', 'Total schema fetches', ['schema_id', 'version'])
schema_create_counter = Counter('schema_create_total', 'Total schema creations', ['schema_id'])
compatibility_check_counter = Counter('compatibility_check_total', 'Total compatibility checks', ['schema_id'])
request_duration = Histogram('request_duration_seconds', 'Request duration in seconds', ['endpoint'])

# Middleware for request timing and logging
@app.middleware("http")
async def log_requests(request, call_next):
    start_time = time.time()
    
    response = await call_next(request)
    
    duration = time.time() - start_time
    request_duration.labels(endpoint=request.url.path).observe(duration)
    
    logger.info(
        "Request processed",
        method=request.method,
        url=str(request.url),
        status_code=response.status_code,
        duration=duration
    )
    
    return response

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    etcd_healthy = await storage.health_check()
    
    if not etcd_healthy:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Etcd connection unhealthy"
        )
    
    return {"status": "healthy", "etcd": "connected"}

# Metrics endpoint
@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return JSONResponse(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )

# Schema endpoints
@app.get("/schema/{schema_id}", response_model=SchemaResponse)
async def get_schema(schema_id: str, version: Optional[str] = None):
    """Get a schema by ID and optional version."""
    try:
        schema_data = await storage.get_schema(schema_id, version)
        
        if not schema_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Schema '{schema_id}' not found"
            )
        
        # Update metrics
        schema_fetch_counter.labels(schema_id=schema_id, version=version or 'latest').inc()
        
        return SchemaResponse(
            schema=schema_data,
            created_at=str(schema_data.get('created_at', '')),
            updated_at=str(schema_data.get('updated_at', ''))
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error retrieving schema", schema_id=schema_id, version=version, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@app.post("/schema/{schema_id}", response_model=SchemaResponse)
async def create_schema(schema_id: str, request: SchemaCreateRequest):
    """Create a new schema version."""
    try:
        schema = request.schema
        
        # Validate schema ID matches path
        if schema.id != schema_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Schema ID in body must match path parameter"
            )
        
        # Validate schema document
        is_valid, error_msg, errors = SchemaValidator.validate_schema_document(schema.dict())
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
        
        # Check if schema already exists
        existing_schema = await storage.get_schema(schema_id, schema.version)
        if existing_schema:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Schema '{schema_id}' version '{schema.version}' already exists"
            )
        
        # Get previous version for compatibility check
        previous_schema = await storage.get_schema(schema_id)
        if previous_schema:
            is_compatible, compat_msg, breaking_changes = SchemaValidator.check_compatibility(
                previous_schema, schema.dict()
            )
            
            if not is_compatible:
                # Check if version bump is appropriate
                version_valid = SchemaValidator.validate_version_compatibility(
                    previous_schema['version'], schema.version, bool(breaking_changes)
                )
                
                if not version_valid:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Breaking changes detected but version bump is incorrect. {compat_msg}"
                    )
        
        # Store schema
        success = await storage.store_schema(schema)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to store schema"
            )
        
        # Update metrics
        schema_create_counter.labels(schema_id=schema_id).inc()
        
        # Return the stored schema
        stored_schema = await storage.get_schema(schema_id, schema.version)
        return SchemaResponse(
            schema=stored_schema,
            created_at=str(stored_schema.get('created_at', '')),
            updated_at=str(stored_schema.get('updated_at', ''))
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error creating schema", schema_id=schema_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@app.post("/schema/{schema_id}/compat", response_model=CompatibilityResponse)
async def check_compatibility(schema_id: str, request: CompatibilityRequest):
    """Check if data is compatible with the latest schema."""
    try:
        # Get latest schema
        schema_data = await storage.get_schema(schema_id)
        if not schema_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Schema '{schema_id}' not found"
            )
        
        # Validate data against schema
        is_valid, message, errors = SchemaValidator.validate_data_against_schema(
            request.data, schema_data
        )
        
        # Update metrics
        compatibility_check_counter.labels(schema_id=schema_id).inc()
        
        return CompatibilityResponse(
            compatible=is_valid,
            message=message,
            errors=errors
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error checking compatibility", schema_id=schema_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@app.get("/compat/{schema_id}/{ver_from}/{ver_to}", response_model=CompatibilityCheckResponse)
async def check_version_compatibility(schema_id: str, ver_from: str, ver_to: str):
    """Check compatibility between two schema versions."""
    try:
        # Get both schema versions
        from_schema = await storage.get_schema(schema_id, ver_from)
        to_schema = await storage.get_schema(schema_id, ver_to)
        
        if not from_schema:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Schema '{schema_id}' version '{ver_from}' not found"
            )
        
        if not to_schema:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Schema '{schema_id}' version '{ver_to}' not found"
            )
        
        # Check compatibility
        is_compatible, message, breaking_changes = SchemaValidator.check_compatibility(
            from_schema, to_schema
        )
        
        return CompatibilityCheckResponse(
            compatible=is_compatible,
            message=message,
            breaking_changes=breaking_changes
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error checking version compatibility", 
                    schema_id=schema_id, ver_from=ver_from, ver_to=ver_to, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@app.get("/schemas", response_model=SchemaListResponse)
async def list_schemas():
    """List all available schemas."""
    try:
        schemas = await storage.list_schemas()
        return SchemaListResponse(
            schemas=schemas,
            total=len(schemas)
        )
        
    except Exception as e:
        logger.error("Error listing schemas", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@app.get("/schema/{schema_id}/versions", response_model=VersionListResponse)
async def list_versions(schema_id: str):
    """List all versions for a schema."""
    try:
        versions = await storage.list_versions(schema_id)
        
        if not versions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Schema '{schema_id}' not found"
            )
        
        # Get latest version
        latest_schema = await storage.get_schema(schema_id)
        latest_version = latest_schema['version'] if latest_schema else versions[-1]
        
        return VersionListResponse(
            versions=versions,
            latest=latest_version,
            total=len(versions)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error listing versions", schema_id=schema_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@app.delete("/schema/{schema_id}")
async def delete_schema(schema_id: str, version: Optional[str] = None):
    """Delete a schema or schema version."""
    try:
        success = await storage.delete_schema(schema_id, version)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Schema '{schema_id}' not found"
            )
        
        return {"message": "Schema deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error deleting schema", schema_id=schema_id, version=version, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=exc.detail,
            message=exc.detail,
            details=None
        ).dict()
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error("Unhandled exception", error=str(exc), exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="Internal server error",
            message="An unexpected error occurred",
            details=None
        ).dict()
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug
    ) 
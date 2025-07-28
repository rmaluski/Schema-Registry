from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, validator
from enum import Enum


class ArrowType(BaseModel):
    name: str
    unit: Optional[str] = None


class ArrowField(BaseModel):
    name: str
    type: ArrowType


class ArrowSchema(BaseModel):
    fields: List[ArrowField]


class SchemaDocument(BaseModel):
    """Schema document with JSON-Schema and optional Arrow types."""
    
    id: str = Field(..., description="Schema identifier")
    schema: str = Field("http://json-schema.org/draft-07/schema#", description="JSON Schema version")
    title: str = Field(..., description="Human-readable title")
    type: str = Field("object", description="Root type")
    properties: Dict[str, Any] = Field(..., description="Schema properties")
    required: List[str] = Field(default_factory=list, description="Required fields")
    additionalProperties: bool = Field(False, description="Allow additional properties")
    arrow: Optional[ArrowSchema] = Field(None, description="Arrow schema for C++ mapping")
    version: str = Field(..., description="Semantic version")
    
    @validator('version')
    def validate_version(cls, v):
        """Validate semantic versioning format."""
        parts = v.split('.')
        if len(parts) != 3:
            raise ValueError('Version must be in format MAJOR.MINOR.PATCH')
        try:
            int(parts[0]), int(parts[1]), int(parts[2])
        except ValueError:
            raise ValueError('Version parts must be integers')
        return v


class SchemaCreateRequest(BaseModel):
    """Request model for creating a new schema."""
    schema: SchemaDocument


class SchemaResponse(BaseModel):
    """Response model for schema retrieval."""
    schema: SchemaDocument
    created_at: str
    updated_at: str


class CompatibilityRequest(BaseModel):
    """Request model for compatibility checking."""
    data: Dict[str, Any]


class CompatibilityResponse(BaseModel):
    """Response model for compatibility checking."""
    compatible: bool
    message: Optional[str] = None
    errors: Optional[List[str]] = None


class CompatibilityCheckResponse(BaseModel):
    """Response model for version-to-version compatibility."""
    compatible: bool
    message: str
    breaking_changes: Optional[List[str]] = None


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    message: str
    details: Optional[Dict[str, Any]] = None


class SchemaListResponse(BaseModel):
    """Response model for listing schemas."""
    schemas: List[str]
    total: int


class VersionListResponse(BaseModel):
    """Response model for listing schema versions."""
    versions: List[str]
    latest: str
    total: int 
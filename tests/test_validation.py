import pytest
import json
from app.validation import SchemaValidator


class TestSchemaValidator:
    """Test cases for SchemaValidator."""
    
    def test_validate_schema_document_valid(self):
        """Test validation of a valid schema document."""
        schema_data = {
            "id": "test_schema",
            "schema": "http://json-schema.org/draft-07/schema#",
            "title": "Test Schema",
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"}
            },
            "required": ["name"],
            "version": "1.0.0"
        }
        
        is_valid, error_msg, errors = SchemaValidator.validate_schema_document(schema_data)
        
        assert is_valid
        assert error_msg is None
        assert errors is None
    
    def test_validate_schema_document_invalid_version(self):
        """Test validation with invalid version format."""
        schema_data = {
            "id": "test_schema",
            "schema": "http://json-schema.org/draft-07/schema#",
            "title": "Test Schema",
            "type": "object",
            "properties": {
                "name": {"type": "string"}
            },
            "version": "invalid"
        }
        
        is_valid, error_msg, errors = SchemaValidator.validate_schema_document(schema_data)
        
        assert not is_valid
        assert "Version must be in format MAJOR.MINOR.PATCH" in error_msg
    
    def test_validate_data_against_schema_valid(self):
        """Test validation of valid data against schema."""
        schema_data = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"}
            },
            "required": ["name"]
        }
        
        data = {"name": "John", "age": 30}
        
        is_valid, message, errors = SchemaValidator.validate_data_against_schema(data, schema_data)
        
        assert is_valid
        assert message == "Data is valid"
        assert errors is None
    
    def test_validate_data_against_schema_invalid(self):
        """Test validation of invalid data against schema."""
        schema_data = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"}
            },
            "required": ["name"]
        }
        
        data = {"age": "thirty"}  # age should be integer
        
        is_valid, message, errors = SchemaValidator.validate_data_against_schema(data, schema_data)
        
        assert not is_valid
        assert "Data validation failed" in message
        assert len(errors) > 0
    
    def test_check_compatibility_compatible(self):
        """Test compatibility check for compatible schemas."""
        old_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"}
            },
            "required": ["name"]
        }
        
        new_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
                "email": {"type": "string"}
            },
            "required": ["name"]
        }
        
        is_compatible, message, breaking_changes = SchemaValidator.check_compatibility(old_schema, new_schema)
        
        assert is_compatible
        assert "Schema is compatible" in message
        assert breaking_changes is None
    
    def test_check_compatibility_breaking_removed_field(self):
        """Test compatibility check for breaking change (removed field)."""
        old_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"}
            },
            "required": ["name"]
        }
        
        new_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"}
            },
            "required": ["name"]
        }
        
        is_compatible, message, breaking_changes = SchemaValidator.check_compatibility(old_schema, new_schema)
        
        assert not is_compatible
        assert "Breaking changes detected" in message
        assert len(breaking_changes) > 0
        assert any("Removed properties" in change for change in breaking_changes)
    
    def test_check_compatibility_breaking_removed_required(self):
        """Test compatibility check for breaking change (removed required field)."""
        old_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"}
            },
            "required": ["name", "age"]
        }
        
        new_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"}
            },
            "required": ["name"]
        }
        
        is_compatible, message, breaking_changes = SchemaValidator.check_compatibility(old_schema, new_schema)
        
        assert not is_compatible
        assert "Breaking changes detected" in message
        assert len(breaking_changes) > 0
        assert any("Removed required fields" in change for change in breaking_changes)
    
    def test_check_compatibility_safe_type_widening(self):
        """Test compatibility check for safe type widening."""
        old_schema = {
            "type": "object",
            "properties": {
                "count": {"type": "integer"}
            }
        }
        
        new_schema = {
            "type": "object",
            "properties": {
                "count": {"type": "number"}
            }
        }
        
        is_compatible, message, breaking_changes = SchemaValidator.check_compatibility(old_schema, new_schema)
        
        assert is_compatible
        assert "Schema is compatible" in message
    
    def test_check_compatibility_unsafe_type_change(self):
        """Test compatibility check for unsafe type change."""
        old_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"}
            }
        }
        
        new_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "integer"}
            }
        }
        
        is_compatible, message, breaking_changes = SchemaValidator.check_compatibility(old_schema, new_schema)
        
        assert not is_compatible
        assert "Breaking changes detected" in message
        assert len(breaking_changes) > 0
    
    def test_get_schema_diff(self):
        """Test schema diff generation."""
        old_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"}
            },
            "required": ["name"]
        }
        
        new_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "email": {"type": "string"}
            },
            "required": ["name", "email"]
        }
        
        diff = SchemaValidator.get_schema_diff(old_schema, new_schema)
        
        assert "age" in diff["removed_fields"]
        assert "email" in diff["added_fields"]
        assert "name" in diff["modified_fields"]
        assert len(diff["required_changes"]["added_required"]) == 1
        assert "email" in diff["required_changes"]["added_required"]
    
    def test_validate_version_compatibility_valid_major_bump(self):
        """Test version compatibility with valid major version bump."""
        old_version = "1.0.0"
        new_version = "2.0.0"
        has_breaking_changes = True
        
        is_valid = SchemaValidator.validate_version_compatibility(old_version, new_version, has_breaking_changes)
        
        assert is_valid
    
    def test_validate_version_compatibility_invalid_major_bump(self):
        """Test version compatibility with invalid major version bump."""
        old_version = "1.0.0"
        new_version = "2.0.0"
        has_breaking_changes = False
        
        is_valid = SchemaValidator.validate_version_compatibility(old_version, new_version, has_breaking_changes)
        
        assert not is_valid
    
    def test_validate_version_compatibility_invalid_format(self):
        """Test version compatibility with invalid version format."""
        old_version = "1.0"
        new_version = "2.0.0"
        has_breaking_changes = True
        
        is_valid = SchemaValidator.validate_version_compatibility(old_version, new_version, has_breaking_changes)
        
        assert not is_valid


class TestArrowSchemaValidation:
    """Test cases for Arrow schema validation."""
    
    def test_validate_schema_with_arrow_valid(self):
        """Test validation of schema with valid Arrow types."""
        schema_data = {
            "id": "test_schema",
            "schema": "http://json-schema.org/draft-07/schema#",
            "title": "Test Schema",
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"}
            },
            "required": ["name"],
            "version": "1.0.0",
            "arrow": {
                "fields": [
                    {"name": "name", "type": {"name": "utf8"}},
                    {"name": "age", "type": {"name": "int32"}}
                ]
            }
        }
        
        is_valid, error_msg, errors = SchemaValidator.validate_schema_document(schema_data)
        
        assert is_valid
        assert error_msg is None
        assert errors is None
    
    def test_validate_schema_with_arrow_invalid(self):
        """Test validation of schema with invalid Arrow types."""
        schema_data = {
            "id": "test_schema",
            "schema": "http://json-schema.org/draft-07/schema#",
            "title": "Test Schema",
            "type": "object",
            "properties": {
                "name": {"type": "string"}
            },
            "required": ["name"],
            "version": "1.0.0",
            "arrow": {
                "fields": [
                    {"name": "", "type": {"name": "utf8"}}  # Invalid empty name
                ]
            }
        }
        
        is_valid, error_msg, errors = SchemaValidator.validate_schema_document(schema_data)
        
        assert not is_valid
        assert "Invalid Arrow field definition" in error_msg 
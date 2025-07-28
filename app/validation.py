import json
from typing import Dict, List, Optional, Any, Tuple
from jsonschema import Draft7Validator, ValidationError, SchemaError
from jsonschema.compat import Draft7Validator as CompatValidator
from structlog import get_logger
from app.models import SchemaDocument

logger = get_logger(__name__)


class SchemaValidator:
    """Schema validation and compatibility checking."""
    
    @staticmethod
    def validate_schema_document(schema_data: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[List[str]]]:
        """Validate a schema document structure."""
        try:
            # Validate JSON Schema structure
            schema = SchemaDocument(**schema_data)
            
            # Validate that the JSON Schema itself is valid
            validator = Draft7Validator(schema_data)
            
            # Validate Arrow schema if present
            if schema.arrow:
                for field in schema.arrow.fields:
                    if not field.name or not field.type.name:
                        return False, "Invalid Arrow field definition", None
            
            return True, None, None
            
        except ValidationError as e:
            return False, f"Schema validation error: {str(e)}", [str(e)]
        except SchemaError as e:
            return False, f"Schema structure error: {str(e)}", [str(e)]
        except Exception as e:
            return False, f"Unexpected error: {str(e)}", [str(e)]
    
    @staticmethod
    def validate_data_against_schema(data: Dict[str, Any], schema_data: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[List[str]]]:
        """Validate data against a schema."""
        try:
            validator = Draft7Validator(schema_data)
            errors = list(validator.iter_errors(data))
            
            if errors:
                error_messages = [str(error) for error in errors]
                return False, "Data validation failed", error_messages
            
            return True, "Data is valid", None
            
        except Exception as e:
            return False, f"Validation error: {str(e)}", [str(e)]
    
    @staticmethod
    def check_compatibility(old_schema: Dict[str, Any], new_schema: Dict[str, Any]) -> Tuple[bool, str, Optional[List[str]]]:
        """Check if new schema is compatible with old schema."""
        try:
            breaking_changes = []
            
            # Check for removed required fields
            old_required = set(old_schema.get('required', []))
            new_required = set(new_schema.get('required', []))
            removed_required = old_required - new_required
            if removed_required:
                breaking_changes.append(f"Removed required fields: {removed_required}")
            
            # Check for removed properties
            old_properties = set(old_schema.get('properties', {}).keys())
            new_properties = set(new_schema.get('properties', {}).keys())
            removed_properties = old_properties - new_properties
            if removed_properties:
                breaking_changes.append(f"Removed properties: {removed_properties}")
            
            # Check for type changes
            old_props = old_schema.get('properties', {})
            new_props = new_schema.get('properties', {})
            
            for field in old_properties & new_properties:
                old_type = old_props[field].get('type')
                new_type = new_props[field].get('type')
                
                if old_type != new_type:
                    # Check if it's a safe type widening
                    if not SchemaValidator._is_safe_type_widening(old_type, new_type):
                        breaking_changes.append(f"Type change for '{field}': {old_type} -> {new_type}")
            
            # Check for enum changes
            for field in old_properties & new_properties:
                old_enum = old_props[field].get('enum')
                new_enum = new_props[field].get('enum')
                
                if old_enum and new_enum:
                    removed_enum_values = set(old_enum) - set(new_enum)
                    if removed_enum_values:
                        breaking_changes.append(f"Removed enum values for '{field}': {removed_enum_values}")
            
            # Check for additionalProperties changes
            old_additional = old_schema.get('additionalProperties', False)
            new_additional = new_schema.get('additionalProperties', False)
            
            if old_additional and not new_additional:
                breaking_changes.append("additionalProperties changed from true to false")
            
            if breaking_changes:
                return False, "Breaking changes detected", breaking_changes
            
            return True, "Schema is compatible", None
            
        except Exception as e:
            return False, f"Compatibility check error: {str(e)}", [str(e)]
    
    @staticmethod
    def _is_safe_type_widening(old_type: str, new_type: str) -> bool:
        """Check if type change is a safe widening."""
        safe_widenings = {
            'integer': ['number'],
            'int32': ['int64', 'float64'],
            'int64': ['float64'],
            'float32': ['float64'],
            'string': [],  # No safe widening
            'boolean': [],  # No safe widening
        }
        
        return new_type in safe_widenings.get(old_type, [])
    
    @staticmethod
    def get_schema_diff(old_schema: Dict[str, Any], new_schema: Dict[str, Any]) -> Dict[str, Any]:
        """Get detailed diff between two schemas."""
        diff = {
            'added_fields': [],
            'removed_fields': [],
            'modified_fields': [],
            'type_changes': [],
            'enum_changes': [],
            'required_changes': []
        }
        
        old_props = old_schema.get('properties', {})
        new_props = new_schema.get('properties', {})
        
        old_fields = set(old_props.keys())
        new_fields = set(new_props.keys())
        
        # Added fields
        diff['added_fields'] = list(new_fields - old_fields)
        
        # Removed fields
        diff['removed_fields'] = list(old_fields - new_fields)
        
        # Modified fields
        common_fields = old_fields & new_fields
        for field in common_fields:
            old_prop = old_props[field]
            new_prop = new_props[field]
            
            if old_prop != new_prop:
                diff['modified_fields'].append(field)
                
                # Type changes
                if old_prop.get('type') != new_prop.get('type'):
                    diff['type_changes'].append({
                        'field': field,
                        'old_type': old_prop.get('type'),
                        'new_type': new_prop.get('type')
                    })
                
                # Enum changes
                if 'enum' in old_prop or 'enum' in new_prop:
                    old_enum = old_prop.get('enum', [])
                    new_enum = new_prop.get('enum', [])
                    if old_enum != new_enum:
                        diff['enum_changes'].append({
                            'field': field,
                            'old_enum': old_enum,
                            'new_enum': new_enum
                        })
        
        # Required field changes
        old_required = set(old_schema.get('required', []))
        new_required = set(new_schema.get('required', []))
        
        if old_required != new_required:
            diff['required_changes'] = {
                'added_required': list(new_required - old_required),
                'removed_required': list(old_required - new_required)
            }
        
        return diff
    
    @staticmethod
    def validate_version_compatibility(old_version: str, new_version: str, has_breaking_changes: bool) -> bool:
        """Validate that version bump follows semantic versioning rules."""
        try:
            old_parts = [int(x) for x in old_version.split('.')]
            new_parts = [int(x) for x in new_version.split('.')]
            
            if len(old_parts) != 3 or len(new_parts) != 3:
                return False
            
            major_old, minor_old, patch_old = old_parts
            major_new, minor_new, patch_new = new_parts
            
            if has_breaking_changes:
                # Breaking changes should bump major version
                return major_new > major_old
            else:
                # Non-breaking changes should only bump minor or patch
                if major_new > major_old:
                    return False  # Major bump without breaking changes
                return True
                
        except (ValueError, IndexError):
            return False 
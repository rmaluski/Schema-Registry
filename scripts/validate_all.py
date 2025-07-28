#!/usr/bin/env python3
"""
Validate all schema files in the schemas directory.
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple
import jsonschema
from jsonschema import Draft7Validator, ValidationError, SchemaError

# Add the app directory to the path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.models import SchemaDocument
from app.validation import SchemaValidator


def validate_schema_file(file_path: Path) -> Tuple[bool, List[str]]:
    """Validate a single schema file."""
    errors = []
    
    try:
        # Read and parse JSON
        with open(file_path, 'r') as f:
            schema_data = json.load(f)
        
        # Validate schema document structure
        is_valid, error_msg, validation_errors = SchemaValidator.validate_schema_document(schema_data)
        
        if not is_valid:
            errors.append(f"Schema validation failed: {error_msg}")
            if validation_errors:
                errors.extend(validation_errors)
            return False, errors
        
        # Validate JSON Schema itself
        try:
            Draft7Validator(schema_data)
        except SchemaError as e:
            errors.append(f"JSON Schema validation failed: {str(e)}")
            return False, errors
        
        # Validate version format
        version = schema_data.get('version', '')
        if not version:
            errors.append("Missing version field")
            return False, errors
        
        # Validate schema ID matches filename
        schema_id = schema_data.get('id', '')
        expected_id = file_path.stem.split('_v')[0]  # Extract base name before version
        if schema_id != expected_id:
            errors.append(f"Schema ID '{schema_id}' doesn't match expected '{expected_id}'")
            return False, errors
        
        return True, errors
        
    except json.JSONDecodeError as e:
        errors.append(f"Invalid JSON: {str(e)}")
        return False, errors
    except Exception as e:
        errors.append(f"Unexpected error: {str(e)}")
        return False, errors


def main():
    """Main validation function."""
    if len(sys.argv) != 2:
        print("Usage: python validate_all.py <schemas_directory>")
        sys.exit(1)
    
    schemas_dir = Path(sys.argv[1])
    
    if not schemas_dir.exists():
        print(f"Error: Directory '{schemas_dir}' does not exist")
        sys.exit(1)
    
    if not schemas_dir.is_dir():
        print(f"Error: '{schemas_dir}' is not a directory")
        sys.exit(1)
    
    # Find all JSON schema files
    schema_files = list(schemas_dir.glob("*.json"))
    
    if not schema_files:
        print(f"No JSON files found in '{schemas_dir}'")
        sys.exit(0)
    
    print(f"Validating {len(schema_files)} schema files...")
    
    all_valid = True
    validation_results = {}
    
    for schema_file in schema_files:
        print(f"Validating {schema_file.name}...")
        is_valid, errors = validate_schema_file(schema_file)
        
        validation_results[schema_file.name] = {
            'valid': is_valid,
            'errors': errors
        }
        
        if not is_valid:
            all_valid = False
            print(f"  ❌ Validation failed:")
            for error in errors:
                print(f"    - {error}")
        else:
            print(f"  ✅ Valid")
    
    # Summary
    print("\n" + "="*50)
    print("VALIDATION SUMMARY")
    print("="*50)
    
    valid_count = sum(1 for result in validation_results.values() if result['valid'])
    total_count = len(validation_results)
    
    print(f"Total schemas: {total_count}")
    print(f"Valid: {valid_count}")
    print(f"Invalid: {total_count - valid_count}")
    
    if not all_valid:
        print("\nFailed validations:")
        for filename, result in validation_results.items():
            if not result['valid']:
                print(f"\n{filename}:")
                for error in result['errors']:
                    print(f"  - {error}")
    
    if all_valid:
        print("\n🎉 All schemas are valid!")
        sys.exit(0)
    else:
        print("\n❌ Some schemas failed validation")
        sys.exit(1)


if __name__ == "__main__":
    main() 
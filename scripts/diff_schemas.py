#!/usr/bin/env python3
"""
Diff schemas between two Git commits and detect breaking changes.
"""

import json
import os
import sys
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Tuple, Set
import argparse

# Add the app directory to the path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.validation import SchemaValidator


def run_git_command(cmd: List[str]) -> str:
    """Run a git command and return the output."""
    try:
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            check=True,
            cwd=Path(__file__).parent.parent
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Git command failed: {' '.join(cmd)}")
        print(f"Error: {e.stderr}")
        sys.exit(1)


def get_changed_files(base_sha: str, head_sha: str) -> Set[str]:
    """Get list of files changed between two commits."""
    cmd = ["git", "diff", "--name-only", base_sha, head_sha]
    output = run_git_command(cmd)
    
    if not output:
        return set()
    
    changed_files = set(output.split('\n'))
    # Filter for schema files
    schema_files = {f for f in changed_files if f.startswith('schemas/') and f.endswith('.json')}
    
    return schema_files


def get_file_content_at_commit(file_path: str, commit_sha: str) -> Dict[str, Any]:
    """Get the content of a file at a specific commit."""
    try:
        cmd = ["git", "show", f"{commit_sha}:{file_path}"]
        content = run_git_command(cmd)
        return json.loads(content)
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return None


def get_schema_id_from_filename(filename: str) -> str:
    """Extract schema ID from filename."""
    # Remove schemas/ prefix and .json suffix
    base_name = filename.replace('schemas/', '').replace('.json', '')
    # Extract base name before version
    return base_name.split('_v')[0]


def analyze_schema_changes(base_sha: str, head_sha: str) -> Dict[str, Any]:
    """Analyze changes in schema files between two commits."""
    changed_files = get_changed_files(base_sha, head_sha)
    
    if not changed_files:
        print("No schema files changed")
        return {}
    
    print(f"Analyzing changes in {len(changed_files)} schema files...")
    
    all_changes = {
        'schema_files': list(changed_files),
        'breaking_changes': [],
        'compatible_changes': [],
        'added_fields': [],
        'removed_fields': [],
        'modified_fields': [],
        'type_changes': [],
        'enum_changes': [],
        'required_changes': []
    }
    
    # Group files by schema ID
    schema_groups = {}
    for file_path in changed_files:
        schema_id = get_schema_id_from_filename(file_path)
        if schema_id not in schema_groups:
            schema_groups[schema_id] = []
        schema_groups[schema_id].append(file_path)
    
    for schema_id, files in schema_groups.items():
        print(f"\nAnalyzing schema: {schema_id}")
        
        # Find the latest version in each commit
        base_files = [f for f in files if f in get_changed_files(base_sha, head_sha)]
        head_files = [f for f in files if f in get_changed_files(base_sha, head_sha)]
        
        # Get the most recent version in base
        base_versions = []
        for file_path in base_files:
            try:
                content = get_file_content_at_commit(file_path, base_sha)
                if content:
                    base_versions.append((content.get('version', '0.0.0'), file_path, content))
            except:
                continue
        
        # Get the most recent version in head
        head_versions = []
        for file_path in head_files:
            try:
                content = get_file_content_at_commit(file_path, head_sha)
                if content:
                    head_versions.append((content.get('version', '0.0.0'), file_path, content))
            except:
                continue
        
        if not base_versions and not head_versions:
            continue
        
        # Sort by version and get the latest
        base_versions.sort(key=lambda x: [int(v) for v in x[0].split('.')])
        head_versions.sort(key=lambda x: [int(v) for v in x[0].split('.')])
        
        base_latest = base_versions[-1] if base_versions else None
        head_latest = head_versions[-1] if head_versions else None
        
        if base_latest and head_latest:
            # Compare schemas
            base_schema = base_latest[2]
            head_schema = head_latest[2]
            
            print(f"  Comparing {base_latest[0]} -> {head_latest[0]}")
            
            # Check compatibility
            is_compatible, message, breaking_changes = SchemaValidator.check_compatibility(
                base_schema, head_schema
            )
            
            if not is_compatible:
                all_changes['breaking_changes'].extend(breaking_changes)
                print(f"  ❌ Breaking changes detected")
                for change in breaking_changes:
                    print(f"    - {change}")
            else:
                print(f"  ✅ Compatible changes")
            
            # Get detailed diff
            diff = SchemaValidator.get_schema_diff(base_schema, head_schema)
            
            all_changes['added_fields'].extend(diff['added_fields'])
            all_changes['removed_fields'].extend(diff['removed_fields'])
            all_changes['modified_fields'].extend(diff['modified_fields'])
            all_changes['type_changes'].extend(diff['type_changes'])
            all_changes['enum_changes'].extend(diff['enum_changes'])
            
            if diff['required_changes']:
                all_changes['required_changes'].append({
                    'schema_id': schema_id,
                    'changes': diff['required_changes']
                })
        
        elif not base_latest and head_latest:
            # New schema
            print(f"  ✅ New schema added: {head_latest[0]}")
            all_changes['compatible_changes'].append(f"New schema {schema_id} added")
        
        elif base_latest and not head_latest:
            # Schema removed
            print(f"  ❌ Schema removed: {base_latest[0]}")
            all_changes['breaking_changes'].append(f"Schema {schema_id} was removed")
    
    return all_changes


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Diff schemas between two Git commits')
    parser.add_argument('base_sha', help='Base commit SHA')
    parser.add_argument('head_sha', help='Head commit SHA')
    parser.add_argument('--output', '-o', help='Output file for changes JSON')
    
    args = parser.parse_args()
    
    print(f"Analyzing schema changes from {args.base_sha[:8]} to {args.head_sha[:8]}...")
    
    changes = analyze_schema_changes(args.base_sha, args.head_sha)
    
    if not changes:
        print("No schema changes detected")
        sys.exit(0)
    
    # Summary
    print("\n" + "="*50)
    print("SCHEMA CHANGES SUMMARY")
    print("="*50)
    
    if changes['breaking_changes']:
        print(f"❌ Breaking changes: {len(changes['breaking_changes'])}")
        for change in changes['breaking_changes']:
            print(f"  - {change}")
    else:
        print("✅ No breaking changes detected")
    
    if changes['added_fields']:
        print(f"➕ Added fields: {len(changes['added_fields'])}")
        for field in changes['added_fields']:
            print(f"  - {field}")
    
    if changes['removed_fields']:
        print(f"➖ Removed fields: {len(changes['removed_fields'])}")
        for field in changes['removed_fields']:
            print(f"  - {field}")
    
    if changes['modified_fields']:
        print(f"🔄 Modified fields: {len(changes['modified_fields'])}")
        for field in changes['modified_fields']:
            print(f"  - {field}")
    
    # Write changes to file
    output_file = args.output or 'schema_changes.json'
    with open(output_file, 'w') as f:
        json.dump(changes, f, indent=2)
    
    print(f"\nChanges written to: {output_file}")
    
    # Exit with error if breaking changes detected
    if changes['breaking_changes']:
        print("\n❌ Breaking changes detected - this may require a MAJOR version bump")
        sys.exit(1)
    else:
        print("\n✅ All changes are compatible")
        sys.exit(0)


if __name__ == "__main__":
    main() 
#!/usr/bin/env python3
"""
Etcd Backup Script for Schema Registry.

This script creates nightly snapshots of etcd data and uploads them to S3,
as mentioned in the roadmap requirements.
"""

import os
import json
import subprocess
import boto3
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from pathlib import Path
import tempfile
import shutil

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EtcdBackupManager:
    """Manages etcd backups and S3 uploads."""
    
    def __init__(
        self,
        etcd_endpoint: str = "localhost:2379",
        s3_bucket: str = "schema-registry-backups",
        s3_prefix: str = "etcd-snapshots",
        retention_days: int = 30,
        aws_region: str = "us-east-1"
    ):
        self.etcd_endpoint = etcd_endpoint
        self.s3_bucket = s3_bucket
        self.s3_prefix = s3_prefix
        self.retention_days = retention_days
        self.aws_region = aws_region
        
        # Initialize S3 client
        self.s3_client = boto3.client('s3', region_name=aws_region)
        
        # Create temporary directory for backups
        self.temp_dir = Path(tempfile.mkdtemp())
    
    def create_etcd_snapshot(self) -> Optional[Path]:
        """Create a snapshot of etcd data."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            snapshot_file = self.temp_dir / f"etcd_snapshot_{timestamp}.db"
            
            # Use etcdctl to create snapshot
            cmd = [
                "etcdctl",
                "--endpoints", self.etcd_endpoint,
                "snapshot", "save", str(snapshot_file)
            ]
            
            logger.info(f"Creating etcd snapshot: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            logger.info(f"Snapshot created successfully: {snapshot_file}")
            logger.info(f"Snapshot info: {result.stdout}")
            
            return snapshot_file
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create etcd snapshot: {e}")
            logger.error(f"Error output: {e.stderr}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error creating snapshot: {e}")
            return None
    
    def create_schema_metadata(self) -> Dict[str, Any]:
        """Create metadata about the current schemas."""
        try:
            # Get schema list from registry API
            import httpx
            
            registry_url = os.getenv("SCHEMA_REGISTRY_URL", "http://localhost:8000")
            
            with httpx.Client(timeout=30.0) as client:
                # Get list of schemas
                response = client.get(f"{registry_url}/schemas")
                response.raise_for_status()
                
                schemas_data = response.json()
                schemas = schemas_data.get('schemas', [])
                
                # Get metadata for each schema
                schema_metadata = {}
                for schema_id in schemas:
                    try:
                        schema_response = client.get(f"{registry_url}/schema/{schema_id}")
                        if schema_response.status_code == 200:
                            schema_data = schema_response.json()
                            schema_metadata[schema_id] = {
                                'version': schema_data['schema'].get('version'),
                                'title': schema_data['schema'].get('title'),
                                'created_at': schema_data.get('created_at'),
                                'updated_at': schema_data.get('updated_at')
                            }
                    except Exception as e:
                        logger.warning(f"Failed to get metadata for schema {schema_id}: {e}")
                
                return {
                    'backup_timestamp': datetime.now().isoformat(),
                    'total_schemas': len(schemas),
                    'schema_list': schemas,
                    'schema_metadata': schema_metadata
                }
                
        except Exception as e:
            logger.error(f"Failed to create schema metadata: {e}")
            return {
                'backup_timestamp': datetime.now().isoformat(),
                'error': str(e)
            }
    
    def upload_to_s3(self, file_path: Path, metadata: Dict[str, Any]) -> bool:
        """Upload backup file and metadata to S3."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Upload snapshot file
            snapshot_key = f"{self.s3_prefix}/snapshots/etcd_snapshot_{timestamp}.db"
            logger.info(f"Uploading snapshot to S3: s3://{self.s3_bucket}/{snapshot_key}")
            
            self.s3_client.upload_file(
                str(file_path),
                self.s3_bucket,
                snapshot_key,
                ExtraArgs={
                    'Metadata': {
                        'backup_timestamp': timestamp,
                        'etcd_endpoint': self.etcd_endpoint,
                        'backup_type': 'etcd_snapshot'
                    }
                }
            )
            
            # Upload metadata
            metadata_key = f"{self.s3_prefix}/metadata/backup_metadata_{timestamp}.json"
            logger.info(f"Uploading metadata to S3: s3://{self.s3_bucket}/{metadata_key}")
            
            self.s3_client.put_object(
                Bucket=self.s3_bucket,
                Key=metadata_key,
                Body=json.dumps(metadata, indent=2),
                ContentType='application/json',
                Metadata={
                    'backup_timestamp': timestamp,
                    'backup_type': 'metadata'
                }
            )
            
            logger.info("Backup uploaded to S3 successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to upload to S3: {e}")
            return False
    
    def cleanup_old_backups(self) -> int:
        """Clean up old backups based on retention policy."""
        try:
            cutoff_date = datetime.now() - timedelta(days=self.retention_days)
            cutoff_timestamp = cutoff_date.strftime("%Y%m%d")
            
            logger.info(f"Cleaning up backups older than {cutoff_timestamp}")
            
            # List objects in S3
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(
                Bucket=self.s3_bucket,
                Prefix=self.s3_prefix
            )
            
            deleted_count = 0
            
            for page in pages:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        key = obj['Key']
                        
                        # Extract timestamp from key
                        if 'etcd_snapshot_' in key:
                            # Extract timestamp from filename
                            parts = key.split('_')
                            if len(parts) >= 3:
                                timestamp_str = parts[-1].replace('.db', '')
                                try:
                                    file_date = datetime.strptime(timestamp_str, "%Y%m%d%H%M%S")
                                    if file_date < cutoff_date:
                                        logger.info(f"Deleting old backup: {key}")
                                        self.s3_client.delete_object(
                                            Bucket=self.s3_bucket,
                                            Key=key
                                        )
                                        deleted_count += 1
                                except ValueError:
                                    logger.warning(f"Could not parse timestamp from key: {key}")
            
            logger.info(f"Cleaned up {deleted_count} old backups")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup old backups: {e}")
            return 0
    
    def list_backups(self) -> Dict[str, Any]:
        """List available backups in S3."""
        try:
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(
                Bucket=self.s3_bucket,
                Prefix=self.s3_prefix
            )
            
            snapshots = []
            metadata_files = []
            
            for page in pages:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        key = obj['Key']
                        if 'etcd_snapshot_' in key and key.endswith('.db'):
                            snapshots.append({
                                'key': key,
                                'size': obj['Size'],
                                'last_modified': obj['LastModified'].isoformat()
                            })
                        elif 'backup_metadata_' in key and key.endswith('.json'):
                            metadata_files.append({
                                'key': key,
                                'size': obj['Size'],
                                'last_modified': obj['LastModified'].isoformat()
                            })
            
            return {
                'snapshots': sorted(snapshots, key=lambda x: x['last_modified'], reverse=True),
                'metadata_files': sorted(metadata_files, key=lambda x: x['last_modified'], reverse=True),
                'total_snapshots': len(snapshots),
                'total_metadata_files': len(metadata_files)
            }
            
        except Exception as e:
            logger.error(f"Failed to list backups: {e}")
            return {'error': str(e)}
    
    def restore_from_backup(self, snapshot_key: str, target_endpoint: str) -> bool:
        """Restore etcd from a backup snapshot."""
        try:
            # Download snapshot from S3
            local_snapshot = self.temp_dir / "restore_snapshot.db"
            
            logger.info(f"Downloading snapshot from S3: {snapshot_key}")
            self.s3_client.download_file(
                self.s3_bucket,
                snapshot_key,
                str(local_snapshot)
            )
            
            # Restore using etcdctl
            cmd = [
                "etcdctl",
                "--endpoints", target_endpoint,
                "snapshot", "restore", str(local_snapshot)
            ]
            
            logger.info(f"Restoring etcd from snapshot: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            logger.info("Restore completed successfully")
            logger.info(f"Restore output: {result.stdout}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to restore from backup: {e}")
            return False
    
    def run_backup(self) -> bool:
        """Run the complete backup process."""
        try:
            logger.info("Starting etcd backup process")
            
            # Create snapshot
            snapshot_file = self.create_etcd_snapshot()
            if not snapshot_file:
                return False
            
            # Create metadata
            metadata = self.create_schema_metadata()
            
            # Upload to S3
            if not self.upload_to_s3(snapshot_file, metadata):
                return False
            
            # Cleanup old backups
            self.cleanup_old_backups()
            
            # Cleanup temporary files
            if snapshot_file.exists():
                snapshot_file.unlink()
            
            logger.info("Backup process completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Backup process failed: {e}")
            return False
    
    def cleanup(self):
        """Clean up temporary directory."""
        try:
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
        except Exception as e:
            logger.error(f"Failed to cleanup temporary directory: {e}")


def main():
    """Main backup function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Etcd Backup Manager for Schema Registry")
    parser.add_argument("--etcd-endpoint", default="localhost:2379", help="Etcd endpoint")
    parser.add_argument("--s3-bucket", required=True, help="S3 bucket for backups")
    parser.add_argument("--s3-prefix", default="etcd-snapshots", help="S3 prefix for backups")
    parser.add_argument("--retention-days", type=int, default=30, help="Backup retention days")
    parser.add_argument("--aws-region", default="us-east-1", help="AWS region")
    parser.add_argument("--action", choices=["backup", "list", "restore"], default="backup", help="Action to perform")
    parser.add_argument("--snapshot-key", help="S3 key for restore (required for restore action)")
    parser.add_argument("--target-endpoint", help="Target etcd endpoint for restore")
    
    args = parser.parse_args()
    
    backup_manager = EtcdBackupManager(
        etcd_endpoint=args.etcd_endpoint,
        s3_bucket=args.s3_bucket,
        s3_prefix=args.s3_prefix,
        retention_days=args.retention_days,
        aws_region=args.aws_region
    )
    
    try:
        if args.action == "backup":
            success = backup_manager.run_backup()
            exit(0 if success else 1)
            
        elif args.action == "list":
            backups = backup_manager.list_backups()
            print(json.dumps(backups, indent=2))
            
        elif args.action == "restore":
            if not args.snapshot_key or not args.target_endpoint:
                print("Error: --snapshot-key and --target-endpoint are required for restore")
                exit(1)
            
            success = backup_manager.restore_from_backup(args.snapshot_key, args.target_endpoint)
            exit(0 if success else 1)
    
    finally:
        backup_manager.cleanup()


if __name__ == "__main__":
    main() 
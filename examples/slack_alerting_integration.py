#!/usr/bin/env python3
"""
Slack Alerting Integration with Schema Registry.

This demonstrates how to send Slack notifications for:
- Schema changes (breaking vs compatible)
- Validation failures
- Registry health issues
"""

import json
import httpx
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SlackNotifier:
    """Slack notification service for Schema Registry events."""
    
    def __init__(self, webhook_url: str, channel: str = "#schema-registry"):
        self.webhook_url = webhook_url
        self.channel = channel
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def send_schema_change_notification(
        self, 
        schema_id: str, 
        version: str, 
        changes: Dict[str, Any],
        pr_url: Optional[str] = None
    ):
        """Send notification about schema changes."""
        breaking_changes = changes.get('breaking_changes', [])
        compatible_changes = changes.get('compatible_changes', [])
        
        # Determine color based on change type
        if breaking_changes:
            color = "#ff0000"  # Red for breaking changes
            title = f"🚨 Breaking Schema Change: {schema_id} v{version}"
        else:
            color = "#36a64f"  # Green for compatible changes
            title = f"✅ Compatible Schema Change: {schema_id} v{version}"
        
        # Build message
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": title
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Schema ID:*\n{schema_id}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Version:*\n{version}"
                    }
                ]
            }
        ]
        
        # Add breaking changes
        if breaking_changes:
            breaking_text = "\n".join([f"• {change}" for change in breaking_changes])
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*🚨 Breaking Changes:*\n{breaking_text}"
                }
            })
        
        # Add compatible changes
        if compatible_changes:
            compatible_text = "\n".join([f"• {change}" for change in compatible_changes])
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*✅ Compatible Changes:*\n{compatible_text}"
                }
            })
        
        # Add PR link if available
        if pr_url:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*🔗 Pull Request:*\n<{pr_url}|View PR>"
                }
            })
        
        # Add timestamp
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Updated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}"
                }
            ]
        })
        
        await self._send_message(blocks, color)
    
    async def send_validation_failure_notification(
        self, 
        schema_id: str, 
        data_source: str, 
        errors: List[str],
        row_count: int = 0
    ):
        """Send notification about validation failures."""
        title = f"❌ Schema Validation Failed: {schema_id}"
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": title
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Schema ID:*\n{schema_id}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Data Source:*\n{data_source}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Rows Processed:*\n{row_count}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Error Count:*\n{len(errors)}"
                    }
                ]
            }
        ]
        
        # Add error details (limit to first 5)
        if errors:
            error_text = "\n".join([f"• {error}" for error in errors[:5]])
            if len(errors) > 5:
                error_text += f"\n• ... and {len(errors) - 5} more errors"
            
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Error Details:*\n{error_text}"
                }
            })
        
        # Add timestamp
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Failed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}"
                }
            ]
        })
        
        await self._send_message(blocks, "#ff0000")  # Red for failures
    
    async def send_registry_health_notification(
        self, 
        status: str, 
        details: Optional[str] = None,
        metrics: Optional[Dict[str, Any]] = None
    ):
        """Send notification about registry health status."""
        if status == "healthy":
            title = "✅ Schema Registry Healthy"
            color = "#36a64f"
        else:
            title = "⚠️ Schema Registry Health Issue"
            color = "#ffa500"
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": title
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Status:*\n{status}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Time:*\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}"
                    }
                ]
            }
        ]
        
        if details:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Details:*\n{details}"
                }
            })
        
        if metrics:
            metrics_text = "\n".join([f"• {k}: {v}" for k, v in metrics.items()])
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Metrics:*\n{metrics_text}"
                }
            })
        
        await self._send_message(blocks, color)
    
    async def send_schema_usage_notification(
        self, 
        schema_id: str, 
        usage_stats: Dict[str, Any]
    ):
        """Send notification about schema usage statistics."""
        title = f"📊 Schema Usage Report: {schema_id}"
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": title
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Schema ID:*\n{schema_id}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Total Fetches:*\n{usage_stats.get('total_fetches', 0)}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Cache Hit Rate:*\n{usage_stats.get('cache_hit_rate', 0):.1f}%"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Avg Response Time:*\n{usage_stats.get('avg_response_time', 0):.2f}ms"
                    }
                ]
            }
        ]
        
        # Add top consumers if available
        consumers = usage_stats.get('top_consumers', [])
        if consumers:
            consumers_text = "\n".join([f"• {consumer}" for consumer in consumers[:5]])
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Top Consumers:*\n{consumers_text}"
                }
            })
        
        await self._send_message(blocks, "#36a64f")
    
    async def _send_message(self, blocks: List[Dict[str, Any]], color: str = "#36a64f"):
        """Send message to Slack."""
        payload = {
            "channel": self.channel,
            "attachments": [
                {
                    "color": color,
                    "blocks": blocks
                }
            ]
        }
        
        try:
            response = await self.client.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            logger.info("Slack notification sent successfully")
        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


class SchemaRegistryAlerting:
    """Schema Registry with integrated alerting."""
    
    def __init__(self, registry_url: str, slack_webhook_url: str):
        self.registry_url = registry_url.rstrip('/')
        self.client = httpx.AsyncClient(timeout=30.0)
        self.slack = SlackNotifier(slack_webhook_url)
    
    async def monitor_schema_changes(self, schema_id: str):
        """Monitor schema changes and send notifications."""
        try:
            # Get schema versions
            response = await self.client.get(f"{self.registry_url}/schema/{schema_id}/versions")
            response.raise_for_status()
            
            versions_data = response.json()
            versions = versions_data.get('versions', [])
            
            if len(versions) > 1:
                # Compare latest with previous version
                latest_version = versions[-1]
                previous_version = versions[-2]
                
                # Get compatibility check
                compat_response = await self.client.get(
                    f"{self.registry_url}/compat/{schema_id}/{previous_version}/{latest_version}"
                )
                compat_response.raise_for_status()
                
                compat_data = compat_response.json()
                
                # Send notification
                await self.slack.send_schema_change_notification(
                    schema_id=schema_id,
                    version=latest_version,
                    changes={
                        'breaking_changes': compat_data.get('breaking_changes', []),
                        'compatible_changes': ['Schema version updated'] if compat_data.get('compatible') else []
                    }
                )
                
        except Exception as e:
            logger.error(f"Error monitoring schema changes: {e}")
    
    async def check_registry_health(self):
        """Check registry health and send notification if issues detected."""
        try:
            # Check health endpoint
            health_response = await self.client.get(f"{self.registry_url}/health")
            health_response.raise_for_status()
            
            health_data = health_response.json()
            status = health_data.get('status', 'unknown')
            
            # Check metrics
            metrics_response = await self.client.get(f"{self.registry_url}/metrics")
            if metrics_response.status_code == 200:
                metrics_text = metrics_response.text
                # Parse basic metrics (simplified)
                error_count = metrics_text.count('schema_fetch_total')
                success_count = metrics_text.count('schema_fetch_total')
                
                metrics = {
                    'total_requests': error_count + success_count,
                    'success_rate': f"{(success_count / (error_count + success_count) * 100):.1f}%" if (error_count + success_count) > 0 else "0%"
                }
            else:
                metrics = None
            
            if status != 'healthy':
                await self.slack.send_registry_health_notification(
                    status=status,
                    details=health_data.get('message', 'Unknown issue'),
                    metrics=metrics
                )
                
        except Exception as e:
            await self.slack.send_registry_health_notification(
                status="error",
                details=f"Health check failed: {str(e)}"
            )
    
    async def close(self):
        """Close all clients."""
        await self.client.aclose()
        await self.slack.close()


# Example usage
async def main():
    """Example of using Schema Registry with Slack alerting."""
    # Initialize with your webhook URL
    registry_alerting = SchemaRegistryAlerting(
        registry_url="http://localhost:8000",
        slack_webhook_url="YOUR_SLACK_WEBHOOK_URL"
    )
    
    # Monitor schema changes
    await registry_alerting.monitor_schema_changes("ticks_v1")
    
    # Check registry health
    await registry_alerting.check_registry_health()
    
    # Send usage notification
    await registry_alerting.slack.send_schema_usage_notification(
        "ticks_v1",
        {
            "total_fetches": 1250,
            "cache_hit_rate": 85.5,
            "avg_response_time": 12.3,
            "top_consumers": ["dataset-cleaner", "backtest-engine", "ml-pipeline"]
        }
    )
    
    await registry_alerting.close()


if __name__ == "__main__":
    asyncio.run(main()) 
from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, List, Set, Optional, Any
import json
import asyncio
from structlog import get_logger
from app.storage import storage
from app.validation import SchemaValidator

logger = get_logger(__name__)


class WebSocketManager:
    """WebSocket connection manager for real-time updates."""
    
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {
            "schema_updates": set(),
            "compatibility_alerts": set(),
            "system_events": set()
        }
        self.connection_metadata: Dict[WebSocket, Dict[str, Any]] = {}
    
    async def connect(self, websocket: WebSocket, channel: str, client_info: Dict[str, Any] = None):
        """Connect a WebSocket to a specific channel."""
        await websocket.accept()
        
        if channel in self.active_connections:
            self.active_connections[channel].add(websocket)
            self.connection_metadata[websocket] = {
                "channel": channel,
                "client_info": client_info or {},
                "connected_at": asyncio.get_event_loop().time()
            }
            
            logger.info(f"WebSocket connected to {channel}", 
                       client_info=client_info,
                       total_connections=len(self.active_connections[channel]))
            
            # Send welcome message
            await self.send_personal_message(websocket, {
                "type": "connection_established",
                "channel": channel,
                "message": f"Connected to {channel} channel"
            })
        else:
            await websocket.close(code=4004, reason="Invalid channel")
    
    async def disconnect(self, websocket: WebSocket):
        """Disconnect a WebSocket."""
        try:
            metadata = self.connection_metadata.get(websocket, {})
            channel = metadata.get("channel")
            
            if channel and channel in self.active_connections:
                self.active_connections[channel].discard(websocket)
            
            if websocket in self.connection_metadata:
                del self.connection_metadata[websocket]
            
            logger.info(f"WebSocket disconnected from {channel}")
        except Exception as e:
            logger.error(f"Error during WebSocket disconnect: {e}")
    
    async def send_personal_message(self, websocket: WebSocket, message: Dict[str, Any]):
        """Send a message to a specific WebSocket."""
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")
            await self.disconnect(websocket)
    
    async def broadcast_to_channel(self, channel: str, message: Dict[str, Any]):
        """Broadcast a message to all connections in a channel."""
        if channel not in self.active_connections:
            return
        
        disconnected = set()
        for websocket in self.active_connections[channel]:
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error broadcasting to WebSocket: {e}")
                disconnected.add(websocket)
        
        # Clean up disconnected WebSockets
        for websocket in disconnected:
            await self.disconnect(websocket)
    
    async def broadcast_schema_update(self, schema_id: str, version: str, action: str, schema_data: Dict[str, Any]):
        """Broadcast schema update to all subscribers."""
        message = {
            "type": "schema_update",
            "schema_id": schema_id,
            "version": version,
            "action": action,  # created, updated, deleted
            "timestamp": asyncio.get_event_loop().time(),
            "schema": schema_data
        }
        
        await self.broadcast_to_channel("schema_updates", message)
        logger.info(f"Broadcasted schema update: {schema_id} v{version} - {action}")
    
    async def broadcast_compatibility_alert(self, schema_id: str, old_version: str, new_version: str, breaking_changes: List[str]):
        """Broadcast compatibility alert."""
        message = {
            "type": "compatibility_alert",
            "schema_id": schema_id,
            "old_version": old_version,
            "new_version": new_version,
            "breaking_changes": breaking_changes,
            "timestamp": asyncio.get_event_loop().time(),
            "severity": "warning" if breaking_changes else "info"
        }
        
        await self.broadcast_to_channel("compatibility_alerts", message)
        logger.info(f"Broadcasted compatibility alert: {schema_id} {old_version} -> {new_version}")
    
    async def broadcast_system_event(self, event_type: str, details: Dict[str, Any]):
        """Broadcast system event."""
        message = {
            "type": "system_event",
            "event_type": event_type,
            "details": details,
            "timestamp": asyncio.get_event_loop().time()
        }
        
        await self.broadcast_to_channel("system_events", message)
        logger.info(f"Broadcasted system event: {event_type}")
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get WebSocket connection statistics."""
        stats = {}
        for channel, connections in self.active_connections.items():
            stats[channel] = {
                "active_connections": len(connections),
                "connections": [
                    {
                        "connected_at": metadata.get("connected_at"),
                        "client_info": metadata.get("client_info", {})
                    }
                    for ws, metadata in self.connection_metadata.items()
                    if metadata.get("channel") == channel
                ]
            }
        return stats


# Global WebSocket manager
websocket_manager = WebSocketManager()


class WebSocketHandler:
    """WebSocket request handler."""
    
    @staticmethod
    async def handle_schema_updates(websocket: WebSocket, client_info: Dict[str, Any] = None):
        """Handle WebSocket connection for schema updates."""
        await websocket_manager.connect(websocket, "schema_updates", client_info)
        
        try:
            while True:
                # Keep connection alive and handle client messages
                data = await websocket.receive_text()
                message = json.loads(data)
                
                # Handle client messages (e.g., subscribe to specific schemas)
                if message.get("type") == "subscribe":
                    schema_id = message.get("schema_id")
                    if schema_id:
                        # Add subscription logic here
                        await websocket_manager.send_personal_message(websocket, {
                            "type": "subscription_confirmed",
                            "schema_id": schema_id
                        })
                
                elif message.get("type") == "ping":
                    await websocket_manager.send_personal_message(websocket, {
                        "type": "pong",
                        "timestamp": asyncio.get_event_loop().time()
                    })
        
        except WebSocketDisconnect:
            await websocket_manager.disconnect(websocket)
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            await websocket_manager.disconnect(websocket)
    
    @staticmethod
    async def handle_compatibility_alerts(websocket: WebSocket, client_info: Dict[str, Any] = None):
        """Handle WebSocket connection for compatibility alerts."""
        await websocket_manager.connect(websocket, "compatibility_alerts", client_info)
        
        try:
            while True:
                # Keep connection alive
                data = await websocket.receive_text()
                message = json.loads(data)
                
                if message.get("type") == "ping":
                    await websocket_manager.send_personal_message(websocket, {
                        "type": "pong",
                        "timestamp": asyncio.get_event_loop().time()
                    })
        
        except WebSocketDisconnect:
            await websocket_manager.disconnect(websocket)
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            await websocket_manager.disconnect(websocket)
    
    @staticmethod
    async def handle_system_events(websocket: WebSocket, client_info: Dict[str, Any] = None):
        """Handle WebSocket connection for system events."""
        await websocket_manager.connect(websocket, "system_events", client_info)
        
        try:
            while True:
                # Keep connection alive
                data = await websocket.receive_text()
                message = json.loads(data)
                
                if message.get("type") == "ping":
                    await websocket_manager.send_personal_message(websocket, {
                        "type": "pong",
                        "timestamp": asyncio.get_event_loop().time()
                    })
        
        except WebSocketDisconnect:
            await websocket_manager.disconnect(websocket)
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            await websocket_manager.disconnect(websocket)


# Event hooks for automatic broadcasting
async def on_schema_created(schema_id: str, version: str, schema_data: Dict[str, Any]):
    """Hook called when a schema is created."""
    await websocket_manager.broadcast_schema_update(schema_id, version, "created", schema_data)


async def on_schema_updated(schema_id: str, version: str, schema_data: Dict[str, Any]):
    """Hook called when a schema is updated."""
    await websocket_manager.broadcast_schema_update(schema_id, version, "updated", schema_data)


async def on_schema_deleted(schema_id: str, version: str):
    """Hook called when a schema is deleted."""
    await websocket_manager.broadcast_schema_update(schema_id, version, "deleted", {})


async def on_compatibility_check(schema_id: str, old_version: str, new_version: str, breaking_changes: List[str]):
    """Hook called when compatibility is checked."""
    if breaking_changes:
        await websocket_manager.broadcast_compatibility_alert(schema_id, old_version, new_version, breaking_changes)


async def on_system_event(event_type: str, details: Dict[str, Any]):
    """Hook called for system events."""
    await websocket_manager.broadcast_system_event(event_type, details) 
"""WebSocket connection manager for real-time updates."""
import asyncio
import json
from typing import Dict, Set, Any
from fastapi import WebSocket
import structlog

logger = structlog.get_logger()


class ConnectionManager:
    """Manages WebSocket connections and broadcasts."""
    
    def __init__(self):
        # Active connections by type
        self.activity_connections: Set[WebSocket] = set()
        self.chat_connections: Set[WebSocket] = set()
        self.notification_connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket, connection_type: str):
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        async with self._lock:
            if connection_type == "activity":
                self.activity_connections.add(websocket)
            elif connection_type == "chat":
                self.chat_connections.add(websocket)
            elif connection_type == "notifications":
                self.notification_connections.add(websocket)
        logger.info("websocket_connected", type=connection_type, 
                   total=len(self._get_connections(connection_type)))
    
    async def disconnect(self, websocket: WebSocket, connection_type: str):
        """Remove a WebSocket connection."""
        async with self._lock:
            if connection_type == "activity":
                self.activity_connections.discard(websocket)
            elif connection_type == "chat":
                self.chat_connections.discard(websocket)
            elif connection_type == "notifications":
                self.notification_connections.discard(websocket)
        logger.info("websocket_disconnected", type=connection_type,
                   total=len(self._get_connections(connection_type)))
    
    def _get_connections(self, connection_type: str) -> Set[WebSocket]:
        """Get connections by type."""
        if connection_type == "activity":
            return self.activity_connections
        elif connection_type == "chat":
            return self.chat_connections
        elif connection_type == "notifications":
            return self.notification_connections
        return set()
    
    async def send_personal_message(self, message: Any, websocket: WebSocket):
        """Send a message to a specific WebSocket."""
        try:
            if isinstance(message, dict):
                await websocket.send_json(message)
            else:
                await websocket.send_text(str(message))
        except Exception as e:
            logger.error("send_personal_message_failed", error=str(e))
    
    async def broadcast(self, message: Any, connection_type: str):
        """Broadcast a message to all connections of a specific type."""
        connections = self._get_connections(connection_type)
        if not connections:
            return
        
        # Convert message to JSON if it's a dict
        if isinstance(message, dict):
            message_data = json.dumps(message)
        else:
            message_data = str(message)
        
        # Send to all connections, remove dead ones
        dead_connections = set()
        for connection in connections:
            try:
                await connection.send_text(message_data)
            except Exception as e:
                logger.error("broadcast_failed", error=str(e))
                dead_connections.add(connection)
        
        # Clean up dead connections
        if dead_connections:
            async with self._lock:
                for conn in dead_connections:
                    if connection_type == "activity":
                        self.activity_connections.discard(conn)
                    elif connection_type == "chat":
                        self.chat_connections.discard(conn)
                    elif connection_type == "notifications":
                        self.notification_connections.discard(conn)
    
    async def broadcast_activity(self, event: Dict[str, Any]):
        """Broadcast an activity log event."""
        await self.broadcast({
            "type": "activity",
            "data": event
        }, "activity")
    
    async def broadcast_notification(self, notification: Dict[str, Any]):
        """Broadcast a notification (PR, error, etc.)."""
        await self.broadcast({
            "type": "notification",
            "data": notification
        }, "notifications")
    
    async def stream_chat_response(self, websocket: WebSocket, response: str, 
                                   chunk_size: int = 50):
        """Stream a chat response in chunks for a typing effect."""
        words = response.split()
        for i in range(0, len(words), chunk_size):
            chunk = " ".join(words[i:i + chunk_size])
            await self.send_personal_message({
                "type": "chat_chunk",
                "chunk": chunk,
                "done": i + chunk_size >= len(words)
            }, websocket)
            await asyncio.sleep(0.05)  # Small delay for streaming effect
    
    def get_stats(self) -> Dict[str, int]:
        """Get connection statistics."""
        return {
            "activity": len(self.activity_connections),
            "chat": len(self.chat_connections),
            "notifications": len(self.notification_connections),
            "total": (len(self.activity_connections) + 
                     len(self.chat_connections) + 
                     len(self.notification_connections))
        }


# Global connection manager instance
manager = ConnectionManager()


def get_websocket_manager() -> ConnectionManager:
    """Get the global WebSocket manager instance."""
    return manager

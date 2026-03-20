"""WebSocket routes for real-time updates."""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import structlog
from app.services.websocket_manager import get_websocket_manager

logger = structlog.get_logger()
router = APIRouter()


@router.websocket("/ws/activity")
async def websocket_activity(websocket: WebSocket):
    """WebSocket endpoint for real-time activity log updates."""
    manager = get_websocket_manager()
    await manager.connect(websocket, "activity")
    
    try:
        # Send initial connection confirmation
        await manager.send_personal_message({
            "type": "connected",
            "message": "Connected to activity stream"
        }, websocket)
        
        # Keep connection alive and handle incoming messages
        while True:
            data = await websocket.receive_text()
            # Echo back for ping/pong
            if data == "ping":
                await manager.send_personal_message({"type": "pong"}, websocket)
    
    except WebSocketDisconnect:
        await manager.disconnect(websocket, "activity")
        logger.info("activity_websocket_disconnected")
    except Exception as e:
        logger.error("activity_websocket_error", error=str(e))
        await manager.disconnect(websocket, "activity")


@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket endpoint for real-time chat with streaming responses."""
    manager = get_websocket_manager()
    await manager.connect(websocket, "chat")
    
    try:
        # Send initial connection confirmation
        await manager.send_personal_message({
            "type": "connected",
            "message": "Connected to chat"
        }, websocket)
        
        # Handle incoming chat messages
        while True:
            data = await websocket.receive_json()
            
            if data.get("type") == "ping":
                await manager.send_personal_message({"type": "pong"}, websocket)
                continue
            
            # Handle chat message
            message = data.get("message", "")
            if message:
                # Import here to avoid circular dependency
                from app.routes.chat import handle_chat_message
                
                # Send typing indicator
                await manager.send_personal_message({
                    "type": "typing",
                    "typing": True
                }, websocket)
                
                # Process the message
                response = await handle_chat_message(
                    message=message,
                    history=data.get("history", []),
                    hours_back=data.get("hours_back", 24)
                )
                
                # Stream the response
                await manager.stream_chat_response(websocket, response)
    
    except WebSocketDisconnect:
        await manager.disconnect(websocket, "chat")
        logger.info("chat_websocket_disconnected")
    except Exception as e:
        logger.error("chat_websocket_error", error=str(e))
        await manager.disconnect(websocket, "chat")


@router.websocket("/ws/notifications")
async def websocket_notifications(websocket: WebSocket):
    """WebSocket endpoint for real-time notifications (PRs, errors, etc.)."""
    manager = get_websocket_manager()
    await manager.connect(websocket, "notifications")
    
    try:
        # Send initial connection confirmation
        await manager.send_personal_message({
            "type": "connected",
            "message": "Connected to notifications"
        }, websocket)
        
        # Keep connection alive
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await manager.send_personal_message({"type": "pong"}, websocket)
    
    except WebSocketDisconnect:
        await manager.disconnect(websocket, "notifications")
        logger.info("notifications_websocket_disconnected")
    except Exception as e:
        logger.error("notifications_websocket_error", error=str(e))
        await manager.disconnect(websocket, "notifications")


@router.get("/ws/stats")
async def websocket_stats():
    """Get WebSocket connection statistics."""
    manager = get_websocket_manager()
    return manager.get_stats()

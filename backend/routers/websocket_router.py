import json
import asyncio
import logging
from typing import Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.db import conjunction_repo
from backend.utils.serialization import serialize_mongo_doc

logger = logging.getLogger("orbit_sentinel.websocket_router")

router = APIRouter()
connected_clients: Set[WebSocket] = set()

async def broadcast(message_dict: dict) -> None:
    """
    Broadcasts message to all connected WebSocket clients.
    """
    message_str = json.dumps(message_dict)
    # Use a copy of the connected clients set to prevent mutation during iteration
    for ws in list(connected_clients):
        try:
            await ws.send_text(message_str)
        except Exception as e:
            logger.debug(f"Failed to send broadcast to a client, removing client: {e}")
            connected_clients.discard(ws)

async def broadcast_message(message_dict: dict) -> None:
    """
    WebSocket broadcast helper for scheduler compatibility.
    """
    await broadcast(message_dict)

def get_broadcaster():
    """
    Returns the broadcast function for dependency injection.
    """
    return broadcast

@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    connected_clients.add(ws)
    logger.info(f"WebSocket client connected. Total clients: {len(connected_clients)}")
    
    # Send initial state immediately on connect
    try:
        from backend.db.mongo_client import get_db
        db = get_db()
        conjunctions = await conjunction_repo.get_active_conjunctions(db)
        
        # Serialize documents to handle MongoDB ObjectIds before JSON conversion
        serialized_conjunctions = [
            serialize_mongo_doc(c.to_dict() if hasattr(c, 'to_dict') else c) 
            for c in conjunctions[:20]
        ]
        
        initial_payload = {
            "type": "initial_state",
            "conjunctions": serialized_conjunctions,
            "total": len(conjunctions)
        }
        await ws.send_text(json.dumps(initial_payload))
    except Exception as e:
        logger.error(f"Failed to send initial state to WebSocket client: {e}")
        
    try:
        while True:
            # Echo back ping messages for keepalive or handle messages
            data = await ws.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await ws.send_text(json.dumps({"type": "pong"}))
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        connected_clients.discard(ws)
        logger.info(f"WebSocket client disconnected safely. Total clients: {len(connected_clients)}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        connected_clients.discard(ws)
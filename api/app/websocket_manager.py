"""WebSocket connection manager for real-time notifications."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Dict, Set

from fastapi import WebSocket

from .cache import get_redis

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections and broadcasts notifications."""
    
    def __init__(self):
        # Map of user_id -> set of WebSocket connections
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()
        self._pubsub_task = None
        self._running = False
        self._max_connections = 15000
    
    async def connect(self, websocket: WebSocket, user_id: int) -> bool:
        """Accept and register a new WebSocket connection. Returns False if limit reached."""
        total_connections = sum(len(conns) for conns in self.active_connections.values())
        if total_connections >= self._max_connections:
            logger.warning(f"Connection limit reached ({self._max_connections}), rejecting connection")
            return False
        
        await websocket.accept()
        async with self._lock:
            if user_id not in self.active_connections:
                self.active_connections[user_id] = set()
            self.active_connections[user_id].add(websocket)
        logger.info(f"User {user_id} connected. Total connections: {self.get_connection_count()}")
        return True
    
    async def disconnect(self, websocket: WebSocket, user_id: int):
        """Remove a WebSocket connection."""
        async with self._lock:
            if user_id in self.active_connections:
                self.active_connections[user_id].discard(websocket)
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]
        logger.info(f"User {user_id} disconnected. Total connections: {self.get_connection_count()}")
    
    async def send_personal_message(self, message: dict, user_id: int):
        """Send a message to all connections for a specific user."""
        if user_id not in self.active_connections:
            return
        
        # Get copy of connections to avoid modification during iteration
        connections = list(self.active_connections[user_id])
        disconnected = []
        
        for websocket in connections:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error sending message to user {user_id}: {e}")
                disconnected.append(websocket)
        
        # Clean up disconnected sockets
        if disconnected:
            async with self._lock:
                for ws in disconnected:
                    if user_id in self.active_connections:
                        self.active_connections[user_id].discard(ws)
                if user_id in self.active_connections and not self.active_connections[user_id]:
                    del self.active_connections[user_id]
    
    def get_connection_count(self) -> int:
        """Get total number of active connections."""
        return sum(len(conns) for conns in self.active_connections.values())
    
    async def start_redis_listener(self):
        """Start Redis Pub/Sub listener for notification broadcasts."""
        if self._running:
            return
        
        self._running = True
        self._pubsub_task = asyncio.create_task(self._redis_listener())
        logger.info("Redis Pub/Sub listener started")
    
    async def stop_redis_listener(self):
        """Stop Redis Pub/Sub listener."""
        self._running = False
        if self._pubsub_task:
            self._pubsub_task.cancel()
            try:
                await self._pubsub_task
            except asyncio.CancelledError:
                pass
        logger.info("Redis Pub/Sub listener stopped")
    
    async def _redis_listener(self):
        """Listen for Redis Pub/Sub messages and broadcast to WebSocket clients."""
        redis = get_redis()
        if not redis:
            logger.error("Redis not available, cannot start Pub/Sub listener")
            return
        
        pubsub = redis.pubsub()
        
        # Subscribe to all notification channels (pattern matching)
        pubsub.psubscribe("notifications:user:*")
        
        try:
            while self._running:
                message = pubsub.get_message(timeout=1.0)
                if message and message['type'] == 'pmessage':
                    try:
                        # Extract user_id from channel name
                        channel = message['channel']
                        if isinstance(channel, bytes):
                            channel = channel.decode('utf-8')
                        user_id = int(channel.split(':')[-1])
                        
                        # Parse notification payload
                        data = message['data']
                        if isinstance(data, bytes):
                            data = data.decode('utf-8')
                        payload = json.loads(data)
                        
                        # Broadcast to all user's connections
                        await self.send_personal_message(payload, user_id)
                    except Exception as e:
                        logger.error(f"Error processing Redis message: {e}")
                
                # Small sleep to prevent busy-waiting
                await asyncio.sleep(0.01)
        except Exception as e:
            logger.error(f"Redis listener error: {e}")
        finally:
            try:
                pubsub.punsubscribe("notifications:user:*")
                pubsub.close()
            except Exception as e:
                logger.error(f"Error closing Redis Pub/Sub: {e}")


# Global connection manager instance
connection_manager = ConnectionManager()

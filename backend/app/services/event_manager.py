import asyncio
import json
from typing import Dict, List, AsyncGenerator
from collections import defaultdict

class EventManager:
    def __init__(self):
        # Map user_id to a list of active connection queues
        self.active_connections: Dict[int, List[asyncio.Queue]] = defaultdict(list)

    async def connect(self, user_id: int) -> AsyncGenerator[str, None]:
        """
        Creates a new connection queue for a user and yields messages as they arrive.
        """
        queue = asyncio.Queue()
        self.active_connections[user_id].append(queue)
        
        try:
            # Yield initial connection message or ping
            yield self._format_sse("CONNECTED", {"message": "Connected to event stream"})
            
            while True:
                # Wait for next message
                message = await queue.get()
                yield message
        except asyncio.CancelledError:
            # Client disconnected
            pass
        finally:
            # Cleanup
            if queue in self.active_connections[user_id]:
                self.active_connections[user_id].remove(queue)
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]

    async def emit(self, user_id: int, event_type: str, data: dict):
        """
        Pushes an event to all active connections for a specific user.
        """
        if user_id in self.active_connections:
            message = self._format_sse(event_type, data)
            connections = self.active_connections[user_id]
            # Create tasks to put messages in queues to avoid blocking
            # But Queue.put is not async unless maxsize is reached.
            # Here we assume infinite size so it's instant.
            for queue in connections:
                queue.put_nowait(message)

    def _format_sse(self, event_type: str, data: dict) -> str:
        """
        Formats data as a Server-Sent Event string.
        """
        return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"

# Global instance
event_manager = EventManager()

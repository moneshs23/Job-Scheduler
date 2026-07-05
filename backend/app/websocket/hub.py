import asyncio
import json
import logging

from fastapi import WebSocket

from app.config.constants import REDIS_PUBSUB_CHANNEL
from app.queues.redis_client import get_redis

logger = logging.getLogger(__name__)


class ConnectionHub:
    """Tracks live WebSocket connections and fans out Redis pub/sub events to all of them."""

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._listener_task: asyncio.Task | None = None

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.add(ws)
        if self._listener_task is None:
            self._listener_task = asyncio.create_task(self._listen())

    def disconnect(self, ws: WebSocket) -> None:
        self._connections.discard(ws)

    async def broadcast(self, message: dict) -> None:
        dead = []
        for ws in self._connections:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    async def _listen(self) -> None:
        redis = get_redis()
        pubsub = redis.pubsub()
        await pubsub.subscribe(REDIS_PUBSUB_CHANNEL)
        try:
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                try:
                    data = json.loads(message["data"])
                except (TypeError, json.JSONDecodeError):
                    continue
                await self.broadcast(data)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("WebSocket pub/sub listener crashed")
        finally:
            await pubsub.unsubscribe(REDIS_PUBSUB_CHANNEL)


hub = ConnectionHub()

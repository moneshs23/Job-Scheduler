import json
from typing import Any

from redis.asyncio import Redis

from app.config.constants import REDIS_PUBSUB_CHANNEL


async def publish_event(redis: Redis, event_type: str, data: dict[str, Any]) -> None:
    payload = json.dumps({"type": event_type, "data": data}, default=str)
    await redis.publish(REDIS_PUBSUB_CHANNEL, payload)

import uuid

from redis.asyncio import Redis

from app.config.constants import REDIS_STREAM_PREFIX

STREAM_MAXLEN = 10_000


def stream_key(queue_id: uuid.UUID) -> str:
    return f"{REDIS_STREAM_PREFIX}{queue_id}"


async def publish_job_ready(redis: Redis, queue_id: uuid.UUID, job_id: uuid.UUID) -> None:
    """Wake up any worker blocked on this queue's stream. Postgres remains the source of truth —
    this is purely a low-latency nudge so workers don't have to poll on a fixed interval."""
    await redis.xadd(
        stream_key(queue_id),
        {"job_id": str(job_id)},
        maxlen=STREAM_MAXLEN,
        approximate=True,
    )


async def wait_for_notifications(
    redis: Redis, queue_ids: list[uuid.UUID], block_ms: int
) -> dict[str, list]:
    """Block until any of the given queues receive a notification, or block_ms elapses.

    Reads only new entries (id '$') so this never replays history — it is a wake signal,
    not a durable log.
    """
    if not queue_ids:
        return {}
    streams = {stream_key(qid): "$" for qid in queue_ids}
    result = await redis.xread(streams, block=block_ms, count=100)
    return dict(result) if result else {}

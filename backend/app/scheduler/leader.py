import asyncio
import logging
import uuid

from redis.asyncio import Redis

LEADER_KEY = "scheduler:leader"

logger = logging.getLogger(__name__)


class LeaderElection:
    """Redis-lock-based leader election so exactly one scheduler instance runs scans,
    even when the scheduler service is horizontally scaled for availability."""

    def __init__(self, redis: Redis, ttl_sec: int):
        self.redis = redis
        self.ttl_sec = ttl_sec
        self.instance_id = str(uuid.uuid4())
        self._is_leader = False

    @property
    def is_leader(self) -> bool:
        return self._is_leader

    async def try_acquire_or_renew(self) -> bool:
        acquired = await self.redis.set(LEADER_KEY, self.instance_id, nx=True, ex=self.ttl_sec)
        if acquired:
            self._is_leader = True
            return True

        current = await self.redis.get(LEADER_KEY)
        if current == self.instance_id:
            await self.redis.expire(LEADER_KEY, self.ttl_sec)
            self._is_leader = True
            return True

        self._is_leader = False
        return False

    async def run_forever(self) -> None:
        while True:
            try:
                was_leader = self._is_leader
                is_leader = await self.try_acquire_or_renew()
                if is_leader and not was_leader:
                    logger.info("Scheduler instance %s became leader", self.instance_id)
                elif not is_leader and was_leader:
                    logger.info("Scheduler instance %s lost leadership", self.instance_id)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Leader election renewal failed")
                self._is_leader = False
            await asyncio.sleep(self.ttl_sec / 3)

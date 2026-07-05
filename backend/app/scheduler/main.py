import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config.settings import get_settings
from app.queues.redis_client import get_redis
from app.scheduler.leader import LeaderElection
from app.scheduler.service import scan_cron_jobs, scan_delayed_jobs

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    settings = get_settings()
    redis = get_redis()
    election = LeaderElection(redis, settings.scheduler_leader_lock_ttl_sec)
    election_task = asyncio.create_task(election.run_forever())

    async def guarded_scan_delayed() -> None:
        if election.is_leader:
            await scan_delayed_jobs()

    async def guarded_scan_cron() -> None:
        if election.is_leader:
            await scan_cron_jobs()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(guarded_scan_delayed, "interval", seconds=settings.scheduler_scan_interval_sec, id="scan_delayed_jobs")
    scheduler.add_job(guarded_scan_cron, "interval", seconds=settings.scheduler_scan_interval_sec, id="scan_cron_jobs")

    scheduler.start()
    logger.info("Scheduler service started (instance %s)", election.instance_id)
    try:
        await asyncio.Event().wait()
    finally:
        election_task.cancel()
        scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())

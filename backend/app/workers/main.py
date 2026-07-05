import asyncio
import logging
import os
import signal
import sys
import uuid

from app.workers.worker import WorkerProcess

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


async def main() -> None:
    project_id_raw = os.environ.get("WORKER_PROJECT_ID")
    if not project_id_raw:
        print("WORKER_PROJECT_ID environment variable is required", file=sys.stderr)
        sys.exit(1)

    worker = WorkerProcess(
        project_id=uuid.UUID(project_id_raw),
        worker_type=os.environ.get("WORKER_TYPE", "generic"),
        concurrency=int(os.environ["WORKER_CONCURRENCY"]) if os.environ.get("WORKER_CONCURRENCY") else None,
    )

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, worker.request_shutdown)

    await worker.start()


if __name__ == "__main__":
    asyncio.run(main())

from __future__ import annotations

import asyncio

from gpu_worker.config import WorkerConfig
from gpu_worker.pool import WorkerPool


async def main() -> None:
    """Start the GPU analysis worker pool and wait until interrupted."""

    config = WorkerConfig()
    pool = WorkerPool([config])
    await pool.start_all()
    print("GPU Analysis Worker Pool started")
    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        await pool.shutdown_all()
        print("Worker pool shut down")


if __name__ == "__main__":
    asyncio.run(main())

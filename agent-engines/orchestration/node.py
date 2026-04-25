from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

from gpu_worker.models import AnalysisRequest, AnalysisResult
from gpu_worker.pool import WorkerPool

from orchestration.models import NodeInfo, NodeStatus

SubmitHandler = Callable[[AnalysisRequest], Awaitable[AnalysisResult]]
HealthHandler = Callable[[], Awaitable[bool] | bool]


class EngineNode:
    """Represents a remote or local engine node."""

    def __init__(
        self,
        info: NodeInfo,
        *,
        worker_pool: WorkerPool | None = None,
        submit_handler: SubmitHandler | None = None,
        health_handler: HealthHandler | None = None,
        simulated_latency_ms: float = 0.0,
    ) -> None:
        self.info = info.model_copy(deep=True)
        self._worker_pool = worker_pool
        self._submit_handler = submit_handler or (worker_pool.submit if worker_pool is not None else None)
        self._health_handler = health_handler
        self._simulated_latency_ms = simulated_latency_ms
        self._condition = asyncio.Condition()

    @property
    def available_capacity(self) -> int:
        """Return the remaining request slots for the node."""

        return max(self.info.max_concurrent - self.info.current_load, 0)

    def attach_worker_pool(self, worker_pool: WorkerPool) -> None:
        """Attach a local worker pool for request execution."""

        self._worker_pool = worker_pool
        self._submit_handler = worker_pool.submit

    def set_health_handler(self, health_handler: HealthHandler | None) -> None:
        """Set or replace the health-check callback for the node."""

        self._health_handler = health_handler

    async def submit_analysis(self, request: AnalysisRequest) -> AnalysisResult:
        """Submit an analysis request to this node."""

        if self.info.status is not NodeStatus.ONLINE:
            raise RuntimeError(f"node {self.info.node_id} is not accepting work")
        if self._submit_handler is None:
            raise RuntimeError(f"node {self.info.node_id} has no submission handler configured")

        async with self._condition:
            if self.available_capacity <= 0:
                raise RuntimeError(f"node {self.info.node_id} has no available capacity")
            self.info.current_load += 1

        try:
            if self._simulated_latency_ms > 0:
                await asyncio.sleep(self._simulated_latency_ms / 1000)
            return await self._submit_handler(request)
        finally:
            async with self._condition:
                self.info.current_load -= 1
                self._condition.notify_all()

    async def health_check(self) -> bool:
        """Check if the node is healthy and responsive."""

        if self.info.status is NodeStatus.OFFLINE:
            return False

        healthy = True
        if self._health_handler is not None:
            result = self._health_handler()
            healthy = await result if asyncio.iscoroutine(result) else bool(result)

        if healthy:
            self.info.last_heartbeat = datetime.now(timezone.utc)
            if self.info.status is NodeStatus.UNHEALTHY:
                self.info.status = NodeStatus.ONLINE
        return healthy

    async def drain(self) -> None:
        """Stop accepting new work and wait for in-flight work to finish."""

        self.info.status = NodeStatus.DRAINING
        async with self._condition:
            await self._condition.wait_for(lambda: self.info.current_load == 0)

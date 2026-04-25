from __future__ import annotations

import asyncio
from contextlib import suppress

from orchestration.config import OrchestrationConfig
from orchestration.models import NodeStatus
from orchestration.node import EngineNode
from orchestration.registry import NodeRegistry


class HealthMonitor:
    """Background health checker for registered nodes."""

    def __init__(self, registry: NodeRegistry, config: OrchestrationConfig) -> None:
        self._registry = registry
        self._config = config
        self._missed_heartbeats: dict[str, int] = {}
        self._task: asyncio.Task[None] | None = None
        self._stopped = asyncio.Event()
        self._stopped.set()

    async def start(self) -> None:
        """Start the background health check loop."""

        if self._task is not None and not self._task.done():
            return
        self._stopped.clear()
        self._task = asyncio.create_task(self._check_loop())

    async def stop(self) -> None:
        """Stop the background health check loop."""

        self._stopped.set()
        if self._task is not None:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def _check_loop(self) -> None:
        """Periodically check all nodes and mark unhealthy nodes."""

        try:
            while not self._stopped.is_set():
                nodes = self._registry.get_all_nodes()
                if nodes:
                    await asyncio.gather(*(self._check_node(node) for node in nodes))
                await asyncio.sleep(self._config.heartbeat_interval_seconds)
        except asyncio.CancelledError:
            raise

    async def _check_node(self, node: EngineNode) -> bool:
        """Perform a single health check on a node."""

        if node.info.status is NodeStatus.OFFLINE:
            return False

        healthy = False
        try:
            healthy = await asyncio.wait_for(
                node.health_check(),
                timeout=self._config.health_check_timeout_seconds,
            )
        except Exception:
            healthy = False

        if healthy:
            self._missed_heartbeats[node.info.node_id] = 0
            if node.info.status is NodeStatus.UNHEALTHY:
                node.info.status = NodeStatus.ONLINE
            return True

        misses = self._missed_heartbeats.get(node.info.node_id, 0) + 1
        self._missed_heartbeats[node.info.node_id] = misses
        if misses >= self._config.unhealthy_threshold:
            node.info.status = NodeStatus.UNHEALTHY
        return False

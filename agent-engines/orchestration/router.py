from __future__ import annotations

import asyncio
from collections import deque

from gpu_worker.models import AnalysisRequest, AnalysisResult

from orchestration.config import OrchestrationConfig
from orchestration.models import OrchestrationEvent
from orchestration.registry import NodeRegistry
from orchestration.scheduler import NoAvailableNodesError, RequestScheduler


class AnalysisRouter:
    """High-level router that submits requests with retry and failover."""

    def __init__(
        self,
        registry: NodeRegistry,
        scheduler: RequestScheduler,
        config: OrchestrationConfig,
    ) -> None:
        self._registry = registry
        self._scheduler = scheduler
        self._config = config
        self._events: deque[OrchestrationEvent] = deque(maxlen=config.event_log_size)

    async def route(self, request: AnalysisRequest) -> AnalysisResult:
        """Route a request to the best available node with retry logic."""

        return await self._route_with_capability(request)

    async def route_batch(self, requests: list[AnalysisRequest]) -> list[AnalysisResult]:
        """Route multiple requests, distributing them across nodes."""

        if not requests:
            return []

        return await asyncio.gather(
            *(self.route(request) for request in requests)
        )

    def get_recent_events(self, limit: int = 50) -> list[OrchestrationEvent]:
        """Return the most recent orchestration events."""

        if limit <= 0:
            return []
        return list(self._events)[-limit:]

    async def _route_with_capability(
        self,
        request: AnalysisRequest,
        required_capability: NodeCapability | None = None,
    ) -> AnalysisResult:
        attempted_nodes: set[str] = set()
        attempts = 1 + max(self._config.max_retries, 0)
        last_error: Exception | None = None

        for attempt in range(attempts):
            try:
                decision = self._scheduler.select_node(
                    request,
                    required_capability,
                    exclude_node_ids=attempted_nodes,
                )
            except NoAvailableNodesError as exc:
                if last_error is not None:
                    raise last_error
                raise exc

            node = self._registry.get_node(decision.node_id)
            if node is None:
                attempted_nodes.add(decision.node_id)
                last_error = NoAvailableNodesError(f"node {decision.node_id} is no longer registered")
                continue

            self._record_event(
                "request_routed",
                node_id=node.info.node_id,
                details={
                    "request_id": request.id,
                    "reason": decision.reason,
                    "attempt": attempt + 1,
                    "latency_estimate_ms": decision.latency_estimate_ms,
                },
            )

            try:
                return await node.submit_analysis(request)
            except Exception as exc:
                attempted_nodes.add(node.info.node_id)
                last_error = exc
                if not self._config.enable_failover or attempt >= attempts - 1:
                    raise
                self._record_event(
                    "failover",
                    node_id=node.info.node_id,
                    details={
                        "request_id": request.id,
                        "attempt": attempt + 1,
                        "error": str(exc),
                    },
                )

        if last_error is not None:
            raise last_error
        raise NoAvailableNodesError("no available nodes for analysis request")

    def _record_event(
        self,
        event_type: str,
        *,
        node_id: str | None = None,
        details: dict[str, object] | None = None,
    ) -> None:
        self._events.append(
            OrchestrationEvent(
                event_type=event_type,
                node_id=node_id,
                details=details or {},
            )
        )

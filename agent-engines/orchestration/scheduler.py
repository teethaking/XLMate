from __future__ import annotations

from gpu_worker.models import AnalysisRequest

from orchestration.config import OrchestrationConfig
from orchestration.models import NodeCapability, RoutingDecision
from orchestration.node import EngineNode
from orchestration.registry import NodeRegistry


class NoAvailableNodesError(RuntimeError):
    """Raised when the registry has no suitable nodes for a request."""


class RequestScheduler:
    """Schedules analysis requests across available nodes."""

    def __init__(self, registry: NodeRegistry, config: OrchestrationConfig) -> None:
        self._registry = registry
        self._config = config
        self._round_robin_index = 0

    def select_node(
        self,
        request: AnalysisRequest,
        required_capability: NodeCapability | None = None,
        *,
        exclude_node_ids: set[str] | None = None,
    ) -> RoutingDecision:
        """Select the best node for a request based on load balancing strategy."""

        candidates = self._registry.get_available_nodes(required_capability)
        if exclude_node_ids:
            candidates = [node for node in candidates if node.info.node_id not in exclude_node_ids]
        if not candidates:
            raise NoAvailableNodesError("no available nodes for analysis request")

        strategy = self._config.load_balance_strategy
        if strategy == "round_robin":
            node = self._select_round_robin(candidates)
            reason = "selected using round_robin"
        elif strategy == "capability_match":
            node = self._select_capability_match(candidates, required_capability)
            if required_capability is not None and required_capability in node.info.capabilities:
                reason = f"matched capability {required_capability.value}"
            else:
                reason = "selected using capability_match fallback"
        else:
            node = self._select_least_loaded(candidates)
            reason = "selected using least_loaded"

        return RoutingDecision(
            node_id=node.info.node_id,
            reason=reason,
            latency_estimate_ms=self._estimate_latency(node),
        )

    def _select_least_loaded(self, candidates: list[EngineNode]) -> EngineNode:
        return min(
            candidates,
            key=lambda node: (
                -node.available_capacity,
                node.info.current_load,
                node.info.address,
                node.info.node_id,
            ),
        )

    def _select_round_robin(self, candidates: list[EngineNode]) -> EngineNode:
        ordered = sorted(candidates, key=lambda node: (node.info.address, node.info.node_id))
        node = ordered[self._round_robin_index % len(ordered)]
        self._round_robin_index = (self._round_robin_index + 1) % len(ordered)
        return node

    def _select_capability_match(
        self,
        candidates: list[EngineNode],
        required_capability: NodeCapability | None,
    ) -> EngineNode:
        if required_capability is None:
            return self._select_least_loaded(candidates)
        matching = [node for node in candidates if required_capability in node.info.capabilities]
        return self._select_least_loaded(matching or candidates)

    def _estimate_latency(self, node: EngineNode) -> float:
        utilization = 0.0
        if node.info.max_concurrent > 0:
            utilization = node.info.current_load / node.info.max_concurrent
        return round(5.0 + utilization * 50.0, 2)

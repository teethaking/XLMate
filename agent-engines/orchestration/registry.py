from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timezone

from orchestration.node import EngineNode
from orchestration.models import NodeCapability, NodeInfo, NodeStatus


class NodeRegistry:
    """Registry for tracking available engine nodes."""

    def __init__(self, *, node_factory: Callable[[NodeInfo], EngineNode] | None = None) -> None:
        self._nodes: dict[str, EngineNode] = {}
        self._lock = asyncio.Lock()
        self._node_factory = node_factory or EngineNode

    async def register(self, node_info: NodeInfo) -> EngineNode:
        """Register a new node."""

        node = self._node_factory(node_info)
        return await self.register_node(node)

    async def register_node(self, node: EngineNode) -> EngineNode:
        """Register an already constructed engine node."""

        async with self._lock:
            node.info.last_heartbeat = datetime.now(timezone.utc)
            self._nodes[node.info.node_id] = node
            return node

    async def deregister(self, node_id: str) -> None:
        """Remove a node from the registry."""

        async with self._lock:
            node = self._nodes.pop(node_id, None)
            if node is not None:
                node.info.status = NodeStatus.OFFLINE

    def get_node(self, node_id: str) -> EngineNode | None:
        """Return a registered node by identifier."""

        return self._nodes.get(node_id)

    def get_available_nodes(self, capability: NodeCapability | None = None) -> list[EngineNode]:
        """Get nodes that are online and have available capacity."""

        nodes = [
            node
            for node in self._nodes.values()
            if node.info.status is NodeStatus.ONLINE and node.available_capacity > 0
        ]
        if capability is not None:
            nodes = [node for node in nodes if capability in node.info.capabilities]
        return sorted(nodes, key=lambda node: node.info.node_id)

    def get_all_nodes(self) -> list[EngineNode]:
        """Return all registered nodes."""

        return sorted(self._nodes.values(), key=lambda node: node.info.node_id)

    @property
    def online_count(self) -> int:
        """Return the number of nodes currently marked online."""

        return sum(1 for node in self._nodes.values() if node.info.status is NodeStatus.ONLINE)

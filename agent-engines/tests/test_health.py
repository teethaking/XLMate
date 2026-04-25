from __future__ import annotations

import pytest

from orchestration.config import OrchestrationConfig
from orchestration.health import HealthMonitor
from orchestration.models import NodeCapability, NodeInfo, NodeStatus
from orchestration.node import EngineNode
from orchestration.registry import NodeRegistry


@pytest.mark.asyncio
async def test_health_monitor_marks_node_unhealthy_after_threshold() -> None:
    registry = NodeRegistry()
    node = EngineNode(
        NodeInfo(address="node-a:9000", capabilities=[NodeCapability.CPU_ANALYSIS]),
        health_handler=lambda: False,
    )
    await registry.register_node(node)
    monitor = HealthMonitor(
        registry,
        OrchestrationConfig(unhealthy_threshold=2, health_check_timeout_seconds=0.1),
    )

    assert await monitor._check_node(node) is False
    assert node.info.status is NodeStatus.ONLINE

    assert await monitor._check_node(node) is False
    assert node.info.status is NodeStatus.UNHEALTHY


@pytest.mark.asyncio
async def test_health_monitor_recovers_node_on_heartbeat() -> None:
    healthy = False

    def check() -> bool:
        return healthy

    registry = NodeRegistry()
    node = EngineNode(
        NodeInfo(address="node-b:9000", capabilities=[NodeCapability.GPU_ANALYSIS]),
        health_handler=check,
    )
    await registry.register_node(node)
    monitor = HealthMonitor(
        registry,
        OrchestrationConfig(unhealthy_threshold=1, health_check_timeout_seconds=0.1),
    )

    assert await monitor._check_node(node) is False
    assert node.info.status is NodeStatus.UNHEALTHY

    healthy = True
    assert await monitor._check_node(node) is True
    assert node.info.status is NodeStatus.ONLINE
    assert node.info.last_heartbeat is not None

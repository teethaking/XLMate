from __future__ import annotations

import asyncio

import pytest

from orchestration.models import NodeCapability, NodeInfo
from orchestration.registry import NodeRegistry


@pytest.mark.asyncio
async def test_registry_registers_and_deregisters_nodes() -> None:
    registry = NodeRegistry()
    node = await registry.register(
        NodeInfo(address="node-a:9000", capabilities=[NodeCapability.GPU_ANALYSIS])
    )

    assert registry.get_node(node.info.node_id) is node
    assert registry.online_count == 1

    await registry.deregister(node.info.node_id)

    assert registry.get_node(node.info.node_id) is None
    assert registry.online_count == 0


@pytest.mark.asyncio
async def test_registry_filters_by_capability() -> None:
    registry = NodeRegistry()
    await registry.register(
        NodeInfo(address="gpu-node:9000", capabilities=[NodeCapability.GPU_ANALYSIS])
    )
    await registry.register(
        NodeInfo(address="cpu-node:9000", capabilities=[NodeCapability.CPU_ANALYSIS])
    )

    gpu_nodes = registry.get_available_nodes(NodeCapability.GPU_ANALYSIS)

    assert len(gpu_nodes) == 1
    assert gpu_nodes[0].info.address == "gpu-node:9000"


@pytest.mark.asyncio
async def test_registry_handles_concurrent_registration() -> None:
    registry = NodeRegistry()

    async def register_node(index: int) -> None:
        await registry.register(
            NodeInfo(
                address=f"node-{index}:9000",
                capabilities=[NodeCapability.CPU_ANALYSIS],
            )
        )

    await asyncio.gather(*(register_node(index) for index in range(20)))

    assert len(registry.get_all_nodes()) == 20
    assert registry.online_count == 20

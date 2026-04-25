from __future__ import annotations

import pytest

from gpu_worker.models import AnalysisRequest
from orchestration.config import OrchestrationConfig
from orchestration.models import NodeCapability, NodeInfo
from orchestration.registry import NodeRegistry
from orchestration.scheduler import NoAvailableNodesError, RequestScheduler


def make_request() -> AnalysisRequest:
    return AnalysisRequest(fen="8/8/8/8/8/8/8/K6k w - - 0 1")


@pytest.mark.asyncio
async def test_scheduler_selects_least_loaded_node() -> None:
    registry = NodeRegistry()
    first = await registry.register(
        NodeInfo(address="node-a:9000", capabilities=[NodeCapability.GPU_ANALYSIS], max_concurrent=4)
    )
    second = await registry.register(
        NodeInfo(address="node-b:9000", capabilities=[NodeCapability.GPU_ANALYSIS], max_concurrent=4)
    )
    first.info.current_load = 3
    second.info.current_load = 1

    scheduler = RequestScheduler(registry, OrchestrationConfig(load_balance_strategy="least_loaded"))
    decision = scheduler.select_node(make_request())

    assert decision.node_id == second.info.node_id
    assert decision.reason == "selected using least_loaded"


@pytest.mark.asyncio
async def test_scheduler_uses_round_robin_strategy() -> None:
    registry = NodeRegistry()
    first = await registry.register(
        NodeInfo(address="node-a:9000", capabilities=[NodeCapability.CPU_ANALYSIS])
    )
    second = await registry.register(
        NodeInfo(address="node-b:9000", capabilities=[NodeCapability.CPU_ANALYSIS])
    )
    scheduler = RequestScheduler(registry, OrchestrationConfig(load_balance_strategy="round_robin"))

    selections = [scheduler.select_node(make_request()).node_id for _ in range(4)]

    assert selections == [first.info.node_id, second.info.node_id, first.info.node_id, second.info.node_id]


@pytest.mark.asyncio
async def test_scheduler_prefers_matching_capability() -> None:
    registry = NodeRegistry()
    cpu = await registry.register(
        NodeInfo(address="cpu-node:9000", capabilities=[NodeCapability.CPU_ANALYSIS])
    )
    batch = await registry.register(
        NodeInfo(
            address="batch-node:9000",
            capabilities=[NodeCapability.CPU_ANALYSIS, NodeCapability.BATCH_ANALYSIS],
        )
    )
    cpu.info.current_load = 0
    batch.info.current_load = 0

    scheduler = RequestScheduler(registry, OrchestrationConfig(load_balance_strategy="capability_match"))
    decision = scheduler.select_node(make_request(), NodeCapability.BATCH_ANALYSIS)

    assert decision.node_id == batch.info.node_id
    assert decision.reason == "matched capability batch_analysis"


@pytest.mark.asyncio
async def test_scheduler_raises_when_no_nodes_available() -> None:
    registry = NodeRegistry()
    scheduler = RequestScheduler(registry, OrchestrationConfig())

    with pytest.raises(NoAvailableNodesError):
        scheduler.select_node(make_request())

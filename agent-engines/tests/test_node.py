from __future__ import annotations

import asyncio

import pytest

from gpu_worker.models import AnalysisRequest, AnalysisResult
from orchestration.models import NodeCapability, NodeInfo, NodeStatus
from orchestration.node import EngineNode


@pytest.mark.asyncio
async def test_node_creation_and_capacity_tracking() -> None:
    async def submit(request: AnalysisRequest) -> AnalysisResult:
        await asyncio.sleep(0.02)
        return AnalysisResult(request_id=request.id, best_move="e2e4")

    node = EngineNode(
        NodeInfo(
            address="node-a:9000",
            capabilities=[NodeCapability.GPU_ANALYSIS],
            max_concurrent=2,
        ),
        submit_handler=submit,
    )

    request = AnalysisRequest(fen="8/8/8/8/8/8/8/K6k w - - 0 1")
    task = asyncio.create_task(node.submit_analysis(request))
    await asyncio.sleep(0.005)

    assert node.available_capacity == 1
    result = await task

    assert result.best_move == "e2e4"
    assert node.available_capacity == 2
    assert node.info.status is NodeStatus.ONLINE


@pytest.mark.asyncio
async def test_node_health_check_restores_online_status() -> None:
    node = EngineNode(
        NodeInfo(
            address="node-b:9000",
            capabilities=[NodeCapability.CPU_ANALYSIS],
            status=NodeStatus.UNHEALTHY,
        ),
        health_handler=lambda: True,
    )

    healthy = await node.health_check()

    assert healthy is True
    assert node.info.status is NodeStatus.ONLINE
    assert node.info.last_heartbeat is not None


@pytest.mark.asyncio
async def test_node_drain_waits_for_inflight_work() -> None:
    started = asyncio.Event()
    release = asyncio.Event()

    async def submit(request: AnalysisRequest) -> AnalysisResult:
        started.set()
        await release.wait()
        return AnalysisResult(request_id=request.id, best_move="d2d4")

    node = EngineNode(
        NodeInfo(
            address="node-c:9000",
            capabilities=[NodeCapability.GPU_ANALYSIS],
            max_concurrent=1,
        ),
        submit_handler=submit,
    )

    request = AnalysisRequest(fen="8/8/8/8/8/8/8/K6k w - - 0 1")
    analysis_task = asyncio.create_task(node.submit_analysis(request))
    await started.wait()

    drain_task = asyncio.create_task(node.drain())
    await asyncio.sleep(0.005)

    assert node.info.status is NodeStatus.DRAINING
    with pytest.raises(RuntimeError):
        await node.submit_analysis(AnalysisRequest(fen="8/8/8/8/8/8/8/K6k w - - 0 1"))

    release.set()
    await analysis_task
    await drain_task

    assert node.info.current_load == 0

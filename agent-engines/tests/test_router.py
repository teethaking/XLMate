from __future__ import annotations

import asyncio

import pytest

from gpu_worker.models import AnalysisRequest, AnalysisResult
from orchestration.config import OrchestrationConfig
from orchestration.models import NodeCapability, NodeInfo
from orchestration.node import EngineNode
from orchestration.registry import NodeRegistry
from orchestration.router import AnalysisRouter
from orchestration.scheduler import RequestScheduler


def make_request() -> AnalysisRequest:
    return AnalysisRequest(fen="8/8/8/8/8/8/8/K6k w - - 0 1")


@pytest.mark.asyncio
async def test_router_routes_successfully() -> None:
    async def submit(request: AnalysisRequest) -> AnalysisResult:
        return AnalysisResult(request_id=request.id, best_move="e2e4")

    registry = NodeRegistry()
    node = EngineNode(
        NodeInfo(address="node-a:9000", capabilities=[NodeCapability.GPU_ANALYSIS]),
        submit_handler=submit,
    )
    await registry.register_node(node)
    router = AnalysisRouter(registry, RequestScheduler(registry, OrchestrationConfig()), OrchestrationConfig())

    result = await router.route(make_request())

    assert result.best_move == "e2e4"
    assert router.get_recent_events(limit=1)[0].event_type == "request_routed"


@pytest.mark.asyncio
async def test_router_retries_failed_requests_on_different_node() -> None:
    failed_attempts: list[str] = []

    async def fail_submit(request: AnalysisRequest) -> AnalysisResult:
        failed_attempts.append(request.id)
        raise RuntimeError("node failure")

    async def succeed_submit(request: AnalysisRequest) -> AnalysisResult:
        return AnalysisResult(request_id=request.id, best_move="g1f3")

    registry = NodeRegistry()
    first = EngineNode(
        NodeInfo(address="node-a:9000", capabilities=[NodeCapability.GPU_ANALYSIS]),
        submit_handler=fail_submit,
    )
    second = EngineNode(
        NodeInfo(address="node-b:9000", capabilities=[NodeCapability.GPU_ANALYSIS]),
        submit_handler=succeed_submit,
    )
    await registry.register_node(first)
    await registry.register_node(second)
    config = OrchestrationConfig(max_retries=1, enable_failover=True)
    router = AnalysisRouter(registry, RequestScheduler(registry, config), config)

    result = await router.route(make_request())
    events = router.get_recent_events()

    assert result.best_move == "g1f3"
    assert len(failed_attempts) == 1
    assert [event.event_type for event in events] == ["request_routed", "failover", "request_routed"]
    assert events[-1].node_id == second.info.node_id


@pytest.mark.asyncio
async def test_router_raises_after_retry_exhaustion() -> None:
    async def fail_submit(request: AnalysisRequest) -> AnalysisResult:
        raise RuntimeError(f"failure for {request.id}")

    registry = NodeRegistry()
    node = EngineNode(
        NodeInfo(address="node-a:9000", capabilities=[NodeCapability.CPU_ANALYSIS]),
        submit_handler=fail_submit,
    )
    await registry.register_node(node)
    config = OrchestrationConfig(max_retries=0, enable_failover=True)
    router = AnalysisRouter(registry, RequestScheduler(registry, config), config)

    with pytest.raises(RuntimeError, match="failure"):
        await router.route(make_request())


@pytest.mark.asyncio
async def test_router_distributes_batch_requests_across_nodes() -> None:
    usage: list[str] = []

    async def submit_from(name: str, request: AnalysisRequest) -> AnalysisResult:
        usage.append(name)
        await asyncio.sleep(0.02)
        return AnalysisResult(request_id=request.id, best_move=name)

    registry = NodeRegistry()
    first = EngineNode(
        NodeInfo(address="node-a:9000", capabilities=[NodeCapability.BATCH_ANALYSIS], max_concurrent=1),
        submit_handler=lambda request: submit_from("node-a", request),
    )
    second = EngineNode(
        NodeInfo(address="node-b:9000", capabilities=[NodeCapability.BATCH_ANALYSIS], max_concurrent=1),
        submit_handler=lambda request: submit_from("node-b", request),
    )
    await registry.register_node(first)
    await registry.register_node(second)
    config = OrchestrationConfig(max_retries=0)
    router = AnalysisRouter(registry, RequestScheduler(registry, config), config)

    results = await router.route_batch([make_request(), make_request()])

    assert {result.best_move for result in results} == {"node-a", "node-b"}
    assert set(usage) == {"node-a", "node-b"}

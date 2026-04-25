from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
import uuid

from pydantic import BaseModel, Field


class NodeCapability(str, Enum):
    """Capabilities advertised by an engine node."""

    GPU_ANALYSIS = "gpu_analysis"
    CPU_ANALYSIS = "cpu_analysis"
    BATCH_ANALYSIS = "batch_analysis"
    PERSONALITY = "personality"


class NodeStatus(str, Enum):
    """Runtime availability state for an engine node."""

    ONLINE = "online"
    OFFLINE = "offline"
    DRAINING = "draining"
    UNHEALTHY = "unhealthy"


class NodeInfo(BaseModel):
    """Serializable description of an engine node."""

    node_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    address: str
    capabilities: list[NodeCapability] = Field(default_factory=list)
    status: NodeStatus = NodeStatus.ONLINE
    gpu_devices: int = 0
    max_concurrent: int = 8
    current_load: int = 0
    last_heartbeat: datetime | None = None
    region: str = "default"
    metadata: dict[str, Any] = Field(default_factory=dict)


class RoutingDecision(BaseModel):
    """Scheduler decision for assigning a request to a node."""

    node_id: str
    reason: str
    latency_estimate_ms: float | None = None


class OrchestrationEvent(BaseModel):
    """In-memory event emitted by the orchestration layer."""

    event_type: str
    node_id: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict[str, Any] = Field(default_factory=dict)

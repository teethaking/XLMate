from __future__ import annotations

from pydantic import BaseModel


class OrchestrationConfig(BaseModel):
    """Configuration for decentralized engine orchestration."""

    heartbeat_interval_seconds: float = 10.0
    health_check_timeout_seconds: float = 5.0
    unhealthy_threshold: int = 3
    max_retries: int = 2
    drain_timeout_seconds: float = 60.0
    load_balance_strategy: str = "least_loaded"
    enable_failover: bool = True
    event_log_size: int = 1000

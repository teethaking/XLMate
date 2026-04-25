# agent-engines

GPU-oriented engine infrastructure for the XLMate chess platform. The module provides an asyncio-based worker pool that wraps UCI-compatible engines, with first-class support for Leela Chess Zero (`lc0`) and CPU fallback support for Stockfish.

## Overview

The GPU worker subsystem is designed for long-running analysis services where neural-network inference should stay close to a dedicated GPU while requests are dispatched through a pool abstraction.

```text
Client/API
   |
   v
AnalysisRequest
   |
   v
WorkerPool ------------------> ResourceMonitor
   |
   +--> GPUAnalysisWorker #1 --> AsyncUciBridge --> lc0 / stockfish
   |
   +--> GPUAnalysisWorker #2 --> AsyncUciBridge --> lc0 / stockfish
   |
   +--> BatchAnalyzer (optional request coalescing)
```

## Package layout

- `gpu_worker/config.py`: worker and GPU configuration models.
- `gpu_worker/models.py`: request, result, and status models.
- `gpu_worker/uci_bridge.py`: async UCI subprocess bridge and protocol parsing.
- `gpu_worker/worker.py`: single-worker lifecycle and analysis orchestration.
- `gpu_worker/pool.py`: least-loaded worker dispatch.
- `gpu_worker/batch.py`: time- and size-based batching layer.
- `gpu_worker/resource_monitor.py`: CPU/GPU monitoring with graceful fallback.
- `orchestration/models.py`: node, routing, and event models for decentralized dispatch.
- `orchestration/node.py`: local/remote node abstraction around worker pools or network handlers.
- `orchestration/registry.py`: async-safe node registration and discovery.
- `orchestration/scheduler.py`: configurable request scheduling and load balancing strategies.
- `orchestration/health.py`: background heartbeat and health-check loop.
- `orchestration/router.py`: failover-aware request routing and bounded event logging.

## Requirements

- Python 3.11+
- A UCI-compliant engine binary
- For GPU acceleration with `lc0`:
  - NVIDIA drivers and CUDA/cuDNN or another supported backend
  - Optional `pynvml` installation for detailed GPU metrics
  - Leela network weights (`.pb.gz` / `.onnx`) when required by the selected engine build

## Installation

```bash
cd agent-engines
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

For NVIDIA monitoring:

```bash
pip install -e .[gpu,dev]
```

## Configuration

`WorkerConfig` controls engine selection, defaults, and GPU tuning.

```python
from gpu_worker.config import EngineBackend, GPUConfig, WorkerConfig

config = WorkerConfig(
    engine_backend=EngineBackend.LC0,
    engine_path="/usr/local/bin/lc0",
    gpu=GPUConfig(device_id=0, max_batch_size=32, memory_limit_mb=2048, backend="cudnn"),
    default_depth=22,
    default_time_limit_ms=3000,
    threads=2,
    hash_size_mb=512,
    network_weights_path="/models/bt4.pb.gz",
)
```

Key options:

- `engine_backend`: `lc0` or `stockfish`
- `engine_path`: path to the engine binary
- `gpu.device_id`: GPU index to bind the worker to
- `gpu.backend`: GPU backend such as `cudnn`, `cuda`, or `opencl`
- `max_concurrent_analyses`: queued work allowed per worker
- `default_depth` / `default_time_limit_ms`: search defaults when requests omit limits
- `threads`: engine thread count
- `hash_size_mb`: cache/hash allocation
- `network_weights_path`: lc0 weights file path

## Usage

### Start a worker pool

```bash
python main.py
```

### Run the orchestration demo

```bash
python main.py orchestration-demo
```

The demo creates a local `WorkerPool`, wraps it in an `EngineNode`, registers the node in a `NodeRegistry`, starts a `HealthMonitor`, and routes a sample `AnalysisRequest` through an `AnalysisRouter`.

### Submit a single request

```python
import asyncio

from gpu_worker.config import WorkerConfig
from gpu_worker.models import AnalysisRequest
from gpu_worker.pool import WorkerPool


async def run() -> None:
    pool = WorkerPool([WorkerConfig()])
    await pool.start_all()
    try:
        result = await pool.submit(
            AnalysisRequest(
                fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
                depth=18,
            )
        )
        print(result.model_dump())
    finally:
        await pool.shutdown_all()


asyncio.run(run())
```

### Batch analysis

```python
import asyncio

from gpu_worker.batch import BatchAnalyzer
from gpu_worker.config import WorkerConfig
from gpu_worker.models import AnalysisRequest
from gpu_worker.pool import WorkerPool


async def run() -> None:
    pool = WorkerPool([WorkerConfig(), WorkerConfig(gpu={"device_id": 1})])
    await pool.start_all()
    analyzer = BatchAnalyzer(pool, batch_size=8, flush_interval_ms=50)
    try:
        results = await analyzer.submit_batch(
            [
                AnalysisRequest(
                    fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
                    priority=10,
                )
            ]
        )
        print([result.best_move for result in results])
    finally:
        await analyzer.shutdown()
        await pool.shutdown_all()


asyncio.run(run())
```

## Personality training pipeline

The `personality/` package adds a training pipeline for configurable agent personas that shape how a UCI engine searches and prioritizes moves.

### Modules

- `personality/profile.py`: profile, trait, and search personalization models.
- `personality/presets.py`: built-in presets such as `The Attacker`, `The Fortress`, and `The Berserker`.
- `personality/style_analyzer.py`: PGN parsing and heuristic style extraction using `python-chess`.
- `personality/tuner.py`: trait-to-UCI and search-parameter mapping for Stockfish and lc0.
- `personality/evaluator.py`: similarity scoring between observed games and target profiles.
- `personality/trainer.py`: async orchestration for analyze, train, refine, evaluate, and save.

### Personality demo CLI

```bash
python main.py personality-demo --style tactical
python main.py personality-demo --preset "The Attacker"
python main.py personality-demo --list-presets
```

### Training example

```python
import asyncio

from personality.config import PipelineConfig, TrainingConfig
from personality.profile import PlayStyle
from personality.trainer import PersonalityTrainer

PGN = """[Event "Test Game"]
[White "Attacker"]
[Black "Defender"]
[Result "1-0"]
1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5 4. b4 Bxb4 5. c3 Ba5 6. d4 exd4 7. O-O 1-0
"""


async def run() -> None:
    trainer = PersonalityTrainer(TrainingConfig(engine_type="stockfish"))
    profile = await trainer.run_pipeline(
        PipelineConfig(
            pgn_data=[PGN],
            target_style=PlayStyle.AGGRESSIVE,
            output_path="trained-profile.json",
        )
    )
    print(profile.model_dump())


asyncio.run(run())
```

## Decentralized orchestration

The `orchestration/` package adds a decentralized coordination layer for distributing engine analysis across multiple nodes while preserving the existing local worker pool implementation.

### Components

- `NodeRegistry` tracks local and remote `EngineNode` instances behind an `asyncio.Lock`.
- `RequestScheduler` supports `least_loaded`, `round_robin`, and `capability_match` strategies.
- `HealthMonitor` performs background heartbeats and marks nodes unhealthy after repeated failures.
- `AnalysisRouter` submits requests with retry and failover, and stores recent routing events in a bounded in-memory log.

### Example

```python
import asyncio

from gpu_worker.models import AnalysisRequest, AnalysisResult
from orchestration import (
    AnalysisRouter,
    EngineNode,
    HealthMonitor,
    NodeCapability,
    NodeInfo,
    NodeRegistry,
    OrchestrationConfig,
    RequestScheduler,
)


async def submit(request: AnalysisRequest) -> AnalysisResult:
    return AnalysisResult(request_id=request.id, best_move="e2e4")


async def run() -> None:
    registry = NodeRegistry()
    node = EngineNode(
        NodeInfo(
            address="127.0.0.1:9000",
            capabilities=[NodeCapability.GPU_ANALYSIS],
            max_concurrent=4,
        ),
        submit_handler=submit,
    )
    await registry.register_node(node)

    config = OrchestrationConfig(load_balance_strategy="least_loaded")
    health = HealthMonitor(registry, config)
    scheduler = RequestScheduler(registry, config)
    router = AnalysisRouter(registry, scheduler, config)

    await health.start()
    try:
        await router.route(AnalysisRequest(fen="8/8/8/8/8/8/8/K6k w - - 0 1"))
    finally:
        await health.stop()


asyncio.run(run())
```

## Testing

The test suite uses mocked UCI processes and does not require `lc0` or Stockfish to be installed.

```bash
pytest
```

## Notes

- The UCI bridge works with any UCI-compatible engine and only applies `setoption` calls for engine options reported during the `uci` handshake.
- GPU monitoring gracefully degrades to empty metrics when NVML or `nvidia-smi` are unavailable.
- `BatchAnalyzer` improves throughput for bursty workloads such as review pipelines or offline game processing.

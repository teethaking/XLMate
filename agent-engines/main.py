from __future__ import annotations

import argparse
import asyncio
import json

from gpu_worker.config import WorkerConfig
from gpu_worker.pool import WorkerPool
from personality.config import TrainingConfig
from personality.presets import get_preset, list_presets
from personality.profile import PlayStyle
from personality.trainer import PersonalityTrainer


_SAMPLE_PGN = """[Event \"Personality Demo\"]
[White \"Attacker\"]
[Black \"Defender\"]
[Result \"1-0\"]
1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5 4. b4 Bxb4 5. c3 Ba5 6. d4 exd4 7. O-O 1-0
"""


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI parser for worker and personality demo commands."""

    parser = argparse.ArgumentParser(description="XLMate agent engine services")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("worker", help="Start the GPU analysis worker pool")

    personality_parser = subparsers.add_parser(
        "personality-demo",
        help="Show personality presets or train a demo profile from sample PGN",
    )
    personality_parser.add_argument(
        "--style",
        choices=[style.value for style in PlayStyle],
        default=PlayStyle.BALANCED.value,
        help="Target style for the demo-trained profile",
    )
    personality_parser.add_argument(
        "--preset",
        help="Show a built-in preset by name or identifier",
    )
    personality_parser.add_argument(
        "--list-presets",
        action="store_true",
        help="List available built-in personality presets",
    )
    return parser


async def run_worker() -> None:
    """Start the GPU analysis worker pool and wait until interrupted."""

    config = WorkerConfig()
    pool = WorkerPool([config])
    await pool.start_all()
    print("GPU Analysis Worker Pool started")
    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        await pool.shutdown_all()
        print("Worker pool shut down")


async def run_personality_demo(args: argparse.Namespace) -> None:
    """Demonstrate preset loading or profile training from sample PGN."""

    if args.list_presets:
        print(json.dumps([preset.name for preset in list_presets()], indent=2))
        return

    if args.preset:
        preset = get_preset(args.preset)
        print(json.dumps(preset.model_dump(mode="json"), indent=2))
        return

    trainer = PersonalityTrainer(TrainingConfig(engine_type="stockfish"))
    profile = await trainer.train_from_games([_SAMPLE_PGN], PlayStyle(args.style))
    print(json.dumps(profile.model_dump(mode="json"), indent=2))


async def main() -> None:
    """Dispatch the requested CLI action."""

    parser = build_parser()
    args = parser.parse_args()
    command = args.command or "worker"

    if command == "personality-demo":
        await run_personality_demo(args)
        return
    await run_worker()


if __name__ == "__main__":
    asyncio.run(main())

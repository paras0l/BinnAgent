#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import signal
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.knowledge.exercise_worker import (
    run_exercise_worker_forever,
    run_exercise_worker_once,
)
from src.providers.router import router


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the persistent unit exercise pool worker.")
    parser.add_argument("--once", action="store_true", help="Claim at most one job and exit.")
    args = parser.parse_args()
    return asyncio.run(_main(once=args.once))


async def _main(*, once: bool) -> int:
    if once:
        processed = await run_exercise_worker_once()
        await router.close()
        return 0 if processed else 3

    stop = False

    def request_stop() -> None:
        nonlocal stop
        stop = True

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, request_stop)
    try:
        await run_exercise_worker_forever(should_stop=lambda: stop)
    finally:
        await router.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

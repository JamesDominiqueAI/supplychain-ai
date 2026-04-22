#!/usr/bin/env python3
"""
Starter local runner for SupplyChain AI.

This script launches only the backend automatically.
The frontend should be started separately with `npm run dev` from `frontend/`.
"""

from __future__ import annotations

import signal
import subprocess
import sys
import time
from pathlib import Path


processes: list[subprocess.Popen[str]] = []


def cleanup(signum=None, frame=None):
    for process in processes:
        try:
            process.terminate()
            process.wait(timeout=3)
        except Exception:
            process.kill()
    sys.exit(0)


signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)


def main():
    project_root = Path(__file__).resolve().parents[1]
    backend_dir = project_root / "backend" / "api"

    backend = subprocess.Popen(
        ["uv", "run", "main.py"],
        cwd=backend_dir,
        text=True,
    )
    processes.append(backend)

    print("SupplyChain AI backend starting on http://127.0.0.1:8010")
    print("Start the frontend separately from supplychain-ai/frontend with `npm run dev`.")

    while True:
        if backend.poll() is not None:
            raise SystemExit(f"Backend exited with code {backend.returncode}")
        time.sleep(0.5)

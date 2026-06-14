"""Resolve LeRobot CLI executables on PATH."""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def lerobot_bin_dir() -> Path:
    override = os.environ.get("LEROBOT_BIN_DIR")
    if override:
        return Path(override)

    rollout = shutil.which("lerobot-rollout")
    if rollout:
        return Path(rollout).parent

    raise FileNotFoundError(
        "LeRobot CLI not found. Run: conda activate lerobot "
        "(or set LEROBOT_BIN_DIR to your env's bin directory)."
    )


def lerobot_cli(name: str) -> str:
    path = lerobot_bin_dir() / name
    if path.is_file():
        return str(path)
    found = shutil.which(name)
    if found:
        return found
    raise FileNotFoundError(
        f"{name} not found. Install LeRobot (see README) or set LEROBOT_BIN_DIR."
    )

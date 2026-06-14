"""Live sorting pipeline: lerobot-rollout → palpation → lerobot-replay.

Each step runs as a separate LeRobot CLI subprocess, matching the hackathon workflow.
"""

from __future__ import annotations

import subprocess
import sys

from lepotager.config import cameras_json, load_config
from lepotager.lerobot_cli import lerobot_cli

PYTHON = sys.executable


def run(cmd: list[str], *, check: bool = True) -> int:
    print(f"\n>>> {' '.join(cmd)}\n")
    result = subprocess.run(cmd)
    if check and result.returncode != 0:
        print(f"\nCommand failed with exit code {result.returncode}")
        sys.exit(result.returncode)
    return result.returncode


def one_cycle(cycle_num: int, cfg: dict) -> None:
    robot = cfg["robot"]
    policy = cfg["policy"]
    routes = cfg["routes"]

    print("\n" + "=" * 50)
    print(f"CYCLE {cycle_num} — STEP 1: ACT ROLLOUT")
    print("=" * 50)
    run([
        lerobot_cli("lerobot-rollout"),
        "--strategy.type=base",
        f"--policy.path={policy['path']}",
        "--robot.discover_packages_path=hardware",
        "--robot.type=so101_tactile_follower",
        f"--robot.id={robot['id']}",
        f"--robot.port={robot['port']}",
        f"--robot.cameras={cameras_json(cfg)}",
        f"--task={policy['task']}",
        f"--duration={policy.get('duration', 30)}",
    ])

    print("\n" + "=" * 50)
    print(f"CYCLE {cycle_num} — STEP 2: PALPATION")
    print("=" * 50)
    ret = run([PYTHON, "-m", "lepotager.palpation"], check=False)
    decision = "ripe" if ret == 0 else "reject"
    print(f"\nDecision: {decision.upper()}")

    route = routes[decision]
    print("\n" + "=" * 50)
    print(f"CYCLE {cycle_num} — STEP 3: REPLAY ({decision.upper()})")
    print("=" * 50)
    run([
        lerobot_cli("lerobot-replay"),
        "--robot.type=so101_follower",
        f"--robot.port={robot['port']}",
        f"--robot.id={robot['id']}",
        f"--dataset.repo_id={route['repo_id']}",
        f"--dataset.episode={route.get('episode', 0)}",
    ])

    print("\n" + "=" * 50)
    print(f"CYCLE {cycle_num} COMPLETE → {decision.upper()}")
    print("=" * 50)


def main() -> int:
    cfg = load_config()
    cycle = 1
    try:
        while True:
            one_cycle(cycle, cfg)
            cycle += 1
    except KeyboardInterrupt:
        print(f"\nStopped after {cycle - 1} cycle(s).")
    return 0

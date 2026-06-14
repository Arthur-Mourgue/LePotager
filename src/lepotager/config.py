"""Load pipeline configuration from YAML with optional environment overrides."""

from __future__ import annotations

import json
import os
from pathlib import Path

import yaml

from lepotager.paths import CONFIGS_DIR

DEFAULT_CONFIG = CONFIGS_DIR / "pipeline.yaml"


def load_config(path: Path | None = None) -> dict:
    cfg_path = path or DEFAULT_CONFIG
    with open(cfg_path) as f:
        cfg = yaml.safe_load(f)

    robot = cfg.setdefault("robot", {})
    if port := os.environ.get("LEPOTAGER_ROBOT_PORT"):
        robot["port"] = port
    if robot_id := os.environ.get("LEPOTAGER_ROBOT_ID"):
        robot["id"] = robot_id

    palpation = cfg.setdefault("palpation", {})
    if sensor_port := os.environ.get("LEPOTAGER_ESP32_PORT"):
        palpation["sensor_port"] = sensor_port

    routes = cfg.setdefault("routes", {})
    if repo := os.environ.get("LEPOTAGER_REPO_RIPE"):
        routes.setdefault("ripe", {})["repo_id"] = repo
    if repo := os.environ.get("LEPOTAGER_REPO_REJECT"):
        routes.setdefault("reject", {})["repo_id"] = repo

    if cameras_json := os.environ.get("LEPOTAGER_CAMERAS_JSON"):
        cfg["cameras"] = json.loads(cameras_json)

    return cfg


def cameras_json(cfg: dict) -> str:
    cameras = cfg.get("cameras", {})
    subset = {k: cameras[k] for k in ("front", "realsense") if k in cameras}
    return json.dumps(subset)

#!/usr/bin/env bash
# Record SO-101 demonstrations with Velostat FPB (observation.state shape 7).

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

NUM_EPISODES="${NUM_EPISODES:-50}"
CONFIG="${CONFIG:-configs/pipeline.yaml}"

if [[ ! -f "$CONFIG" ]]; then
  echo "Missing $CONFIG — copy configs/pipeline.example.yaml to configs/pipeline.yaml" >&2
  exit 1
fi

# Read values from pipeline.yaml (requires python + pyyaml)
read -r ROBOT_PORT ROBOT_ID ESP32_PORT FRONT_CAMERA REALSENSE_SERIAL <<EOF
$(python3 - <<PY
import yaml
from pathlib import Path
cfg = yaml.safe_load(Path("$CONFIG").read_text())
robot = cfg["robot"]
palp = cfg["palpation"]
cams = cfg["cameras"]
print(robot["port"])
print(robot.get("id", "my_awesome_follower_arm"))
print(palp["sensor_port"])
print(cams["front"]["index_or_path"])
print(cams["realsense"]["serial_number_or_name"])
PY
)
EOF

ROBOT_PORT="${ROBOT_PORT:-${LEPOTAGER_ROBOT_PORT:-}}"
ESP32_PORT="${ESP32_PORT:-${LEPOTAGER_ESP32_PORT:-}}"
LEADER_PORT="${LEADER_PORT:-${LEPOTAGER_LEADER_PORT:-}}"
LEADER_ID="${LEADER_ID:-my_awesome_leader_arm}"
DATASET_REPO="${DATASET_REPO:-local_dir/my_dataset_v5_50_tactile}"

exec lerobot-record \
  --robot.discover_packages_path=hardware \
  --robot.type=so101_tactile_follower \
  --robot.port="${ROBOT_PORT}" \
  --robot.id="${ROBOT_ID}" \
  --robot.pressure_sensor_port="${ESP32_PORT}" \
  --robot.pressure_sensor_column=3 \
  --robot.cameras="{
    \"front\": {\"type\": \"opencv\", \"index_or_path\": \"${FRONT_CAMERA}\", \"width\": 640, \"height\": 480, \"fps\": 30},
    \"realsense\": {\"type\": \"intelrealsense\", \"serial_number_or_name\": \"${REALSENSE_SERIAL}\", \"width\": 640, \"height\": 480, \"fps\": 30}
  }" \
  --teleop.type=so101_leader \
  --teleop.port="${LEADER_PORT}" \
  --teleop.id="${LEADER_ID}" \
  --display_data=true \
  --dataset.repo_id="${DATASET_REPO}" \
  --dataset.single_task="Grasp the target object and place it in the designated area" \
  --dataset.num_episodes="${NUM_EPISODES}" \
  --dataset.episode_time_s=30 \
  --dataset.reset_time_s=10 \
  --dataset.push_to_hub=false \
  "$@"

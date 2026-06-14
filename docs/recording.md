# Recording demonstrations

## Prerequisites

```bash
conda activate lerobot
pip install -e .
pip install -e "./lerobot[feetech,pyserial-dep]"
cp configs/pipeline.example.yaml configs/pipeline.yaml
```

## Tactile dataset (observation.state shape `[7]`)

```bash
LEADER_PORT=/dev/serial/by-id/... \
LEADER_ID=my_awesome_leader_arm \
NUM_EPISODES=50 \
./scripts/record_tactile_dataset.sh
```

Uses values from `configs/pipeline.yaml` for robot port, cameras, and ESP32 port.

### Verify shape

```python
from lerobot.datasets import LeRobotDataset

ds = LeRobotDataset("local_dir/my_dataset_v5_50_tactile")
print(ds.meta.features["observation.state"]["shape"])  # (7,)
```

## Route replay datasets

Record teleop trajectories from a fixed start pose (gripper closed on fruit in the palpation bowl):

```bash
lerobot-record \
  --robot.type=so101_follower \
  --robot.port=<from pipeline.yaml> \
  --teleop.type=so101_leader \
  --teleop.port=<leader port> \
  --dataset.repo_id=local_dir/ripesort_routes_ripe \
  --dataset.num_episodes=1 \
  --dataset.push_to_hub=false
```

Point `routes.ripe.repo_id` and `routes.reject.repo_id` in `configs/pipeline.yaml` to these datasets.

## Policy

- `qualia-robotics/act-2orange-50-Tactile-v2-5742f3f9`
- Trained on demonstrations with vision + `gripper_pressure` in `observation.state`

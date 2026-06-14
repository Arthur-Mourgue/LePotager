# Hardware

## Robot

- **Arm:** SO-101 follower (LeRobot `so101_follower` / `so101_tactile_follower`)
- **Teleop (recording):** SO-101 leader
- **Cameras:** USB front + Intel RealSense (ACT policy inputs)

## Tactile sensor

Velostat pad on the gripper, ESP32 streaming 14 tab-separated floats at ~700 Hz.

`observation.state` (7 dims):

```
[shoulder_pan, shoulder_lift, elbow_flex, wrist_flex, wrist_roll, gripper, gripper_pressure]
```

Index 6 is filtered **FPB** from column `BR_est` (Dual-EMA, `alpha1=0.167`, `alpha2=0.01`).

Implementation: [`velostat_reader.py`](../src/lepotager/hardware/velostat_reader.py)

```bash
python tests/test_velostat_fpb.py --mock --duration 10
python tests/test_velostat_fpb.py --port /dev/ttyUSB0
```

## LeRobot plugin

[`so101_tactile_follower.py`](../src/lepotager/hardware/so101_tactile_follower.py) registers the tactile follower for dataset recording and rollout:

```bash
--robot.discover_packages_path=hardware
--robot.type=so101_tactile_follower
```

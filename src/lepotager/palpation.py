"""Three-cycle gripper palpation with Velostat FPB pressure."""

from __future__ import annotations

import sys
import time

import serial
from lerobot.robots.so_follower import SOFollower, SOFollowerRobotConfig

from lepotager.config import load_config

OPEN_POS = 50.0
CLOSED_LIMIT = 20.0
APPROACH_STEP = 0.5
DEFORMATION = 2.0
CONTACT_THRESHOLD = 10.0
BAUD = 115200
TARGET_IDX = 3
ALPHA1, ALPHA2 = 0.167, 0.01


class DualEMAFilter:
    def __init__(self, alpha1: float, alpha2: float) -> None:
        self.alpha1 = alpha1
        self.alpha2 = alpha2
        self._high: float | None = None
        self._low: float | None = None

    def process(self, raw_val: float) -> float:
        if self._high is None:
            self._high = self._low = raw_val
        self._high = (1.0 - self.alpha1) * self._high + self.alpha1 * raw_val
        self._low = (1.0 - self.alpha2) * self._low + self.alpha2 * raw_val
        return max(0.0, self._high - self._low)


def run_palpation() -> str:
    cfg = load_config()
    robot_cfg = cfg["robot"]
    palp_cfg = cfg.get("palpation", {})
    threshold = float(palp_cfg.get("hardness_threshold", 40.0))

    sensor_port = palp_cfg["sensor_port"]
    robot_port = robot_cfg["port"]
    robot_id = robot_cfg.get("id", "my_awesome_follower_arm")

    print(f"Connecting to sensor on {sensor_port}...")
    ser = serial.Serial(sensor_port, baudrate=BAUD, timeout=0.05)
    ser.reset_input_buffer()
    filt = DualEMAFilter(ALPHA1, ALPHA2)
    time.sleep(0.5)

    def get_fpb() -> float:
        line = ser.readline().decode("ascii", errors="ignore").strip()
        parts = line.split("\t")
        if len(parts) == 14:
            return filt.process(float(parts[TARGET_IDX]))
        return 0.0

    print(f"Connecting to robot on {robot_port}...")
    config = SOFollowerRobotConfig(port=robot_port, id=robot_id)

    with SOFollower(config) as robot:
        peaks: list[float] = []
        print("\n" + "=" * 40)
        print("STARTING 3 PALPATION CYCLES")
        print("=" * 40)

        for i in range(3):
            print(f"\nCycle {i + 1}/3")
            print("  Opening...")
            robot.send_action({"gripper.pos": OPEN_POS})
            time.sleep(1.0)

            print("  Approaching...")
            current_pos = OPEN_POS
            contact_pos = OPEN_POS
            while current_pos > CLOSED_LIMIT:
                current_pos -= APPROACH_STEP
                robot.send_action({"gripper.pos": current_pos})
                time.sleep(0.03)
                fpb = get_fpb()
                if fpb > CONTACT_THRESHOLD:
                    print(f"  Contact (FPB: {fpb:.2f})")
                    contact_pos = current_pos
                    break

            print("  Measuring peak...")
            current_peak = 0.0
            robot.send_action({"gripper.pos": contact_pos - DEFORMATION})
            start_t = time.time()
            while time.time() - start_t < 2.5:
                fpb = get_fpb()
                current_peak = max(current_peak, fpb)
                time.sleep(0.03)

            peaks.append(current_peak)
            print(f"  Cycle {i + 1} max pressure: {current_peak:.2f}")
            robot.send_action({"gripper.pos": OPEN_POS})
            time.sleep(1.0)

        max_peak = max(peaks)
        decision = "RIPE" if max_peak >= threshold else "REJECT"

        print("\n" + "=" * 40)
        print("FINAL RESULTS:")
        for i, peak in enumerate(peaks):
            print(f"  Cycle {i + 1}: {peak:.2f}")
        print(f"  MAX PEAK: {max_peak:.2f}")
        print(f"  DECISION: {decision}")
        print("=" * 40 + "\n")

    ser.close()
    return decision


def main() -> int:
    decision = run_palpation()
    return 0 if decision == "RIPE" else 1


if __name__ == "__main__":
    raise SystemExit(main())

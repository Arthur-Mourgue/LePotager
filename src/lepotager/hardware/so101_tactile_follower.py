"""SO-101 follower with ESP32 Velostat pressure in observation.state."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import cached_property

from lerobot.robots import RobotConfig
from lerobot.robots.so_follower import SO101Follower
from lerobot.robots.so_follower.config_so_follower import SOFollowerRobotConfig
from lerobot.types import RobotObservation
from lerobot.utils.constants import HF_LEROBOT_CALIBRATION, ROBOTS
from lerobot.utils.decorators import check_if_not_connected

from hardware.velostat_reader import VelostatReader

logger = logging.getLogger(__name__)


@RobotConfig.register_subclass("so101_tactile_follower")
@dataclass
class SO101TactileFollowerConfig(SOFollowerRobotConfig):
    """SO-101 follower config with optional ESP32 Velostat pressure sensor."""

    pressure_sensor_port: str | None = None
    pressure_sensor_baudrate: int = 115200
    pressure_sensor_column: int = 3
    pressure_sensor_alpha1: float = 0.167
    pressure_sensor_alpha2: float = 0.01


class SO101TactileFollower(SO101Follower):
    """SO-101 follower with Velostat pressure in ``observation.state`` (6 → 7 dims).

    Registered with LeRobot as ``so101_tactile_follower`` for tactile demonstration recording.

    Extra state dimension (index 6):
      - gripper_pressure: ESP32 BR_est FPB (Dual-EMA bandpass, capped at 0)
    """

    config_class = SO101TactileFollowerConfig
    name = "so101_tactile_follower"

    def __init__(self, config: SO101TactileFollowerConfig) -> None:
        # Same arm as so101_follower — reuse its calibration dir (my_awesome_follower_arm.json).
        if config.calibration_dir is None:
            config.calibration_dir = HF_LEROBOT_CALIBRATION / ROBOTS / "so_follower"
        super().__init__(config)
        self.config = config
        self._pressure_reader: VelostatReader | None = None
        if config.pressure_sensor_port:
            self._pressure_reader = VelostatReader(
                port_name=config.pressure_sensor_port,
                baudrate=config.pressure_sensor_baudrate,
                mock=False,
                column_index=config.pressure_sensor_column,
                alpha1=config.pressure_sensor_alpha1,
                alpha2=config.pressure_sensor_alpha2,
            )

    @cached_property
    def observation_features(self) -> dict[str, type | tuple]:
        motors_ft = {f"{motor}.pos": float for motor in self.bus.motors}
        extras_ft = {"gripper_pressure.pos": float}
        return {**motors_ft, **extras_ft, **self._cameras_ft}

    def connect(self, calibrate: bool = True) -> None:
        super().connect(calibrate=calibrate)
        if self._pressure_reader is not None:
            self._pressure_reader.start_monitoring()

    def disconnect(self) -> None:
        if self._pressure_reader is not None:
            self._pressure_reader.stop_monitoring()
        super().disconnect()

    @check_if_not_connected
    def get_observation(self) -> RobotObservation:
        obs_dict = super().get_observation()
        obs_dict["gripper_pressure.pos"] = self._read_pressure_sensor()
        return obs_dict

    def _read_pressure_sensor(self) -> float:
        """Return latest FPB from ESP32 (BR_est → Dual-EMA), or 0.0 if not configured."""
        if self._pressure_reader is not None:
            return float(self._pressure_reader.get_current_force())
        return 0.0

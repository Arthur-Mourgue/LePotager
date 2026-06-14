"""Background thread reading Velostat FPB from ESP32 serial (or mock).

Protocol: 14 tab-separated floats per line (700 Hz from ESP32 firmware).
Signal: BR_est (or any column_index) → Dual-EMA bandpass → FPB (capped at 0).
Observation value: ``get_current_force()`` returns the latest FPB.
"""

from __future__ import annotations

import logging
import math
import threading
import time
from collections import deque
from typing import Any

logger = logging.getLogger(__name__)

ESP32_COLUMN_COUNT = 14

ESP32_COLUMNS = [
    "TL_est",
    "TR_est",
    "BL_est",
    "BR_est",
    "ax",
    "ay",
    "az",
    "gx",
    "gy",
    "gz",
    "extra_1",
    "extra_2",
    "extra_3",
    "extra_4",
]

# Velostat on gripper: BR_est per ESP32 capture script.
DEFAULT_COLUMN_INDEX = 3
DEFAULT_COLUMN_NAME = "BR_est"


class DualEMAFilter:
    """Dual-EMA bandpass filter. FPB = max(0, FPBH - FPBL)."""

    def __init__(self, alpha1: float = 0.167, alpha2: float = 0.01) -> None:
        self.alpha1 = alpha1
        self.alpha2 = alpha2
        self._anterior_h: float | None = None
        self._anterior_l: float | None = None

    def process(self, raw_val: float) -> float:
        if self._anterior_h is None:
            self._anterior_h = raw_val
            self._anterior_l = raw_val

        fpbh = (1.0 - self.alpha1) * self._anterior_h + self.alpha1 * raw_val
        fpbl = (1.0 - self.alpha2) * self._anterior_l + self.alpha2 * raw_val
        fpb = max(0.0, fpbh - fpbl)

        self._anterior_h = fpbh
        self._anterior_l = fpbl
        return fpb

    update = process

    def reset(self) -> None:
        self._anterior_h = None
        self._anterior_l = None


class VelostatReader:
    def __init__(
        self,
        port_name: str,
        baudrate: int = 115200,
        mock: bool = True,
        read_hz: float = 700.0,
        column_index: int = DEFAULT_COLUMN_INDEX,
        alpha1: float = 0.167,
        alpha2: float = 0.01,
    ) -> None:
        if not (0 <= column_index < ESP32_COLUMN_COUNT):
            raise ValueError(
                f"column_index must be 0-{ESP32_COLUMN_COUNT - 1}, got {column_index}"
            )

        self.port_name = port_name
        self.baudrate = baudrate
        self.mock = mock
        self.read_hz = read_hz
        self.column_index = column_index
        self._filter = DualEMAFilter(alpha1=alpha1, alpha2=alpha2)

        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._raw_force = 0.0
        self._filtered_force = 0.0
        self._serial: Any = None
        self._mock_start = time.monotonic()
        self._squeeze_active = False
        self._squeeze_start = 0.0

    @property
    def column_name(self) -> str:
        return ESP32_COLUMNS[self.column_index]

    def start_monitoring(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return

        if not self.mock:
            import serial

            self._serial = serial.Serial(self.port_name, self.baudrate, timeout=0.01)
            self._serial.reset_input_buffer()
            time.sleep(0.3)
            logger.info(
                "Velostat ESP32 on %s (column %d: %s) → FPB",
                self.port_name,
                self.column_index,
                self.column_name,
            )

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._read_loop, daemon=True, name="velostat-reader")
        self._thread.start()
        logger.info("Velostat started (mock=%s)", self.mock)

    def _read_loop(self) -> None:
        if self.mock:
            interval = 1.0 / self.read_hz
            while not self._stop_event.is_set():
                t0 = time.monotonic()
                raw, fpb = self._read_sample()
                self._store_sample(raw, fpb)
                elapsed = time.monotonic() - t0
                sleep_time = max(0.0, interval - elapsed)
                if self._stop_event.wait(sleep_time):
                    break
            return

        # Real ESP32 @ ~700 Hz: drain serial buffer, keep latest FPB.
        while not self._stop_event.is_set():
            got_sample = False
            while True:
                # Try to read one line
                raw, fpb, status = self._read_serial_line()
                if status == "timeout":
                    break
                if status == "error":
                    continue # Skip malformed line but keep draining
                
                self._store_sample(raw, fpb)
                got_sample = True

            if got_sample:
                self._stop_event.wait(0.001)
            else:
                self._stop_event.wait(0.005)

    def _store_sample(self, raw: float, fpb: float) -> None:
        with self._lock:
            self._raw_force = raw
            self._filtered_force = fpb

    def activate_squeeze(self) -> None:
        """Mock: mark start of gripper closing for force ramp simulation."""
        self._squeeze_active = True
        self._squeeze_start = time.monotonic()

    def deactivate_squeeze(self) -> None:
        self._squeeze_active = False

    def _read_sample(self) -> tuple[float, float]:
        raw = self._read_mock_raw()
        return raw, self._filter.process(raw)

    def _read_serial_line(self) -> tuple[float, float, str]:
        """Parse one ESP32 line. Returns (raw, fpb, status).
        Status can be "ok", "timeout", or "error".
        """
        if self._stop_event.is_set() or self._serial is None:
            return 0.0, 0.0, "timeout"

        try:
            line_bytes = self._serial.readline()
            if not line_bytes:
                return 0.0, 0.0, "timeout"

            line_str = line_bytes.decode("ascii", errors="ignore").strip()
            if not line_str or line_str.startswith("#"):
                return 0.0, 0.0, "error"

            parts = line_str.split("\t")
            if len(parts) != ESP32_COLUMN_COUNT:
                return 0.0, 0.0, "error"

            vals = [float(p) for p in parts]
            raw = vals[self.column_index]
            fpb = self._filter.process(raw)
            return raw, fpb, "ok"
        except (ValueError, OSError, TypeError) as exc:
            if self._stop_event.is_set():
                return 0.0, 0.0, "timeout"
            logger.debug("Velostat read error: %s", exc)
            return 0.0, 0.0, "error"

    def _read_mock_raw(self) -> float:
        if self._squeeze_active:
            elapsed = time.monotonic() - self._squeeze_start
            return min(130.0, elapsed * 40.0)
        t = time.monotonic() - self._mock_start
        return 0.1 + 0.05 * math.sin(t * 2.0)

    def get_fpb(self) -> float:
        """Latest filtered bandpass value (FPB), same as get_current_force()."""
        return self.get_current_force()

    def get_current_force(self) -> float:
        with self._lock:
            return self._filtered_force

    def stop_monitoring(self) -> None:
        self._stop_event.set()
        if self._serial is not None:
            try:
                self._serial.close()
            except OSError:
                pass
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        self._serial = None
        logger.info("Velostat stopped")

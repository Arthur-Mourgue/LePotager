#!/usr/bin/env python3
"""Test ESP32 Velostat FPB — terminal + live matplotlib plot.

FPB from BR_est (Dual-EMA, capped at 0) — same value as observation.state[6].

Usage:
  python tests/test_velostat_fpb.py
  python tests/test_velostat_fpb.py --port /dev/ttyUSB0 --duration 120
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hardware.velostat_reader import DEFAULT_COLUMN_INDEX, ESP32_COLUMNS, VelostatReader

WINDOW_SEC = 0.5
MIN_INTENSITY_VAL = 0.0
MAX_INTENSITY_VAL = 130.0
PLOT_YLIM = 150.0


def setup_live_plot(col_name: str):
    import matplotlib.pyplot as plt
    import numpy as np

    plt.ion()
    fig, (ax_plot, ax_img) = plt.subplots(
        1, 2, figsize=(12, 4), gridspec_kw={"width_ratios": [4, 1]}
    )

    ax_plot.set_title(f"Real-time FPB: {col_name} (→ gripper_pressure)")
    ax_plot.set_xlabel("Time (s)")
    ax_plot.set_ylabel("FPB")
    ax_plot.grid(True)
    ax_plot.set_ylim(0, PLOT_YLIM)
    line_filter, = ax_plot.plot([], [], "b-", linewidth=2, alpha=0.9, label="FPB")
    ax_plot.legend(loc="upper left")

    ax_img.set_title("Intensity")
    ax_img.axis("off")
    color_array = np.zeros((255, 255, 3))
    color_array[:, :, 0] = 1.0
    color_array[:, :, 1] = 1.0
    img_display = ax_img.imshow(color_array)

    plt.tight_layout()
    return fig, ax_plot, line_filter, ax_img, img_display, color_array, plt, np


def update_plot(
    ax_plot,
    line_filter,
    img_display,
    color_array,
    plt,
    np,
    times: deque[float],
    fpbs: deque[float],
    latest_fpb: float,
) -> None:
    if not times:
        return

    t_arr = np.array(times)
    f_arr = np.array(fpbs)
    current_time = t_arr[-1]

    if current_time > WINDOW_SEC:
        mask = t_arr >= current_time - WINDOW_SEC
        line_filter.set_xdata(t_arr[mask])
        line_filter.set_ydata(f_arr[mask])
        ax_plot.set_xlim(current_time - WINDOW_SEC, current_time)
    else:
        line_filter.set_xdata(t_arr)
        line_filter.set_ydata(f_arr)
        ax_plot.set_xlim(0, max(WINDOW_SEC, current_time + 0.05))

    clamped = max(MIN_INTENSITY_VAL, min(MAX_INTENSITY_VAL, latest_fpb))
    ratio = (clamped - MIN_INTENSITY_VAL) / (MAX_INTENSITY_VAL - MIN_INTENSITY_VAL)
    color_array[:, :, 1] = 1.0 - ratio
    img_display.set_data(color_array)

    plt.pause(0.001)


def show_final_plot(col_name: str, times: list[float], fpbs: list[float]) -> None:
    import matplotlib.pyplot as plt

    if not times:
        return

    plt.ioff()
    plt.figure(figsize=(10, 4))
    plt.plot(times, fpbs, "b-", linewidth=1.5, label=f"FPB {col_name}")
    plt.title(f"Captured FPB — {col_name}")
    plt.xlabel("Time (s)")
    plt.ylabel("FPB")
    plt.ylim(0, PLOT_YLIM)
    plt.legend()
    plt.grid(True)
    plt.show()


def main() -> None:
    parser = argparse.ArgumentParser(description="Stream ESP32 Velostat FPB (terminal + plot)")
    parser.add_argument("--port", default="/dev/ttyUSB0", help="ESP32 serial port")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--column", type=int, default=DEFAULT_COLUMN_INDEX, help="Channel index")
    parser.add_argument("--alpha1", type=float, default=0.167)
    parser.add_argument("--alpha2", type=float, default=0.01)
    parser.add_argument("--duration", type=float, default=10.0, help="Seconds (0 = until Ctrl+C)")
    parser.add_argument("--mock", action="store_true", help="Simulate signal without hardware")
    parser.add_argument("--hz", type=float, default=10.0, help="Terminal print rate (Hz)")
    parser.add_argument("--plot-hz", type=float, default=30.0, help="Plot refresh rate (Hz)")
    parser.add_argument("--no-plot", action="store_true", help="Terminal only, no matplotlib")
    args = parser.parse_args()

    col_name = ESP32_COLUMNS[args.column]
    print(f"Channel: [{args.column}] {col_name}")
    print(f"Filter: Dual-EMA alpha1={args.alpha1} alpha2={args.alpha2} → FPB (max 0)")
    if not args.no_plot:
        print("Live plot enabled (yellow → red intensity map).")
    print("Press Ctrl+C to stop.\n")

    plot_ctx = None
    if not args.no_plot:
        try:
            plot_ctx = setup_live_plot(col_name)
        except ImportError:
            print("WARNING: matplotlib not installed — terminal only. pip install matplotlib")
            args.no_plot = True

    reader = VelostatReader(
        port_name=args.port,
        baudrate=args.baud,
        mock=args.mock,
        column_index=args.column,
        alpha1=args.alpha1,
        alpha2=args.alpha2,
    )

    try:
        reader.start_monitoring()
    except Exception as exc:
        print(f"ERROR: could not open {args.port}: {exc}", file=sys.stderr)
        sys.exit(1)

    print_interval = 1.0 / args.hz
    plot_interval = 1.0 / args.plot_hz
    t0 = time.monotonic()
    last_print = 0.0
    last_plot = 0.0

    times: deque[float] = deque(maxlen=5000)
    fpbs: deque[float] = deque(maxlen=5000)

    try:
        while True:
            now = time.monotonic()
            elapsed = now - t0
            fpb = reader.get_fpb()

            times.append(elapsed)
            fpbs.append(fpb)

            if now - last_print >= print_interval:
                print(f"[{elapsed:6.2f}s] FPB = {fpb:7.2f}  (→ gripper_pressure)")
                last_print = now

            if plot_ctx and now - last_plot >= plot_interval:
                fig, ax_plot, line_filter, _ax_img, img_display, color_array, plt, np = plot_ctx
                if plt.fignum_exists(fig.number):
                    update_plot(
                        ax_plot, line_filter, img_display, color_array, plt, np,
                        times, fpbs, fpb,
                    )
                else:
                    break
                last_plot = now

            if args.duration > 0 and elapsed >= args.duration:
                break

            time.sleep(0.001)

    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        reader.stop_monitoring()

    if plot_ctx and not args.no_plot:
        show_final_plot(col_name, list(times), list(fpbs))


if __name__ == "__main__":
    main()

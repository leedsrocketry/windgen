"""Radiosonde sounding fetch — reads a local ``*.sounding.csv`` file.

The CSV format is produced by the windsonde logger:

    # Radiation correction v2.3. Params: lat=..., lon=..., utc_time=...
    Height (m AGL), Pressure (mb), Temperature (C), Relative humidity (%), Wind speed (m/s), Wind direction (true deg)
    20, 997.57, 12.40, ...

Heights are already in metres AGL so no hypsometric conversion is needed.
Wind components are computed using the standard meteorological convention
(u = towards east, v = towards north).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

import sys
_pkg_root = Path(__file__).resolve().parent.parent
if str(_pkg_root) not in sys.path:
    sys.path.insert(0, str(_pkg_root))

from windsonde.parser import parse


def fetch_mean_profile(
    path: str | Path,
    elevation: float,
    altitude_max_m: int,
    altitude_step_m: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Read a radiosonde sounding CSV and return a wind profile.

    The sounding provides a single observed profile (no temporal averaging).
    Heights are already AGL; ``elevation`` is only used to confirm the data
    source and is not applied to the altitudes.

    Returns ``(altitude_m, wind_east_ms, wind_north_ms)`` where
    ``altitude_m`` is in metres AGL and wind arrays have shape ``(1, M)``.
    Wind components use the "blowing towards" convention (u = towards east,
    v = towards north).

    Parameters
    ----------
    path:
        Path to the ``*.sounding.csv`` file.
    elevation:
        Site elevation in metres ASL (unused in conversion; kept for API
        consistency with other fetch modules).
    altitude_max_m:
        Upper bound of the output grid in metres AGL.
    altitude_step_m:
        Grid spacing in metres for the interpolated output.

    Raises
    ------
    FileNotFoundError
        If ``path`` does not exist.
    ValueError
        If the sounding file contains no valid levels within the requested
        altitude range.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Sounding file not found: {path}")

    sounding = parse(path)

    levels = [lv for lv in sounding.levels if 0 <= lv.height_m <= altitude_max_m]
    if not levels:
        raise ValueError(
            f"No sounding levels found within 0–{altitude_max_m} m AGL in {path}."
        )

    levels.sort(key=lambda lv: lv.height_m)

    raw_alt = np.array([lv.height_m for lv in levels])
    raw_u   = np.array([lv.wind_u   for lv in levels])
    raw_v   = np.array([lv.wind_v   for lv in levels])

    grid = np.arange(0, altitude_max_m + altitude_step_m, altitude_step_m, dtype=float)
    grid = grid[grid <= raw_alt[-1]]

    u_interp = np.interp(grid, raw_alt, raw_u)
    v_interp = np.interp(grid, raw_alt, raw_v)

    return grid, u_interp.reshape(1, -1), v_interp.reshape(1, -1)

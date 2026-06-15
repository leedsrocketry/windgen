"""UKV mean wind profile — reads locally cached Met Office GRIB2 files.

Expects files in ``met/grib/`` (relative to the package root) with the naming
convention produced by the met renamer tool:

    isbl_<pressure>hPa_<YYYY_MM_DD>_T_<HHMM>_Z.grib2

One or more specific valid-time files are loaded, the nearest grid point to
(lat, lon) is extracted from each, and u/v/t are averaged across the requested
datetimes before the pressure levels are converted to AGL altitude using the
hypsometric equation.  The profile is then interpolated onto a regular altitude
grid.
"""

from __future__ import annotations

import datetime
import warnings
from collections import defaultdict
from pathlib import Path

import numpy as np

_GRIB_DIR = Path(__file__).resolve().parent.parent / "met" / "grib"

_R = 287.058   # J/kg/K  dry-air gas constant
_g = 9.80665   # m/s²    standard gravity
_P0 = 101325.0 # Pa      standard sea-level pressure


def _pressure_to_altitude(p_hpa: float, t_k: float) -> float:
    """Hypsometric equation: altitude (m ASL) for a given pressure and temperature."""
    return (_R * t_k / _g) * np.log(_P0 / (p_hpa * 100.0))


def fetch_mean_profile(
    datetimes: datetime.datetime | list[datetime.datetime],
    lat: float,
    lon: float,
    elevation: float,
    altitude_max_m: int,
    altitude_step_m: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Read UKV GRIB2 files from met/grib and return a mean wind profile.

    Loads files for each requested datetime from ``met/grib/``, extracts u, v, t
    at the nearest grid point to (lat, lon), averages across the provided
    datetimes, then converts pressure to altitude AGL using the hypsometric
    equation.

    Returns ``(altitude_m, wind_east_ms, wind_north_ms)`` where
    ``altitude_m`` is in metres AGL and wind arrays have shape ``(1, M)``.
    Wind components use the "blowing towards" convention (u = towards east,
    v = towards north — matches UKV native GRIB2 convention).

    Parameters
    ----------
    datetimes:
        One or more UTC datetimes to load.  Files must exist for each
        requested datetime; missing files are skipped with a warning.
    lat, lon:
        Site coordinates in decimal degrees (lon may be negative or 0–360).
    elevation:
        Site elevation in metres ASL.  Used to convert altitude ASL → AGL.
    altitude_max_m:
        Upper bound of the output grid in metres AGL.
    altitude_step_m:
        Grid spacing in metres for the interpolated output.

    Raises
    ------
    FileNotFoundError
        If no GRIB2 files are found for any of the requested datetimes.
    RuntimeError
        If no pressure levels fall within 0–altitude_max_m AGL after conversion.
    ImportError
        If xarray or cfgrib are not installed.
    """
    try:
        import xarray as xr
    except ImportError:
        raise ImportError(
            "ukv requires xarray and cfgrib. "
            "Install with: pip install xarray cfgrib"
        )

    if isinstance(datetimes, datetime.datetime):
        datetimes = [datetimes]

    lon_360 = lon % 360  # GRIB2 grids use 0–360 longitude

    all_files: list[Path] = []
    for dt in datetimes:
        date_str = dt.strftime("%Y_%m_%d")
        time_str = dt.strftime("%H%M")
        matched = sorted(_GRIB_DIR.glob(f"isbl_*_{date_str}_T_{time_str}_Z.grib2"))
        all_files.extend(matched)

    if not all_files:
        labels = ", ".join(dt.strftime("%Y-%m-%d T%H%MZ") for dt in datetimes)
        raise FileNotFoundError(
            f"No UKV GRIB2 files found for [{labels}] in {_GRIB_DIR}.\n"
            f"Expected pattern: isbl_<P>hPa_<YYYY_MM_DD>_T_<HHMM>_Z.grib2\n"
            f"Run met/downloader.py and met/renamer.py to populate this directory."
        )

    # Group files by pressure-level label (e.g. "850hPa")
    by_level: dict[str, list[Path]] = defaultdict(list)
    for f in all_files:
        # stem: isbl_<level>_<YYYY>_<MM>_<DD>_T_<HHMM>_Z
        level_label = f.stem.split("_")[1]
        by_level[level_label].append(f)

    results: list[dict] = []

    for level_label, files in by_level.items():
        u_vals: list[float] = []
        v_vals: list[float] = []
        t_vals: list[float] = []
        p_hpa: float | None = None

        for f in files:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    ds = xr.open_dataset(f, engine="cfgrib")
                try:
                    point = ds.sel(latitude=lat, longitude=lon_360, method="nearest")
                    if p_hpa is None:
                        p_hpa = float(point.isobaricInhPa.values)
                    u_vals.append(float(point.u.values))
                    v_vals.append(float(point.v.values))
                    t_vals.append(float(point.t.values))
                finally:
                    ds.close()
            except Exception:
                continue

        if not u_vals or p_hpa is None:
            continue

        alt_asl = _pressure_to_altitude(p_hpa, float(np.mean(t_vals)))
        alt_agl = alt_asl - elevation
        if alt_agl < 0 or alt_agl > altitude_max_m:
            continue

        results.append({
            "altitude_m": alt_agl,
            "u_ms": float(np.mean(u_vals)),
            "v_ms": float(np.mean(v_vals)),
        })

    if not results:
        raise RuntimeError(
            f"No valid UKV pressure levels found within 0–{altitude_max_m} m AGL "
            f"for {date} at lat={lat}, lon={lon}. "
            f"Check that met/grib files cover this site and date."
        )

    results.sort(key=lambda r: r["altitude_m"])

    raw_alt = np.array([r["altitude_m"] for r in results])
    raw_u   = np.array([r["u_ms"]       for r in results])
    raw_v   = np.array([r["v_ms"]       for r in results])

    grid = np.arange(0, altitude_max_m + altitude_step_m, altitude_step_m, dtype=float)
    grid = grid[grid <= raw_alt[-1]]

    u_interp = np.interp(grid, raw_alt, raw_u)
    v_interp = np.interp(grid, raw_alt, raw_v)

    return grid, u_interp.reshape(1, -1), v_interp.reshape(1, -1)

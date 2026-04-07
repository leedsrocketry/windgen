"""GFS forecast download — NOAA NOMADS API → mean wind .npz."""

from __future__ import annotations

import datetime
import io
import struct
import urllib.request
import urllib.error

import numpy as np

# GFS pressure levels (hPa) available on NOMADS — standard 26-level set.
_PRESSURE_LEVELS_HPA = [
    1000, 975, 950, 925, 900, 850, 800, 750, 700, 650,
    600, 550, 500, 450, 400, 350, 300, 250, 200, 150,
    100, 70, 50, 30, 20, 10,
]

# NOMADS GFS filter URL template.
_NOMADS_URL = (
    "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl"
    "?dir=%2Fgfs.{date}%2F{cycle:02d}%2Fatmos"
    "&file=gfs.t{cycle:02d}z.pgrb2.0p25.f000"
    "&var_UGRD=on&var_VGRD=on&var_HGT=on"
    "&lev_{level}_mb=on"
    "&subregion="
    "&toplat={lat_n}&leftlon={lon_w}&rightlon={lon_e}&bottomlat={lat_s}"
)


def _nearest_cycle(date: datetime.date) -> tuple[str, int]:
    """Return (YYYYMMDD, cycle_hour) for the latest available GFS cycle."""
    # Use 00Z cycle for the requested date (most complete).
    return date.strftime("%Y%m%d"), 0


def _download_level(
    date_str: str,
    cycle: int,
    level: int,
    lat: float,
    lon: float,
) -> bytes:
    """Download a single pressure level's GRIB2 data from NOMADS."""
    # Build a tight bounding box (0.5° around the point).
    url = _NOMADS_URL.format(
        date=date_str,
        cycle=cycle,
        level=level,
        lat_n=lat + 0.5,
        lat_s=lat - 0.5,
        lon_w=lon - 0.5,
        lon_e=lon + 0.5,
    )
    req = urllib.request.Request(url, headers={"User-Agent": "windgen/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read()
    except urllib.error.URLError as exc:
        raise RuntimeError(f"GFS download failed for {level} hPa: {exc}") from exc


def _parse_grib2_values(data: bytes) -> dict[str, float]:
    """Minimal GRIB2 parser — extract UGRD, VGRD, HGT from a single-point subset.

    This is a very simplified parser that works with the NOMADS subregion filter
    output (typically a 3×3 or smaller grid).  For robustness in production,
    consider using cfgrib.

    Returns dict with keys 'ugrd', 'vgrd', 'hgt' (whichever are present).
    """
    try:
        import cfgrib
        import xarray as xr

        results: dict[str, float] = {}
        datasets = cfgrib.open_datasets(io.BytesIO(data))
        for ds in datasets:
            for var in ("u", "v", "gh"):
                if var in ds:
                    arr = ds[var].values
                    # Take central grid point value
                    if arr.ndim == 0:
                        results[var] = float(arr)
                    elif arr.ndim == 2:
                        cy, cx = arr.shape[0] // 2, arr.shape[1] // 2
                        results[var] = float(arr[cy, cx])
                    elif arr.ndim == 1:
                        results[var] = float(arr[len(arr) // 2])
        return {
            "ugrd": results.get("u", 0.0),
            "vgrd": results.get("v", 0.0),
            "hgt": results.get("gh", 0.0),
        }
    except ImportError:
        raise ImportError(
            "gfs requires cfgrib and xarray. "
            "Install with: pip install cfgrib xarray"
        )


def fetch_mean_profile(
    date: datetime.date,
    lat: float,
    lon: float,
    elevation: float,
    altitude_max_m: int,
    altitude_step_m: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Download GFS forecast data and return a mean wind profile.

    Returns ``(altitude_m, wind_east_ms, wind_north_ms)`` where
    ``altitude_m`` is in metres AGL and wind arrays have shape ``(1, M)``.
    Wind components use the "blowing towards" convention (GFS native:
    ``ugrd`` = towards east, ``vgrd`` = towards north).
    """
    date_str, cycle = _nearest_cycle(date)

    heights_m: list[float] = []
    u_winds: list[float] = []
    v_winds: list[float] = []

    for level in _PRESSURE_LEVELS_HPA:
        data = _download_level(date_str, cycle, level, lat, lon)
        vals = _parse_grib2_values(data)

        geopotential_height_m = vals["hgt"]
        agl = geopotential_height_m - elevation
        if agl < 0 or agl > altitude_max_m:
            continue

        heights_m.append(agl)
        u_winds.append(vals["ugrd"])
        v_winds.append(vals["vgrd"])

    if not heights_m:
        raise RuntimeError("No valid GFS levels found for the requested location/date.")

    # Sort by altitude and interpolate onto a regular grid
    order = np.argsort(heights_m)
    raw_alt = np.array(heights_m)[order]
    raw_u = np.array(u_winds)[order]
    raw_v = np.array(v_winds)[order]

    grid = np.arange(0, altitude_max_m + altitude_step_m, altitude_step_m, dtype=float)
    # Clip grid to the range of available data
    grid = grid[grid <= raw_alt[-1]]

    u_interp = np.interp(grid, raw_alt, raw_u)
    v_interp = np.interp(grid, raw_alt, raw_v)

    return grid, u_interp.reshape(1, -1), v_interp.reshape(1, -1)

"""
Reads each raw .grib2 file in the grib/ directory, extracts the valid time
and pressure level from the file itself, then renames it to:

    isbl_{pressure}hPa_{valid_time}.grib2

e.g.  isbl_1000hPa_20260616T1800Z.grib2
"""

import os
import xarray as xr
import numpy as np
from pathlib import Path
import pandas as pd

GRIB_DIR = Path("grib")

# A nearby point just to open the dataset — we only need metadata, not values
LAT = 58.608974
LON = -4.944191 % 360


def extract_metadata(path: Path) -> tuple[float, str]:
    """Return (pressure_hpa, valid_time_str) from a GRIB2 file."""
    ds = xr.open_dataset(path, engine="cfgrib")
    point = ds.sel(latitude=LAT, longitude=LON, method="nearest")

    pressure_hpa = float(point.isobaricInhPa.values)

    # valid_time is a numpy datetime64 — convert to a clean UTC string
    valid_time = pd.Timestamp(point.valid_time.values).strftime("%Y_%m_%d_T_%H%M_Z")

    return pressure_hpa, valid_time


def new_name(pressure_hpa: float, valid_time: str) -> str:
    pressure_str = f"{int(pressure_hpa)}hPa"
    return f"isbl_{pressure_str}_{valid_time}.grib2"


files = sorted(GRIB_DIR.glob("*.grib2"))
print(f"Found {len(files)} files to rename\n")

for path in files:
    try:
        pressure, valid_time = extract_metadata(path)
        name = new_name(pressure, valid_time)
        dest = GRIB_DIR / name

        if dest == path:
            print(f"  unchanged  {path.name}")
            continue

        if dest.exists():
            print(f"  SKIP (already exists)  {dest.name}")
            continue

        os.rename(path, dest)
        print(f"  {path.name}")
        print(f"       -> {dest.name}")

    except Exception as e:
        print(f"  ERROR {path.name}: {e}")
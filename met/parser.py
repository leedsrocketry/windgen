import xarray as xr
import numpy as np
from pathlib import Path

# ── Configuration ─────────────────────────────────────────────────────────────

LAT = 58.608974
LON = -4.944191 % 360

# ── Timestamp to inspect ─────────────────────────────────────────────────────
VALID_TIME = "2026_06_17_T_1200_Z"

GRIB_DIR = Path("grib")

# ── Physics ───────────────────────────────────────────────────────────────────

R  = 287.058   # J/kg/K
g  = 9.80665   # m/s²
P0 = 101325.0  # Pa

def pressure_to_altitude(p_hpa, t_k):
    return (R * t_k / g) * np.log(P0 / (p_hpa * 100))

# ── Load files matching the requested timestamp ───────────────────────────────

files = sorted(GRIB_DIR.glob(f"isbl_*_{VALID_TIME}.grib2"))

if not files:
    raise FileNotFoundError(
        f"No files found for timestamp '{VALID_TIME}' in {GRIB_DIR}/\n"
        f"Expected pattern: isbl_<pressure>hPa_{VALID_TIME}.grib2"
    )

print(f"Found {len(files)} pressure levels for {VALID_TIME}\n")

results = []

for f in files:
    ds = xr.open_dataset(f, engine="cfgrib")
    point = ds.sel(latitude=LAT, longitude=LON, method="nearest")
    p_hpa = float(point.isobaricInhPa.values)
    t_k   = float(point.t.values)
    results.append({
        "pressure_hpa": p_hpa,
        "altitude_m":   pressure_to_altitude(p_hpa, t_k),
        "t_k":          t_k,
        "u_ms":         float(point.u.values),
        "v_ms":         float(point.v.values),
    })

results.sort(key=lambda x: x["altitude_m"], reverse=True)

# ── Print ─────────────────────────────────────────────────────────────────────

print(f"Valid time : {VALID_TIME}")
print(f"Location   : {LAT}°N, {-4.944191}°W (Cape Wrath)")
print()
print(f"{'hPa':>8} {'Alt (m)':>10} {'T (K)':>8} {'U (m/s)':>10} {'V (m/s)':>10}")
print("─" * 52)
for r in results:
    print(
        f"{r['pressure_hpa']:>8.0f}"
        f"{r['altitude_m']:>10.0f}"
        f"{r['t_k']:>8.2f}"
        f"{r['u_ms']:>10.2f}"
        f"{r['v_ms']:>10.2f}"
    )
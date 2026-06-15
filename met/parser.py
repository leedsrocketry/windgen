import xarray as xr
import numpy as np
from pathlib import Path

lat = 58.608974
lon = -4.944191 % 360

timestep = "66"
grib_dir = Path("grib")

R = 287.058   # J/kg/K
g = 9.80665   # m/s²
P0 = 101325.0 # Pa - sea level pressure

def pressure_to_altitude(p_hpa, t_k):
    p_pa = p_hpa * 100
    return (R * t_k / g) * np.log(P0 / p_pa)

results = []

for f in sorted(grib_dir.glob(f"isbl_*_+15_{timestep}.grib2")):
    ds = xr.open_dataset(f, engine="cfgrib")
    point = ds.sel(latitude=lat, longitude=lon, method="nearest")
    p_hpa = float(point.isobaricInhPa.values)
    t_k = float(point.t.values)
    results.append({
        "pressure_hpa": p_hpa,
        "altitude_m": pressure_to_altitude(p_hpa, t_k),
        "valid_time": str(point.valid_time.values),
        "t_k": t_k,
        "u_ms": float(point.u.values),
        "v_ms": float(point.v.values),
    })

results.sort(key=lambda x: x["pressure_hpa"], reverse=True)

print(f"Valid time: {results[0]['valid_time']}")
print()
print(f"{'hPa':>8} {'Alt (m)':>10} {'T (K)':>8} {'U (m/s)':>10} {'V (m/s)':>10}")
print("-" * 50)
for r in results:
    print(f"{r['pressure_hpa']:>8.0f} {r['altitude_m']:>10.0f} {r['t_k']:>8.2f} {r['u_ms']:>10.2f} {r['v_ms']:>10.2f}")
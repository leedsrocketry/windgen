import xarray as xr
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import seaborn as sns
from pathlib import Path

# ── Configuration ─────────────────────────────────────────────────────────────

LAT = 58.608974
LON = -4.944191 % 360

VALID_TIME = "2026_06_17_T_0900_Z"

GRIB_DIR = Path("grib")

# ── Physics ───────────────────────────────────────────────────────────────────

R  = 287.058
g  = 9.80665
P0 = 101325.0

def pressure_to_altitude(p_hpa, t_k):
    return (R * t_k / g) * np.log(P0 / (p_hpa * 100))

# ── Load ──────────────────────────────────────────────────────────────────────

files = sorted(GRIB_DIR.glob(f"isbl_*_{VALID_TIME}.grib2"))

if not files:
    raise FileNotFoundError(
        f"No files found for timestamp '{VALID_TIME}' in {GRIB_DIR}/\n"
        f"Expected pattern: isbl_<pressure>hPa_{VALID_TIME}.grib2"
    )

print(f"Found {len(files)} pressure levels for {VALID_TIME}\n")

results = []
for f in files:
    ds    = xr.open_dataset(f, engine="cfgrib")
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
df = pd.DataFrame(results)

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

# ── Plot ──────────────────────────────────────────────────────────────────────

alt = df["altitude_m"].values / 1000  # km

sns.set_theme(style="whitegrid", font="monospace")

BLUE   = "#3A7FD5"
ORANGE = "#E8753A"
GRID   = "#E8E8E8"
TEXT   = "#2A2A2A"

fig, ax = plt.subplots(figsize=(6, 9))
fig.patch.set_facecolor("white")
ax.set_facecolor("white")

ax.plot(df["u_ms"], alt, color=BLUE,   lw=1.8, label="U  (zonal)",      zorder=3)
ax.plot(df["v_ms"], alt, color=ORANGE, lw=1.8, label="V  (meridional)", zorder=3)
ax.scatter(df["u_ms"], alt, color=BLUE,   s=22, zorder=4, linewidths=0)
ax.scatter(df["v_ms"], alt, color=ORANGE, s=22, zorder=4, linewidths=0)

ax.axvline(0, color=TEXT, lw=0.7, ls="--", alpha=0.35, zorder=2)

ax.set_xlabel("Wind speed  (m s⁻¹)", fontsize=10, color=TEXT, labelpad=8)
ax.set_ylabel("Altitude  (km)",       fontsize=10, color=TEXT, labelpad=8)
ax.set_xlim(-30, 30)
ax.set_ylim(0, alt.max() * 1.03)

ax.yaxis.set_major_locator(ticker.MultipleLocator(5))
ax.yaxis.set_minor_locator(ticker.MultipleLocator(1))
ax.xaxis.set_major_locator(ticker.MultipleLocator(10))
ax.xaxis.set_minor_locator(ticker.MultipleLocator(5))

ax.tick_params(axis="both", which="major", labelsize=8.5, color="#BBBBBB", length=3)
ax.tick_params(axis="both", which="minor", color="#DDDDDD", length=2)
for spine in ax.spines.values():
    spine.set_edgecolor("#DDDDDD")

ax.grid(which="major", color=GRID, lw=0.7, zorder=1)
ax.grid(which="minor", color=GRID, lw=0.3, zorder=1)

legend = ax.legend(
    frameon=True, framealpha=0.9, edgecolor="#DDDDDD",
    fontsize=9, loc="upper left",
    handlelength=1.6, handletextpad=0.6,
)
legend.get_frame().set_linewidth(0.6)

# Format title from VALID_TIME: "2026_06_17_T_1200_Z" → "2026-06-17  12:00 Z"
date_str, time_str = VALID_TIME.split("_T_")
date_fmt = date_str.replace("_", "-")
time_fmt = f"{time_str[:2]}:{time_str[2:4]} Z".replace("_Z", "")

ax.set_title(
    f"Wind Profile  ·  Cape Wrath\n{date_fmt}  {time_fmt}  ·  {LAT:.2f}°N  {4.944191:.2f}°W",
    fontsize=10, color=TEXT, pad=14, linespacing=1.6,
)

plt.tight_layout()

out = Path(f"wind_profile_{VALID_TIME}.png")
plt.savefig(out, dpi=180, bbox_inches="tight")
print(f"\nSaved → {out}")
plt.show()
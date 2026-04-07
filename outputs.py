""".npz read/write with metadata, filename date/source parsing, and ensemble plotting."""

from __future__ import annotations

import datetime
import json
import re
from pathlib import Path
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# Filename conventions
# ---------------------------------------------------------------------------

_FILENAME_RE = re.compile(r"^(\d{2})-(\d{2})-(\d{2})-(\w+)\.npz$")


def parse_filename(name: str) -> tuple[datetime.date, str]:
    """Parse date and source from a wind profile filename.

    Expected format: ``DD-MM-YY-source.npz`` (e.g. ``13-07-26-gfs.npz``).
    Returns ``(date, source_name)``.

    Raises ValueError if the filename does not match.
    """
    m = _FILENAME_RE.match(name)
    if m is None:
        raise ValueError(
            f"Cannot parse date from filename: {name}. "
            "Expected {DD-MM-YY}-{source}.npz"
        )
    day, month, year, source = m.groups()
    date = datetime.date(2000 + int(year), int(month), int(day))
    return date, source


def make_filename(date: datetime.date, source: str) -> str:
    """Build a wind profile filename from date and source."""
    return f"{date.strftime('%d-%m-%y')}-{source}.npz"


# ---------------------------------------------------------------------------
# .npz I/O
# ---------------------------------------------------------------------------


def save_ensemble(
    path: Path,
    altitude_m: np.ndarray,
    wind_east_ms: np.ndarray,
    wind_north_ms: np.ndarray,
    *,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Write a wind profile ensemble to ``.npz``.

    Parameters
    ----------
    path : Path
        Output file path.
    altitude_m : ndarray, shape (M,)
        Altitude grid in metres AGL.
    wind_east_ms : ndarray, shape (N, M)
        Eastward wind component per profile.
    wind_north_ms : ndarray, shape (N, M)
        Northward wind component per profile.
    metadata : dict, optional
        Generation metadata (serialised as JSON string).
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    arrays: dict[str, Any] = {
        "altitude_m": np.asarray(altitude_m, dtype=np.float64),
        "wind_east_ms": np.asarray(wind_east_ms, dtype=np.float64),
        "wind_north_ms": np.asarray(wind_north_ms, dtype=np.float64),
    }
    if metadata is not None:
        arrays["metadata"] = np.array(json.dumps(metadata))
    np.savez(path, **arrays)


def load_ensemble(
    path: Path,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, Any] | None]:
    """Read a wind profile ensemble from ``.npz``.

    Returns ``(altitude_m, wind_east_ms, wind_north_ms, metadata)``.
    ``metadata`` is ``None`` if the key is absent.
    """
    data = np.load(path, allow_pickle=False)
    altitude_m = data["altitude_m"]
    wind_east_ms = data["wind_east_ms"]
    wind_north_ms = data["wind_north_ms"]
    meta = None
    if "metadata" in data:
        meta = json.loads(str(data["metadata"]))
    return altitude_m, wind_east_ms, wind_north_ms, meta


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------

_METRES_PER_FOOT = 0.3048

def _fit_ellipse(
    east: np.ndarray,
    north: np.ndarray,
    threshold: float = 1.0,
) -> dict | None:
    """Fit a PCA ellipse containing *threshold* fraction of points.

    Returns dict with center_e, center_n, semi_a, semi_b, angle_deg,
    or None if fewer than 3 points.
    """
    if len(east) < 3:
        return None
    mean_e, mean_n = east.mean(), north.mean()
    cov = np.cov(np.vstack([east - mean_e, north - mean_n]))
    vals, vecs = np.linalg.eigh(cov)
    order = np.argsort(vals)[::-1]
    vals, vecs = vals[order], vecs[:, order]
    angle_rad = np.arctan2(vecs[1, 0], vecs[0, 0])
    de, dn = east - mean_e, north - mean_n
    proj_a = de * vecs[0, 0] + dn * vecs[1, 0]
    proj_b = de * vecs[0, 1] + dn * vecs[1, 1]
    sigma_a = np.sqrt(vals[0]) if vals[0] > 0 else 1e-10
    sigma_b = np.sqrt(vals[1]) if vals[1] > 0 else 1e-10
    mahal_sq = (proj_a / sigma_a) ** 2 + (proj_b / sigma_b) ** 2
    sorted_mahal_sq = np.sort(mahal_sq)
    idx = max(0, int(np.ceil(threshold * len(sorted_mahal_sq))) - 1)
    idx = min(idx, len(sorted_mahal_sq) - 1)
    scale = np.sqrt(sorted_mahal_sq[idx])
    return dict(
        center_e=float(mean_e),
        center_n=float(mean_n),
        semi_a=float(scale * sigma_a),
        semi_b=float(scale * sigma_b),
        angle_deg=float(np.degrees(angle_rad)),
    )


def plot_ensemble(
    path: Path,
    *,
    save: bool = False,
) -> None:
    """Plot a wind profile ensemble from a ``.npz`` file.

    Three panels:

    1. Wind speed vs altitude — mean with min/max envelope.
    2. Wind heading vs altitude — circular mean.
    3. East vs North wind scatter at three altitudes (surface, mid,
       top) with PCA ellipses showing the spread.

    Parameters
    ----------
    path : Path
        Path to a ``.npz`` file.
    save : bool
        If True, save as PNG alongside the ``.npz`` instead of showing.
    """
    import matplotlib.pyplot as plt
    from matplotlib.patches import Ellipse
    import numpy as np

    altitude_m, wind_east_ms, wind_north_ms, _meta = load_ensemble(path)
    n_alts = len(altitude_m)

    # --- Wind speed ---
    wind_speed = np.sqrt(wind_east_ms**2 + wind_north_ms**2)
    mean_speed = np.mean(wind_speed, axis=0)
    min_speed = np.min(wind_speed, axis=0)
    max_speed = np.max(wind_speed, axis=0)

    # --- Wind direction (towards) ---
    direction_rad = np.arctan2(wind_east_ms, wind_north_ms)
    direction_deg = np.degrees(direction_rad)

    # Circular mean
    sin_mean = np.mean(np.sin(np.radians(direction_deg)), axis=0)
    cos_mean = np.mean(np.cos(np.radians(direction_deg)), axis=0)
    mean_dir = np.degrees(np.arctan2(sin_mean, cos_mean))
    mean_dir = ((mean_dir + 180) % 360) - 180

    # --- Layout: 3 columns ---
    fig = plt.figure(figsize=(14, 10))
    gs = fig.add_gridspec(1, 3, width_ratios=[1, 1, 1])
    ax_speed = fig.add_subplot(gs[0, 0])
    ax_dir = fig.add_subplot(gs[0, 1], sharey=ax_speed)
    ax_scatter = fig.add_subplot(gs[0, 2], aspect="equal")

    # --- Speed subplot ---
    ax_speed.fill_betweenx(
        altitude_m, min_speed, max_speed,
        alpha=0.25, color="steelblue", label="Min/max",
    )
    ax_speed.plot(
        mean_speed, altitude_m,
        color="steelblue", linewidth=1.5, label="Mean",
    )
    ax_speed.set_xlabel("Wind Speed (m/s)")
    ax_speed.set_ylabel("Altitude (m)")
    ax_speed.legend(loc="upper right")
    ax_speed.grid(True, alpha=0.3)

    # Secondary y-axis (feet) on left
    ax_ft = ax_speed.secondary_yaxis(
        "left",
        functions=(
            lambda m: m / _METRES_PER_FOOT,
            lambda ft: ft * _METRES_PER_FOOT,
        ),
    )
    ax_ft.spines["left"].set_position(("outward", 60))
    ax_ft.set_ylabel("Altitude (ft)")

    # --- Direction subplot (mean only) ---
    ax_dir.plot(
        mean_dir, altitude_m,
        color="darkorange", linewidth=1.5, label="Mean",
    )
    ax_dir.set_xlim(-180, 180)
    ax_dir.set_xticks([-180, -90, 0, 90, 180])
    ax_dir.set_xlabel("Wind Heading (deg)")
    ax_dir.grid(True, alpha=0.3)
    ax_dir.tick_params(labelleft=False)
    ax_dir.legend(loc="upper right")

    # --- Scatter subplot: east vs north at 3 altitudes ---
    alt_indices = [0, n_alts // 2, n_alts - 1]
    colours = ["steelblue", "seagreen", "coral"]

    for alt_idx, colour in zip(alt_indices, colours):
        alt = altitude_m[alt_idx]
        ew = wind_east_ms[:, alt_idx]
        ns = wind_north_ms[:, alt_idx]
        ax_scatter.scatter(ew, ns, s=2, c=colour, alpha=0.5, zorder=3,
                           label=f"{alt / 1000:.0f} km")

        el = _fit_ellipse(ew, ns, threshold=1.0)
        if el is not None:
            ax_scatter.add_patch(Ellipse(
                xy=(el["center_e"], el["center_n"]),
                width=2 * el["semi_a"],
                height=2 * el["semi_b"],
                angle=el["angle_deg"],
                edgecolor=colour, facecolor="none",
                linewidth=1.5, zorder=4,
            ))

    # Axes through origin, no axis labels (tick values are self-explanatory)
    ax_scatter.spines["left"].set_position("zero")
    ax_scatter.spines["bottom"].set_position("zero")
    ax_scatter.spines["top"].set_visible(False)
    ax_scatter.spines["right"].set_visible(False)
    ax_scatter.set_title("East vs North (m/s)", fontsize=10)
    ax_scatter.legend(fontsize=8, loc="upper right")

    # --- Centered figure title ---
    fig.suptitle(path.stem, fontsize=14, y=0.95, ha="center")

    fig.tight_layout(rect=[0, 0, 1, 0.94])

    if save:
        out = path.with_suffix(".png")
        fig.savefig(out, dpi=150)
        plt.close(fig)
    else:
        plt.show()

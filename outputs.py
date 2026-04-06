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

def plot_ensemble(
    path: Path,
    *,
    save: bool = False,
) -> None:
    """Plot a wind profile ensemble from a ``.npz`` file.

    Shows mean wind speed with min/max envelope and mean wind direction.
    Altitude on the y-axis with metres (primary) and feet (secondary)
    scales both on the left.

    Parameters
    ----------
    path : Path
        Path to a ``.npz`` file.
    save : bool
        If True, save as PNG alongside the ``.npz`` instead of showing.
    """
    import matplotlib.pyplot as plt
    import numpy as np

    altitude_m, wind_east_ms, wind_north_ms, _meta = load_ensemble(path)

    # --- Wind speed ---
    wind_speed = np.sqrt(wind_east_ms**2 + wind_north_ms**2)
    mean_speed = np.mean(wind_speed, axis=0)
    min_speed = np.min(wind_speed, axis=0)
    max_speed = np.max(wind_speed, axis=0)

    # --- Wind direction (towards) ---
    direction_rad = np.arctan2(wind_east_ms, wind_north_ms)
    direction_deg = np.degrees(direction_rad)  # can be negative

    # Circular mean
    sin_mean = np.mean(np.sin(np.radians(direction_deg)), axis=0)
    cos_mean = np.mean(np.cos(np.radians(direction_deg)), axis=0)
    mean_dir = np.degrees(np.arctan2(sin_mean, cos_mean))

    # Wrap mean to [-180, 180] for plotting
    mean_dir = ((mean_dir + 180) % 360) - 180

    # --- Layout ---
    fig, (ax_speed, ax_dir) = plt.subplots(
        ncols=2,
        sharey=True,
        figsize=(10, 10),
        gridspec_kw={"width_ratios": [2, 1]},
    )

    # --- Speed subplot ---
    ax_speed.fill_betweenx(
        altitude_m,
        min_speed,
        max_speed,
        alpha=0.25,
        color="steelblue",
        label="Min/max",
    )
    ax_speed.plot(
        mean_speed,
        altitude_m,
        color="steelblue",
        linewidth=1.5,
        label="Mean",
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
        mean_dir,
        altitude_m,
        color="darkorange",
        linewidth=1.5,
        label="Mean",
    )
    ax_dir.set_xlim(-180, 180)
    ax_dir.set_xticks([-180, -90, 0, 90, 180])
    ax_dir.set_xlabel("Wind Heading (deg)")
    ax_dir.grid(True, alpha=0.3)
    ax_dir.legend(loc="upper right")

    # --- Centered figure title ---
    fig.suptitle(path.stem, fontsize=14, y=0.95, ha="center")

    fig.tight_layout(rect=[0, 0, 1, 0.94])  # leave space for suptitle

    if save:
        out = path.with_suffix(".png")
        fig.savefig(out, dpi=150)
        plt.close(fig)
    else:
        plt.show()

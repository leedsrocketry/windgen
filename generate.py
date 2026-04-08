"""EarthGRAM orchestration: NAMELIST writing, subprocess invocation, CSV parsing."""

from __future__ import annotations

import csv
import datetime
import io
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable

import numpy as np

from .config import SiteConfig

# Path to the EarthGRAM executable, relative to the windgen package root.
_PACKAGE_DIR = Path(__file__).resolve().parent
_EARTHGRAM_EXE = _PACKAGE_DIR / "earthgram" / "bin" / "EarthGRAM.exe"
_SPICE_PATH = _PACKAGE_DIR / "earthgram" / "SPICE"
_DATA_PATH = _PACKAGE_DIR / "earthgram" / "data"

# ---------------------------------------------------------------------------
# NAMELIST generation
# ---------------------------------------------------------------------------


def _namelist(
    *,
    site: SiteConfig,
    date: datetime.date,
    seed: int,
    perturbation_scale: float,
    altitude_max_m: int,
    altitude_step_m: int,
    output_file: str,
    list_file: str,

) -> str:
    """Build an EarthGRAM NAMELIST input string."""
    # EarthGRAM uses km for heights and expects DeltaHeight in km.
    initial_height_km = site.elevation / 1000.0
    delta_height_km = altitude_step_m / 1000.0
    n_positions = int(altitude_max_m / altitude_step_m) + 1

    # Longitude: EarthGRAM expects east-positive.  Config stores WGS-84 which
    # can be negative (west).  EarthGRAM's EastLongitudePositive=1 handles it.
    lon = site.longitude

    # Relative paths from the bin/ directory where EarthGRAM runs.
    lines = [
        " $INPUT",
        "  SpicePath      = '../SPICE'",
        "  DataPath       = '../data'",
        f"  ListFileName   = '{list_file}'",
        f"  ColumnFileName = '{output_file}'",
        "",
        f"  Month     = {date.month}",
        f"  Day       = {date.day}",
        f"  Year      = {date.year}",
        "  Hour      = 12",
        "  Minute    = 0",
        "  Seconds   = 0.0",
        "",
        f"  InitialRandomSeed               = {seed}",
        f"  HorizontalWindPerturbationScale = {perturbation_scale}",
        "  NumberOfMonteCarloRuns          = 1",
        "",
        "  ThermosphereModel = 1",
        "",
        "  UseNCEP    = 1",
        "  NCEPYear   = 9715",
        "  NCEPHour   = 5",
        "",
        "  UseRRA  = 0",
        "  Patchy  = 0",
        "  SurfaceRoughness = -1",
        "",
        "  UseTrajectoryFile     = 0",
        f"  NumberOfPositions     = {n_positions}",
        "  EastLongitudePositive = 1",
        f"  InitialHeight         = {initial_height_km}",
        f"  InitialLatitude       = {site.latitude}",
        f"  InitialLongitude      = {lon}",
        f"  DeltaHeight           = {delta_height_km}",
        "  DeltaLatitude         = 0.0",
        "  DeltaLongitude        = 0.0",
        "  DeltaTime             = 0.0",
        "",
    ]

    lines.append("  UseAuxiliaryAtmosphere = 0")

    lines += [
        "  FastModeOn        = 0",
        "  ExtraPrecision    = 0",
        "  UseLegacyOutputs  = 0",
        "",
        " $END",
    ]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# CSV parsing
# ---------------------------------------------------------------------------


def _parse_output_csv(
    csv_path: Path,
    elevation_km: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Parse EarthGRAM output CSV, returning AGL arrays.

    Returns
    -------
    altitude_m : ndarray, shape (M,)
        Altitude in metres AGL.
    ew_wind : ndarray, shape (M,)
        Perturbed eastward wind (m/s, positive = blowing towards east).
    ns_wind : ndarray, shape (M,)
        Perturbed northward wind (m/s, positive = blowing towards north).
    """
    heights_km: list[float] = []
    ew: list[float] = []
    ns: list[float] = []

    text = Path(csv_path).read_text(encoding="utf-8")
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
            h = float(row["Height_km"])
            if h < elevation_km:
                continue
            heights_km.append(h)
            ew.append(float(row["PerturbedEWWind_ms"]))
            ns.append(float(row["PerturbedNSWind_ms"]))

    altitude_m = (np.array(heights_km) - elevation_km) * 1000.0
    return altitude_m, np.array(ew), np.array(ns)


# ---------------------------------------------------------------------------
# Seed derivation
# ---------------------------------------------------------------------------


def derive_seed(master_seed: int, profile_index: int) -> int:
    """Deterministically derive a per-profile seed from master seed and index."""
    # Simple but effective: combine with a large prime to spread values.
    return (master_seed * 104729 + profile_index * 65537) % (2**31 - 1)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def check_earthgram() -> None:
    """Verify that the EarthGRAM executable exists.

    Raises FileNotFoundError if missing.
    """
    if not _EARTHGRAM_EXE.is_file():
        raise FileNotFoundError(
            f"EarthGRAM not found at {_EARTHGRAM_EXE}. See CLAUDE.md for setup."
        )


def generate_ensemble(
    *,
    site: SiteConfig,
    date: datetime.date,
    n_profiles: int,
    master_seed: int,
    perturbation_scale: float,
    altitude_max_m: int,
    altitude_step_m: int,
    on_progress: Callable[[int, int], None] | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Generate a perturbed wind profile ensemble via EarthGRAM.

    Parameters
    ----------
    site : SiteConfig
        Launch site parameters.
    date : datetime.date
        Date for the profiles.
    n_profiles : int
        Number of ensemble members.
    master_seed : int
        Master random seed.
    perturbation_scale : float
        Perturbation magnitude (0.0–1.0).
    altitude_max_m : int
        Maximum altitude in metres AGL.
    altitude_step_m : int
        Altitude grid spacing in metres.
    on_progress : callable, optional
        Called with ``(current_index, n_profiles)`` after each profile.

    Returns
    -------
    altitude_m : ndarray, shape (M,)
    wind_east_ms : ndarray, shape (N, M)
    wind_north_ms : ndarray, shape (N, M)
    """
    check_earthgram()
    elevation_km = site.elevation / 1000.0

    all_ew: list[np.ndarray] = []
    all_ns: list[np.ndarray] = []
    altitude_m: np.ndarray | None = None

    # EarthGRAM writes output files relative to its own executable directory
    # (bin/), not the CWD.  Run from bin/ and manage all I/O there.
    bin_dir = _EARTHGRAM_EXE.parent

    try:
        for i in range(n_profiles):
            seed = derive_seed(master_seed, i)
            output_csv = f"_wg_out_{i}.csv"
            list_file = f"_wg_out_{i}.md"
            nml_file = f"_wg_in_{i}.txt"

            nml_content = _namelist(
                site=site,
                date=date,
                seed=seed,
                perturbation_scale=perturbation_scale,
                altitude_max_m=altitude_max_m,
                altitude_step_m=altitude_step_m,
                output_file=output_csv,
                list_file=list_file,
            )

            nml_path = bin_dir / nml_file
            nml_path.write_text(nml_content, encoding="utf-8")

            # EarthGRAM cannot overwrite existing output files (fails with
            # "bad allocation" instead of an error).  Remove them first.
            for stale in (bin_dir / output_csv, bin_dir / list_file):
                stale.unlink(missing_ok=True)

            result = subprocess.run(
                [str(_EARTHGRAM_EXE), "-file", nml_file],
                cwd=str(bin_dir),
                capture_output=True,
                text=True,
            )
            if result.returncode != 0 or "bad allocation" in result.stderr:
                raise RuntimeError(
                    f"EarthGRAM failed (exit {result.returncode}): {result.stderr}"
                )

            csv_path = bin_dir / output_csv
            alt_m, ew_wind, ns_wind = _parse_output_csv(csv_path, elevation_km)

            if altitude_m is None:
                altitude_m = alt_m
            all_ew.append(ew_wind)
            all_ns.append(ns_wind)

            if on_progress is not None:
                on_progress(i + 1, n_profiles)
    finally:
        # Clean up temporary files from bin/
        for f in bin_dir.glob("_wg_*"):
            f.unlink(missing_ok=True)

    assert altitude_m is not None
    return altitude_m, np.stack(all_ew), np.stack(all_ns)


def build_metadata(
    *,
    source: str,
    date: datetime.date,
    site: SiteConfig,
    perturbation_scale: float,
    n_profiles: int,
    master_seed: int,
) -> dict[str, Any]:
    """Build generation metadata dict for embedding in .npz."""
    meta: dict[str, Any] = {
        "source": source,
        "generation_timestamp": datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
        "date": date.isoformat(),
        "site": {
            "latitude": site.latitude,
            "longitude": site.longitude,
            "elevation": site.elevation,
        },
        "perturbation_scale": perturbation_scale,
        "n_profiles": n_profiles,
        "master_seed": master_seed,
    }
    return meta

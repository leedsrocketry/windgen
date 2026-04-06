"""LFS config.yaml loading — site location, elevation, Monte Carlo parameters."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class SiteConfig:
    """Launch site parameters extracted from config.yaml."""

    latitude: float
    longitude: float
    elevation: float


@dataclass(frozen=True)
class MonteCarloConfig:
    """Monte Carlo parameters extracted from config.yaml."""

    n_samples: int
    master_seed: int


def _get(data: dict[str, Any], *keys: str) -> Any:
    """Traverse nested dict by key path, returning None if any key is missing."""
    current = data
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def load_site(config_path: Path) -> SiteConfig:
    """Load site parameters from an LFS config.yaml.

    Raises ValueError if required fields are missing.
    """
    data = _load_yaml(config_path)

    lat = _get(data, "site", "latitude")
    lon = _get(data, "site", "longitude")
    elev = _get(data, "site", "elevation")

    if lat is None:
        raise ValueError("Config missing required field: site.latitude")
    if lon is None:
        raise ValueError("Config missing required field: site.longitude")
    if elev is None:
        elev = 0.0

    return SiteConfig(latitude=float(lat), longitude=float(lon), elevation=float(elev))


def load_montecarlo(config_path: Path) -> MonteCarloConfig:
    """Load Monte Carlo parameters from an LFS config.yaml.

    Falls back to defaults if fields are missing.
    """
    data = _load_yaml(config_path)

    n_samples = _get(data, "monte_carlo", "samples")
    master_seed = _get(data, "monte_carlo", "seed")

    if n_samples is None:
        n_samples = 1000
    if master_seed is None:
        master_seed = 42

    return MonteCarloConfig(n_samples=int(n_samples), master_seed=int(master_seed))


def _load_yaml(config_path: Path) -> dict[str, Any]:
    """Read and parse a YAML file.

    Raises FileNotFoundError or ValueError on failure.
    """
    path = Path(config_path)
    if not path.is_file():
        raise FileNotFoundError(f"Cannot read config: {path}")
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise ValueError(f"Cannot read config: {path}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Cannot read config: {path}")
    return data

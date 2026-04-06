"""UKV forecast download — placeholder requiring Met Office DataPoint."""

from __future__ import annotations

import datetime

import numpy as np


def fetch_mean_profile(
    date: datetime.date,
    lat: float,
    lon: float,
    elevation: float,
    altitude_max_m: int,
    altitude_step_m: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Download UKV forecast data and return a mean wind profile.

    Returns ``(altitude_m, wind_east_ms, wind_north_ms)`` where
    ``altitude_m`` is in metres AGL and wind arrays have shape ``(1, M)``.
    """
    try:
        import datapoint  # noqa: F401
    except ImportError:
        raise ImportError(
            "ukv requires datapoint. "
            "Install with: pip install datapoint"
        )

    raise NotImplementedError("UKV fetch is not yet implemented.")

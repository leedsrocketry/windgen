"""ECMWF forecast download — placeholder requiring ecmwf-api-client."""

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
    """Download ECMWF forecast data and return a mean wind profile.

    Returns ``(altitude_m, wind_east_ms, wind_north_ms)`` where
    ``altitude_m`` is in metres AGL and wind arrays have shape ``(1, M)``.
    """
    try:
        import ecmwflibs  # noqa: F401
    except ImportError:
        raise ImportError(
            "ecmwf requires ecmwf-api-client. "
            "Install with: pip install ecmwf-api-client"
        )

    raise NotImplementedError("ECMWF fetch is not yet implemented.")

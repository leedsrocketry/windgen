"""Tests for generate.py — NAMELIST writing, CSV parsing, seed derivation."""

from __future__ import annotations

import datetime
from pathlib import Path

import numpy as np
import pytest

from windgen.config import SiteConfig
from windgen.generate import (
    _namelist,
    _parse_output_csv,
    derive_seed,
)


class TestDeriveSeeds:
    def test_deterministic(self) -> None:
        assert derive_seed(42, 0) == derive_seed(42, 0)

    def test_different_indices(self) -> None:
        seeds = [derive_seed(42, i) for i in range(100)]
        assert len(set(seeds)) == 100  # all unique

    def test_different_masters(self) -> None:
        assert derive_seed(42, 0) != derive_seed(43, 0)

    def test_positive(self) -> None:
        for i in range(50):
            assert derive_seed(42, i) > 0


class TestNamelist:
    def test_basic(self) -> None:
        site = SiteConfig(latitude=58.61, longitude=-4.94, elevation=0.0)
        nml = _namelist(
            site=site,
            date=datetime.date(2026, 7, 13),
            seed=12345,
            perturbation_scale=1.0,
            altitude_max_m=20000,
            altitude_step_m=250,
            output_file="out.csv",
            list_file="out.md",
        )
        assert "$INPUT" in nml
        assert "$END" in nml
        assert "Month     = 7" in nml
        assert "Day       = 13" in nml
        assert "Year      = 2026" in nml
        assert "InitialRandomSeed               = 12345" in nml
        assert "InitialLatitude       = 58.61" in nml
        assert "UseAuxiliaryAtmosphere = 0" in nml

    def test_only_horizontal_wind_scaled(self) -> None:
        site = SiteConfig(latitude=58.61, longitude=-4.94, elevation=0.0)
        nml = _namelist(
            site=site,
            date=datetime.date(2026, 7, 13),
            seed=1,
            perturbation_scale=0.5,
            altitude_max_m=20000,
            altitude_step_m=250,
            output_file="out.csv",
            list_file="out.md",
        )
        assert "HorizontalWindPerturbationScale = 0.5" in nml
        assert "RandomPerturbationScale" not in nml
        assert "VerticalWindPerturbationScale" not in nml

    def test_altitude_grid(self) -> None:
        site = SiteConfig(latitude=0, longitude=0, elevation=100.0)
        nml = _namelist(
            site=site,
            date=datetime.date(2026, 1, 1),
            seed=1,
            perturbation_scale=1.0,
            altitude_max_m=5000,
            altitude_step_m=250,
            output_file="o.csv",
            list_file="o.md",
        )
        # 5000/250 + 1 = 21 positions
        assert "NumberOfPositions     = 21" in nml
        # Initial height = 100/1000 = 0.1 km
        assert "InitialHeight         = 0.1" in nml


class TestParseOutputCsv:
    def test_basic(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "output.csv"
        lines = [
            "Height_km,PerturbedEWWind_ms,PerturbedNSWind_ms,Other",
            "0.0,1.0,2.0,x",
            "0.25,3.0,4.0,x",
            "0.5,5.0,6.0,x",
        ]
        csv_path.write_text("\n".join(lines), encoding="utf-8")
        alt, ew, ns = _parse_output_csv(csv_path, elevation_km=0.0)
        np.testing.assert_array_almost_equal(alt, [0.0, 250.0, 500.0])
        np.testing.assert_array_almost_equal(ew, [1.0, 3.0, 5.0])
        np.testing.assert_array_almost_equal(ns, [2.0, 4.0, 6.0])

    def test_elevation_offset(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "output.csv"
        lines = [
            "Height_km,PerturbedEWWind_ms,PerturbedNSWind_ms",
            "0.0,1.0,2.0",   # below pad — skipped
            "0.1,3.0,4.0",   # at pad — AGL=0
            "0.35,5.0,6.0",  # AGL=250m
        ]
        csv_path.write_text("\n".join(lines), encoding="utf-8")
        alt, ew, ns = _parse_output_csv(csv_path, elevation_km=0.1)
        np.testing.assert_array_almost_equal(alt, [0.0, 250.0])
        np.testing.assert_array_almost_equal(ew, [3.0, 5.0])



"""Tests for config.py — YAML loading, missing fields, default fallbacks."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from windgen.config import load_montecarlo, load_site


@pytest.fixture()
def config_dir(tmp_path: Path) -> Path:
    return tmp_path


def _write_config(path: Path, data: dict) -> Path:
    cfg = path / "config.yaml"
    cfg.write_text(yaml.dump(data), encoding="utf-8")
    return cfg


class TestLoadSite:
    def test_valid(self, config_dir: Path) -> None:
        cfg = _write_config(config_dir, {
            "site": {"latitude": 58.61, "longitude": -4.94, "elevation": 10.0}
        })
        site = load_site(cfg)
        assert site.latitude == pytest.approx(58.61)
        assert site.longitude == pytest.approx(-4.94)
        assert site.elevation == pytest.approx(10.0)

    def test_elevation_defaults_to_zero(self, config_dir: Path) -> None:
        cfg = _write_config(config_dir, {
            "site": {"latitude": 58.61, "longitude": -4.94}
        })
        site = load_site(cfg)
        assert site.elevation == 0.0

    def test_missing_latitude(self, config_dir: Path) -> None:
        cfg = _write_config(config_dir, {
            "site": {"longitude": -4.94}
        })
        with pytest.raises(ValueError, match="site.latitude"):
            load_site(cfg)

    def test_missing_longitude(self, config_dir: Path) -> None:
        cfg = _write_config(config_dir, {
            "site": {"latitude": 58.61}
        })
        with pytest.raises(ValueError, match="site.longitude"):
            load_site(cfg)

    def test_file_not_found(self, config_dir: Path) -> None:
        with pytest.raises(FileNotFoundError, match="Cannot read config"):
            load_site(config_dir / "nonexistent.yaml")

    def test_invalid_yaml(self, config_dir: Path) -> None:
        bad = config_dir / "bad.yaml"
        bad.write_text(": : :\n  bad yaml {{", encoding="utf-8")
        with pytest.raises(ValueError, match="Cannot read config"):
            load_site(bad)


class TestLoadMonteCarlo:
    def test_values_from_config(self, config_dir: Path) -> None:
        cfg = _write_config(config_dir, {
            "monte_carlo": {"samples": 500, "seed": 99}
        })
        mc = load_montecarlo(cfg)
        assert mc.n_samples == 500
        assert mc.master_seed == 99

    def test_defaults(self, config_dir: Path) -> None:
        cfg = _write_config(config_dir, {"site": {"latitude": 0, "longitude": 0}})
        mc = load_montecarlo(cfg)
        assert mc.n_samples == 1000
        assert mc.master_seed == 42

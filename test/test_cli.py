"""Tests for cli.py — command invocation, argument validation, error/warning panels."""

from __future__ import annotations

from pathlib import Path

import yaml
from click.testing import CliRunner

from windgen.cli import main


def _write_config(path: Path) -> Path:
    cfg = path / "config.yaml"
    cfg.write_text(yaml.dump({
        "site": {"latitude": 58.61, "longitude": -4.94, "elevation": 0.0},
        "monte_carlo": {"samples": 5, "seed": 42},
    }), encoding="utf-8")
    return cfg


class TestMainGroup:
    def test_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "fetch" in result.output
        assert "generate" in result.output
        assert "preview" in result.output


class TestGenerateCommand:
    def test_no_date_no_mean_errors(self, tmp_path: Path) -> None:
        cfg = _write_config(tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["generate", str(cfg)])
        assert result.exit_code != 0

    def test_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["generate", "--help"])
        assert result.exit_code == 0
        assert "--mean" in result.output
        assert "--perturbation-scale" in result.output


class TestFetchCommand:
    def test_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["fetch", "--help"])
        assert result.exit_code == 0
        assert "--source" in result.output


class TestPreviewCommand:
    def test_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["preview", "--help"])
        assert result.exit_code == 0
        assert "--no-popup" in result.output

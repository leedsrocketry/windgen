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
        assert "window" in result.output


class TestGenerateCommand:
    def test_no_date_errors(self, tmp_path: Path) -> None:
        cfg = _write_config(tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["generate", str(cfg)])
        assert result.exit_code != 0

    def test_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["generate", "--help"])
        assert result.exit_code == 0
        assert "--scale" in result.output


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


class TestWindowCommand:
    def test_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["window", "--help"])
        assert result.exit_code == 0
        assert "--scale" in result.output
        assert "--confidence" in result.output
        assert "--duration" in result.output

    def test_scale_05(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["window", "--scale", "0.5"])
        assert result.exit_code == 0
        assert "2 days" in result.output

    def test_scale_02(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["window", "--scale", "0.2"])
        assert result.exit_code == 0
        assert "5 days" in result.output

    def test_scale_1(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["window", "--scale", "1.0"])
        assert result.exit_code == 0
        assert "1 days" in result.output

    def test_custom_confidence(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["window", "--scale", "0.5", "--confidence", "0.90"])
        assert result.exit_code == 0
        assert "2 days" in result.output

    def test_duration_mode(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["window", "--scale", "0.5", "--duration", "10"])
        assert result.exit_code == 0
        assert "at least 7 of 10" in result.output

    def test_invalid_scale_zero(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["window", "--scale", "0.0"])
        assert result.exit_code != 0

    def test_invalid_scale_too_high(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["window", "--scale", "3.0"])
        assert result.exit_code != 0

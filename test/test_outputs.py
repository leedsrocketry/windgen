"""Tests for output.py — .npz round-trip, metadata, filename parsing."""

from __future__ import annotations

import datetime
from pathlib import Path

import numpy as np
import pytest

from windgen.outputs import (
    load_ensemble,
    make_filename,
    parse_filename,
    save_ensemble,
)

class TestFilenameParsing:
    def test_valid(self) -> None:
        date, source = parse_filename("13-07-26-gfs.npz")
        assert date == datetime.date(2026, 7, 13)
        assert source == "gfs"

    def test_earthgram(self) -> None:
        date, source = parse_filename("01-01-27-earthgram.npz")
        assert date == datetime.date(2027, 1, 1)
        assert source == "earthgram"

    def test_invalid(self) -> None:
        with pytest.raises(ValueError, match="Cannot parse date"):
            parse_filename("bad-name.npz")

    def test_no_extension(self) -> None:
        with pytest.raises(ValueError, match="Cannot parse date"):
            parse_filename("13-07-26-gfs")


class TestMakeFilename:
    def test_round_trip(self) -> None:
        d = datetime.date(2026, 7, 13)
        fname = make_filename(d, "gfs")
        assert fname == "13-07-26-gfs.npz"
        date, source = parse_filename(fname)
        assert date == d
        assert source == "gfs"


class TestNpzRoundTrip:
    def test_save_and_load(self, tmp_path: Path) -> None:
        alt = np.arange(0, 5000, 250, dtype=float)
        ew = np.random.default_rng(42).normal(size=(10, len(alt)))
        ns = np.random.default_rng(43).normal(size=(10, len(alt)))
        meta = {"source": "test", "n_profiles": 10}

        p = tmp_path / "test.npz"
        save_ensemble(p, alt, ew, ns, metadata=meta)
        alt2, ew2, ns2, meta2 = load_ensemble(p)

        np.testing.assert_array_equal(alt, alt2)
        np.testing.assert_array_almost_equal(ew, ew2)
        np.testing.assert_array_almost_equal(ns, ns2)
        assert meta2 is not None
        assert meta2["source"] == "test"
        assert meta2["n_profiles"] == 10

    def test_no_metadata(self, tmp_path: Path) -> None:
        alt = np.array([0.0, 250.0, 500.0])
        ew = np.array([[1.0, 2.0, 3.0]])
        ns = np.array([[4.0, 5.0, 6.0]])

        p = tmp_path / "no_meta.npz"
        save_ensemble(p, alt, ew, ns)
        _, _, _, meta = load_ensemble(p)
        assert meta is None

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        p = tmp_path / "a" / "b" / "test.npz"
        alt = np.array([0.0])
        ew = np.array([[1.0]])
        ns = np.array([[2.0]])
        save_ensemble(p, alt, ew, ns)
        assert p.exists()

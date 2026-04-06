"""Click CLI with Rich display — fetch, generate, and preview commands."""

from __future__ import annotations

import datetime
import sys
import warnings as _warnings_mod
from pathlib import Path

import click
import numpy as np
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    ProgressColumn,
    Task,
    TextColumn,
)
from rich.spinner import Spinner
from rich.text import Text

from . import generate as gen
from . import outputs
from .config import load_montecarlo, load_site

console = Console()

# Maximum date range (days) for climatology mode before warning.
_MAX_CLIM_RANGE_DAYS = 14

# ---------------------------------------------------------------------------
# CLI display helpers (reimplemented from LFS conventions, no LFS dependency)
# ---------------------------------------------------------------------------


class _ElapsedColumn(ProgressColumn):
    """Elapsed time shown as ``mm:ss`` in white.

    Reads ``_start`` and ``_finish`` from ``task.fields`` so each bar
    tracks its own wall-clock interval independently.
    """

    def render(self, task: Task) -> Text:
        import time as _time

        start = task.fields.get("_start")
        finish = task.fields.get("_finish")
        if start is None:
            return Text("00:00", style="white")
        elapsed = (finish if finish is not None else _time.monotonic()) - start
        mins, secs = divmod(int(elapsed), 60)
        return Text(f"{mins:02d}:{secs:02d}", style="white")


def _progress_columns() -> tuple:
    """Return the standard column tuple shared by all progress bars."""
    return (
        TextColumn("[bold]{task.description:<30}"),
        BarColumn(bar_width=40, complete_style="white", finished_style="white"),
        TextColumn("{task.completed}/{task.total}"),
        TextColumn("\u2014"),
        _ElapsedColumn(),
    )


class _RunDisplay:
    """Composite live display: spinner + warnings panel + progress bars.

    The spinner sits at the top.  Warnings accumulate as bullet points in
    a single yellow-bordered panel beneath it.  Progress bars (when active)
    appear below the warnings panel.
    """

    def __init__(self, con: Console) -> None:
        self._console = con
        self._warnings: list[str] = []
        self._spinner = Spinner("line", text="Initialising...")
        self._progress = Progress(*_progress_columns(), auto_refresh=False)
        self._live = Live(
            self._build(), console=con, refresh_per_second=12,
        )

    # -- lifecycle -----------------------------------------------------------

    def start(self) -> None:
        self._live.start()

    def stop(self) -> None:
        self._live.stop()

    # -- status --------------------------------------------------------------

    def update_status(self, text: str) -> None:
        self._spinner.update(text=text, style="default")
        self._refresh()

    def add_warning(self, text: str) -> None:
        self._warnings.append(text)
        self._refresh()

    # -- progress ------------------------------------------------------------

    def add_task(self, description: str, total: int) -> int:
        task_id = self._progress.add_task(description, total=total)
        self._refresh()
        return task_id

    def start_task(self, task_id: int) -> None:
        import time
        self._progress.update(task_id, _start=time.monotonic())
        self._refresh()

    def advance_task(self, task_id: int, advance: int = 1) -> None:
        self._progress.update(task_id, advance=advance)
        self._refresh()

    def update_task(self, task_id: int, completed: int) -> None:
        self._progress.update(task_id, completed=completed)
        self._refresh()

    def finish_task(self, task_id: int) -> None:
        import time
        self._progress.update(
            task_id,
            completed=self._progress.tasks[task_id].total,
            _finish=time.monotonic(),
        )
        self._live.update(self._build())
        self._live.refresh()

    # -- internals -----------------------------------------------------------

    def _build(self) -> Group:
        parts: list = [Text(), self._spinner, Text()]
        if self._warnings:
            bullet_list = "\n".join(f"\u2022 {w}" for w in self._warnings)
            parts.append(Panel(
                bullet_list,
                border_style="yellow",
                title="WARNINGS",
                title_align="left",
            ))
            parts.append(Text())
        if self._progress.tasks:
            parts.append(self._progress)
        return Group(*parts)

    def _refresh(self) -> None:
        self._live.update(self._build())
        self._live.refresh()


def _error_exit(message: str, display: _RunDisplay | None = None) -> None:
    """Stop any live display, print a red ERROR panel, and exit."""
    if display is not None:
        display.stop()
    console.print(Panel(message, title="ERROR", border_style="red"))
    sys.exit(1)


def _print_warnings(warnings_list: list[str]) -> None:
    """Print collected warnings as a yellow panel with bullet points."""
    if not warnings_list:
        return
    body = "\n".join(f"\u2022 {w}" for w in warnings_list)
    console.print(Panel(body, title="WARNINGS", border_style="yellow"))


def _start_warning_capture(
    display: _RunDisplay | None = None,
) -> tuple[list[str], object]:
    """Begin routing ``warnings.warn()`` to *display* (if provided)."""
    collected: list[str] = []
    original = _warnings_mod.showwarning

    def _hook(
        message: Warning | str,
        category: type[Warning],
        filename: str,
        lineno: int,
        file: object = None,
        line: str | None = None,
    ) -> None:
        text = str(message)
        collected.append(text)
        if display is not None:
            display.add_warning(text)

    _warnings_mod.showwarning = _hook  # type: ignore[assignment]
    return collected, original


def _stop_warning_capture(original: object) -> None:
    """Restore the original ``warnings.showwarning``."""
    _warnings_mod.showwarning = original  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Click group
# ---------------------------------------------------------------------------


class _QuietGroup(click.Group):
    """Suppress Click's default ``Aborted!`` on keyboard interrupt."""

    def invoke(self, ctx: click.Context):
        try:
            return super().invoke(ctx)
        except KeyboardInterrupt:
            raise SystemExit(130)


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------


def _parse_date(date_str: str) -> datetime.date:
    """Parse DD-MM-YY date string."""
    try:
        return datetime.datetime.strptime(date_str, "%d-%m-%y").date()
    except ValueError:
        raise click.BadParameter(
            f"Invalid date format: {date_str}. Expected DD-MM-YY."
        )


def _date_range(
    start: datetime.date, end: datetime.date,
) -> list[datetime.date]:
    """Return list of dates from start to end inclusive."""
    days = (end - start).days
    return [start + datetime.timedelta(days=d) for d in range(days + 1)]


# ---------------------------------------------------------------------------
# CLI group
# ---------------------------------------------------------------------------


@click.group(cls=_QuietGroup, help="windgen \u2014 Wind profile ensemble generator for LFS.")
def main() -> None:
    pass


# ---------------------------------------------------------------------------
# fetch command
# ---------------------------------------------------------------------------


@main.command()
@click.argument("config", type=click.Path(exists=True))
@click.option(
    "--source",
    type=click.Choice(["gfs", "ecmwf", "ukv"], case_sensitive=False),
    required=True,
    help="Forecast data source.",
)
@click.argument("date", type=str)
@click.argument("date_end", type=str, required=False, default=None)
def fetch(config: str, source: str, date: str, date_end: str | None) -> None:
    """Download forecast mean wind profiles from GFS/ECMWF/UKV."""
    config_path = Path(config)

    try:
        site = load_site(config_path)
    except (FileNotFoundError, ValueError) as exc:
        _error_exit(str(exc))
        return

    start = _parse_date(date)
    end = _parse_date(date_end) if date_end else start
    dates = _date_range(start, end)

    # Lazy-import the source module
    source_lower = source.lower()
    try:
        if source_lower == "gfs":
            from .fetch import gfs as src_mod
        elif source_lower == "ecmwf":
            from .fetch import ecmwf as src_mod
        elif source_lower == "ukv":
            from .fetch import ukv as src_mod
        else:
            _error_exit(f"Unknown source: {source}")
            return
    except ImportError as exc:
        _error_exit(str(exc))
        return

    out_dir = config_path.parent / "wind" / "mean"
    out_dir.mkdir(parents=True, exist_ok=True)

    display = _RunDisplay(console)
    display.update_status("Fetching forecast data...")
    display.start()
    captured, original_warn = _start_warning_capture(display)

    try:
        task = display.add_task("Fetching profiles", total=len(dates))
        display.start_task(task)

        for d in dates:
            fname = outputs.make_filename(d, source_lower)
            out_path = out_dir / fname
            if out_path.exists():
                display.add_warning(f"Overwriting {out_path}")

            try:
                alt, ew, ns = src_mod.fetch_mean_profile(
                    date=d,
                    lat=site.latitude,
                    lon=site.longitude,
                    elevation=site.elevation,
                    altitude_max_m=20000,
                    altitude_step_m=250,
                )
            except Exception as exc:
                display.stop()
                _stop_warning_capture(original_warn)
                _print_warnings(captured)
                _error_exit(f"Failed to download {source_lower} data: {exc}")
                return

            meta = gen.build_metadata(
                source=source_lower,
                date=d,
                site=site,
                perturbation_scale=0.0,
                n_profiles=1,
                master_seed=0,
            )
            outputs.save_ensemble(out_path, alt, ew, ns, metadata=meta)
            display.advance_task(task)

        display.finish_task(task)
    finally:
        display.stop()
        _stop_warning_capture(original_warn)

    _print_warnings(captured)
    console.print(f"[green]Saved {len(dates)} mean profile(s) to {out_dir}[/green]")


# ---------------------------------------------------------------------------
# generate command
# ---------------------------------------------------------------------------


@main.command()
@click.argument("config", type=click.Path(exists=True))
@click.argument("date", type=str, required=False, default=None)
@click.argument("date_end", type=str, required=False, default=None)
@click.option("--mean", "mean_path", type=click.Path(), default=None,
              help="Mean wind profile .npz or directory of .npz files.")
@click.option("--perturbation-scale", type=float, default=1.0,
              help="Perturbation magnitude (0.0\u20131.0).")
@click.option("--n-profiles", type=int, default=None,
              help="Number of ensemble members.")
@click.option("--master-seed", type=int, default=None,
              help="Master random seed.")
@click.option("--altitude-max", type=int, default=20000,
              help="Maximum altitude in metres AGL.")
@click.option("--altitude-step", type=int, default=250,
              help="Altitude grid spacing in metres.")
@click.option("-q", "--no-popup", is_flag=True, default=False,
              help="Suppress matplotlib preview.")
def generate(
    config: str,
    date: str | None,
    date_end: str | None,
    mean_path: str | None,
    perturbation_scale: float,
    n_profiles: int | None,
    master_seed: int | None,
    altitude_max: int,
    altitude_step: int,
    no_popup: bool,
) -> None:
    """Generate a perturbed wind profile ensemble (.npz)."""
    config_path = Path(config)
    warns: list[str] = []

    try:
        site = load_site(config_path)
    except (FileNotFoundError, ValueError) as exc:
        _error_exit(str(exc))
        return

    try:
        gen.check_earthgram()
    except FileNotFoundError as exc:
        _error_exit(str(exc))
        return

    # Resolve n_profiles and master_seed from config fallbacks
    mc = load_montecarlo(config_path)
    if n_profiles is None:
        n_profiles = mc.n_samples
        warns.append(f"Using n-profiles={n_profiles} from config")
    if master_seed is None:
        master_seed = mc.master_seed
        warns.append(f"Using master-seed={master_seed} from config")

    # Resolve dates and mean profiles
    jobs: list[tuple[datetime.date, str, tuple | None]] = []

    if mean_path is not None:
        mp = Path(mean_path)
        if date_end is not None:
            _print_warnings(warns)
            _error_exit("DATE_END is not valid with --mean. Dates are taken from the mean profile filename(s).")
            return
        if date is not None:
            warns.append("Ignoring DATE argument \u2014 dates taken from mean profile filename(s)")

        if mp.is_dir():
            npz_files = sorted(mp.glob("*.npz"))
            if not npz_files:
                warns.append(f"No .npz files found in {mp}")
                _print_warnings(warns)
                _error_exit(f"No .npz files found in {mp}")
                return
            for npz in npz_files:
                try:
                    d, source_name = outputs.parse_filename(npz.name)
                except ValueError as exc:
                    _print_warnings(warns)
                    _error_exit(str(exc))
                    return
                alt, ew, ns, _ = outputs.load_ensemble(npz)
                jobs.append((d, source_name, (alt, ew, ns)))
        elif mp.is_file():
            try:
                d, source_name = outputs.parse_filename(mp.name)
            except ValueError as exc:
                _print_warnings(warns)
                _error_exit(str(exc))
                return
            alt, ew, ns, _ = outputs.load_ensemble(mp)
            jobs.append((d, source_name, (alt, ew, ns)))
        else:
            _error_exit(f"Mean profile not found: {mean_path}")
            return
    else:
        if date is None:
            _print_warnings(warns)
            _error_exit("DATE is required in climatology mode (no --mean).")
            return
        start = _parse_date(date)
        end = _parse_date(date_end) if date_end else start
        if start == end:
            jobs.append((start, "earthgram", None))
        else:
            span_days = (end - start).days
            if span_days > 14:
                warns.append(
                    f"Date range spans {span_days} days (>{_MAX_CLIM_RANGE_DAYS}). "
                    "Climatological variability may be non-negligible across this window."
                )
            midpoint = start + datetime.timedelta(days=span_days // 2)
            warns.append(
                f"Climatology mode: using midpoint date {midpoint.strftime('%d-%m-%y')} "
                f"for range {start.strftime('%d-%m-%y')} to {end.strftime('%d-%m-%y')}"
            )
            jobs.append((midpoint, "earthgram", None))

    out_dir = config_path.parent / "wind"
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs_paths: list[Path] = []

    display = _RunDisplay(console)
    for w in warns:
        display.add_warning(w)
    display.update_status("Generating ensemble...")
    display.start()
    captured, original_warn = _start_warning_capture(display)

    try:
        for job_date, source_name, mean_prof in jobs:
            fname = outputs.make_filename(job_date, source_name)
            out_path = out_dir / fname
            if out_path.exists():
                display.add_warning(f"Overwriting {out_path}")

            task = display.add_task(fname, total=n_profiles)
            display.start_task(task)

            def _on_progress(current: int, total: int, _t: int = task) -> None:
                display.update_task(_t, completed=current)

            alt, ew, ns = gen.generate_ensemble(
                site=site,
                date=job_date,
                n_profiles=n_profiles,
                master_seed=master_seed,
                perturbation_scale=perturbation_scale,
                altitude_max_m=altitude_max,
                altitude_step_m=altitude_step,
                mean_profile=mean_prof,
                on_progress=_on_progress,
            )

            display.finish_task(task)

            meta = gen.build_metadata(
                source=source_name,
                date=job_date,
                site=site,
                perturbation_scale=perturbation_scale,
                n_profiles=n_profiles,
                master_seed=master_seed,
                mean_profile_path=str(mean_path) if mean_path else None,
            )
            outputs.save_ensemble(out_path, alt, ew, ns, metadata=meta)
            outputs_paths.append(out_path)
    finally:
        display.stop()
        _stop_warning_capture(original_warn)

    _print_warnings(captured)
    console.print(f"[green]Generated {len(outputs_paths)} ensemble(s) in {out_dir}[/green]")

    for p in outputs_paths:
        outputs.plot_ensemble(p, save=no_popup)


# ---------------------------------------------------------------------------
# preview command
# ---------------------------------------------------------------------------


@main.command()
@click.argument("target", type=click.Path(exists=True))
@click.option("-q", "--no-popup", is_flag=True, default=False,
              help="Save figures to disk instead of interactive display.")
def preview(target: str, no_popup: bool) -> None:
    """Plot wind profiles from .npz file(s)."""
    target_path = Path(target)

    if target_path.is_dir():
        npz_files = sorted(target_path.glob("*.npz"))
        if not npz_files:
            _error_exit(f"No .npz files found in {target_path}")
            return
    else:
        npz_files = [target_path]

    for npz in npz_files:
        outputs.plot_ensemble(npz, save=no_popup)
        if no_popup:
            console.print(f"[green]Saved {npz.with_suffix('.png')}[/green]")

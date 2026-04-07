# Wind Profile Generator — Specification
---

## 1 Purpose

This tool generates ensembles of perturbed wind profiles for consumption by the Leeds Flight Simulator (LFS). It encapsulates all wind data source handling (EarthGRAM climatology, GFS forecasts, ECMWF forecasts, UKV forecasts and radiosonde measurements) and perturbation modelling behind a CLI, producing `.npz` files that the simulator reads without knowledge of the source.

The tool is used at each stage of a launch campaign — safety case preparation (months before), operations planning (days before), and launch-day go/no-go (hours before) — to generate the appropriate wind input for the simulator.


## 2 Output Format

All commands that produce wind data write NumPy `.npz` files containing:

| Array key | Shape | Description |
|-----------|-------|-------------|
| `altitude_m` | `(M,)` | Altitude grid in metres AGL, monotonically increasing |
| `wind_east_ms` | `(N, M)` | Eastward wind component per profile per altitude (m/s, positive = blowing towards east) |
| `wind_north_ms` | `(N, M)` | Northward wind component per profile per altitude (m/s, positive = blowing towards north) |

`N` is the number of profiles (ensemble size). `M` is the number of altitude grid points. Mean wind files from `fetch` have N=1; perturbed ensembles from `generate` have N≥1. Both use the same format and are directly loadable by LFS `wind.py`.

The file also stores generation metadata as a serialised JSON string under the key `metadata`, containing: source type, generation timestamp, applicable date, launch site coordinates (including elevation), perturbation scale, and (where applicable) the input mean profile path.

### 2.1 Altitude Convention

All wind profiles use **metres AGL** (above ground level). EarthGRAM outputs altitude in km MSL; the tool subtracts `site.elevation` and converts to metres, discarding any points below pad level. LFS handles the MSL conversion internally for atmospheric model lookups.


## 3 Wind Data Sources

### 3.1 EarthGRAM 2024 Climatology

**When:** Months before launch, for safety case preparation.

Uses EarthGRAM's internal climatological database (NCEP) for both the mean wind profile and perturbations at the specified launch site and month. Represents the full range of wind conditions historically observed. This is the basis for the safety case submitted to the CAA.

### 3.2 GFS Forecast

**When:** Days before launch, for operations planning.

The `fetch` command downloads GFS forecast data from the NOAA API for the specified date range and extracts the mean wind profile at the launch site (nearest grid point or bilinear interpolation). The resulting mean profile can then be fed to `generate` as an auxiliary atmosphere for perturbation generation. GFS data is freely available and updated four times daily.

### 3.3 ECMWF Forecast

**When:** Days before launch, for operations planning.

The `fetch` command downloads ECMWF forecast data for the specified date range. Handling is analogous to GFS. ECMWF generally offers higher accuracy over Europe but requires a data subscription. Having both available allows cross-checking.

### 3.4 UKV Forecast

**When:** Days before launch, for operations planning.

The `fetch` command downloads UKV forecast data for the specified date range. Handling is analogous to GFS and ECMWF. UKV offers higher accuracy and detail over the UK but requires a data subscription. Having all three available allows cross-checking.

### 3.5 Radiosonde Measurement

**When:** Hours before launch, on site, for go/no-go decision.

A weather balloon sounding from the launch site gives the actual wind profile overhead at the time of measurement. The sounding is converted to a mean wind `.npz` (N=1) and fed to `generate --mean`, the same as any forecast source. This is the most accurate input and is what the launch director uses for the final call.


## 4 Perturbation Model

All sources use NASA EarthGRAM 2024, invoked as a prebuilt executable (`earthgram/bin/EarthGRAM.exe`) via `subprocess`. Each profile in the ensemble is produced by a separate EarthGRAM run with a different random seed (`InitialRandomSeed`), creating statistically independent realisations of wind variability around the mean.

The `RandomPerturbationScale` / `HorizontalWindPerturbationScale` parameters control perturbation magnitude: 1.0 applies the full climatological variability, 0.0 produces N identical copies of the deterministic mean (useful for debugging or verification runs).


## 5 Profile Generation Process

For each profile `i` in the ensemble (i = 0 … N−1):

1. Write a NAMELIST input file configuring: launch site lat/lon, date/time, perturbation scale, altitude grid (`InitialHeight`, `DeltaHeight`, `NumberOfPositions`), `InitialRandomSeed` derived deterministically from a master seed and profile index `i`, and data/SPICE paths. If a mean wind profile is provided (from any source — forecast or radiosonde), configure it as an auxiliary atmosphere (`UseAuxiliaryAtmosphere = 1`).
2. Invoke `earthgram/bin/EarthGRAM.exe -file <namelist>` via `subprocess.run()`.
3. Parse the output CSV. Read `PerturbedEWWind_ms` (eastward, m/s) and `PerturbedNSWind_ms` (northward, m/s) at each altitude from the `Height_km` column. Subtract site elevation and convert to metres AGL.
4. Store as row `i` of the output arrays.
5. Clean up the temporary NAMELIST and output files.


## 6 Command-Line Interface

### 6.1 Technology

Click command group with Rich console output, reimplementing (not importing) the LFS CLI conventions:

- **`_QuietGroup`** — custom `click.Group` subclass that suppresses Click's "Aborted!" on keyboard interrupt.
- **`_RunDisplay`** — composite Rich `Live` display with an animated **spinner** (top), a **warnings panel** (yellow-bordered, bullet-pointed, appears when warnings are collected), and **progress bars** (bottom) using the standard column layout: bold description (30 chars), 40-char white bar, count, em-dash, mm:ss elapsed.
- **`_error_exit(message, display=None)`** — stops any live display, prints a red-bordered `ERROR` panel, and calls `sys.exit(1)`. All user-facing errors must go through this.
- **`_print_warnings(warnings_list)`** — prints collected warnings as a yellow-bordered `WARNINGS` panel with bullet points.
- **Warning capture** — redirect `warnings.warn()` to the live display during command execution so warnings appear in the warnings panel rather than as bare stderr text.

LFS will not be a dependency of windgen.

### 6.2 Error and Warning Conditions

**Errors** (red panel, exit 1):

| Condition | Message |
|-----------|---------|
| `CONFIG` file not found or invalid YAML | "Cannot read config: {path}" |
| Missing required config fields (`site.latitude`, etc.) | "Config missing required field: site.{field}" |
| `earthgram/bin/EarthGRAM.exe` not found | "EarthGRAM not found at {path}. See CLAUDE.md for setup." |
| EarthGRAM process exits non-zero | "EarthGRAM failed (exit {code}): {stderr}" |
| `--mean` file/directory not found | "Mean profile not found: {path}" |
| Date cannot be parsed from mean profile filename | "Cannot parse date from filename: {name}. Expected {DD-MM-YY}-{source}.npz" |
| `fetch` network request fails | "Failed to download {source} data: {reason}" |
| `fetch` source dependency not installed | "{source} requires {package}. Install with: pip install {package}" |
| NCEP data missing for requested month | "NCEP data not found for month {month}. Copy Nb9715{mm}.bin to earthgram/data/NCEPdata/FixedBin/" |

**Warnings** (yellow panel, non-fatal):

| Condition | Message |
|-----------|---------|
| `DATE` supplied with `--mean` (dates derived from filenames) | "Ignoring DATE argument — dates taken from mean profile filename(s)" |
| `--mean` directory contains no `.npz` files | "No .npz files found in {path}" (then errors) |
| Output file already exists (will be overwritten) | "Overwriting {path}" |
| `--n-profiles` or `--master-seed` not given and not in config | "Using default {param}={value}" |

### 6.3 Entry Point

Invoked as `python .` from the `windgen/` directory:

```
windgen — Wind profile ensemble generator for LFS.

Commands:
  fetch      Download forecast mean wind profiles from GFS/ECMWF/UKV
  generate   Generate a perturbed wind profile ensemble (.npz)
  preview    Plot wind profiles from .npz file(s)
```

### 6.4 `fetch` Command

```
python . fetch CONFIG --source SOURCE DATE [DATE_END]
```

Downloads forecast wind data and saves one mean wind profile per day as `.npz` (N=1).

**Arguments:**

| Name | Type | Description |
|------|------|-------------|
| `CONFIG` | `click.Path(exists=True)` | LFS simulation `config.yaml` (provides `site.latitude`, `site.longitude`, `site.elevation`) |
| `DATE` | `str` | Start date (`DD-MM-YY`). If `DATE_END` omitted, fetches this single day. |
| `DATE_END` | `str` (optional) | End date, inclusive. Fetches one profile per day in the range. |

**Options:**

| Flag | Type | Description |
|------|------|-------------|
| `--source` | `click.Choice(["gfs", "ecmwf", "ukv"])` | Forecast data source (required) |

**Output files:** Written to `wind/mean/` relative to `CONFIG`, named `{date}-{source}.npz` (e.g. `wind/mean/13-07-26-gfs.npz`). Creates the directory if it does not exist.

This is the only command that requires internet access.

### 6.5 `generate` Command

```
python . generate CONFIG [DATE] [DATE_END] [OPTIONS]
```

Generates a perturbed wind profile ensemble for each day.

**Date resolution:** The dates to generate for are determined by one of two mutually exclusive modes:

- **Climatology mode** (no `--mean`): `DATE` is required. `DATE_END` is optional (defaults to `DATE`). Generates one ensemble per day in the range.
- **Mean profile mode** (`--mean`): dates are parsed from the mean profile filename(s) (`{DD-MM-YY}-{source}.npz`). If `DATE` is also supplied, it is ignored with a warning. If a date cannot be parsed from a filename, error and exit.

When `--mean` points to a **directory**, all `.npz` files in that directory are processed — one ensemble per file, dates and source names taken from filenames.

**Arguments:**

| Name | Type | Description |
|------|------|-------------|
| `CONFIG` | `click.Path(exists=True)` | LFS simulation `config.yaml` (provides `site.latitude`, `site.longitude`, `site.elevation`) |
| `DATE` | `str` (optional) | Start date (`DD-MM-YY`). Required in climatology mode, ignored with warning in mean profile mode. |
| `DATE_END` | `str` (optional) | End date, inclusive. Only used in climatology mode. |

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--mean` | `Path` | — | Mean wind profile `.npz` (from `fetch`), or directory of `.npz` files. If omitted, uses EarthGRAM climatology. |
| `--perturbation-scale` | `float` | `1.0` | Perturbation magnitude (0.0 = deterministic, 1.0 = full variability) |
| `--n-profiles` | `int` | from config | Number of ensemble members. Falls back to LFS config `montecarlo.n_samples`, then default 1000. |
| `--master-seed` | `int` | from config | Master random seed. Falls back to LFS config `montecarlo.master_seed`, then default 42. |
| `--altitude-max` | `int` | `20000` | Maximum altitude in metres AGL |
| `--altitude-step` | `int` | `250` | Altitude grid spacing in metres |
| `-q` / `--no-popup` | flag | off | Suppress the matplotlib preview window |

**Output files:** Written to `wind/` relative to `CONFIG`. The filename is derived from the date and source:

- With `--mean wind/mean/13-07-26-gfs.npz` → `wind/13-07-26-gfs.npz`
- Without `--mean` (climatology) → `wind/13-07-26-earthgram.npz`

One `.npz` per day. Creates the directory if it does not exist.

**Progress:** The spinner shows the current status. A Rich progress bar tracks per-profile generation (one bar per day if multiple days). On completion, displays a matplotlib preview for each ensemble (unless `-q`). Does not save figures unless `-q` is set. Same plotting method as `preview` command.

### 6.6 `preview` Command

```
python . preview TARGET [-q]
```

**Argument:**

| Name | Type | Description |
|------|------|-------------|
| `TARGET` | `click.Path(exists=True)` | A single `.npz` file or a directory containing `.npz` files |

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `-q` / `--no-popup` | flag | off | Save figures to disk instead of interactive display |

Plots mean wind speed (m/s) on the x-axis and altitude on the y-axis with two scales: metres (primary) and feet (secondary), both on the left. Shows the mean wind profile and the bounds (min/max envelope) of all profiles in the file. If a directory is given, creates one plot per `.npz` file.

When `-q` is set, saves each figure as a `.png` alongside its `.npz` file instead of displaying interactively.


## 7 File Layout

All wind data lives under `wind/` relative to the LFS simulation case directory:

```
simulations/cases/g2b2-cape-wrath/
├── config.yaml                      # LFS simulation config (site location, etc.)
├── wind/
│   ├── mean/
│   │   ├── 12-07-26-gfs.npz        # fetch output: GFS mean, 12 Jul 2026
│   │   ├── 12-07-26-ecmwf.npz      # fetch output: ECMWF mean, 12 Jul 2026
│   │   └── 13-07-26-gfs.npz        # fetch output: GFS mean, 13 Jul 2026
│   ├── 12-07-26-gfs.npz            # generate output: perturbed ensemble from GFS mean
│   ├── 12-07-26-ecmwf.npz          # generate output: perturbed ensemble from ECMWF mean
│   ├── 12-07-26-earthgram.npz      # generate output: perturbed ensemble from climatology
│   └── 13-07-26-gfs.npz
└── results/
```

The LFS `config.yaml` references the ensemble file(s):

```yaml
launch:
  wind_profiles: "wind/13-07-26-gfs.npz"
```


## 8 Architecture

```
windgen/
├── __main__.py      # Entry point (imports main from cli)
├── cli.py           # Click group + fetch/generate/preview commands, Rich display helpers
├── config.py        # LFS config.yaml loading (site location, elevation, MC params)
├── generate.py      # EarthGRAM orchestration: NAMELIST writing, subprocess, CSV parsing
├── fetch/
│   ├── gfs.py       # GFS API download → mean .npz
│   ├── ecmwf.py     # ECMWF API download → mean .npz
│   └── ukv.py       # UKV API download → mean .npz
├── output.py        # .npz read/write with metadata, and ensemble visualisation (matplotlib)
└── test/
    ├── test_cli.py       # Command invocation, argument validation, error/warning panels
    ├── test_config.py    # YAML loading, missing fields, default fallbacks
    ├── test_generate.py  # NAMELIST writing, CSV parsing, AGL conversion, seed derivation
    └── test_output.py    # .npz round-trip, metadata serialisation, filename parsing
```

### 8.1 Fetch Source Interface

All fetch source modules implement a common download interface:

```python
def fetch_mean_profile(
    date: datetime.date,
    lat: float,
    lon: float,
    elevation: float,
    altitude_max_m: int,
    altitude_step_m: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Download forecast data and return (altitude_m, wind_east_ms, wind_north_ms).
    altitude_m is in metres AGL. wind arrays have shape (1, M)."""
```

### 8.2 Generate

`generate.py` handles all EarthGRAM interaction. It builds a NAMELIST template from the site config, optionally sets `UseAuxiliaryAtmosphere = 1` if a mean profile is provided, then iterates over seeds — writing a NAMELIST, invoking `EarthGRAM.exe`, and parsing the CSV output for each ensemble member. The auxiliary atmosphere mechanism is source-agnostic: any `.npz` with the standard arrays (§2) works, regardless of whether it came from `fetch`, a radiosonde conversion, or manual creation.


## 9 Dependencies

| Package | Purpose |
|---------|---------|
| click | CLI command group and argument parsing |
| rich | Console output, progress bars, error/warning panels |
| numpy | Arrays, `.npz` output |
| matplotlib | Preview plot |
| pyyaml | YAML configuration file loading |
| pytest | Test suite (`python -m pytest`) |
| cfgrib or eccodes | GFS GRIB2 reading (`fetch --source gfs` only) |
| netCDF4 or xarray | ECMWF netCDF reading (`fetch --source ecmwf` only) |

**External:** NASA EarthGRAM 2024 prebuilt executable and runtime data in `earthgram/` (gitignored, ~480 MB). See `CLAUDE.md` for setup. No compilation required — the tool invokes `earthgram/bin/EarthGRAM.exe` via `subprocess`.


## 10 Operational Workflow

| Campaign stage | Command | Notes |
|----------------|---------|-------|
| Safety case (months before) | `generate CONFIG 12-07-26 14-07-26` | EarthGRAM climatology (no `--mean`), full perturbation |
| Operations planning (days before) | `fetch CONFIG --source gfs 12-07-26 14-07-26` then `generate CONFIG --mean wind/mean/` | Fetch forecast, generate perturbed ensemble for all fetched days |
| Go/no-go (hours before, on site) | `generate CONFIG --mean sounding.npz` | Radiosonde measurement as mean input |
| Debugging/verification | `generate CONFIG 13-07-26 --perturbation-scale 0.0` | Deterministic — all profiles identical to the mean |
| Visual check | `preview wind/` or `preview wind/13-07-26-gfs.npz` | Inspect before running LFS |

Update `wind_profiles` in `config.yaml` to point at the chosen `.npz` file, then run the simulator.

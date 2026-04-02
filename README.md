# windgen

Generates ensembles of perturbed wind profiles for use as input to the Leeds Flight Simulator. Supports EarthGRAM 2016 climatology, GFS and ECMWF forecasts, and radiosonde measurements, covering every stage of a launch campaign from safety case preparation to launch-day go/no-go.

---

## Table of Contents

- [Background](#background)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Usage](#usage)
- [Input Files](#input-files)
- [Output Files](#output-files)
- [Operational Workflow](#operational-workflow)
- [Contact](#contact)
- [Licence](#licence)

---

## Background

LFS requires wind profiles as a `.npz` ensemble — N independently perturbed profiles on a common altitude grid. Each Monte Carlo sample draws one profile from the ensemble, so the spread of profiles is what drives landing dispersion due to wind uncertainty.

windgen encapsulates all wind data source handling and perturbation modelling behind a GUI, so the simulator operator does not need to interact with EarthGRAM directly. The output is a single `.npz` file that LFS reads without knowledge of the source.

All perturbations are generated via NASA EarthGRAM (through the GRAMpy interface), using a different random seed per profile to produce statistically independent realisations. The RUSCALE parameter controls perturbation magnitude: 1.0 applies the full climatological variability; 0.0 produces N identical copies of the deterministic mean.

Built for the Gryphon II Block II (G2B2) campaign by the Leeds University Rocketry Association (LURA).

> **Status: not yet implemented.** `specification.md` defines the planned design.


## Installation

**Prerequisites:** Python 3.10+, GRAMpy (`_gram.so`/`.pyd`) and EarthGRAM data files.

```
git clone git@github.com:leedsrocketry/windgen.git
cd windgen
pip install numpy matplotlib pyyaml
```

Optional source dependencies (only required if the corresponding source is selected):

```
pip install cfgrib        # GFS GRIB2 mode
pip install netCDF4       # ECMWF netCDF mode
```


## Quick Start

```
python -m wind_gen
```

Configure launch site, date/time, wind source, ensemble size, and output path in the GUI, then click Generate. The output `.npz` file can then be passed to LFS via the `wind_profiles` field in `simulation.yaml`.


## Usage

windgen is a single-window tkinter GUI. All configuration is done through the interface — no command-line arguments.

**Configuration fields:**

| Field | Description |
|-------|-------------|
| Latitude / Longitude | Launch site coordinates (degrees N / degrees E) |
| Date/time | ISO 8601, or `"now"` for the system clock |
| Mean wind source | EarthGRAM 2016 Climatology, GFS Forecast, ECMWF Forecast, or Radiosonde Measurement |
| Forecast/radiosonde file | Required for GFS, ECMWF, and radiosonde modes; greyed out otherwise |
| Perturbation scale (RUSCALE) | Default 1.0. Set to 0.0 for a deterministic mean ensemble |
| Maximum altitude | Upper bound of the altitude grid (m). Default 20 000 |
| Altitude step | Grid spacing (m). Default 250 |
| Number of profiles | Ensemble size N. Default 1000. Must be ≥ `samples` in `simulation.yaml` |
| Master seed | Seed for deterministic profile generation. Default 42 |
| EarthGRAM data path | Directory containing the compiled EarthGRAM data files |
| Output file | Save path for the `.npz` output. Default `wind_profiles.npz` |

RRA settings (radiosonde mode only): RRA site list file, inner and outer search radii.

A progress bar shows per-profile progress during generation. Generation runs in a background thread; the UI remains responsive. After completion a preview panel shows all N profiles overlaid (east and north components vs altitude) with the ensemble mean highlighted.


## Input Files

### Forecast File (GFS or ECMWF mode)

A GFS GRIB2 file or ECMWF GRIB/netCDF file covering the launch site and time. The tool extracts the wind profile at the nearest grid point (or bilinearly interpolates) and passes it to EarthGRAM as an auxiliary atmosphere for perturbation generation.

### Radiosonde File (radiosonde mode)

A weather balloon sounding from the launch site. Supplied to EarthGRAM via its RRA (Radiosonde Representative Atmosphere) interface.

### EarthGRAM Data Files

Compiled EarthGRAM 2016 data files. Required for all modes. Path set in the GUI.


## Output Files

### Wind Profile `.npz`

A NumPy archive containing:

| Key | Shape | Description |
|-----|-------|-------------|
| `altitude_m` | `(M,)` | Altitude grid, metres AGL, monotonically increasing |
| `wind_east_ms` | `(N, M)` | Eastward wind component per profile per altitude (m/s) |
| `wind_north_ms` | `(N, M)` | Northward wind component per profile per altitude (m/s) |
| `metadata` | string | JSON: source type, timestamp, site coordinates, RUSCALE, grid parameters, ensemble size |

Pass the file path to LFS via `wind_profiles` in `simulation.yaml`. `N` must be ≥ `samples` under `monte_carlo`.


## Operational Workflow

| Campaign stage | Source | RUSCALE | When |
|----------------|--------|---------|------|
| Safety case | EarthGRAM 2016 Climatology | 1.0 | Months before launch — full climatological spread for the planned launch month |
| Operations planning | GFS or ECMWF Forecast | 1.0 | Days before launch — is it worth travelling to the site? |
| Go/no-go | Radiosonde Measurement | 1.0 | Hours before launch, on site — actual conditions overhead. Set date/time to `"now"` |
| Debugging / verification | Any | 0.0 | Deterministic mean — all N profiles identical |


## Contact

- **Toby Thomson** — el21tbt@leeds.ac.uk, me@tobythomson.co.uk
- **LURA Team** — launch@leedsrocketry.co.uk


## Licence

<!-- TODO: Add licence information -->

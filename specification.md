# Wind Profile Generator — Specification
---

## 1 Purpose

This tool generates ensembles of perturbed wind profiles for consumption by the Leeds Flight Simulator (LFS). It encapsulates all wind data source handling (EarthGRAM climatology, GFS forecasts, ECMWF forecasts, radiosonde measurements) and perturbation modelling behind a GUI, producing a single `.npz` file that the simulator reads without knowledge of the source.

The tool is used at each stage of a launch campaign — safety case preparation (months before), operations planning (days before), and launch-day go/no-go (hours before) — to generate the appropriate wind input for the simulator.


## 2 Output Format

The tool produces a NumPy `.npz` file containing:

| Array key | Shape | Description |
|-----------|-------|-------------|
| `altitude_m` | `(M,)` | Altitude grid in metres AGL, monotonically increasing |
| `wind_east_ms` | `(N, M)` | Eastward wind component per profile per altitude (m/s) |
| `wind_north_ms` | `(N, M)` | Northward wind component per profile per altitude (m/s) |

`N` is the number of profiles (ensemble size). `M` is the number of altitude grid points.

The file also stores generation metadata as a serialised JSON string under the key `metadata`, containing: source type, generation timestamp, launch site coordinates, EarthGRAM RUSCALE, altitude grid parameters, ensemble size, and (where applicable) the path to the input forecast/radiosonde file.


## 3 Wind Data Sources

### 3.1 EarthGRAM 2016 Climatology

**When:** Months before launch, for safety case preparation.

Uses EarthGRAM's internal climatological database for both the mean wind profile and perturbations at the specified launch site and month. Represents the full range of wind conditions historically observed. This is the basis for the safety case submitted to the CAA.

### 3.2 GFS Forecast

**When:** Days before launch, for operations planning.

A GFS GRIB2 file provides the mean wind profile at the launch site. The tool extracts the nearest grid point or performs bilinear interpolation, then feeds the profile to EarthGRAM as an auxiliary atmosphere for perturbation generation. GFS data is freely available and updated four times daily.

### 3.3 ECMWF Forecast

**When:** Days before launch, for operations planning.

An ECMWF GRIB or netCDF file provides the mean wind profile. Handling is analogous to GFS. ECMWF generally offers higher accuracy over Europe but requires a data subscription. Having both available allows cross-checking.

### 3.4 Radiosonde Measurement

**When:** Hours before launch, on site, for go/no-go decision.

A weather balloon sounding from the launch site gives the actual wind profile overhead at the time of measurement. The radiosonde data file is supplied to EarthGRAM via its RRA (Radiosonde Representative Atmosphere) interface. This is the most accurate input and is what the launch director uses for the final call.


## 4 Perturbation Model

All sources use NASA EarthGRAM (via GRAMpy) for perturbation generation. Each profile in the ensemble is produced with a different EarthGRAM random seed, creating statistically independent realisations of wind variability around the mean.

The RUSCALE parameter controls perturbation magnitude: 1.0 applies the full climatological variability, 0.0 produces N identical copies of the deterministic mean (useful for debugging or verification runs).


## 5 Profile Generation Process

For each profile `i` in the ensemble (i = 0 … N−1):

1. Configure `EarthAtmosphere` with launch site lat/lon, date/time, RUSCALE, and (if applicable) the auxiliary mean profile from the forecast or radiosonde source.
2. Set seed via `setSeed()` using a deterministic derivation from a master seed and profile index `i`.
3. Step through the altitude grid (0 to `altitude_max` m, spacing `altitude_step` m), calling `update()` at each height.
4. Read `perturbedEWWind` (eastward, m/s) and `perturbedNSWind` (northward, m/s) at each altitude.
5. Store as row `i` of the output arrays.

For radiosonde mode, enable RRA via `setUseRRA(True)` with the supplied data file and RRA configuration parameters.


## 6 User Interface

### 6.1 Technology

tkinter + ttk. Dark theme (#2b2b2b background, #e0e0e0 text, #4a9eff accent). Flat, no gradients or animations. Single window.

### 6.2 Configuration Panel

**Launch site:**

| Widget | Type | Notes |
|--------|------|-------|
| Latitude | Entry | Degrees North |
| Longitude | Entry | Degrees East (negative = West) |

**Date/time:**

| Widget | Type | Notes |
|--------|------|-------|
| Date/time | Entry | ISO 8601, or `"now"` for system clock |

**Wind source:**

| Widget | Type | Behaviour |
|--------|------|-----------|
| Mean wind source | Dropdown | "EarthGRAM 2016 Climatology", "GFS Forecast", "ECMWF Forecast", "Radiosonde Measurement" |
| Forecast/radiosonde file | File selector | Enabled only when source requires a file; greyed out otherwise. Label updates per source. |
| Perturbation scale (RUSCALE) | Entry | Default 1.0. Always enabled. |

**Altitude grid:**

| Widget | Type | Default |
|--------|------|---------|
| Maximum altitude | Entry (m) | 20000 |
| Altitude step | Entry (m) | 250 |

**Ensemble:**

| Widget | Type | Default |
|--------|------|---------|
| Number of profiles | Entry | 1000 |
| Master seed | Entry | 42 |

**RRA settings** (visible only in radiosonde mode):

| Widget | Type | Default |
|--------|------|---------|
| RRA site list | File selector | — |
| Inner radius | Entry (degrees) | 1.0 |
| Outer radius | Entry (degrees) | 5.0 |

**EarthGRAM data:**

| Widget | Type | Notes |
|--------|------|-------|
| EarthGRAM data path | Directory selector | Path to compiled EarthGRAM data files |

**Output:**

| Widget | Type | Default |
|--------|------|---------|
| Output file | File selector (save) | `wind_profiles.npz` |

### 6.3 Run Control

| Widget | Behaviour |
|--------|-----------|
| "Generate" button | Generates the ensemble. Greyed out while running. |
| "Cancel" button | Visible during generation only. Sets stop flag. |
| Progress bar | Determinate, per-profile. Label: "{done}/{total} profiles". |
| Status label | "Ready" / "Generating: 342/1000" / "Complete — saved to wind_profiles.npz" |

Generation runs in a background thread; UI updates via `root.after()`.

### 6.4 Preview Panel

After generation completes, displays a matplotlib figure showing all `N` profiles overlaid (east and north components vs altitude), with the ensemble mean highlighted. This provides a visual sanity check before using the file in the simulator.


## 7 Architecture

```
wind_gen/
├── __main__.py              # Entry point (launches GUI)
├── gui.py                   # tkinter UI
├── config.py                # UI state → generation parameters
├── generator.py             # EarthGRAM orchestration, profile loop
├── sources/
│   ├── earthgram.py         # Climatology mode (EarthGRAM-only mean + perturbation)
│   ├── gfs.py               # GFS GRIB2 reader → auxiliary atmosphere
│   ├── ecmwf.py             # ECMWF GRIB/netCDF reader → auxiliary atmosphere
│   └── radiosonde.py        # RRA configuration
├── writer.py                # .npz output with metadata
└── preview.py               # Ensemble visualisation
```

### 7.1 Source Interface

All source modules implement a common setup interface:

```python
def configure_earthgram(atm: EarthAtmosphere, config: SourceConfig) -> None:
    """Configure EarthAtmosphere instance with source-specific mean profile.
    For climatology mode, this is a no-op (EarthGRAM uses its internal database).
    For GFS/ECMWF, sets the auxiliary atmosphere.
    For radiosonde, enables RRA."""
```

The generation loop in `generator.py` calls this once, then iterates over seeds to produce the ensemble.


## 8 Dependencies

| Package | Purpose |
|---------|---------|
| numpy | Arrays, `.npz` output |
| GRAMpy (_gram) | EarthGRAM interface. Requires compiled `_gram.so`/`.pyd` + data files. |
| matplotlib | Preview plot |
| pyyaml | Optional config file support |
| cfgrib or eccodes | GFS GRIB2 reading (GFS mode only) |
| netCDF4 or xarray | ECMWF netCDF reading (ECMWF mode only) |
| tkinter | GUI (standard library) |

GFS and ECMWF reader dependencies are optional — only required if the corresponding source is selected. The tool should handle their absence gracefully (grey out the corresponding source option if the import fails).


## 9 Operational Workflow

| Campaign stage | Source | RUSCALE | Notes |
|----------------|--------|---------|-------|
| Safety case (months before) | EarthGRAM 2016 Climatology | 1.0 | Full climatological spread for the planned launch month |
| Operations planning (days before) | GFS or ECMWF Forecast | 1.0 | Is it worth travelling to the launch site? |
| Go/no-go (hours before, on site) | Radiosonde Measurement | 1.0 | Final check with actual conditions overhead. Set datetime to `"now"`. |
| Debugging/verification | Any | 0.0 | Deterministic — all profiles identical to the mean |

Generate the `.npz` file, copy it to the simulator's `input/` directory (or update the `wind_profiles` path in `sim_config.yaml`), and run the simulator.

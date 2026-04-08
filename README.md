# windgen

Wind profile ensemble generator meant for use with the [Leeds Flight Simulator](https://github.com/leedsrocketry/leeds-flight-simulator). Generates `.npz` ensembles of perturbed wind profiles from EarthGRAM 2024 climatology for safety case preparation, and fetches deterministic mean profiles from GFS/ECMWF/UKV forecasts for operations planning.

Built for the Gryphon II Block II (G2B2) campaign by the Leeds University Rocketry Association (LURA).

![Example wind profile ensemble (Cape Wrath, 21 Jun 2026, EarthGRAM climatology)](doc/example-ensemble.png)

---

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Commands](#commands)
  - [generate](#generate)
  - [fetch](#fetch)
  - [preview](#preview)
  - [window](#window)
- [Perturbation Scaling](#perturbation-scaling)
- [Launch Window Sizing](#launch-window-sizing)
- [Output Format](#output-format)
- [Operational Workflow](#operational-workflow)
- [File Layout](#file-layout)
- [EarthGRAM Setup](#earthgram-setup)
- [Contact](#contact)

---

## Installation

**Prerequisites:** Python 3.10+, EarthGRAM 2024 runtime (see [EarthGRAM Setup](#earthgram-setup)).

```
pip install numpy matplotlib pyyaml click rich
```

Optional — only needed if using the corresponding forecast source:

```
pip install cfgrib xarray    # GFS
pip install netCDF4           # ECMWF
```

## Quick Start

Run from the `windgen/` directory. All commands use `python .` as the entry point.

```bash
# Generate a climatology ensemble for a single date
python . generate ../simulations/cases/g2b2-cape-wrath/config.yaml 21-06-26

# Generate a climatology ensemble for a date range (uses midpoint)
python . generate ../simulations/cases/g2b2-cape-wrath/config.yaml 15-06-26 28-06-26

# Preview the result
python . preview ../simulations/cases/g2b2-cape-wrath/wind/21-06-26-earthgram.npz
```

Then point LFS at the output by setting `launch.wind_profiles` in `config.yaml`:

```yaml
launch:
  wind_profiles: "wind/21-06-26-earthgram.npz"
```


## Commands

### `generate`

```
python . generate CONFIG [DATE] [DATE_END] [OPTIONS]
```

Generates a perturbed wind profile ensemble (`.npz`) via EarthGRAM.

Generates a climatological ensemble via EarthGRAM. `DATE` is required; `DATE_END` is optional. When a date range is given, a single ensemble is generated for the midpoint (climatological statistics barely shift over short windows). A warning is emitted if the range exceeds 14 days.

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--scale` | `1.0` | Horizontal wind perturbation scale factor (0.1–2.0). See [Perturbation Scaling](#perturbation-scaling). |
| `--n-profiles` | from config | Ensemble size. Read from `monte_carlo.samples` in config if not given. |
| `--master-seed` | from config | Master random seed. Read from `monte_carlo.seed` in config if not given. |
| `--altitude-max` | `20000` | Maximum altitude in metres AGL |
| `--altitude-step` | `250` | Altitude grid spacing in metres |
| `-q` / `--no-popup` | off | Save preview PNGs to disk instead of opening matplotlib windows |

**Output:** Written to `wind/` relative to the config file. Filename is `{DD-MM-YY}-{source}.npz` (e.g. `wind/21-06-26-earthgram.npz`).


### `fetch`

```
python . fetch CONFIG --source SOURCE DATE [DATE_END]
```

Downloads forecast mean wind profiles and saves one `.npz` per day (N=1 profile each).

| Option | Description |
|--------|-------------|
| `--source` | `gfs`, `ecmwf`, or `ukv` (required) |

**Output:** Written to `wind/mean/` relative to the config file, named `{DD-MM-YY}-{source}.npz`.

This is the only command that requires internet access. The resulting mean profiles are used directly by LFS (as N=1 deterministic wind input) without EarthGRAM perturbation.


### `preview`

```
python . preview TARGET [-q]
```

Plots wind profiles from a `.npz` file or a directory of `.npz` files. Three panels:

1. **Wind speed vs altitude** — mean with min/max envelope.
2. **Wind heading vs altitude** — circular mean direction.
3. **East vs North scatter** — directional distribution of wind at three altitudes (surface, midpoint, and top of the grid) with PCA ellipses enclosing all points. A circular scatter cloud indicates no prevailing wind direction (and will produce circular landing dispersion in LFS); an elongated cloud indicates a directional bias.

| Option | Description |
|--------|-------------|
| `-q` / `--no-popup` | Save PNGs alongside the `.npz` files instead of displaying interactively |


### `window`

```
python . window --scale SCALE [OPTIONS]
```

Computes how long a launch window you need, or how many launch opportunities to expect in a given window. Based on the perturbation scale factor you used with `generate` — see [Perturbation Scaling](#perturbation-scaling) and [Launch Window Sizing](#launch-window-sizing) for the full explanation.

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--scale` | (required) | Perturbation scale factor used in `generate` (0.1–2.0) |
| `--confidence` | `0.95` | Target confidence level (e.g. 0.95 = 95%) |
| `--duration` | — | Launch window length in days. If omitted, computes the minimum window instead. |

**Without `--duration`** — prints the minimum number of days you need for a launch window:

```bash
$ python . window --scale 0.5
Minimum launch window: 2 days
(95.0% confidence of at least 1 launchable day, perturbation scale 0.50)
```

**With `--duration`** — prints the minimum number of launchable days you can count on:

```bash
$ python . window --scale 0.5 --duration 10
Guaranteed launchable days: at least 7 of 10
(95.0% confidence, perturbation scale 0.50)
```

Note: this is a **conservative lower bound**, not the average. On average you would get about 9 launchable days out of 10 at scale 0.5 — but you can only *guarantee* 7 at 95% confidence.


## Perturbation Scaling

EarthGRAM models the atmosphere at any location and date as a **mean** wind profile plus a random **perturbation**. The perturbation represents the day-to-day variability in real weather — some days the wind is stronger than average, some days weaker.

The perturbations follow a **normal (bell-curve) distribution**. If you have seen the bell curve before, you will know that about 68% of values fall within one standard deviation (σ) of the mean, and about 95% fall within two standard deviations.

### What the scale factor does

When you run `generate --scale 0.5`, windgen tells EarthGRAM to use a **narrower** bell curve for horizontal wind: it multiplies σ by your scale factor. The Monte Carlo ensemble is then drawn from this narrower distribution, so the profiles stay closer to the mean and the dispersion fan is tighter.

windgen only scales **horizontal wind** perturbations (`HorizontalWindPerturbationScale` in EarthGRAM's input). Density, temperature, pressure, and vertical wind perturbations are left at their nominal values. The valid range is 0.1–2.0 (an EarthGRAM constraint).

### Coverage: what fraction of real days does your ensemble represent?

If your vehicle passes a Monte Carlo simulation at a given scale factor, it means it can handle any day whose wind falls within the range covered by that ensemble. With a typical 1000-profile ensemble, the most extreme samples reach about ±3σ from the mean of the narrowed distribution — so the ensemble effectively tests the vehicle against winds up to ±3·s·σ_real from the climatological mean, where s is the scale factor.

The fraction of real days whose wind falls within that range is:

| Scale factor | Envelope (±3·s·σ) | Approximate coverage |
|---|---|---|
| 0.1 | ±0.3σ | 24% |
| 0.2 | ±0.6σ | 45% |
| 0.3 | ±0.9σ | 63% |
| 0.5 | ±1.5σ | 87% |
| 0.7 | ±2.1σ | 96% |
| 1.0 | ±3.0σ | 99.7% |

At scale 1.0 the ensemble spans ±3σ of the real-world distribution — covering 99.7% of days. At scale 0.5 it spans ±1.5σ, covering about 87%. The exact formula is `p = erf(3·s / √2)`.


## Launch Window Sizing

Once you know the coverage fraction *p* for a given scale factor, you can answer: **how many days do I need in my launch window to be confident that at least one day will have acceptable wind?**

### The model

Each day in your launch window is treated as an independent coin flip. The probability that any single day has wind within your Monte Carlo envelope is *p* (from the table above). The question becomes: if I flip a coin that lands heads with probability *p*, how many flips do I need before I'm 95% sure I'll get at least one heads?

The answer is:

```
n = ⌈log(1 − confidence) / log(1 − p)⌉
```

where ⌈·⌉ means round up to the next whole number.

### Worked example

You run `generate --scale 0.2` and your vehicle passes the Monte Carlo. The coverage is *p* ≈ 0.45 (45% of days). You want 95% confidence of at least one launchable day:

```
n = ⌈log(0.05) / log(0.55)⌉ = ⌈5.0⌉ = 5 days
```

So you need a 5-day launch window. You can verify this with `python . window --scale 0.2`, which prints `5 days`.

### A common misconception: doubling the window does not double the opportunities

It is tempting to reason: "if 3 days gives me 95% confidence of 1 launchable day, then 6 days gives me 95% confidence of 2." **This is not quite right.**

The number of launchable days follows a **binomial distribution**, which does not scale linearly. With scale 0.3 (*p* = 0.63):

- 3 days → 95% confidence of ≥ 1 launchable day
- 6 days → 95% confidence of ≥ 2 (not necessarily 2) launchable days

In this case it happens to work out, but the relationship depends on the specific numbers and does not hold as a general rule. Rather than guessing, use `window --duration` to check directly:

```bash
$ python . window --scale 0.3 --duration 6
Guaranteed launchable days: at least 2 of 6
(95.0% confidence, perturbation scale 0.30)
```

### Assumptions and limitations

- **Independence:** the model assumes each day's wind is independent of the previous day's. In reality, weather is correlated over a few days (a stormy week tends to stay stormy). For windows shorter than about 3 days, the real number of independent opportunities may be lower than predicted.
- **Gaussian wind:** the model assumes EarthGRAM's Gaussian perturbation model is a good fit for real wind variability. This is well-validated for mid-latitude sites (see EarthGRAM User Guide, Section 3).
- **On-the-day verification:** this tool helps you plan your launch window, but the actual launch decision must always be based on **measured** wind profiles on the day — a radiosonde sounding or forecast, run through the flight simulator to confirm safety.


## Output Format

All commands produce NumPy `.npz` archives with:

**Wind components use the "blowing towards" convention.** Positive `wind_east_ms` means wind blowing towards east; positive `wind_north_ms` means wind blowing towards north. This matches the standard meteorological u/v component convention used by GFS, ECMWF, and EarthGRAM.

| Key | Shape | Description |
|-----|-------|-------------|
| `altitude_m` | `(M,)` | Altitude grid in metres AGL, monotonically increasing |
| `wind_east_ms` | `(N, M)` | Eastward wind component per profile (m/s, positive = blowing towards east) |
| `wind_north_ms` | `(N, M)` | Northward wind component per profile (m/s, positive = blowing towards north) |
| `metadata` | string | JSON: source, timestamp, site, perturbation scale, ensemble size |

`N` = number of profiles (1 for `fetch`, typically 1000 for `generate`). `M` = altitude grid points (typically 81 for 0–20,000 m at 250 m). LFS loads these via `wind.py` without knowledge of the source.


## Operational Workflow

| Campaign stage | Command | Notes |
|----------------|---------|-------|
| Safety case (months before) | `python . generate CONFIG 15-06-26 28-06-26` | EarthGRAM climatology, full perturbation, midpoint date |
| Ops planning (days before) | `python . fetch CONFIG --source gfs 12-07-26 14-07-26` | Download forecast means; use directly in LFS |
| Go/no-go (hours before) | Convert radiosonde sounding to `.npz` | Use directly in LFS |
| Debugging | `python . generate CONFIG 21-06-26 --scale 0.1` | Near-identical profiles (minimum variability) |
| Visual check | `python . preview wind/` | Inspect before running LFS |

After generating, update `launch.wind_profiles` in `config.yaml` to point at the chosen ensemble, then run LFS.


## File Layout

```
simulations/cases/g2b2-cape-wrath/
├── config.yaml
├── wind/
│   ├── mean/                        # fetch output (N=1 mean profiles)
│   │   ├── 12-07-26-gfs.npz
│   │   └── 13-07-26-gfs.npz
│   ├── 21-06-26-earthgram.npz      # generate output (perturbed ensembles)
│   ├── 12-07-26-gfs.npz
│   └── ...
└── results/
```


## EarthGRAM Setup

The `earthgram/` directory (gitignored, ~480 MB) contains NASA's EarthGRAM 2024 runtime: prebuilt Windows executable, SPICE kernels, and NCEP climatology data. It is not redistributable.

**To set up:**

1. Obtain the `earthgram/` archive from the LURA OneDrive (`team-member-space/Nick/earthgram/`).
2. Place it at `windgen/earthgram/` so that `windgen/earthgram/bin/EarthGRAM.exe` exists.

No compilation required — windgen invokes `EarthGRAM.exe` via subprocess.


## Contact

- **Toby Thomson** — el21tbt@leeds.ac.uk, me@tobythomson.co.uk
- **LURA Team** — launch@leedsrocketry.co.uk

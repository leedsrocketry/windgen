# windgen

Wind profile generator for the Leeds Flight Simulator.

## What it does

windgen produces ensembles of perturbed wind profiles for use as input to LFS.
It supports four wind data sources, covering every stage of a launch campaign:

| Campaign stage | Source | When |
|---|---|---|
| Safety case | EarthGRAM 2016 Climatology | Months before launch |
| Operations planning | GFS or ECMWF Forecast | Days before launch |
| Go/no-go | Radiosonde Measurement | Hours before launch, on site |

Each source uses NASA EarthGRAM (via GRAMpy) to generate statistically
independent realisations of wind variability. The output is a single `.npz`
file containing an ensemble of N wind profiles on a common altitude grid, which
LFS reads directly.

See `specification.md` for full details of the output format, data sources,
perturbation model, GUI design, and architecture.

## Status

Not yet implemented. `specification.md` defines what will be built.

## Output format

```
altitude_m       (M,)    altitude grid, metres AGL
wind_east_ms     (N, M)  eastward wind per profile per altitude (m/s)
wind_north_ms    (N, M)  northward wind per profile per altitude (m/s)
metadata                 JSON string with source, timestamp, site, parameters
```

## Usage

```
python -m wind_gen
```

Configure launch site, date/time, wind source, ensemble size, and output path
in the GUI, then click Generate.

## Dependencies

- Python 3.10+
- numpy
- GRAMpy (`_gram.so`/`.pyd`) + EarthGRAM data files
- matplotlib
- tkinter (standard library)
- cfgrib or eccodes (GFS mode only)
- netCDF4 or xarray (ECMWF mode only)

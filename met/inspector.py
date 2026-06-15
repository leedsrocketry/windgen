import xarray as xr
import numpy as np
from pathlib import Path


file = "grib/isbl_temperature+u-component-of-wind+v-component-of-wind_1000_+15_51.grib2"

ds = xr.open_dataset(file, engine="cfgrib")
lat = 58.608974
lon = -4.944191 % 360  # = 355.055809
point = ds.sel(latitude=lat, longitude=lon, method="nearest")
print("Valid time:", point.valid_time.values)
print("Pressure level (hPa):", point.isobaricInhPa.values)
print("Temperature (K):", point.t.values)
print("U wind (m/s):", point.u.values)
print("V wind (m/s):", point.v.values)
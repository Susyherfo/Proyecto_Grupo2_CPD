"""
unificar_dataset.py
Une focos + clima (ERA5) + terreno (DEM) + vegetacion (NDVI) en un CSV.
Lee los .nc desde adentro de los zip, en memoria, SIN extraerlos, usando netcdf4.
Requisitos: pip install xarray netcdf4 rasterio pandas numpy
"""
import io, os, glob, zipfile
import numpy as np
import pandas as pd
import xarray as xr
import netCDF4
import rasterio

def abrir_zip_nc(ruta):
    """Abre el .nc de adentro del zip, en memoria (no extrae nada), con netcdf4."""
    with zipfile.ZipFile(ruta) as z:
        data = z.read(z.namelist()[0])
    nc = netCDF4.Dataset("inmem", mode="r", memory=data)
    return xr.open_dataset(xr.backends.NetCDF4DataStore(nc))

# 1. BASE: focos
focos = pd.read_csv("focos_centroamerica_2002_2026.csv")
focos["acq_date"] = pd.to_datetime(focos["acq_date"])
focos["anio"] = focos["acq_date"].dt.year
print(f"Focos: {len(focos)}")

# Detectar variables y coordenada de tiempo con el primer archivo
primer = sorted(glob.glob("era5_centroamerica_*.nc"))[0]
ds0 = abrir_zip_nc(primer)
variables = list(ds0.data_vars)
tiempo = "valid_time" if "valid_time" in ds0.coords else "time"
print("Variables de clima:", variables)
for v in variables:
    focos[v] = np.nan
ds0.close()

# 2. CLIMA: extraccion por punto, ano por ano
for anio in sorted(focos["anio"].unique()):
    ruta = f"era5_centroamerica_{anio}.nc"
    if not os.path.exists(ruta):
        continue
    sub = focos[focos["anio"] == anio]
    ds = abrir_zip_nc(ruta)
    m = ds.sel(latitude=xr.DataArray(sub["latitude"].values, dims="p"),
               longitude=xr.DataArray(sub["longitude"].values, dims="p"),
               **{tiempo: xr.DataArray(sub["acq_date"].values, dims="p")},
               method="nearest")
    for v in variables:
        focos.loc[sub.index, v] = m[v].values
    ds.close()
    print(f"  clima {anio}: {len(sub)} focos")

# 3. TERRENO (DEM)
with rasterio.open("dem_centroamerica.tif") as src:
    coords = list(zip(focos["longitude"].values, focos["latitude"].values))
    focos["elevacion"] = [val[0] for val in src.sample(coords)]
print("Elevacion lista.")

# 4. VEGETACION (NDVI)
try:
    ndvi = pd.read_csv("ndvi_guanacaste_serie_temporal.csv")
    ndvi["fecha"] = pd.to_datetime(ndvi["fecha"])
    ndvi = ndvi.sort_values("fecha").rename(columns={"fecha": "fecha_ndvi"})
    focos = focos.sort_values("acq_date")
    focos = pd.merge_asof(focos, ndvi, left_on="acq_date", right_on="fecha_ndvi",
                          direction="backward", tolerance=pd.Timedelta("32D"))
    print("NDVI listo.")
except FileNotFoundError:
    print("(NDVI omitido)")

# 5. Guardar
focos = focos.drop(columns=["anio"])
focos.to_csv("dataset_unificado.csv", index=False)
print(f"\nListo: {len(focos)} filas x {len(focos.columns)} columnas "
      f"-> dataset_unificado.csv")

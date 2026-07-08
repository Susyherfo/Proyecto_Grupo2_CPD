"""
generar_dataset_modelo.py
Crea el dataset para el modelo con columna flag:
  flag=1 -> incendios (de FIRMS)
  flag=0 -> puntos al azar en tierra SIN incendio, con las mismas variables.
"""
import os, zipfile
import numpy as np, pandas as pd, xarray as xr, netCDF4, rasterio

BBOX = dict(oeste=-92.5, sur=6.0, este=-77.0, norte=18.5)
CLIMA = ["t2m", "u10", "v10", "d2m", "tp"]
NDVI_COLS = ["ndvi_media","ndvi_mediana","ndvi_min","ndvi_max","pixeles_validos"]

def abrir_zip_nc(ruta):
    with zipfile.ZipFile(ruta) as z:
        data = z.read(z.namelist()[0])
    nc = netCDF4.Dataset("m", mode="r", memory=data)
    return xr.open_dataset(xr.backends.NetCDF4DataStore(nc))

def extraer_clima(df):
    df["anio"] = df["acq_date"].dt.year
    for c in CLIMA:
        df[c] = np.nan
    for anio in sorted(df["anio"].unique()):
        ruta = f"era5_centroamerica_{anio}.nc"
        if not os.path.exists(ruta):
            continue
        sub = df[df["anio"] == anio]
        ds = abrir_zip_nc(ruta)
        t = "valid_time" if "valid_time" in ds.coords else "time"
        m = ds.sel(latitude=xr.DataArray(sub["latitude"].values, dims="p"),
                   longitude=xr.DataArray(sub["longitude"].values, dims="p"),
                   **{t: xr.DataArray(sub["acq_date"].values, dims="p")},
                   method="nearest")
        for c in CLIMA:
            df.loc[sub.index, c] = m[c].values
        ds.close()
        print(f"  clima {anio}: {len(sub)}")
    return df.drop(columns=["anio"])

# 1. INCENDIOS (flag=1)
fuego = pd.read_csv("dataset_unificado.csv")
fuego["acq_date"] = pd.to_datetime(fuego["acq_date"])
keep = ["latitude","longitude","acq_date"] + CLIMA + ["elevacion"] + NDVI_COLS
fuego = fuego[[c for c in keep if c in fuego.columns]].copy()
fuego["flag"] = 1
N = len(fuego)
print(f"Incendios: {N}")

# 2. NO INCENDIOS (flag=0): puntos al azar en tierra
rng = np.random.default_rng(42)
F = 3  # genera de mas para filtrar mar
lat = rng.uniform(BBOX["sur"], BBOX["norte"], N*F)
lon = rng.uniform(BBOX["oeste"], BBOX["este"], N*F)
dias = rng.integers(0, (pd.Timestamp("2025-12-31")-pd.Timestamp("2002-01-01")).days, N*F)
fechas = pd.Timestamp("2002-01-01") + pd.to_timedelta(dias, unit="D")
no = pd.DataFrame({"latitude": lat, "longitude": lon, "acq_date": fechas})

with rasterio.open("dem_centroamerica.tif") as src:
    nd = src.nodata
    elev = np.array([v[0] for v in src.sample(list(zip(no["longitude"], no["latitude"])))])
no["elevacion"] = elev
tierra = np.isfinite(elev) & (elev != nd) & (elev > 0)
no = no[tierra].head(N).reset_index(drop=True)
print(f"No incendios (en tierra): {len(no)}")

no = extraer_clima(no)
ndvi = pd.read_csv("ndvi_guanacaste_serie_temporal.csv")
ndvi["fecha"] = pd.to_datetime(ndvi["fecha"])
ndvi = ndvi.sort_values("fecha").rename(columns={"fecha": "fecha_ndvi"})
no = no.sort_values("acq_date")
no = pd.merge_asof(no, ndvi, left_on="acq_date", right_on="fecha_ndvi",
                   direction="backward", tolerance=pd.Timedelta("32D"))
no = no.drop(columns=["fecha_ndvi"])
no["flag"] = 0

# 3. UNIR y mezclar
final = pd.concat([fuego, no], ignore_index=True)
final = final.sample(frac=1, random_state=42).reset_index(drop=True)
final.to_csv("dataset_modelo.csv", index=False)
print(f"\nListo: {len(final)} filas "
      f"({int((final.flag==1).sum())} incendios + {int((final.flag==0).sum())} no) "
      f"-> dataset_modelo.csv")

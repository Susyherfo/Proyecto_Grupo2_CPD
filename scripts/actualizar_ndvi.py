"""
actualizar_ndvi.py
Reemplaza el NDVI provisional (Guanacaste) por el de Centroamerica en el
dataset consolidado, uniendo por fecha (composite mas reciente).
"""
import pandas as pd

COLS_NDVI = ["ndvi_media", "ndvi_mediana", "ndvi_min", "ndvi_max", "pixeles_validos"]

# 1. Cargar el consolidado
df = pd.read_csv("dataset_modelo_worldcover.csv")
df["acq_date"] = pd.to_datetime(df["acq_date"])
print(f"Dataset: {len(df):,} filas")
print(f"NDVI viejo (ejemplo): {df['ndvi_media'].iloc[0]}")

# 2. Quitar el NDVI provisional de Guanacaste
df = df.drop(columns=[c for c in COLS_NDVI if c in df.columns])

# 3. Cargar el NDVI de Centroamerica
ndvi = pd.read_csv("outputs/ndvi_centroamerica_serie_temporal.csv")
ndvi["fecha"] = pd.to_datetime(ndvi["fecha"])
ndvi = ndvi[["fecha"] + COLS_NDVI].sort_values("fecha").rename(columns={"fecha": "fecha_ndvi"})

# 4. Unir por fecha (backward = composite mas reciente antes del foco)
df = df.sort_values("acq_date")
df = pd.merge_asof(df, ndvi, left_on="acq_date", right_on="fecha_ndvi",
                   direction="backward", tolerance=pd.Timedelta("32D"))

# 5. Guardar (sobrescribe el consolidado)
df.to_csv("dataset_modelo_worldcover.csv", index=False)
print(f"NDVI nuevo (Centroamerica) integrado.")
print(f"Nulos en NDVI: {df['ndvi_media'].isna().sum():,} de {len(df):,}")
print("\nEjemplo (mismo dia, distintos puntos):")
print(df.sort_values('acq_date')[['acq_date','latitude','longitude','ndvi_media']].head(5).to_string(index=False))

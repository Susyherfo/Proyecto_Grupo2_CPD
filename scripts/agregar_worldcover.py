"""
agregar_worldcover.py
Agrega la cobertura de suelo (WorldCover) al dataset del modelo, reutilizando
la funcion asignar_worldcover() del script de la companera.
Requisitos: pip install pandas numpy scipy
Necesita en la carpeta:
  - extraer_worldcover.py
  - worldcover_centroamerica_limpio.csv  (o worldcover_centroamerica_1km.csv)
  - dataset_modelo.csv
"""
import os
import pandas as pd
from extraer_worldcover import asignar_worldcover, CLASES

# 1. Cargar la grilla WorldCover de Centroamerica
ruta_wc = ("worldcover_centroamerica_limpio.csv"
           if os.path.exists("worldcover_centroamerica_limpio.csv")
           else "worldcover_centroamerica_1km.csv")
print(f"WorldCover: {ruta_wc}")
wc = pd.read_csv(ruta_wc)
if "worldcover_clase" not in wc.columns:
    wc["worldcover_clase"] = wc["worldcover_code"].map(CLASES).fillna("Unknown")

# 2. Cargar tu dataset grande
datos = pd.read_csv("dataset_modelo.csv")
print(f"Filas a enriquecer: {len(datos):,}")

# 3. Asignar la cobertura de suelo a cada punto (por coordenada mas cercana)
datos = asignar_worldcover(datos, wc, col_lat="latitude", col_lon="longitude")

# 4. Guardar
datos.to_csv("dataset_modelo_worldcover.csv", index=False)
print(f"\nListo: {len(datos):,} filas con WorldCover -> dataset_modelo_worldcover.csv")

"""
extraer_worldcover.py

Para cada foco activo del dataset, extrae la clase de cobertura
del suelo del tile ESA WorldCover 2021 y la agrega como columna.

Clases WorldCover:
    10  = Tree cover (bosque)
    20  = Shrubland (arbustos)
    30  = Grassland (pastizal)
    40  = Cropland (cultivos)
    50  = Built-up (zona urbana)
    60  = Bare / sparse vegetation
    70  = Snow and ice
    80  = Permanent water bodies
    90  = Herbaceous wetland
    95  = Mangrove
    100 = Moss and lichen

Requisitos:
    pip install pandas rasterio numpy
"""

import numpy as np
import pandas as pd
import rasterio
from rasterio.sample import sample_gen

# ----------------------------------------------------------------
# Configuración
# ----------------------------------------------------------------
INPUT_CSV    = "focos_guanacaste_ndvi.csv"
WORLDCOVER   = "data/worldcover/ESA_WorldCover_10m_2021_v200_N09W087_Map.tif"
OUTPUT_CSV   = "focos_guanacaste_ndvi_worldcover.csv"

# Diccionario de clases WorldCover
CLASES = {
    10:  "Tree cover",
    20:  "Shrubland",
    30:  "Grassland",
    40:  "Cropland",
    50:  "Built-up",
    60:  "Bare / sparse vegetation",
    70:  "Snow and ice",
    80:  "Permanent water bodies",
    90:  "Herbaceous wetland",
    95:  "Mangrove",
    100: "Moss and lichen",
}


# ----------------------------------------------------------------
# Main
# ----------------------------------------------------------------
def main():
    # 1. Cargar dataset
    print(f"Cargando {INPUT_CSV}...")
    df = pd.read_csv(INPUT_CSV)
    print(f"Registros: {len(df):,}")

    # 2. Extraer clase WorldCover para cada punto (lat, lon)
    print(f"\nExtrayendo cobertura del suelo desde {WORLDCOVER}...")

    coords = list(zip(df["longitude"], df["latitude"]))

    with rasterio.open(WORLDCOVER) as src:
        # Verificar que los puntos caen dentro del tile
        bounds = src.bounds
        print(f"Bounds del tile: {bounds}")
        print(f"Rango lon dataset: {df['longitude'].min():.2f} → {df['longitude'].max():.2f}")
        print(f"Rango lat dataset: {df['latitude'].min():.2f} → {df['latitude'].max():.2f}")

        # Extraer valores — sample_gen devuelve un valor por coordenada
        valores = np.array([v[0] for v in sample_gen(src, coords)])

    # 3. Agregar columnas
    df["worldcover_code"]  = valores.astype("int16")
    df["worldcover_clase"] = df["worldcover_code"].map(CLASES).fillna("Unknown")

    # 4. Resumen de clases encontradas
    print("\nDistribución de clases de cobertura del suelo:")
    resumen = (
        df.groupby(["worldcover_code", "worldcover_clase"])
        .size()
        .reset_index(name="focos")
        .sort_values("focos", ascending=False)
    )
    print(resumen.to_string(index=False))

    # 5. Puntos fuera del tile (valor 0 o nulo)
    fuera = (df["worldcover_code"] == 0) | df["worldcover_code"].isna()
    if fuera.sum() > 0:
        print(f"\n[aviso] {fuera.sum()} focos quedaron fuera del tile (sin cobertura asignada)")

    # 6. Guardar
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"\nListo: {len(df):,} registros guardados en '{OUTPUT_CSV}'")
    print(f"Columnas nuevas: worldcover_code, worldcover_clase")


if __name__ == "__main__":
    main()
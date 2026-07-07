"""
extraer_worldcover.py

Versión independiente — no depende del CSV de focos activos.

Lee el CSV de cobertura del suelo generado por ESAWorldCover_Data.py
(worldcover_centroamerica_1km.csv) y lo deja listo para el cruce con cualquier 
otro dataset por coordenada más cercana (join espacial aproximado a 1 km).

También incluye una función de utilidad para extraer la clase
WorldCover para un conjunto arbitrario de coordenadas (lat/lon),
útil cuando haya que cruzarlo directamente con los datos
sin hacer un merge de CSVs.

Requisitos:
    pip install pandas numpy scipy
"""

import numpy as np
import pandas as pd
from pathlib import Path
from scipy.spatial import cKDTree

# ----------------------------------------------------------------
# Configuración
# ----------------------------------------------------------------
WORLDCOVER_CSV = "worldcover_centroamerica_1km.csv"
OUTPUT_CSV     = "worldcover_centroamerica_limpio.csv"

# Clases WorldCover (para referencia)
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

# Bounding box de Guanacaste para el closeup
GUANACASTE_BOUNDS = (-86.4, 9.5, -84.6, 11.3)


# ----------------------------------------------------------------
# Función principal: limpiar y validar el CSV de WorldCover
# ----------------------------------------------------------------
def limpiar_worldcover(input_csv: str = WORLDCOVER_CSV,
                       output_csv: str = OUTPUT_CSV):
    print(f"Cargando {input_csv}...")
    df = pd.read_csv(input_csv)
    print(f"Registros originales: {len(df):,}")

    # Eliminar códigos inválidos
    df = df[df["worldcover_code"] > 0].reset_index(drop=True)

    # Asegurar que la columna de clase esté presente
    if "worldcover_clase" not in df.columns:
        df["worldcover_clase"] = df["worldcover_code"].map(CLASES).fillna("Unknown")

    print(f"Registros válidos:    {len(df):,}")
    print(f"Cobertura geográfica: "
          f"lon [{df['longitude'].min():.2f}, {df['longitude'].max():.2f}] "
          f"lat [{df['latitude'].min():.2f}, {df['latitude'].max():.2f}]")

    # Resumen de clases
    print("\nDistribución de clases en Centroamérica:")
    resumen = (
        df.groupby(["worldcover_code", "worldcover_clase"])
        .size()
        .reset_index(name="puntos")
        .sort_values("puntos", ascending=False)
    )
    print(resumen.to_string(index=False))

    df.to_csv(output_csv, index=False)
    print(f"\nListo: {len(df):,} puntos guardados en '{output_csv}'")
    return df


# ----------------------------------------------------------------
# Función de utilidad: extraer clase WorldCover para coordenadas
# arbitrarias usando KD-Tree (join espacial por vecino más cercano)
# ----------------------------------------------------------------
def asignar_worldcover(df_datos: pd.DataFrame,
                       df_wc: pd.DataFrame,
                       col_lat: str = "latitude",
                       col_lon: str = "longitude") -> pd.DataFrame:
    """
    Dado un DataFrame con columnas de latitud y longitud,
    asigna la clase WorldCover del punto más cercano en la grilla
    de 1 km usando un KD-Tree para búsqueda eficiente.

    Parámetros:
        df_datos: DataFrame con los datos a enriquecer (ej. ERA5, FIRMS)
        df_wc:    DataFrame de worldcover_centroamerica_1km.csv
        col_lat:  nombre de la columna de latitud en df_datos
        col_lon:  nombre de la columna de longitud en df_datos

    Retorna:
        df_datos con columnas worldcover_code y worldcover_clase agregadas
    """
    print("Construyendo KD-Tree sobre la grilla WorldCover...")
    wc_coords = np.column_stack([df_wc["latitude"].values,
                                 df_wc["longitude"].values])
    tree = cKDTree(wc_coords)

    print(f"Asignando WorldCover a {len(df_datos):,} puntos...")
    query_coords = np.column_stack([df_datos[col_lat].values,
                                    df_datos[col_lon].values])
    _, indices = tree.query(query_coords, workers=-1)  # usa todos los cores

    df_datos = df_datos.copy()
    df_datos["worldcover_code"]  = df_wc["worldcover_code"].values[indices]
    df_datos["worldcover_clase"] = df_wc["worldcover_clase"].values[indices]

    print("Asignación completada.")
    print("\nDistribución de clases en los datos enriquecidos:")
    resumen = (
        df_datos.groupby(["worldcover_code", "worldcover_clase"])
        .size()
        .reset_index(name="puntos")
        .sort_values("puntos", ascending=False)
    )
    print(resumen.to_string(index=False))

    return df_datos


# ----------------------------------------------------------------
# Función de utilidad: filtrar solo Guanacaste
# ----------------------------------------------------------------
def filtrar_guanacaste(df: pd.DataFrame,
                       col_lat: str = "latitude",
                       col_lon: str = "longitude") -> pd.DataFrame:
    """
    Filtra el DataFrame para quedarse solo con los puntos
    dentro del bounding box de Guanacaste.
    """
    west, south, east, north = GUANACASTE_BOUNDS
    mask = (
        (df[col_lon] >= west) & (df[col_lon] <= east) &
        (df[col_lat] >= south) & (df[col_lat] <= north)
    )
    resultado = df[mask].reset_index(drop=True)
    print(f"Puntos en Guanacaste: {len(resultado):,} "
          f"(de {len(df):,} totales)")
    return resultado


# ----------------------------------------------------------------
# Main — modo standalone: limpia y valida el CSV de WorldCover
# ----------------------------------------------------------------
def main():
    print("=" * 60)
    print("Procesamiento WorldCover — Centroamérica")
    print("=" * 60)

    # 1. Limpiar y validar el CSV generado por ESAWorldCover_Data.py
    df_wc = limpiar_worldcover()

    # 2. Ejemplo de closeup a Guanacaste
    print("\n" + "=" * 60)
    print("Closeup — solo Guanacaste:")
    df_guanacaste = filtrar_guanacaste(df_wc)
    df_guanacaste.to_csv("worldcover_guanacaste_1km.csv", index=False)
    print(f"Guardado en 'worldcover_guanacaste_1km.csv'")

    print("\n✓ Archivos generados:")
    print(f"  worldcover_centroamerica_limpio.csv — dataset completo de Centroamérica")
    print(f"  worldcover_guanacaste_1km.csv       — solo provincia de Guanacaste")
    print("\nPara cruzar con otros datasets, usar la función asignar_worldcover():")
    print("  from extraer_worldcover import asignar_worldcover")
    print("  df_enriquecido = asignar_worldcover(df_firms, df_wc)")


if __name__ == "__main__":
    main()

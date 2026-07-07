"""
ESAWorldCover_Data.py

Descarga los tiles de ESA WorldCover 2021 (10m) que cubren
Centroamérica completa y genera un CSV con la clase de cobertura
del suelo para una grilla regular de puntos a 1 km de resolución.

Solución al error de memoria: en lugar de fusionar todos los tiles
en memoria (36 GB), procesa cada tile por separado y extrae solo
los puntos que caen dentro de ese tile.

Requisitos:
    pip install geopandas requests tqdm rasterio numpy pandas shapely
"""

import numpy as np
import pandas as pd
import requests
import geopandas as gpd
import rasterio
from rasterio.sample import sample_gen
from pathlib import Path
from shapely.geometry import box, Point
from tqdm.auto import tqdm

# ----------------------------------------------------------------
# Configuración
# ----------------------------------------------------------------
CENTROAMERICA_BOUNDS = (-92.5, 7.0, -77.0, 18.5)

S3_URL_PREFIX = "https://esa-worldcover.s3.eu-central-1.amazonaws.com"
YEAR          = 2021
VERSION       = "v200"
OUTPUT_FOLDER = "data/worldcover"

# Resolución de la grilla (~1 km)
RESOLUCION_GRADOS = 0.009

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
# Paso 1 — Descargar tiles
# ----------------------------------------------------------------
def descargar_tiles() -> list[Path]:
    Path(OUTPUT_FOLDER).mkdir(parents=True, exist_ok=True)

    print("Cargando grid oficial de ESA WorldCover desde S3...")
    grid_url = f"{S3_URL_PREFIX}/esa_worldcover_grid.geojson"
    grid = gpd.read_file(grid_url)
    print(f"Grid cargado: {len(grid)} tiles en total")

    ca_geom = box(*CENTROAMERICA_BOUNDS)
    tiles = grid[grid.intersects(ca_geom)]
    print(f"Tiles que cubren Centroamérica: {len(tiles)}")
    for t in tiles.ll_tile:
        print(f"  - {t}")

    print(f"\nDescargando {len(tiles)} tile(s) en '{OUTPUT_FOLDER}'...\n")
    rutas = []

    for tile in tqdm(tiles.ll_tile, desc="Tiles"):
        url = (
            f"{S3_URL_PREFIX}/{VERSION}/{YEAR}/map/"
            f"ESA_WorldCover_10m_{YEAR}_{VERSION}_{tile}_Map.tif"
        )
        out_path = Path(OUTPUT_FOLDER) / Path(url).name

        if out_path.exists():
            print(f"  Ya existe, se omite: {out_path.name}")
            rutas.append(out_path)
            continue

        print(f"  Descargando: {Path(url).name}")
        r = requests.get(url, allow_redirects=True, stream=True, timeout=180)
        r.raise_for_status()

        total = int(r.headers.get("content-length", 0))
        with open(out_path, "wb") as f, tqdm(
            total=total, unit="B", unit_scale=True,
            desc=out_path.name, leave=False
        ) as bar:
            for chunk in r.iter_content(chunk_size=65536):
                f.write(chunk)
                bar.update(len(chunk))

        size_mb = out_path.stat().st_size / 1024 / 1024
        print(f"  ✓ {out_path.name} ({size_mb:.1f} MB)")
        rutas.append(out_path)

    return rutas


# ----------------------------------------------------------------
# Paso 2 — Generar grilla de puntos
# ----------------------------------------------------------------
def generar_grilla() -> tuple[np.ndarray, np.ndarray]:
    west, south, east, north = CENTROAMERICA_BOUNDS
    lons = np.arange(west, east, RESOLUCION_GRADOS)
    lats = np.arange(south, north, RESOLUCION_GRADOS)
    grid_lon, grid_lat = np.meshgrid(lons, lats)
    lons_flat = grid_lon.flatten()
    lats_flat = grid_lat.flatten()
    print(f"Grilla generada: {len(lons_flat):,} puntos "
          f"({len(lons)} lon × {len(lats)} lat)")
    return lons_flat, lats_flat


# ----------------------------------------------------------------
# Paso 3 — Extraer WorldCover tile por tile (sin fusionar en memoria)
# ----------------------------------------------------------------
def extraer_por_tile(rutas_tiles: list[Path],
                     lons: np.ndarray,
                     lats: np.ndarray) -> np.ndarray:
    """
    Procesa cada tile por separado:
    1. Lee los bounds del tile
    2. Filtra solo los puntos de la grilla que caen dentro
    3. Extrae los valores de WorldCover para esos puntos
    4. Los registra en el array de resultados

    Esto evita cargar todos los tiles en memoria al mismo tiempo.
    """
    valores = np.zeros(len(lons), dtype=np.uint8)
    asignados = np.zeros(len(lons), dtype=bool)

    print(f"\nProcesando {len(rutas_tiles)} tiles uno por uno "
          f"(sin fusionar en memoria)...")

    for ruta in tqdm(rutas_tiles, desc="Extrayendo"):
        with rasterio.open(ruta) as src:
            bounds = src.bounds

            # Filtrar puntos que caen dentro de este tile
            mask = (
                (lons >= bounds.left)  & (lons <= bounds.right) &
                (lats >= bounds.bottom) & (lats <= bounds.top)
            )
            idx = np.where(mask)[0]

            if len(idx) == 0:
                continue

            # Extraer valores para esos puntos
            coords = list(zip(lons[idx], lats[idx]))
            vals = np.array([v[0] for v in sample_gen(src, coords)],
                            dtype=np.uint8)

            valores[idx] = vals
            asignados[idx] = True

        tqdm.write(f"  {ruta.name}: {len(idx):,} puntos extraídos")

    total_asignados = asignados.sum()
    print(f"\nTotal de puntos con valor asignado: {total_asignados:,} "
          f"de {len(lons):,}")

    return valores


# ----------------------------------------------------------------
# Paso 4 — Guardar CSV
# ----------------------------------------------------------------
def guardar_csv(lons: np.ndarray,
                lats: np.ndarray,
                valores: np.ndarray,
                out_path: str = "worldcover_centroamerica_1km.csv"):
    df = pd.DataFrame({
        "longitude":       lons,
        "latitude":        lats,
        "worldcover_code": valores.astype("int16"),
    })

    df["worldcover_clase"] = df["worldcover_code"].map(CLASES).fillna("Unknown")

    # Eliminar puntos sin dato
    df = df[df["worldcover_code"] > 0].reset_index(drop=True)

    print(f"\nDistribución de clases en Centroamérica:")
    resumen = (
        df.groupby(["worldcover_code", "worldcover_clase"])
        .size()
        .reset_index(name="puntos")
        .sort_values("puntos", ascending=False)
    )
    print(resumen.to_string(index=False))

    df.to_csv(out_path, index=False)
    size_mb = Path(out_path).stat().st_size / 1024 / 1024
    print(f"\nListo: {len(df):,} puntos guardados en '{out_path}' "
          f"({size_mb:.1f} MB)")

    return df


# ----------------------------------------------------------------
# Main
# ----------------------------------------------------------------
def main():
    print("=" * 60)
    print("ESA WorldCover 2021 — Centroamérica (grilla 1 km)")
    print("=" * 60)

    # 1. Descargar tiles
    rutas = descargar_tiles()

    # 2. Generar grilla
    print("\n" + "=" * 60)
    lons, lats = generar_grilla()

    # 3. Extraer tile por tile (sin explotar la RAM)
    print("\n" + "=" * 60)
    valores = extraer_por_tile(rutas, lons, lats)

    # 4. Guardar
    print("\n" + "=" * 60)
    guardar_csv(lons, lats, valores)

    print("\n✓ Proceso completado.")
    print("  Siguiente paso: py extraer_worldcover.py")


if __name__ == "__main__":
    main()
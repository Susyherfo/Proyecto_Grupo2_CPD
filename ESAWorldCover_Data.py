"""
worldcover_guanacaste.py

Descarga los tiles de ESA WorldCover 2021 (10m) que cubren
la provincia de Guanacaste, Costa Rica, usando el grid oficial
de ESA y el bucket S3 público — sin registro ni API key.

Basado en el snippet oficial de ESA WorldCover:
https://esa-worldcover.org/en/data-access

Requisitos:
    pip install geopandas requests tqdm
"""

import os
import requests
import geopandas as gpd
from pathlib import Path
from tqdm.auto import tqdm

# ----------------------------------------------------------------
# Configuración
# ----------------------------------------------------------------

# Bounding box de Guanacaste (west, south, east, north)
GUANACASTE_BOUNDS = (-86.4, 9.5, -84.6, 11.3)

S3_URL_PREFIX = "https://esa-worldcover.s3.eu-central-1.amazonaws.com"
YEAR          = 2021
VERSION       = "v200"
OUTPUT_FOLDER = "data/worldcover"


# ----------------------------------------------------------------
# Main
# ----------------------------------------------------------------
def main():
    # Crear carpeta de salida
    Path(OUTPUT_FOLDER).mkdir(parents=True, exist_ok=True)

    # 1. Cargar el grid oficial de ESA WorldCover desde S3
    #    Este GeoJSON tiene un polígono por cada tile disponible
    #    con su nombre (ll_tile) que se usa para construir la URL
    print("Cargando grid de tiles de ESA WorldCover...")
    grid_url = f"{S3_URL_PREFIX}/esa_worldcover_grid.geojson"
    grid = gpd.read_file(grid_url)
    print(f"Grid cargado: {len(grid)} tiles en total")

    # 2. Filtrar los tiles que intersectan con el bbox de Guanacaste
    from shapely.geometry import box
    guanacaste_geom = box(*GUANACASTE_BOUNDS)
    tiles = grid[grid.intersects(guanacaste_geom)]
    print(f"Tiles que cubren Guanacaste: {len(tiles)}")
    print("Tiles a descargar:")
    for t in tiles.ll_tile:
        print(f"  - {t}")

    # 3. Descargar cada tile
    print(f"\nDescargando {len(tiles)} tile(s) en '{OUTPUT_FOLDER}'...\n")

    for tile in tqdm(tiles.ll_tile):
        url = (
            f"{S3_URL_PREFIX}/{VERSION}/{YEAR}/map/"
            f"ESA_WorldCover_10m_{YEAR}_{VERSION}_{tile}_Map.tif"
        )
        out_path = Path(OUTPUT_FOLDER) / Path(url).name

        # Si ya existe, saltar
        if out_path.exists():
            print(f"  Ya existe, se omite: {out_path.name}")
            continue

        print(f"  Descargando: {Path(url).name}")
        r = requests.get(url, allow_redirects=True, stream=True, timeout=120)
        r.raise_for_status()

        # Guardar con barra de progreso por tile
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

    print(f"\nListo. Archivos guardados en '{OUTPUT_FOLDER}':")
    for f in Path(OUTPUT_FOLDER).glob("*.tif"):
        print(f"  {f.name} — {f.stat().st_size/1024/1024:.1f} MB")


if __name__ == "__main__":
    main()
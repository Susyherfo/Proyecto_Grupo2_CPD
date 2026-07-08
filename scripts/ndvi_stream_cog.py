"""
ndvi_stream_cog.py

Lee los GeoTIFF de NDVI de AppEEARS directamente desde la nube
para Centroamerica completa (2002-2026), sin descargar archivos
a disco permanentemente.

Cada fecha puede tener multiples tiles que se fusionan antes
de calcular las estadisticas de NDVI.

Requisitos:
    pip install rioxarray rasterio dask xarray requests numpy pandas
"""

import os
import re
import gc
import tempfile
import numpy as np
import pandas as pd
import requests
import rasterio
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# ----------------------------------------------------------------
# Configuracion
# ----------------------------------------------------------------
EARTHDATA_USER = "susyherfo"
EARTHDATA_PASS = "Sehffhes2008*"
TASK_ID        = "7d3492cd-2264-4bcf-86dd-0edd0f0d5855"
URLS_FILE      = "urls_ndvi_centroamerica.txt"
OUTPUT_CSV     = "ndvi_centroamerica_serie_temporal.csv"
MAX_WORKERS    = 4
NDVI_SCALE     = 0.0001


# ----------------------------------------------------------------
# Login
# ----------------------------------------------------------------
def obtener_token(usuario: str, password: str) -> str:
    r = requests.post(
        "https://appeears.earthdatacloud.nasa.gov/api/login",
        auth=(usuario, password)
    )
    r.raise_for_status()
    token = r.json()["token"]
    print(f"Token OK: {token[:20]}...")
    return token


# ----------------------------------------------------------------
# Leer URLs
# ----------------------------------------------------------------
def leer_urls(ruta: str) -> list[str]:
    with open(ruta) as f:
        # Strip maneja tanto \n como \r\n (Windows)
        urls = [l.strip() for l in f if l.strip()]
    print(f"URLs cargadas: {len(urls)}")
    return urls


# ----------------------------------------------------------------
# Agrupar URLs por fecha via bundle API
# ----------------------------------------------------------------
def agrupar_por_fecha(urls: list[str], token: str) -> dict:
    print("Obteniendo metadata del bundle para agrupar por fecha...")
    r = requests.get(
        f"https://appeears.earthdatacloud.nasa.gov/api/bundle/{TASK_ID}",
        headers={"Authorization": f"Bearer {token}"}
    )
    r.raise_for_status()
    archivos = r.json()["files"]

    # Mapa url -> filename
    id_a_nombre = {}
    for f in archivos:
        if f["file_name"].endswith(".tif") and "NDVI" in f["file_name"]:
            file_id = f["file_id"]
            url_archivo = (
                f"https://appeears.earthdatacloud.nasa.gov"
                f"/api/bundle/{TASK_ID}/{file_id}"
            )
            id_a_nombre[url_archivo] = f["file_name"]

    # Agrupar por DOY (año + dia del año)
    grupos: dict[str, list] = {}
    for url in urls:
        filename = id_a_nombre.get(url, "")
        match = re.search(r"doy(\d{7})", filename)
        if match:
            doy_key = match.group(1)
            if doy_key not in grupos:
                grupos[doy_key] = []
            grupos[doy_key].append((url, filename))

    print(f"Fechas unicas encontradas: {len(grupos)}")
    print(f"Tiles promedio por fecha:  "
          f"{sum(len(v) for v in grupos.values()) / len(grupos):.1f}")
    return grupos


# ----------------------------------------------------------------
# Descargar tile a numpy array sin dejar handle abierto (fix Windows)
# ----------------------------------------------------------------
def descargar_tile_a_numpy(url: str, filename: str,
                           token: str) -> np.ndarray | None:
    headers = {"Authorization": f"Bearer {token}"}
    tmp_path = None
    try:
        r = requests.get(url, headers=headers, stream=True, timeout=120)
        r.raise_for_status()

        with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as tmp:
            tmp_path = tmp.name
            for chunk in r.iter_content(chunk_size=65536):
                tmp.write(chunk)

        with rasterio.open(tmp_path) as src:
            data = src.read(1).astype("float32")
            nodata = src.nodata

        if nodata is not None:
            data[data == nodata] = np.nan

        gc.collect()
        os.unlink(tmp_path)
        return data

    except Exception as e:
        print(f"  [error tile] {filename}: {e}")
        if tmp_path:
            try:
                gc.collect()
                os.unlink(tmp_path)
            except Exception:
                pass
        return None


# ----------------------------------------------------------------
# Procesar una fecha (todos sus tiles -> estadisticas NDVI)
# ----------------------------------------------------------------
def procesar_fecha(doy_key: str, tiles: list[tuple],
                   token: str) -> dict | None:
    arrays = []
    for url, filename in tiles:
        arr = descargar_tile_a_numpy(url, filename, token)
        if arr is not None:
            arrays.append(arr)

    if not arrays:
        return None

    # Combinar todos los tiles de esta fecha
    combinado = np.concatenate([a.flatten() for a in arrays])

    # Aplicar escala y filtrar valores validos
    ndvi = combinado * NDVI_SCALE
    validos = ndvi[(ndvi >= -0.2) & (ndvi <= 1.0) & ~np.isnan(ndvi)]

    if len(validos) == 0:
        return None

    # Convertir DOY a fecha
    anio = int(doy_key[:4])
    doy  = int(doy_key[4:])
    fecha = datetime.strptime(f"{anio} {doy}", "%Y %j")

    return {
        "fecha":           fecha.strftime("%Y-%m-%d"),
        "ndvi_media":      round(float(np.mean(validos)),   4),
        "ndvi_mediana":    round(float(np.median(validos)), 4),
        "ndvi_min":        round(float(np.min(validos)),    4),
        "ndvi_max":        round(float(np.max(validos)),    4),
        "pixeles_validos": int(len(validos)),
        "tiles_usados":    len(arrays),
    }


# ----------------------------------------------------------------
# Main
# ----------------------------------------------------------------
def main():
    # 1. Login
    token = obtener_token(EARTHDATA_USER, EARTHDATA_PASS)

    # 2. Leer URLs
    urls = leer_urls(URLS_FILE)

    # 3. Agrupar por fecha
    grupos = agrupar_por_fecha(urls, token)

    # 4. Procesar en paralelo
    print(f"\nProcesando {len(grupos)} fechas con {MAX_WORKERS} hilos...\n")
    resultados = []
    items = list(grupos.items())

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futuros = {
            executor.submit(procesar_fecha, doy_key, tiles, token): doy_key
            for doy_key, tiles in items
        }
        completados = 0
        for futuro in as_completed(futuros):
            completados += 1
            resultado = futuro.result()
            if resultado:
                resultados.append(resultado)
            if completados % 25 == 0 or completados == len(items):
                print(f"  {completados}/{len(items)} fechas procesadas "
                      f"({len(resultados)} con datos)...")

    # 5. Construir DataFrame
    df = (
        pd.DataFrame(resultados)
        .sort_values("fecha")
        .reset_index(drop=True)
    )

    # 6. Guardar
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"\nListo: {len(df)} fechas guardadas en '{OUTPUT_CSV}'")
    print(f"\nPrimeras filas:")
    print(df.head(10).to_string(index=False))
    print(f"\nRango: {df['fecha'].min()} → {df['fecha'].max()}")


if __name__ == "__main__":
    main()
"""
firms_guanacaste_basico.py

Extraccion de focos activos MODIS/VIIRS para Guanacaste, Costa Rica,
usando la FIRMS Area API directamente (sin descargar archivos crudos
del repositorio NRT).

Version SECUENCIAL — punto de partida funcional antes de paralelizar.

Requisitos:
    pip install requests pandas

Antes de correr:
    1. Pedir un MAP_KEY gratuito en:
       https://firms.modaps.eosdis.nasa.gov/api/area/
       (llega por correo casi al instante)
    2. Exportarlo como variable de entorno:
       export FIRMS_MAP_KEY="tu_map_key_aqui"
"""

import os
import time
from datetime import date, timedelta

import pandas as pd
import requests

# ---------------------------------------------------------------------
# Configuracion
# ---------------------------------------------------------------------

MAP_KEY = os.environ.get("FIRMS_MAP_KEY")
if not MAP_KEY:
    raise RuntimeError(
        "No se encontro FIRMS_MAP_KEY en las variables de entorno. "
        "Solicita uno gratis en https://firms.modaps.eosdis.nasa.gov/api/area/ "
        "y luego corre: export FIRMS_MAP_KEY='TU-API-KEY'"
    )

# Bounding box aproximado de Guanacaste, Costa Rica (west, south, east, north)
# Ajustar si se cuenta con un shapefile mas preciso del limite provincial.
GUANACASTE_BBOX = "-86.0,9.9,-84.6,11.3"

# Fuente de datos. Para historico ya procesado y con mejor calidad usar
# MODIS_SP (Standard Processing). Para los ultimos ~2 meses, MODIS_NRT.
SOURCE = "MODIS_SP"

# La API permite maximo 5 dias por llamada
MAX_DAY_RANGE = 5

BASE_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"


def build_url(map_key: str, source: str, bbox: str, day_range: int, start_date: str) -> str:
    """Construye la URL de la FIRMS Area API."""
    return f"{BASE_URL}/{map_key}/{source}/{bbox}/{day_range}/{start_date}"


def fetch_window(start_date: date, day_range: int = MAX_DAY_RANGE) -> pd.DataFrame:
    """
    Descarga un bloque de hasta 5 dias de focos activos para Guanacaste,
    a partir de start_date, y lo retorna como DataFrame.
    """
    url = build_url(MAP_KEY, SOURCE, GUANACASTE_BBOX, day_range, start_date.isoformat())
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    # La API a veces responde con un CSV vacio (solo encabezados) o con un
    # mensaje de error en texto plano si algo salio mal con los parametros.
    if "Invalid" in response.text[:200] or response.text.strip() == "":
        print(f"  [aviso] respuesta inesperada para {start_date}: {response.text[:150]}")
        return pd.DataFrame()

    from io import StringIO
    df = pd.read_csv(StringIO(response.text))
    return df


def generar_ventanas(fecha_inicio: date, fecha_fin: date, paso: int = MAX_DAY_RANGE):
    """
    Genera una lista de fechas de inicio para cubrir [fecha_inicio, fecha_fin]
    en bloques de `paso` dias (maximo 5, segun limite de la API).
    """
    ventanas = []
    cursor = fecha_inicio
    while cursor <= fecha_fin:
        ventanas.append(cursor)
        cursor += timedelta(days=paso)
    return ventanas


def main():
    fecha_inicio = date(2023, 1, 1)
    fecha_fin = date(2023, 12, 31)  # todo el año, para comparar con el paralelo

    ventanas = generar_ventanas(fecha_inicio, fecha_fin)
    print(f"Se descargaran {len(ventanas)} ventanas de {MAX_DAY_RANGE} dias cada una "
          f"(secuencial)...")

    frames = []
    for i, inicio_ventana in enumerate(ventanas, start=1):
        print(f"[{i}/{len(ventanas)}] Descargando desde {inicio_ventana} ...")
        df = fetch_window(inicio_ventana)
        if not df.empty:
            frames.append(df)
        # Respetar el limite de 5000 transacciones / 10 minutos
        time.sleep(0.2)

    if frames:
        resultado = pd.concat(frames, ignore_index=True)
        resultado = resultado.drop_duplicates()
        out_path = "focos_guanacaste.csv"
        resultado.to_csv(out_path, index=False)
        print(f"\nListo: {len(resultado)} registros guardados en {out_path}")
    else:
        print("\nNo se obtuvieron registros para el rango solicitado.")


if __name__ == "__main__":
    main()

"""
firms_guanacaste_paralelo.py

Extraccion paralela de focos activos MODIS/VIIRS para Guanacaste, Costa Rica,
usando la FIRMS Area API directamente. No se descarga ningun archivo crudo
del repositorio NRT; toda la extraccion ocurre via requests HTTP a la API.

Como cada llamada a la API es independiente (ventana de hasta 5 dias) y el
cuello de botella es I/O (espera de red, no CPU), se usa
concurrent.futures.ThreadPoolExecutor: varias peticiones HTTP en vuelo al
mismo tiempo, sin bloquear la descarga de las demas mientras una espera
respuesta del servidor.

Requisitos:
    pip install requests pandas

Antes de correr:
    1. Pedir un MAP_KEY gratuito en:
       https://firms.modaps.eosdis.nasa.gov/api/area/
    2. export FIRMS_MAP_KEY="tu_map_key_aqui"
"""

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from io import StringIO

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
        "y luego corre: export FIRMS_MAP_KEY='tu_key'"
    )

GUANACASTE_BBOX = "-86.0,9.9,-84.6,11.3"

# MODIS_SP = standard processing (calidad cientifica, con 2-3 meses de lag)
# MODIS_NRT = near real-time (solo cubre los ultimos ~2 meses)
SOURCE = "MODIS_SP"

MAX_DAY_RANGE = 5  # limite duro de la API
BASE_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"

# Numero de hilos concurrentes. La cuenta gratuita permite 5000
# transacciones / 10 minutos, asi que con un pool moderado (8-10 hilos)
# se mantiene un margen amplio incluso con reintentos.
MAX_WORKERS = 8

# Reintentos simples ante errores de red transitorios
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 2


def build_url(source: str, bbox: str, day_range: int, start_date: str) -> str:
    return f"{BASE_URL}/{MAP_KEY}/{source}/{bbox}/{day_range}/{start_date}"


def fetch_window(start_date: date, day_range: int = MAX_DAY_RANGE) -> pd.DataFrame:
    """
    Descarga un bloque de hasta `day_range` dias de focos activos para
    Guanacaste a partir de start_date. Reintenta ante fallos de red.
    """
    url = build_url(SOURCE, GUANACASTE_BBOX, day_range, start_date.isoformat())

    last_error = None
    for intento in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            texto = response.text
            if texto.strip() == "" or "Invalid" in texto[:200]:
                # Ventana sin datos o parametros mal formados; no es un
                # error de red, asi que no tiene sentido reintentar.
                return pd.DataFrame()

            df = pd.read_csv(StringIO(texto))
            # Trazabilidad: registrar desde que ventana de consulta vino
            # cada bloque, util para depuracion y para el reporte de
            # rendimiento del pipeline.
            df["ventana_inicio"] = start_date.isoformat()
            return df

        except (requests.RequestException, pd.errors.ParserError) as e:
            last_error = e
            if intento < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SECONDS * intento)
            continue

    print(f"  [error] ventana {start_date} fallo tras {MAX_RETRIES} intentos: {last_error}")
    return pd.DataFrame()


def generar_ventanas(fecha_inicio: date, fecha_fin: date, paso: int = MAX_DAY_RANGE):
    ventanas = []
    cursor = fecha_inicio
    while cursor <= fecha_fin:
        ventanas.append(cursor)
        cursor += timedelta(days=paso)
    return ventanas


def descargar_en_paralelo(ventanas: list[date]) -> pd.DataFrame:
    """
    Lanza las descargas de todas las ventanas usando un pool de hilos.
    Cada hilo hace su propia peticion HTTP independiente; como el tiempo
    se gasta esperando la respuesta del servidor (I/O-bound) y no en
    computo de CPU, ThreadPoolExecutor es apropiado aqui (a diferencia
    de tareas CPU-bound, donde convendria multiprocessing).
    """
    frames = []
    t0 = time.perf_counter()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futuros = {executor.submit(fetch_window, v): v for v in ventanas}

        completados = 0
        for futuro in as_completed(futuros):
            ventana = futuros[futuro]
            completados += 1
            try:
                df = futuro.result()
                if not df.empty:
                    frames.append(df)
                print(f"[{completados}/{len(ventanas)}] ventana {ventana} -> "
                      f"{len(df)} registros")
            except Exception as e:
                print(f"[{completados}/{len(ventanas)}] ventana {ventana} -> ERROR: {e}")

    t1 = time.perf_counter()
    print(f"\nTiempo total de descarga (paralelo, {MAX_WORKERS} hilos): "
          f"{t1 - t0:.2f} s")

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True).drop_duplicates()


def main():
    fecha_inicio = date(2023, 1, 1)
    fecha_fin = date(2023, 12, 31)  # ejemplo: un anio completo

    ventanas = generar_ventanas(fecha_inicio, fecha_fin)
    print(f"Se descargaran {len(ventanas)} ventanas de {MAX_DAY_RANGE} dias "
          f"cada una, usando {MAX_WORKERS} hilos en paralelo...\n")

    resultado = descargar_en_paralelo(ventanas)

    if not resultado.empty:
        out_path = "focos_guanacaste_2023.csv"
        resultado.to_csv(out_path, index=False)
        print(f"\nListo: {len(resultado)} registros guardados en {out_path}")
    else:
        print("\nNo se obtuvieron registros para el rango solicitado.")


if __name__ == "__main__":
    main()

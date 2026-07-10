"""
gee_extraccion_centroamerica.py

Version mejorada con celdas de 2x2 grados (mas puntos por mes)
para superar el GB de datos limpios.

Cambios respecto a la version anterior:
  - PASO = 2.0 en lugar de 3.0 → ~48 celdas vs 24 anteriores
  - Doble de puntos por mes
  - Mismo checkpoint y sistema de parciales

Resultado esperado: ~50M registros → 1.5-2 GB limpios

Requisitos:
    pip install earthengine-api==0.1.370 pandas tqdm --user
"""

import ee
import pandas as pd
import time
from pathlib import Path
from tqdm.auto import tqdm

# ----------------------------------------------------------------
# Inicializar GEE
# ----------------------------------------------------------------
ee.Initialize(project='tribal-isotope-501923-f9')
print("Google Earth Engine inicializado correctamente.")

# ----------------------------------------------------------------
# Configuracion
# ----------------------------------------------------------------
ESCALA         = 1000
FECHA_INICIO   = "2002-01-01"
FECHA_FIN      = "2025-12-31"
MESES          = list(range(1, 13))
PUNTOS_CELDA   = 4500
PAUSA_CADA     = 10
PAUSA_SEG      = 60
PAUSA_CELDA    = 0.3

OUTPUT_DIR  = Path("data_gee")
OUTPUT_CSV  = "dataset_gee_centroamerica_completo.csv"
CHECKPOINT  = OUTPUT_DIR / "checkpoint.txt"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Celdas de 2x2 grados (~48 celdas vs 24 anteriores)
PASO = 2.0
CELDAS = []
lon = -92.5
while lon < -77.0:
    lat = 7.0
    while lat < 18.5:
        lon_max = min(lon + PASO, -77.0)
        lat_max = min(lat + PASO, 18.5)
        CELDAS.append((lon, lat, lon_max, lat_max))
        lat += PASO
    lon += PASO

print(f"Celdas de {PASO}x{PASO} grados: {len(CELDAS)}")
print(f"Puntos por celda:  {PUNTOS_CELDA:,}")
print(f"Maximo estimado:   {len(CELDAS) * PUNTOS_CELDA * 288:,} registros")
print()


# ----------------------------------------------------------------
# Datasets GEE
# ----------------------------------------------------------------
def get_imagen_mes(anio, mes):
    if mes == 12:
        fecha_fin = f"{anio+1}-01-01"
    else:
        fecha_fin = f"{anio}-{mes+1:02d}-01"
    fecha_ini = f"{anio}-{mes:02d}-01"

    firms_col = ee.ImageCollection("FIRMS").filterDate(fecha_ini, fecha_fin)
    firms = ee.Image(ee.Algorithms.If(
        firms_col.size().gt(0),
        firms_col.select("T21")
                 .map(lambda img: img.gt(325).rename("fuego"))
                 .max().unmask(0),
        ee.Image.constant(0).rename("fuego")
    ))

    ndvi_col = ee.ImageCollection("MODIS/061/MOD13A2").filterDate(fecha_ini, fecha_fin)
    ndvi = ee.Image(ee.Algorithms.If(
        ndvi_col.size().gt(0),
        ndvi_col.select("NDVI").mean().multiply(0.0001)
                .rename("ndvi").unmask(-9999),
        ee.Image.constant(-9999).rename("ndvi")
    ))

    era5_col = ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR").filterDate(fecha_ini, fecha_fin)
    era5 = ee.Image(ee.Algorithms.If(
        era5_col.size().gt(0),
        era5_col.select([
            "temperature_2m",
            "total_precipitation_sum",
            "u_component_of_wind_10m",
            "v_component_of_wind_10m"
        ]).mean().rename([
            "temperatura", "precipitacion", "viento_u", "viento_v"
        ]).unmask(-9999),
        ee.Image.constant([-9999, -9999, -9999, -9999]).rename([
            "temperatura", "precipitacion", "viento_u", "viento_v"
        ])
    ))

    dem       = ee.Image("USGS/SRTMGL1_003").select("elevation")
    pendiente = ee.Terrain.slope(dem).rename("pendiente")
    worldcover = (ee.ImageCollection("ESA/WorldCover/v200")
                    .first().select("Map").rename("cobertura"))

    return (firms.addBands(ndvi).addBands(era5)
            .addBands(dem).addBands(pendiente).addBands(worldcover))


# ----------------------------------------------------------------
# Extraer una celda
# ----------------------------------------------------------------
def extraer_celda(imagen, celda, anio, mes):
    lon_min, lat_min, lon_max, lat_max = celda
    region = ee.Geometry.Rectangle([lon_min, lat_min, lon_max, lat_max])

    try:
        puntos = imagen.sample(
            region=region,
            scale=ESCALA,
            geometries=True,
            seed=42,
            numPixels=PUNTOS_CELDA,
            dropNulls=True
        )

        info     = puntos.getInfo()
        features = info.get('features', [])
        if not features:
            return None

        rows = []
        for f in features:
            props  = f.get('properties', {})
            coords = f.get('geometry', {}).get('coordinates', [None, None])
            props['longitude'] = coords[0]
            props['latitude']  = coords[1]
            props['anio']  = anio
            props['mes']   = mes
            props['fecha'] = f"{anio}-{mes:02d}"
            rows.append(props)

        return pd.DataFrame(rows)

    except Exception:
        return None


# ----------------------------------------------------------------
# Extraer un mes (todas las celdas)
# ----------------------------------------------------------------
def extraer_mes(anio, mes):
    try:
        imagen = get_imagen_mes(anio, mes)
        frames_celda = []

        for celda in CELDAS:
            df_celda = extraer_celda(imagen, celda, anio, mes)
            if df_celda is not None and not df_celda.empty:
                frames_celda.append(df_celda)
            time.sleep(PAUSA_CELDA)

        if not frames_celda:
            return None

        df = pd.concat(frames_celda, ignore_index=True)
        cols_drop = [c for c in df.columns
                     if c in ["system:index", ".geo", "system:time_start"]]
        return df.drop(columns=cols_drop, errors="ignore")

    except Exception as e:
        print(f"\n  [error mes] {anio}-{mes:02d}: {e}")
        return None


# ----------------------------------------------------------------
# Main
# ----------------------------------------------------------------
def main():
    anio_ini = int(FECHA_INICIO[:4])
    anio_fin = int(FECHA_FIN[:4])

    todos = [
        (anio, mes)
        for anio in range(anio_ini, anio_fin + 1)
        for mes in MESES
    ]

    # Checkpoint
    procesados = set()
    if CHECKPOINT.exists():
        with open(CHECKPOINT) as f:
            for linea in f:
                procesados.add(linea.strip())
        print(f"Checkpoint: {len(procesados)} meses ya procesados.")

    pendientes = [(a, m) for a, m in todos if f"{a}-{m:02d}" not in procesados]

    print(f"Total meses:    {len(todos)}")
    print(f"Pendientes:     {len(pendientes)}")
    print(f"Celdas/mes:     {len(CELDAS)}")
    print(f"Puntos/celda:   {PUNTOS_CELDA:,}")
    print(f"Max registros:  {len(pendientes)*len(CELDAS)*PUNTOS_CELDA:,}\n")

    frames    = []
    contador  = 0
    parcial_n = 0
    total_reg = 0

    with tqdm(total=len(pendientes), desc="Extrayendo") as pbar:
        for anio, mes in pendientes:
            pbar.set_description(f"{anio}-{mes:02d}")

            df = extraer_mes(anio, mes)

            if df is not None and not df.empty:
                frames.append(df)
                total_reg += len(df)
                fuegos = int(df["fuego"].sum()) if "fuego" in df.columns else 0
                pbar.set_postfix({
                    "total": f"{total_reg:,}",
                    "fuegos": fuegos
                })

            with open(CHECKPOINT, "a") as f:
                f.write(f"{anio}-{mes:02d}\n")

            contador += 1
            pbar.update(1)

            if contador % PAUSA_CADA == 0 and frames:
                parcial_n += 1
                parcial_path = OUTPUT_DIR / f"parcial_{parcial_n:03d}.csv"
                pd.concat(frames, ignore_index=True).to_csv(
                    parcial_path, index=False)
                size_mb = parcial_path.stat().st_size / 1024 / 1024
                tqdm.write(
                    f"\n  Parcial {parcial_n}: "
                    f"{total_reg:,} registros ({size_mb:.1f} MB)")
                frames = []
                tqdm.write(f"  Pausa de {PAUSA_SEG}s...")
                time.sleep(PAUSA_SEG)

    if frames:
        parcial_n += 1
        pd.concat(frames, ignore_index=True).to_csv(
            OUTPUT_DIR / f"parcial_{parcial_n:03d}.csv", index=False)
        frames = []

    # Concatenar parciales
    print("\nConcatenando parciales...")
    parciales = sorted(OUTPUT_DIR.glob("parcial_*.csv"))
    print(f"Parciales: {len(parciales)}")

    if not parciales:
        print("No hay datos.")
        return

    dfs = [pd.read_csv(p) for p in tqdm(parciales, desc="Leyendo")]
    resultado = pd.concat(dfs, ignore_index=True)

    out_path = OUTPUT_DIR / OUTPUT_CSV
    resultado.to_csv(out_path, index=False)

    size_mb = out_path.stat().st_size / 1024 / 1024
    print(f"\n{'='*60}")
    print(f"Dataset final:  {len(resultado):,} registros")
    print(f"Tamano:         {size_mb:.1f} MB ({size_mb/1024:.2f} GB)")
    print(f"Columnas:       {resultado.columns.tolist()}")

    if "fuego" in resultado.columns:
        vc = resultado["fuego"].value_counts()
        print(f"\nDistribucion:")
        print(f"  Sin incendio (0): {vc.get(0, 0):,}")
        print(f"  Con incendio (1): {vc.get(1, 0):,}")

    for p in parciales:
        p.unlink()
    CHECKPOINT.unlink(missing_ok=True)
    print(f"\nArchivo: {out_path}")


if __name__ == "__main__":
    main()

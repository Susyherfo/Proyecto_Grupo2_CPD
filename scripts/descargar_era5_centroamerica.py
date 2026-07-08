import os
import cdsapi

# Bounding box de CENTROAMERICA: [Norte, Oeste, Sur, Este]
# Cubre Guatemala/Belice hasta Panama.
AREA = [18.5, -92.5, 6.0, -77.0]
ANIO_INICIO = 2002
ANIO_FIN = 2026
VARIABLES = [
    "2m_temperature",
    "10m_u_component_of_wind",
    "10m_v_component_of_wind",
    "2m_dewpoint_temperature",
    "total_precipitation",
]
# 2 momentos al dia. Si diera "cost limits exceeded", dejalo en ["12:00"].
TIMES = ["00:00", "12:00"]

cliente = cdsapi.Client()

for anio in range(ANIO_INICIO, ANIO_FIN + 1):
    salida = f"era5_centroamerica_{anio}.nc"
    if os.path.exists(salida):
        print(f"(ya existe, salto) {salida}")
        continue

    print(f"\n=== Descargando año {anio} (Centroamerica) ===")
    try:
        cliente.retrieve(
            "reanalysis-era5-land",
            {
                "variable": VARIABLES,
                "year": str(anio),
                "month": [f"{m:02d}" for m in range(1, 13)],
                "day": [f"{d:02d}" for d in range(1, 32)],
                "time": TIMES,
                "area": AREA,
                "data_format": "netcdf",
            },
            salida,
        )
        print(f"Listo: {salida}")
    except Exception as e:
        print(f"  [error] {salida}: {e}  (se reintenta al volver a correr)")

print("\nProceso terminado.")

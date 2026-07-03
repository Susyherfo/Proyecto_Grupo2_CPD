# Pipeline de Datos — Detección y Predicción de Incendios en Guanacaste, Costa Rica

Pipeline de adquisición y procesamiento de datos satelitales para la provincia de Guanacaste, Costa Rica, orientado a la predicción de propagación de incendios forestales al día siguiente. Utiliza herramientas de **computación paralela y distribuida** en Python como `ThreadPoolExecutor` y `rioxarray` con Dask.

Forma parte del proyecto de curso *Exploración de Herramientas Paralelas y Distribuidas para el Análisis de Datos en Python* — Universidad LEAD.

---

## Contenido

| Archivo | Descripción |
|---|---|
| `firms_guanacaste_basico.py` | Extracción **secuencial** de focos activos MODIS/VIIRS vía FIRMS Area API. Punto de partida para validar conexión y MAP_KEY. |
| `firms_guanacaste_paralelo.py` | Extracción **paralela** con `ThreadPoolExecutor`. Para rangos largos (varios años) de forma eficiente. |
| `firms_guanacaste_benchmark.py` | **Benchmark** de rendimiento: mide tiempo, *speedup* y eficiencia variando el número de hilos (1, 2, 4, 8). Genera tabla CSV y gráfica PNG. |
| `ndvi_stream_cog.py` | Extracción **paralela** de índice de vegetación NDVI (MOD13A2) desde AppEEARS vía bundle API, sin descargar archivos a disco. Fusiona 2 tiles por fecha y genera serie temporal CSV. |
| `ndvi_guanacaste_serie_temporal.csv` | Serie temporal de NDVI para Guanacaste: 595 fechas, febrero 2000 – diciembre 2025, una observación cada 16 días. |
| `guanacaste.geojson` | Bounding box de la provincia de Guanacaste usado para filtrar todas las fuentes de datos. |
| `urls_ndvi.txt` | URLs de los 595 GeoTIFF de NDVI del bundle de AppEEARS (generado automáticamente). |
| `requirements.txt` | Dependencias del proyecto. |

---

## Fuentes de datos

| Fuente | Dato | Período | Acceso |
|---|---|---|---|
| NASA FIRMS API | Focos activos MODIS/VIIRS | 2000–presente | MAP_KEY gratuito |
| NASA AppEEARS | NDVI MOD13A2 (cada 16 días) | 2000–2025 | Earthdata Login gratuito |
| Copernicus CDS | ERA5: temperatura, lluvia, viento | Pendiente | Cuenta CDS gratuita |
| OpenTopography | DEM SRTM 30m | Estático | API Key gratuita |

---

## Estado del pipeline

```
Paso 1 ✅  Focos activos FIRMS (secuencial + paralelo + benchmark)
Paso 2 ✅  NDVI serie temporal 2000-2025 (595 fechas, AppEEARS)
Paso 3 ⬜  ERA5 clima (temperatura, lluvia, viento)
Paso 4 ⬜  Integración de fuentes en dataset unificado por fecha
Paso 5 ⬜  Construcción de variable target (focos día siguiente)
Paso 6 ⬜  Entrenamiento del modelo (CNN / XGBoost)
Paso 7 ⬜  Dashboard / mapa interactivo
```

---

## 1. Requisitos previos

- Python 3.10 o superior.
- Cuenta de correo para el MAP_KEY de FIRMS (gratuito).
- Cuenta Earthdata Login para AppEEARS (gratuita).

---

## 2. Instalación

```bash
git clone <url-del-repositorio>
cd Proyecto_Grupo2_CPD
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
pip install matplotlib rioxarray rasterio
```

---

## 3. Credenciales necesarias

### FIRMS MAP_KEY (para focos activos)
1. Ir a https://firms.modaps.eosdis.nasa.gov/api/area/
2. Click en **Get MAP_KEY** e ingresar un correo — llega al instante.

**Windows (PowerShell):**
```powershell
$env:FIRMS_MAP_KEY = "tu_map_key_aqui"
```

**macOS / Linux:**
```bash
export FIRMS_MAP_KEY="tu_map_key_aqui"
```

### Earthdata Login (para NDVI AppEEARS)
1. Registrarse en https://urs.earthdata.nasa.gov/users/new
2. Usar las mismas credenciales en `ndvi_stream_cog.py`:
```python
EARTHDATA_USER = "tu_usuario"
EARTHDATA_PASS = "tu_contraseña"
```

> **Seguridad:** nunca subas MAP_KEY ni contraseñas directamente en el código. Usá variables de entorno o un archivo `.env` excluido del repositorio.

---

## 4. Uso

### Paso 1 — Validar conexión FIRMS (secuencial)
```bash
py firms_guanacaste_basico.py
```
Genera `focos_guanacaste.csv` con los focos activos del rango configurado.

### Paso 2 — Descarga histórica FIRMS (paralela)
Editá `fecha_inicio` y `fecha_fin` en `main()` según el rango deseado:
```bash
py firms_guanacaste_paralelo.py
```
Genera `focos_guanacaste_2023.csv`.

### Paso 3 — Benchmark de rendimiento FIRMS
```bash
py firms_guanacaste_benchmark.py
```
Genera `benchmark_resultados.csv` y `benchmark_speedup.png`.

> **Límite de la API:** 5000 transacciones cada 10 minutos. Para el benchmark, usar un rango corto (un trimestre) para no agotar la cuota.

### Paso 4 — Extracción NDVI desde AppEEARS
Requiere haber generado `urls_ndvi.txt` previamente (ver sección 5). Luego:
```bash
py ndvi_stream_cog.py
```
Genera `ndvi_guanacaste_serie_temporal.csv` con 595 fechas (2000–2025).

---

## 5. Generar urls_ndvi.txt (primera vez)

Si `urls_ndvi.txt` no existe, corré este script una sola vez para obtener las URLs del bundle de AppEEARS:

```python
import requests, json

usuario  = "tu_usuario_earthdata"
password = "tu_contraseña_earthdata"
task_id  = "044bcf2a-abc5-4a2e-97be-2bf436a160cc"

token = requests.post(
    "https://appeears.earthdatacloud.nasa.gov/api/login",
    auth=(usuario, password)
).json()["token"]

archivos = requests.get(
    f"https://appeears.earthdatacloud.nasa.gov/api/bundle/{task_id}",
    headers={"Authorization": f"Bearer {token}"}
).json()["files"]

with open("urls_ndvi.txt", "w") as f:
    for a in archivos:
        if a["file_name"].endswith(".tif") and "NDVI" in a["file_name"]:
            file_id = a["file_id"]
            f.write(
                f"https://appeears.earthdatacloud.nasa.gov"
                f"/api/bundle/{task_id}/{file_id}\n"
            )
print("urls_ndvi.txt generado.")
```

---

## 6. Resultados de referencia

### FIRMS — Benchmark de speedup (año 2023, 73 ventanas)

| Hilos | Speedup | Eficiencia |
|---|---|---|
| 1 (secuencial) | 1.0× | 1.00 |
| 2 | 2.5× | — |
| 4 | 4.8× | — |
| 8 | **8.0×** | 1.00 |

La tarea es **I/O-bound** (espera de red), por lo que `ThreadPoolExecutor` escala casi linealmente. A partir de 8 hilos la eficiencia cae por saturación de red (rendimientos decrecientes).

### NDVI AppEEARS — Serie temporal generada

| Métrica | Valor |
|---|---|
| Fechas cubiertas | Feb 2000 – Dic 2025 |
| Total de observaciones | 595 |
| Frecuencia | Cada 16 días |
| NDVI medio histórico (Guanacaste) | 0.619 |
| Píxeles válidos por fecha | ~24,000 |
| Nulos | 0 |

---

## 7. Parámetros configurables

### firms_guanacaste_paralelo.py

| Variable | Descripción | Valor por defecto |
|---|---|---|
| `GUANACASTE_BBOX` | Bounding box `west,south,east,north` | `-86.4,9.5,-84.6,11.3` |
| `SOURCE` | `MODIS_SP` (calidad científica) o `MODIS_NRT` (tiempo real) | `MODIS_SP` |
| `MAX_WORKERS` | Hilos concurrentes | `8` |
| `MAX_RETRIES` | Reintentos ante errores de red | `3` |

### ndvi_stream_cog.py

| Variable | Descripción | Valor por defecto |
|---|---|---|
| `MAX_WORKERS` | Hilos concurrentes para descarga de tiles | `4` |
| `NDVI_SCALE` | Factor de escala oficial MOD13A2 | `0.0001` |
| `TASK_ID` | ID del request en AppEEARS | `044bcf2a-...` |

---

## 8. Estructura del repositorio

```
Proyecto_Grupo2_CPD/
├── firms_guanacaste_basico.py
├── firms_guanacaste_paralelo.py
├── firms_guanacaste_benchmark.py
├── ndvi_stream_cog.py
├── ndvi_guanacaste_serie_temporal.csv
├── guanacaste.geojson
├── urls_ndvi.txt
├── requirements.txt
└── README.md
```

---

## 9. Límites de APIs

| API | Límite |
|---|---|
| FIRMS Area API | 5000 transacciones / 10 minutos por MAP_KEY |
| FIRMS por request | Máximo 5 días por llamada |
| AppEEARS bundle | Sin límite de descarga, requiere autenticación Bearer |

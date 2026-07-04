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
| `worldcover_guanacaste.py` | Descarga los tiles de **ESA WorldCover 2021** (cobertura del suelo a 10m) que cubren Guanacaste desde el bucket S3 público de ESA. Sin registro ni API key. |
| `extraer_worldcover.py` | Extrae la clase de cobertura del suelo para cada foco activo del dataset, cruzando coordenadas lat/lon con el GeoTIFF de WorldCover. |
| `limpiar_dataset.py` | Limpia el dataset eliminando registros del 2026 y filas con NDVI nulo. |
| `ndvi_guanacaste_serie_temporal.csv` | Serie temporal de NDVI para Guanacaste: 595 fechas, febrero 2000 – diciembre 2025, una observación cada 16 días. |
| `focos_guanacaste_ndvi_limpio.csv` | Dataset limpio de focos activos + NDVI (2002–2025, sin nulos). |
| `focos_guanacaste_ndvi_worldcover.csv` | Dataset final con focos activos + NDVI + cobertura del suelo WorldCover. |
| `guanacaste.geojson` | Bounding box de la provincia de Guanacaste usado para filtrar todas las fuentes de datos. |
| `urls_ndvi.txt` | URLs de los 595 GeoTIFF de NDVI del bundle de AppEEARS (generado automáticamente). |
| `requirements.txt` | Dependencias del proyecto. |

---

## Fuentes de datos

| Fuente | Dato | Período | Acceso |
|---|---|---|---|
| NASA FIRMS API | Focos activos MODIS/VIIRS | 2002–2025 | MAP_KEY gratuito |
| NASA AppEEARS | NDVI MOD13A2 (cada 16 días) | 2000–2025 | Earthdata Login gratuito |
| ESA WorldCover | Cobertura del suelo 10m | 2021 (estático) | S3 público, sin registro |
| Copernicus CDS | ERA5: temperatura, lluvia, viento | Pendiente (compañero) | Cuenta CDS gratuita |
| OpenTopography | DEM SRTM 30m | Estático (compañero) | API Key gratuita |

---

## Estado del pipeline

```
Paso 1 ✅  Focos activos FIRMS (secuencial + paralelo + benchmark)
Paso 2 ✅  NDVI serie temporal 2000-2025 (595 fechas, AppEEARS)
Paso 3 ✅  Cobertura del suelo (ESA WorldCover 2021, tile N09W087)
Paso 4 ✅  Limpieza del dataset (sin 2026, sin nulos)
Paso 5 ⬜  ERA5 clima (temperatura, lluvia, viento) — compañero
Paso 6 ⬜  DEM topografía — compañero
Paso 7 ⬜  Integración de fuentes en dataset unificado
Paso 8 ⬜  Construcción de variable target (focos día siguiente)
Paso 9 ⬜  Entrenamiento del modelo (CNN / XGBoost)
Paso 10 ⬜  Dashboard / mapa interactivo
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

## 4. Uso — orden de ejecución

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

### Paso 5 — Limpiar el dataset
```bash
py limpiar_dataset.py
```
Genera `focos_guanacaste_ndvi_limpio.csv` sin registros del 2026 ni nulos de NDVI.

### Paso 6 — Descargar ESA WorldCover
```bash
py worldcover_guanacaste.py
```
Descarga los tiles GeoTIFF de cobertura del suelo en `data/worldcover/`. No requiere registro.

### Paso 7 — Extraer cobertura del suelo
```bash
py extraer_worldcover.py
```
Genera `focos_guanacaste_ndvi_worldcover.csv` con la clase de cobertura del suelo para cada foco activo.

---

## 5. Generar urls_ndvi.txt (primera vez)

Si `urls_ndvi.txt` no existe, corré este script una sola vez para obtener las URLs del bundle de AppEEARS:

```python
import requests

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

### ESA WorldCover — Distribución de focos por cobertura

| Clase | Focos | Porcentaje |
|---|---|---|
| Tree cover (bosque) | 11,266 | 50.2% |
| Grassland (pastizal) | 7,360 | 32.8% |
| Cropland (cultivos) | 3,043 | 13.6% |
| Built-up (urbano) | 417 | 1.9% |
| Otros | 348 | 1.5% |

### Dataset final actual

| Métrica | Valor |
|---|---|
| Registros totales | 22,434 |
| Período cubierto | 2002–2025 |
| Columnas | 24 (lat, lon, fecha, brillo, FRP, confianza, NDVI, cobertura...) |
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

### extraer_worldcover.py

| Variable | Descripción | Valor por defecto |
|---|---|---|
| `INPUT_CSV` | Dataset de entrada | `focos_guanacaste_ndvi_limpio.csv` |
| `WORLDCOVER` | Ruta al tile GeoTIFF | `data/worldcover/ESA_WorldCover_10m_2021_v200_N09W087_Map.tif` |
| `OUTPUT_CSV` | Dataset de salida | `focos_guanacaste_ndvi_worldcover.csv` |

---

## 8. Estructura del repositorio

```
Proyecto_Grupo2_CPD/
├── data/
│   └── worldcover/
│       └── ESA_WorldCover_10m_2021_v200_N09W087_Map.tif
├── firms_guanacaste_basico.py
├── firms_guanacaste_paralelo.py
├── firms_guanacaste_benchmark.py
├── ndvi_stream_cog.py
├── worldcover_guanacaste.py
├── extraer_worldcover.py
├── limpiar_dataset.py
├── focos_guanacaste_ndvi_limpio.csv
├── focos_guanacaste_ndvi_worldcover.csv
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
| ESA WorldCover S3 | Sin límite, acceso público sin registro |

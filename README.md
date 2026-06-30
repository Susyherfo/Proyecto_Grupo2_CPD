# Extracción de Focos Activos — Guanacaste, Costa Rica (NASA FIRMS)

Pipeline de adquisición **paralela** de datos de focos activos MODIS/VIIRS para la provincia de Guanacaste, Costa Rica, usando directamente la **FIRMS Area API** de la NASA. No se descarga ningún archivo crudo del repositorio NRT: toda la extracción ocurre mediante peticiones HTTP a la API, que ya filtra por bounding box y rango de fechas del lado del servidor.

El proyecto incluye además un **benchmark de rendimiento** que compara la versión secuencial contra la paralela y mide el *speedup* al variar el número de hilos, que es el objetivo central del curso.

Forma parte del proyecto de curso *Exploración de Herramientas Paralelas y Distribuidas para el Análisis de Datos en Python*.

## Contenido

| Archivo | Descripción |
|---|---|
| `firms_guanacaste_basico.py` | Versión **secuencial**. Punto de partida para validar que la conexión y el MAP_KEY funcionan. |
| `firms_guanacaste_paralelo.py` | Versión **paralela** con `ThreadPoolExecutor`. Para descargar rangos largos de forma eficiente. |
| `firms_guanacaste_benchmark.py` | **Benchmark** de rendimiento: mide el tiempo del mismo rango variando el número de hilos (1, 2, 4, 8, 16) y genera una tabla y una gráfica de *speedup*. Promedia varias corridas y se detiene solo al llegar al punto de rendimientos decrecientes. |
| `requirements.txt` | Dependencias del proyecto. |

## 1. Requisitos previos

- Python 3.10 o superior.
- Una cuenta de correo para solicitar el `MAP_KEY` (gratuito, no requiere Earthdata Login).

## 2. Instalación

Con el entorno virtual activado (`.venv`), instala las dependencias:

```bash
pip install -r requirements.txt
```

El benchmark requiere además `matplotlib` para generar la gráfica:

```bash
pip install matplotlib
```

## 3. Obtener el MAP_KEY de FIRMS

1. Ir a [https://firms.modaps.eosdis.nasa.gov/api/area/](https://firms.modaps.eosdis.nasa.gov/api/area/)
2. Hacer clic en **Get MAP_KEY**, ingresar un correo y enviarlo.
3. El key llega casi al instante al correo indicado.

Para consultar cuántas transacciones quedan disponibles:

```
https://firms.modaps.eosdis.nasa.gov/mapserver/mapkey_status/?MAP_KEY=tu_map_key_aqui
```

## 4. Configurar el MAP_KEY como variable de entorno

**Windows (PowerShell)** — solo para la sesión actual:

```powershell
$env:FIRMS_MAP_KEY = "tu_map_key_aqui"
```

**macOS / Linux (bash/zsh)**:

```bash
export FIRMS_MAP_KEY="tu_map_key_aqui"
```

> **Nota de seguridad:** el `MAP_KEY` es de uso gratuito, pero evita subirlo a un repositorio público. No lo escribas directamente en el código; siempre como variable de entorno.

## 5. Uso

### Paso 1 — validar la conexión (versión secuencial)

```bash
python3 firms_guanacaste_basico.py
```

Si todo está bien, se genera `focos_guanacaste.csv`.

### Paso 2 — descarga del histórico (versión paralela)

Edita las fechas `fecha_inicio` y `fecha_fin` dentro de `main()` según el rango deseado, y corre:

```bash
python3 firms_guanacaste_paralelo.py
```

### Paso 3 — benchmark de rendimiento

```bash
python3 firms_guanacaste_benchmark.py
```

Salidas: `benchmark_resultados.csv` (tabla con tiempo, *speedup* y eficiencia) y `benchmark_speedup.png` (gráfica de dos paneles).

> **Importante — límite de la API.** El `MAP_KEY` permite **5000 transacciones cada 10 minutos**. El benchmark multiplica las peticiones (ventanas × hilos × repeticiones), así que correr el **año completo varias veces seguidas agota la cuota** y la API responde `400 Bad Request`. Para iterar sin chocar con el límite, se recomienda usar un **rango corto** (un mes o un trimestre) ajustando `FECHA_FIN`. Si aparece el error 400, espera ~10 minutos a que el contador se reinicie.

## 6. Resultados de referencia

Ejecución de prueba sobre el **primer trimestre de 2023** (~18 ventanas), con 3 repeticiones promediadas, en un MacBook Pro. Los tiempos absolutos dependen de la red y la máquina; lo relevante es la tendencia:

| Hilos | Speedup | Eficiencia |
|---|---|---|
| 1 (secuencial) | 1.0× | 1.00 |
| 2 | 2.5× | — |
| 4 | 4.8× | — |
| 8 | **8.0×** | 1.00 |
| 16 | 9.7× | 0.61 |

La extracción es una tarea **I/O-bound** (el tiempo se gasta esperando la respuesta de la red, no en cómputo de CPU). Por eso `ThreadPoolExecutor` es la herramienta apropiada y el *speedup* escala casi linealmente hasta **8 hilos** (punto óptimo, eficiencia ≈ 1.0). A partir de ahí la eficiencia **cae** (0.61 con 16 hilos): hay más hilos que ventanas por descargar y la red se satura, evidenciando los **rendimientos decrecientes**. Todas las configuraciones producen el mismo número de registros, confirmando que la paralelización no altera el resultado, solo la velocidad.

> Nota: pequeñas variaciones de red pueden producir eficiencias ligeramente superiores a 1 en corridas individuales; promediar varias repeticiones (`REPETICIONES = 3`) reduce ese ruido.

## 7. Parámetros configurables

**Extracción** (`firms_guanacaste_basico.py` / `firms_guanacaste_paralelo.py`):

| Variable | Descripción | Valor por defecto |
|---|---|---|
| `GUANACASTE_BBOX` | Bounding box `west,south,east,north` | `-86.0,9.9,-84.6,11.3` (aproximado) |
| `SOURCE` | `MODIS_SP` (calidad científica, 2-3 meses de rezago) o `MODIS_NRT` (últimos ~2 meses) | `MODIS_SP` |
| `MAX_WORKERS` | Número de hilos concurrentes (versión paralela) | `8` |
| `MAX_RETRIES` | Reintentos ante errores de red transitorios | `3` |

**Benchmark** (`firms_guanacaste_benchmark.py`):

| Variable | Descripción | Valor recomendado |
|---|---|---|
| `FECHA_INICIO` / `FECHA_FIN` | Rango de fechas a descargar en cada prueba | un trimestre (ej. `2023-01-01` a `2023-03-31`) |
| `LISTA_HILOS` | Configuraciones de hilos a comparar | `[1, 2, 4, 8, 16]` |
| `REPETICIONES` | Corridas por configuración (se promedian para reducir ruido) | `3` |
| `UMBRAL_MEJORA` | Si agregar hilos mejora menos que este porcentaje, el benchmark se detiene | `0.10` (10%) |

> El bounding box actual es un rectángulo aproximado de Guanacaste. Para un recorte más preciso al polígono provincial real, se recomienda agregar un paso posterior de filtrado espacial con `geopandas`/`shapely`.

## 8. Límites de la API

- Máximo **5 días por solicitud** (`DAY_RANGE`); los rangos largos se trocean en ventanas de 5 días.
- Máximo **5000 transacciones cada 10 minutos** por MAP_KEY.
- Documentación oficial: [https://firms.modaps.eosdis.nasa.gov/api/area/](https://firms.modaps.eosdis.nasa.gov/api/area/)

## 9. Reproducibilidad

```bash
git clone <url-del-repositorio>
cd Proyecto_Grupo2_CPD
python -m venv .venv
source .venv/bin/activate        # macOS / Linux
pip install -r requirements.txt
export FIRMS_MAP_KEY="tu_map_key_aqui"
python3 firms_guanacaste_basico.py
python3 firms_guanacaste_benchmark.py
```

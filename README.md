# Extracción de Focos Activos — Guanacaste, Costa Rica (NASA FIRMS)

Pipeline de adquisición de datos de focos activos MODIS/VIIRS para la provincia de Guanacaste, Costa Rica, usando directamente la **FIRMS Area API** de la NASA. No se descarga ningún archivo crudo del repositorio NRT: toda la extracción ocurre mediante peticiones HTTP a la API, que ya filtra por bounding box y rango de fechas del lado del servidor.

Forma parte del proyecto de curso *Exploración de Herramientas Paralelas y Distribuidas para el Análisis de Datos en Python*.

## Contenido

| Archivo | Descripción |
|---|---|
| `firms_guanacaste_basico.py` | Versión secuencial. Punto de partida para validar que la conexión y el MAP_KEY funcionan. |
| `firms_guanacaste_paralelo.py` | Versión paralela con `ThreadPoolExecutor`. Para descargar rangos largos (varios años) de forma eficiente. |
| `requirements.txt` | Dependencias del proyecto. |

## 1. Requisitos previos

- Python 3.10 o superior.
- Una cuenta de correo para solicitar el `MAP_KEY` (gratuito, no requiere Earthdata Login).

## 2. Instalación

Con el entorno virtual activado (`.venv`), instala las dependencias:

```bash
pip install -r requirements.txt
```

## 3. Obtener el MAP_KEY de FIRMS

1. Ir a [https://firms.modaps.eosdis.nasa.gov/api/area/](https://firms.modaps.eosdis.nasa.gov/api/area/)
2. Hacer clic en **Get MAP_KEY**, ingresar un correo y enviarlo.
3. El key llega casi al instante al correo indicado.

El `MAP_KEY` permite hasta **5000 transacciones cada 10 minutos**. Cada solicitud de varios días de rango puede contar como más de una transacción.

## 4. Configurar el MAP_KEY como variable de entorno

**Windows (PowerShell)** — solo para la sesión actual:

```powershell
$env:FIRMS_MAP_KEY = "tu_map_key_aqui"
```

**Windows (PowerShell)** — persistente entre sesiones (requiere reabrir la terminal):

```powershell
setx FIRMS_MAP_KEY "tu_map_key_aqui"
```

**macOS / Linux (bash/zsh)**:

```bash
export FIRMS_MAP_KEY="tu_map_key_aqui"
```

Para hacerlo persistente en Linux/macOS, agrega esa misma línea a `~/.bashrc`, `~/.zshrc` o equivalente.

> **Nota de seguridad:** el `MAP_KEY` es de uso gratuito y de bajo riesgo, pero evita subirlo a un repositorio público (GitLab/GitHub). No lo escribas directamente en el código; siempre como variable de entorno.

## 5. Uso

### Paso 1 — validar la conexión (versión secuencial)

Descarga un mes de prueba (enero 2023) para confirmar que el MAP_KEY y la conexión funcionan:

```bash
py firms_guanacaste_basico.py
```

Si todo está bien, se genera `focos_guanacaste.csv` con los registros del mes de prueba.

### Paso 2 — descarga del histórico completo (versión paralela)

Una vez validado el paso anterior, edita en `firms_guanacaste_paralelo.py` las fechas `fecha_inicio` y `fecha_fin` dentro de `main()` según el rango deseado, y corre:

```bash
py firms_guanacaste_paralelo.py
```

Esto genera `focos_guanacaste_2023.csv` (o el nombre de salida configurado) y reporta el tiempo total de descarga, útil para el análisis de rendimiento del proyecto (comparación secuencial vs. paralelo, número de hilos, etc.).

## 6. Parámetros configurables

| Variable (en el script) | Descripción | Valor por defecto |
|---|---|---|
| `GUANACASTE_BBOX` | Bounding box `west,south,east,north` | `-86.0,9.9,-84.6,11.3` (aproximado) |
| `SOURCE` | Fuente de datos: `MODIS_SP` (calidad científica, con 2-3 meses de rezago) o `MODIS_NRT` (últimos ~2 meses) | `MODIS_SP` |
| `MAX_WORKERS` | Número de hilos concurrentes (solo en la versión paralela) | `8` |
| `MAX_RETRIES` | Reintentos ante errores de red transitorios | `3` |

> El bounding box actual es un rectángulo aproximado de Guanacaste. Para un recorte más preciso al polígono provincial real, se recomienda agregar un paso posterior de filtrado espacial con `geopandas`/`shapely` sobre el CSV resultante.

## 7. Límites de la API

- Máximo **5 días por solicitud** (`DAY_RANGE`), por lo que los rangos largos se trocean automáticamente en ventanas de 5 días.
- Máximo **5000 transacciones cada 10 minutos** por MAP_KEY.
- Documentación oficial: [https://firms.modaps.eosdis.nasa.gov/api/area/](https://firms.modaps.eosdis.nasa.gov/api/area/)

## 8. Reproducibilidad

```bash
git clone <url-del-repositorio>
cd Codigo_Base
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate # macOS / Linux
pip install -r requirements.txt
$env:FIRMS_MAP_KEY = "tu_map_key_aqui"   # PowerShell
py firms_guanacaste_basico.py
```

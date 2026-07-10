# Predicción de Incendios Forestales en Centroamérica

Proyecto que extrae datos satelitales de Google Earth Engine (GEE), los limpia y utiliza para entrenar un modelo de Random Forest (CPU vs GPU) que predice la probabilidad de incendios en la región centroamericana.

## Contenido del repositorio

| Archivo | Descripción |
|---|---|
| `gee_extraccion_centroamerica.py` | Extrae datos mensuales (2002–2025) de incendios (FIRMS), vegetación (NDVI/MODIS), clima (ERA5), elevación/pendiente (SRTM) y cobertura de suelo (ESA WorldCover) para toda Centroamérica, dividiendo el área en celdas de 2°x2° para maximizar la cantidad de puntos por mes. |
| `Limpiar_Dataset.ipynb` | Limpieza del dataset extraído, entrenamiento de un modelo Random Forest acelerado por GPU (RAPIDS/cuML) frente a su versión en CPU (scikit-learn), manejo de desbalanceo de clases (oversampling), benchmark de tiempos CPU vs GPU, y visualización de un mapa de calor de riesgo de incendio con Folium. |

> **Nota:** los datasets (`dataset_gee_centroamerica_completo.csv`, `dataset_limpio.csv`) **no se incluyen en este repositorio** por su tamaño (300+ MB cada uno, superan el límite de GitHub). Debes generarlos localmente ejecutando el script de extracción, o solicitarlos por un medio externo (Drive, S3, etc.).

## Requisitos

Instala las dependencias con:

```bash
pip install -r requirements.txt
```

### Nota sobre librerías GPU (RAPIDS)

El notebook `Limpiar_Dataset.ipynb` usa **cuML**, **cuDF** y **CuPy** (ecosistema [RAPIDS](https://rapids.ai)) para acelerar el entrenamiento del Random Forest en GPU. Estas librerías **no se instalan solo con `pip install`** en la mayoría de entornos: requieren una GPU NVIDIA compatible (CUDA) y, normalmente, un entorno conda con el canal de RAPIDS. Sigue la [guía oficial de instalación de RAPIDS](https://docs.rapids.ai/install/) según tu versión de CUDA.

Si vas a ejecutar el notebook en un entorno **sin GPU**, puedes omitir las secciones que usan `cudf`/`cuml`/`cupy` y adaptar el código para trabajar solo con pandas y `scikit-learn.ensemble.RandomForestClassifier`.

## Configuración de Google Earth Engine

El script de extracción requiere autenticación previa con GEE:

```bash
earthengine authenticate
```

y un proyecto de Google Cloud habilitado para Earth Engine. Reemplaza el ID de proyecto en la línea:

```python
ee.Initialize(project='tribal-isotope-501923-f9')
```

por el de tu propio proyecto de GCP.

## Uso

1. Extraer los datos crudos desde GEE (genera archivos parciales y un checkpoint para poder reanudar si se corta):
   ```bash
   python gee_extraccion_centroamerica.py
   ```
   El resultado se guarda en `data_gee/dataset_gee_centroamerica_completo.csv`.

2. Abrir y ejecutar `Limpiar_Dataset.ipynb` para limpiar el dataset, entrenar el modelo y generar el mapa de calor de riesgo de incendio.

## Estructura esperada de datos (no versionada)

```
data_gee/
├── checkpoint.txt          # meses ya procesados (se autogenera)
├── parcial_XXX.csv         # archivos temporales (se autogenera)
└── dataset_gee_centroamerica_completo.csv   # resultado final (pesado, no subir a git)
```

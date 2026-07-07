import os
import requests

API_KEY = os.environ.get("OT_API_KEY")
if not API_KEY:
    raise RuntimeError("Falta OT_API_KEY. Corre: export OT_API_KEY='tu_key'")

# Centroamerica (Sur, Norte, Oeste, Este)
WEST, SOUTH, EAST, NORTH = -92.5, 6.0, -77.0, 18.5
DEMTYPE = "SRTMGL3"          # 30 m. Si da error por tamano, cambia a "SRTMGL3" (90 m)
OUT_PATH = "dem_centroamerica.tif"
BASE_URL = "https://portal.opentopography.org/API/globaldem"

params = {
    "demtype": DEMTYPE, "south": SOUTH, "north": NORTH,
    "west": WEST, "east": EAST, "outputFormat": "GTiff", "API_Key": API_KEY,
}
print(f"Descargando DEM {DEMTYPE} de Centroamerica...")
resp = requests.get(BASE_URL, params=params, timeout=600)
resp.raise_for_status()
with open(OUT_PATH, "wb") as f:
    f.write(resp.content)
print(f"Listo: {OUT_PATH} ({len(resp.content)/1e6:.1f} MB)")

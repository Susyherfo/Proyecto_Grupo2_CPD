"""
benchmark_procesamiento.py
Compara el PROCESAMIENTO del dataset construido:
  - Secuencial: pandas (1 core)
  - Distribuido: Dask con 1, 2, 4, 8 procesos
Mide tiempo y speedup, y genera una grafica.
Requisitos: pip install pandas "dask[dataframe]" distributed matplotlib
"""
import time
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ARCHIVO = "dataset_modelo_worldcover.csv"
WORKERS = [1, 2, 4, 8]

def procesar_pandas():
    df = pd.read_csv(ARCHIVO)
    df["temp_c"] = df["t2m"] - 273.15
    df["viento"] = np.sqrt(df["u10"]**2 + df["v10"]**2)
    df["riesgo"] = (df["temp_c"].clip(lower=0) * df["viento"]) / \
                   (1 + df["tp"]*1000) * np.exp(-df["ndvi_media"])
    return df.groupby("worldcover_clase").agg(
        {"riesgo": "mean", "temp_c": "mean", "viento": "mean",
         "flag": ["size", "mean"]})

def procesar_dask(nw):
    import dask.dataframe as dd
    df = dd.read_csv(ARCHIVO, assume_missing=True)
    df["temp_c"] = df["t2m"] - 273.15
    df["viento"] = (df["u10"]**2 + df["v10"]**2) ** 0.5
    df["riesgo"] = (df["temp_c"].clip(lower=0) * df["viento"]) / \
                   (1 + df["tp"]*1000) * np.exp(-df["ndvi_media"])
    return df.groupby("worldcover_clase").agg(
        {"riesgo": "mean", "temp_c": "mean", "viento": "mean",
         "flag": ["size", "mean"]}
    ).compute(scheduler="processes", num_workers=nw)

def main():
    print(f"Procesando {ARCHIVO}\n")
    t0 = time.perf_counter(); procesar_pandas(); t_seq = time.perf_counter() - t0
    print(f"Secuencial (pandas, 1 core):        {t_seq:6.2f} s")
    res = [{"modo": "pandas", "workers": 1, "tiempo": t_seq}]
    for w in WORKERS:
        t0 = time.perf_counter(); procesar_dask(w); t = time.perf_counter() - t0
        print(f"Distribuido (Dask, {w} procesos):     {t:6.2f} s")
        res.append({"modo": f"dask-{w}", "workers": w, "tiempo": t})
    for r in res:
        r["speedup"] = t_seq / r["tiempo"]

    print("\n" + "=" * 46)
    print(f"{'Modo':>14} | {'Tiempo(s)':>10} | {'Speedup':>8}")
    print("-" * 46)
    for r in res:
        print(f"{r['modo']:>14} | {r['tiempo']:>10.2f} | {r['speedup']:>7.2f}x")
    print("=" * 46)

    dask_res = [r for r in res if r["modo"].startswith("dask")]
    w = [r["workers"] for r in dask_res]; t = [r["tiempo"] for r in dask_res]
    sp = [t[0] / x for x in t]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 5))
    a1.axhline(t_seq, color="green", ls="--", label=f"pandas secuencial ({t_seq:.1f}s)")
    a1.plot(w, t, "-o", color="#1f6feb", label="Dask distribuido")
    a1.set_xlabel("Procesos (workers)"); a1.set_ylabel("Tiempo (s)")
    a1.set_title("Tiempo de procesamiento"); a1.set_xticks(w)
    a1.legend(); a1.grid(alpha=.3); a1.set_ylim(bottom=0)
    a2.plot(w, sp, "-o", color="#fb8500")
    a2.set_xlabel("Procesos (workers)"); a2.set_ylabel("Speedup (vs 1 proceso)")
    a2.set_title("Escalabilidad de Dask"); a2.set_xticks(w); a2.grid(alpha=.3)
    fig.suptitle("Benchmark de procesamiento: pandas vs Dask", fontweight="bold")
    fig.tight_layout(); fig.savefig("benchmark_procesamiento.png", dpi=150)
    print("\nGrafica -> benchmark_procesamiento.png")

if __name__ == "__main__":
    main()

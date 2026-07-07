"""
benchmark_comparativo.py
Compara el PROCESAMIENTO del dataset con las tres herramientas del curso:
  - pandas  : secuencial (1 core), linea base
  - Dask    : distribuido, con 1, 2, 4, 8 procesos
  - Polars  : multi-hilo, con 1, 2, 4, 8 hilos
Mide tiempos y speedup, y genera una grafica comparativa.
Requisitos: pip install pandas numpy "dask[dataframe]" distributed polars matplotlib
"""
import sys, os, time, subprocess

ARCHIVO = "dataset_modelo_worldcover.csv"
NIVELES = [1, 2, 4, 8]

def tarea_pandas():
    import pandas as pd, numpy as np
    df = pd.read_csv(ARCHIVO)
    df["temp_c"] = df["t2m"] - 273.15
    df["viento"] = np.sqrt(df["u10"]**2 + df["v10"]**2)
    df["riesgo"] = df["temp_c"] * df["viento"] / (1 + df["tp"]*1000) * np.exp(-df["ndvi_media"])
    return df.groupby("worldcover_clase").agg(
        r=("riesgo", "mean"), n=("flag", "size"), t=("flag", "mean"))

def tarea_dask(n):
    import dask.dataframe as dd, numpy as np
    df = dd.read_csv(ARCHIVO, assume_missing=True)
    df["temp_c"] = df["t2m"] - 273.15
    df["viento"] = (df["u10"]**2 + df["v10"]**2) ** 0.5
    df["riesgo"] = df["temp_c"] * df["viento"] / (1 + df["tp"]*1000) * np.exp(-df["ndvi_media"])
    return df.groupby("worldcover_clase").agg(
        {"riesgo": "mean", "flag": ["size", "mean"]}
    ).compute(scheduler="processes", num_workers=n)

def tarea_polars():
    import polars as pl
    df = pl.read_csv(ARCHIVO)
    df = df.with_columns([
        (pl.col("t2m") - 273.15).alias("temp_c"),
        ((pl.col("u10")**2 + pl.col("v10")**2) ** 0.5).alias("viento")])
    df = df.with_columns(
        (pl.col("temp_c") * pl.col("viento") / (1 + pl.col("tp")*1000)
         * (-pl.col("ndvi_media")).exp()).alias("riesgo"))
    return df.group_by("worldcover_clase").agg([
        pl.col("riesgo").mean().alias("r"),
        pl.col("flag").count().alias("n"),
        pl.col("flag").mean().alias("t")])

def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    print(f"Procesando {ARCHIVO}\n")
    t0 = time.perf_counter(); tarea_pandas(); t_pd = time.perf_counter() - t0
    print(f"pandas (secuencial): {t_pd:6.3f} s")

    t_dask = []
    for n in NIVELES:
        t0 = time.perf_counter(); tarea_dask(n); t = time.perf_counter() - t0
        t_dask.append(t)
        print(f"Dask   {n} procesos: {t:6.3f} s")

    t_pol = []
    for n in NIVELES:
        env = dict(os.environ, POLARS_MAX_THREADS=str(n))
        out = subprocess.run([sys.executable, __file__, str(n)],
                             env=env, capture_output=True, text=True)
        L = [l for l in out.stdout.splitlines() if l.startswith("TIME")]
        if not L:
            print("ERROR:", out.stderr[-300:]); return
        t = float(L[0].split()[1]); t_pol.append(t)
        print(f"Polars {n} hilos:    {t:6.3f} s")

    # Tabla
    print("\n" + "=" * 56)
    print(f"{'Nivel':>6} | {'Dask (s)':>10} {'x':>6} | {'Polars (s)':>11} {'x':>6}")
    print(f"{'pandas':>6} | {t_pd:>10.3f} {'1.0x':>6} | {'':>11} {'':>6}")
    print("-" * 56)
    for i, n in enumerate(NIVELES):
        print(f"{n:>6} | {t_dask[i]:>10.3f} {t_pd/t_dask[i]:>5.1f}x | "
              f"{t_pol[i]:>11.3f} {t_pd/t_pol[i]:>5.1f}x")
    print("=" * 56)
    print("(x = cuantas veces mas rapido que pandas)")

    # Grafica
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(14, 5))
    a1.axhline(t_pd, color="green", ls="--", label=f"pandas ({t_pd:.2f}s)")
    a1.plot(NIVELES, t_dask, "-o", color="#8250df", label="Dask (distribuido)")
    a1.plot(NIVELES, t_pol, "-o", color="#1f6feb", label="Polars (multi-hilo)")
    a1.set_xlabel("Procesos / hilos"); a1.set_ylabel("Tiempo (s)")
    a1.set_title("Tiempo de procesamiento"); a1.set_xticks(NIVELES)
    a1.legend(); a1.grid(alpha=.3); a1.set_ylim(bottom=0)
    a2.plot(NIVELES, [t_pd/x for x in t_dask], "-o", color="#8250df", label="Dask")
    a2.plot(NIVELES, [t_pd/x for x in t_pol], "-o", color="#1f6feb", label="Polars")
    a2.axhline(1, color="green", ls="--", label="pandas (1x)")
    a2.set_xlabel("Procesos / hilos"); a2.set_ylabel("Speedup vs pandas")
    a2.set_title("Speedup vs pandas"); a2.set_xticks(NIVELES)
    a2.legend(); a2.grid(alpha=.3)
    fig.suptitle("Benchmark de procesamiento: pandas vs Dask vs Polars", fontweight="bold")
    fig.tight_layout(); fig.savefig("benchmark_comparativo.png", dpi=150)
    print("\nGrafica -> benchmark_comparativo.png")

if __name__ == "__main__":
    if len(sys.argv) > 1:            # modo worker (Polars con N hilos)
        t0 = time.perf_counter(); tarea_polars()
        print(f"TIME {time.perf_counter()-t0:.4f}")
    else:
        main()

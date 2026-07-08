"""
benchmark_polars.py
Compara el PROCESAMIENTO del dataset:
  - Secuencial: pandas (1 core)
  - Paralelo:   Polars con 1, 2, 4, 8 hilos
Polars fija el numero de hilos al importar, asi que cada medicion se corre
en un subproceso con POLARS_MAX_THREADS distinto.
Mide tiempo y speedup, y genera una grafica.
Requisitos: pip install pandas polars matplotlib
"""
import sys, os, time, subprocess

ARCHIVO = "dataset_modelo_worldcover.csv"
HILOS = [1, 2, 4, 8]

def tarea_polars():
    import polars as pl
    df = pl.read_csv(ARCHIVO)
    df = df.with_columns([
        (pl.col("t2m") - 273.15).alias("temp_c"),
        ((pl.col("u10")**2 + pl.col("v10")**2) ** 0.5).alias("viento"),
    ])
    df = df.with_columns(
        (pl.col("temp_c") * pl.col("viento") / (1 + pl.col("tp")*1000)
         * (-pl.col("ndvi_media")).exp()).alias("riesgo"))
    return df.group_by("worldcover_clase").agg([
        pl.col("riesgo").mean().alias("riesgo_medio"),
        pl.col("temp_c").mean().alias("temp_media"),
        pl.col("viento").mean().alias("viento_medio"),
        pl.col("flag").count().alias("n"),
        pl.col("flag").mean().alias("tasa_fuego"),
    ])

def tarea_pandas():
    import pandas as pd, numpy as np
    df = pd.read_csv(ARCHIVO)
    df["temp_c"] = df["t2m"] - 273.15
    df["viento"] = np.sqrt(df["u10"]**2 + df["v10"]**2)
    df["riesgo"] = df["temp_c"] * df["viento"] / (1 + df["tp"]*1000) * np.exp(-df["ndvi_media"])
    return df.groupby("worldcover_clase").agg(
        riesgo=("riesgo", "mean"), temp=("temp_c", "mean"),
        n=("flag", "size"), tasa=("flag", "mean"))

def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    print(f"Procesando {ARCHIVO}\n")
    t0 = time.perf_counter(); tarea_pandas(); t_pd = time.perf_counter() - t0
    print(f"Secuencial (pandas):      {t_pd:6.3f} s")

    tiempos = []
    for n in HILOS:
        env = dict(os.environ, POLARS_MAX_THREADS=str(n))
        out = subprocess.run([sys.executable, __file__, str(n)],
                             env=env, capture_output=True, text=True)
        linea = [l for l in out.stdout.splitlines() if l.startswith("TIME")]
        if not linea:
            print("ERROR:", out.stderr[-300:]); return
        t = float(linea[0].split()[1])
        tiempos.append(t)
        print(f"Polars ({n} hilos):         {t:6.3f} s   "
              f"({t_pd/t:.1f}x mas rapido que pandas)")

    # Tabla
    print("\n" + "=" * 50)
    print(f"{'Modo':>16} | {'Tiempo(s)':>10} | {'vs pandas':>10}")
    print("-" * 50)
    print(f"{'pandas':>16} | {t_pd:>10.3f} | {'1.0x':>10}")
    for n, t in zip(HILOS, tiempos):
        print(f"{'polars '+str(n)+'h':>16} | {t:>10.3f} | {t_pd/t:>9.1f}x")
    print("=" * 50)

    # Grafica
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 5))
    a1.axhline(t_pd, color="green", ls="--", label=f"pandas ({t_pd:.2f}s)")
    a1.plot(HILOS, tiempos, "-o", color="#1f6feb", label="Polars")
    a1.set_xlabel("Hilos"); a1.set_ylabel("Tiempo (s)")
    a1.set_title("Tiempo de procesamiento"); a1.set_xticks(HILOS)
    a1.legend(); a1.grid(alpha=.3); a1.set_ylim(bottom=0)
    sp = [tiempos[0] / t for t in tiempos]
    a2.plot(HILOS, sp, "-o", color="#fb8500", label="Speedup real")
    a2.plot(HILOS, HILOS, "--", color="gray", label="Ideal")
    a2.set_xlabel("Hilos"); a2.set_ylabel("Speedup (vs 1 hilo)")
    a2.set_title("Escalabilidad de Polars"); a2.set_xticks(HILOS)
    a2.legend(); a2.grid(alpha=.3)
    fig.suptitle("Benchmark de procesamiento: pandas vs Polars", fontweight="bold")
    fig.tight_layout(); fig.savefig("benchmark_polars.png", dpi=150)
    print("\nGrafica -> benchmark_polars.png")

if __name__ == "__main__":
    if len(sys.argv) > 1:            # modo worker (mide Polars con N hilos)
        t0 = time.perf_counter(); tarea_polars()
        print(f"TIME {time.perf_counter()-t0:.4f}")
    else:
        main()

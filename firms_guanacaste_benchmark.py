"""
firms_guanacaste_benchmark.py
Mide el tiempo de descarga del MISMO rango de fechas variando el numero
de hilos y genera una tabla y una grafica de speedup. Se detiene solo
cuando agregar mas hilos ya casi no mejora (rendimientos decrecientes).
"""
import csv
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

import pandas as pd
import matplotlib.pyplot as plt

# Reutilizamos las piezas ya probadas del script paralelo.
from firms_guanacaste_paralelo import fetch_window, generar_ventanas


# ---------------------------------------------------------------------
# Configuracion del experimento
# ---------------------------------------------------------------------
FECHA_INICIO = date(2023, 1, 1)
FECHA_FIN = date(2023, 12, 31)        # año completo (1 ene - 31 dic 2023)
LISTA_HILOS = [1, 2, 4, 8]        # configuraciones de hilos a comparar
REPETICIONES = 1                       
UMBRAL_MEJORA = 0.10                   # si mejora < 10%, se detiene

def descargar_con_hilos(ventanas, n_workers):
    """
    Descarga todas las ventanas usando un pool de `n_workers` hilos y
    retorna el DataFrame combinado.
    """
    frames = []
    with ThreadPoolExecutor(max_workers=n_workers) as executor:
        futuros = [executor.submit(fetch_window, v) for v in ventanas]
        for futuro in as_completed(futuros):
            df = futuro.result()
            if not df.empty:
                frames.append(df)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True).drop_duplicates()


def correr_benchmark():
    ventanas = generar_ventanas(FECHA_INICIO, FECHA_FIN)
    print(f"Rango: {FECHA_INICIO} a {FECHA_FIN}  ->  {len(ventanas)} ventanas")
    print(f"Configuraciones de hilos a probar: {LISTA_HILOS}")
    print(f"Repeticiones por configuracion: {REPETICIONES}\n")

    resultados = []
    tiempo_anterior = None
    for n in LISTA_HILOS:
        # No tiene sentido usar mas hilos que ventanas por descargar.
        if n > len(ventanas):
            print(f"  (se omite {n} hilos: solo hay {len(ventanas)} ventanas)")
            break

        tiempos = []
        registros = 0
        for r in range(REPETICIONES):
            t0 = time.perf_counter()
            df = descargar_con_hilos(ventanas, n)
            t1 = time.perf_counter()
            tiempos.append(t1 - t0)
            registros = len(df)
        tiempo_prom = sum(tiempos) / len(tiempos)
        resultados.append({"hilos": n, "tiempo_s": tiempo_prom, "registros": registros})
        print(f"  {n:>2} hilo(s): {tiempo_prom:7.2f} s   ({registros} registros)")

        # Parada automatica: si mejorar respecto al anterior fue pequeno, detener.
        if tiempo_anterior is not None:
            mejora = (tiempo_anterior - tiempo_prom) / tiempo_anterior
            if mejora < UMBRAL_MEJORA:
                print(f"  -> Mejora de solo {mejora*100:.1f}% al pasar a {n} hilos; "
                      f"se detiene (rendimientos decrecientes).")
                break
        tiempo_anterior = tiempo_prom

    # Speedup y eficiencia relativos al caso de 1 hilo (linea base).
    tiempo_base = resultados[0]["tiempo_s"]
    for r in resultados:
        r["speedup"] = tiempo_base / r["tiempo_s"]
        r["eficiencia"] = r["speedup"] / r["hilos"]

    return resultados


def guardar_csv(resultados, ruta="benchmark_resultados.csv"):
    with open(ruta, "w", newline="") as f:
        campos = ["hilos", "tiempo_s", "registros", "speedup", "eficiencia"]
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()
        for r in resultados:
            writer.writerow({
                "hilos": r["hilos"],
                "tiempo_s": round(r["tiempo_s"], 3),
                "registros": r["registros"],
                "speedup": round(r["speedup"], 2),
                "eficiencia": round(r["eficiencia"], 3),
            })
    print(f"\nTabla guardada en {ruta}")


def graficar(resultados, ruta="benchmark_speedup.png"):
    hilos = [r["hilos"] for r in resultados]
    tiempos = [r["tiempo_s"] for r in resultados]
    speedups = [r["speedup"] for r in resultados]

    azul = "#1f6feb"
    naranja = "#fb8500"
    gris = "#9aa0a6"

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle(
        "Benchmark de extraccion FIRMS — Guanacaste 2023 (secuencial vs paralelo)",
        fontsize=13, fontweight="bold",
    )

    # Panel 1: tiempo vs hilos
    ax1.plot(hilos, tiempos, "-o", color=azul, linewidth=2, markersize=7)
    for x, y in zip(hilos, tiempos):
        ax1.annotate(f"{y:.1f}s", (x, y), textcoords="offset points",
                     xytext=(0, 9), ha="center", fontsize=9, color=azul)
    ax1.set_title("Tiempo total de descarga", fontsize=11)
    ax1.set_xlabel("Numero de hilos")
    ax1.set_ylabel("Tiempo (segundos)")
    ax1.set_xticks(hilos)
    ax1.grid(True, linestyle="--", alpha=0.4)
    ax1.set_ylim(bottom=0)

    # Panel 2: speedup real vs ideal
    ax2.plot(hilos, speedups, "-o", color=naranja, linewidth=2,
             markersize=7, label="Speedup real")
    ax2.plot(hilos, hilos, "--", color=gris, linewidth=1.5,
             label="Speedup ideal (lineal)")
    for x, y in zip(hilos, speedups):
        ax2.annotate(f"{y:.1f}x", (x, y), textcoords="offset points",
                     xytext=(0, 9), ha="center", fontsize=9, color=naranja)
    ax2.set_title("Speedup vs numero de hilos", fontsize=11)
    ax2.set_xlabel("Numero de hilos")
    ax2.set_ylabel("Speedup (veces mas rapido)")
    ax2.set_xticks(hilos)
    ax2.grid(True, linestyle="--", alpha=0.4)
    ax2.legend(frameon=False)

    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(ruta, dpi=150)
    print(f"Grafica guardada en {ruta}")


def main():
    resultados = correr_benchmark()

    print("\n" + "=" * 52)
    print(f"{'Hilos':>6} | {'Tiempo (s)':>11} | {'Speedup':>8} | {'Eficiencia':>10}")
    print("-" * 52)
    for r in resultados:
        print(f"{r['hilos']:>6} | {r['tiempo_s']:>11.2f} | "
              f"{r['speedup']:>7.2f}x | {r['eficiencia']:>9.2f}")
    print("=" * 52)

    guardar_csv(resultados)
    graficar(resultados)
    print("\nListo. Revisa benchmark_speedup.png para la grafica.")


if __name__ == "__main__":
    main()
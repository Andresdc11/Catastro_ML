# -*- coding: utf-8 -*-
"""Orquestador del proyecto Catastro_ML.

    python run_pipeline.py              # pipeline completo (~5 min)
    python run_pipeline.py --rapido     # prueba con 200k construcciones
    python run_pipeline.py --desde 3    # reanudar desde el EDA
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"

ETAPAS = [
    (1, "Ingesta del GeoJSON", "ingest.py"),
    (2, "Target IVS y variables de ubicacion", "features.py"),
    (3, "Analisis exploratorio", "eda.py"),
    (4, "Modelado supervisado", "models.py"),
    (5, "Informe final", "report.py"),
]


def correr(script, extra=()):
    cmd = [sys.executable, str(SRC / script), *extra]
    r = subprocess.run(cmd, cwd=str(ROOT))
    if r.returncode != 0:
        raise SystemExit("La etapa %s fallo (codigo %d)" % (script, r.returncode))


def main():
    ap = argparse.ArgumentParser(description="Pipeline completo Catastro_ML")
    ap.add_argument("--rapido", action="store_true",
                    help="ingesta limitada a 200.000 construcciones")
    ap.add_argument("--desde", type=int, default=1, choices=[1, 2, 3, 4, 5],
                    help="etapa inicial (por defecto 1)")
    ap.add_argument("--hasta", type=int, default=5, choices=[1, 2, 3, 4, 5])
    args = ap.parse_args()

    t0 = time.time()
    for num, titulo, script in ETAPAS:
        if not (args.desde <= num <= args.hasta):
            continue
        print("\n" + "=" * 72)
        print("  ETAPA %d - %s" % (num, titulo))
        print("=" * 72)
        extra = ["--max-lineas", "200000"] if (num == 1 and args.rapido) else []
        correr(script, extra)

    print("\n" + "=" * 72)
    print("  Pipeline completo en %.1f minutos" % ((time.time() - t0) / 60))
    print("  Informe   -> reports/informe.html")
    print("  Figuras   -> outputs/figuras/")
    print("  Tablas    -> outputs/tablas/")
    print("  Modelos   -> outputs/modelos/")
    print("=" * 72)


if __name__ == "__main__":
    main()

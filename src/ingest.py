# -*- coding: utf-8 -*-
"""01 - Ingesta en streaming del GeoJSON de construcciones.

El archivo pesa ~1.8 GB (2.4 M de features) y no cabe en memoria, por lo que se
recorre linea a linea (formato ogr2ogr: una feature por linea) acumulando:

  1. Una muestra aleatoria reproducible a nivel de construccion (EDA fino).
  2. La agregacion COMPLETA por manzana catastral -> universo de modelado.
  3. La agregacion COMPLETA por sector catastral.
  4. Estadisticas de calidad de datos.

Estructura del codigo catastral de Bogota (LOTECODIGO, 12 digitos):
    SSSSSS  MMM  LLL   ->  sector | manzana | lote/predio
CONCODIGO = LOTECODIGO + 13 digitos de unidad (edificio/torre/piso/unidad).
"""
import argparse
import csv
import gzip
import json
import os
import random
import sys
import time
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config as C
from geo_utils import factores_metricos, metricas_geometria

# indices del acumulador por manzana
(N_CONST, S_AREA, S_AREA_PISOS, S_PERIM, S_PISOS, MAX_PISOS, N_GE3, N_SUB,
 N_VOLAD, N_MEJORA, MIN_LON, MAX_LON, MIN_LAT, MAX_LAT, W_LON, W_LAT,
 S_ALTURA, N_ALT_POS, S_PISOS_AREA, N_ELEV_DIF) = range(20)
LOTES = 20
N_SLOTS = 21

COLS_MUESTRA = [
    "lote", "manzana", "sector", "n_pisos", "semisotanos", "sotanos",
    "mejora", "voladizo", "altura", "elevacion", "area_m2", "perimetro_m",
    "compacidad", "lon", "lat",
]

COLS_MANZANA = [
    "manzana", "sector", "n_construcciones", "n_lotes", "area_huella_m2",
    "area_construida_m2", "perimetro_total_m", "pisos_prom", "pisos_prom_pond",
    "pisos_max", "frac_pisos_ge3", "frac_subterraneo", "frac_voladizo",
    "frac_mejora", "altura_prom", "frac_altura_pos", "frac_elev_distinta",
    "huella_media_m2", "constr_media_por_lote_m2", "bbox_area_m2",
    "bbox_ancho_m", "bbox_alto_m", "lon", "lat",
]


def nuevo_acumulador():
    acc = [0.0] * N_SLOTS
    acc[N_CONST] = 0
    acc[MAX_PISOS] = 0
    acc[MIN_LON] = 999.0
    acc[MAX_LON] = -999.0
    acc[MIN_LAT] = 999.0
    acc[MAX_LAT] = -999.0
    acc[LOTES] = set()
    return acc


def _num(v, default=0.0):
    return default if v is None else v


def ingerir(ruta, max_lineas=None, sample_frac=C.SAMPLE_FRAC, seed=C.SEED):
    """Recorre el GeoJSON y devuelve (acumuladores_por_manzana, estadisticas)."""
    rnd = random.Random(seed)
    manzanas = {}
    stats = {
        "features_leidas": 0,
        "features_validas": 0,
        "geometria_invalida": 0,
        "codigo_invalido": 0,
        "fuera_de_bbox": 0,
        "area_fuera_de_rango": 0,
        "pisos_fuera_de_rango": 0,
        "tipos_geometria": Counter(),
        "nulos_por_campo": Counter(),
        "muestra_filas": 0,
    }
    min_max = {}

    f_muestra = gzip.open(C.F_MUESTRA, "wt", newline="", encoding="utf-8",
                          compresslevel=5)
    w_muestra = csv.writer(f_muestra)
    w_muestra.writerow(COLS_MUESTRA)

    t0 = time.time()
    with open(ruta, "r", encoding="utf-8", buffering=1024 * 1024) as fh:
        for linea in fh:
            if max_lineas and stats["features_leidas"] >= max_lineas:
                break
            if not linea.startswith('{ "type": "Feature"'):
                continue
            stats["features_leidas"] += 1
            n = stats["features_leidas"]
            if n % 250000 == 0:
                print("  ... %8d features  (%.0f s)" % (n, time.time() - t0),
                      flush=True)

            linea = linea.rstrip()
            if linea.endswith(","):
                linea = linea[:-1]
            try:
                feat = json.loads(linea)
            except ValueError:
                stats["geometria_invalida"] += 1
                continue

            props = feat.get("properties") or {}
            geom = feat.get("geometry") or {}
            stats["tipos_geometria"][geom.get("type", "NULO")] += 1

            for k, v in props.items():
                if v is None:
                    stats["nulos_por_campo"][k] += 1

            codigo = props.get("LOTECODIGO") or (props.get("CONCODIGO") or "")[:12]
            if not codigo or len(codigo) < 12 or not codigo.isdigit():
                stats["codigo_invalido"] += 1
                continue

            m = metricas_geometria(geom)
            if m is None:
                stats["geometria_invalida"] += 1
                continue
            area, perim, lon, lat = m

            if not (C.LON_MIN <= lon <= C.LON_MAX and C.LAT_MIN <= lat <= C.LAT_MAX):
                stats["fuera_de_bbox"] += 1
                continue
            if not (C.MIN_AREA_M2 <= area <= C.MAX_AREA_M2):
                stats["area_fuera_de_rango"] += 1
                continue

            pisos = int(_num(props.get("CONNPISOS"), 0))
            if pisos < 1 or pisos > C.MAX_PISOS:
                stats["pisos_fuera_de_rango"] += 1
                pisos = min(max(pisos, 1), C.MAX_PISOS)

            semis = int(_num(props.get("CONTSEMIS"), 0))
            sotanos = int(_num(props.get("CONNSOTANO"), 0))
            mejora = int(_num(props.get("CONMEJORA"), 0))
            voladizo = int(_num(props.get("CONVOLADIZ"), 0))
            altura = float(_num(props.get("CONALTURA"), 0.0))
            elev = int(_num(props.get("CONELEVACI"), 0))

            for k, v in (("area_m2", area), ("perimetro_m", perim),
                         ("n_pisos", pisos), ("altura", altura),
                         ("sotanos", sotanos), ("elevacion", elev)):
                lo, hi = min_max.get(k, (v, v))
                min_max[k] = (min(lo, v), max(hi, v))

            stats["features_validas"] += 1
            sector, manz_id, lote_id = codigo[:6], codigo[:9], codigo[9:12]

            acc = manzanas.get(manz_id)
            if acc is None:
                acc = nuevo_acumulador()
                manzanas[manz_id] = acc

            acc[N_CONST] += 1
            acc[S_AREA] += area
            acc[S_AREA_PISOS] += area * pisos
            acc[S_PERIM] += perim
            acc[S_PISOS] += pisos
            acc[S_PISOS_AREA] += pisos * area
            if pisos > acc[MAX_PISOS]:
                acc[MAX_PISOS] = pisos
            if pisos >= 3:
                acc[N_GE3] += 1
            if sotanos > 0 or semis > 0:
                acc[N_SUB] += 1
            if voladizo > 0:
                acc[N_VOLAD] += 1
            if mejora > 0:
                acc[N_MEJORA] += 1
            if lon < acc[MIN_LON]:
                acc[MIN_LON] = lon
            if lon > acc[MAX_LON]:
                acc[MAX_LON] = lon
            if lat < acc[MIN_LAT]:
                acc[MIN_LAT] = lat
            if lat > acc[MAX_LAT]:
                acc[MAX_LAT] = lat
            acc[W_LON] += lon * area
            acc[W_LAT] += lat * area
            acc[S_ALTURA] += altura
            if altura > 0:
                acc[N_ALT_POS] += 1
            if elev != pisos:
                acc[N_ELEV_DIF] += 1
            acc[LOTES].add(lote_id)

            if rnd.random() < sample_frac:
                compac = (12.566370614 * area / (perim * perim)) if perim > 0 else 0.0
                w_muestra.writerow([
                    codigo[:12], manz_id, sector, pisos, semis, sotanos, mejora,
                    voladizo, round(altura, 2), elev, round(area, 2),
                    round(perim, 2), round(compac, 4), round(lon, 7), round(lat, 7),
                ])
                stats["muestra_filas"] += 1

    f_muestra.close()
    stats["segundos"] = round(time.time() - t0, 1)
    stats["tipos_geometria"] = dict(stats["tipos_geometria"])
    stats["nulos_por_campo"] = dict(stats["nulos_por_campo"])
    stats["rangos"] = {k: [round(v[0], 4), round(v[1], 4)] for k, v in min_max.items()}
    return manzanas, stats


def escribir_manzanas(manzanas):
    """Vuelca los acumuladores a CSV a nivel de manzana catastral."""
    filas = 0
    with gzip.open(C.F_MANZANAS, "wt", newline="", encoding="utf-8",
                   compresslevel=5) as fh:
        w = csv.writer(fh)
        w.writerow(COLS_MANZANA)
        for manz, a in manzanas.items():
            n = a[N_CONST]
            if n == 0 or a[S_AREA] <= 0:
                continue
            lon = a[W_LON] / a[S_AREA]
            lat = a[W_LAT] / a[S_AREA]
            kx, ky = factores_metricos(lat)
            ancho = max((a[MAX_LON] - a[MIN_LON]) * kx, 1.0)
            alto = max((a[MAX_LAT] - a[MIN_LAT]) * ky, 1.0)
            n_lotes = max(len(a[LOTES]), 1)
            w.writerow([
                manz, manz[:6], n, n_lotes,
                round(a[S_AREA], 2), round(a[S_AREA_PISOS], 2), round(a[S_PERIM], 2),
                round(a[S_PISOS] / n, 4), round(a[S_PISOS_AREA] / a[S_AREA], 4),
                int(a[MAX_PISOS]), round(a[N_GE3] / n, 4), round(a[N_SUB] / n, 4),
                round(a[N_VOLAD] / n, 4), round(a[N_MEJORA] / n, 4),
                round(a[S_ALTURA] / n, 4), round(a[N_ALT_POS] / n, 4),
                round(a[N_ELEV_DIF] / n, 4),
                round(a[S_AREA] / n, 2), round(a[S_AREA_PISOS] / n_lotes, 2),
                round(ancho * alto, 2), round(ancho, 2), round(alto, 2),
                round(lon, 7), round(lat, 7),
            ])
            filas += 1
    return filas


def escribir_sectores():
    """Agrega el nivel manzana a nivel de sector catastral."""
    import pandas as pd
    import numpy as np

    df = pd.read_csv(C.F_MANZANAS, dtype={"manzana": str, "sector": str})

    # promedios ponderados por area de huella, vectorizados
    w = df["area_huella_m2"]
    for col in ("pisos_prom_pond", "lon", "lat"):
        df["_w_" + col] = df[col] * w

    g = df.groupby("sector")
    suma_w = g["area_huella_m2"].sum()
    sec = pd.DataFrame({
        "n_manzanas": g.size(),
        "n_construcciones": g["n_construcciones"].sum(),
        "n_lotes": g["n_lotes"].sum(),
        "area_huella_m2": suma_w,
        "area_construida_m2": g["area_construida_m2"].sum(),
        "pisos_prom_pond": g["_w_pisos_prom_pond"].sum() / suma_w,
        "pisos_max": g["pisos_max"].max(),
        "frac_pisos_ge3": g["frac_pisos_ge3"].mean(),
        "frac_subterraneo": g["frac_subterraneo"].mean(),
        "lon": g["_w_lon"].sum() / suma_w,
        "lat": g["_w_lat"].sum() / suma_w,
    }).reset_index()
    sec = sec.replace([np.inf, -np.inf], np.nan)
    sec.to_csv(C.F_SECTORES, index=False)
    return len(sec)


def main():
    ap = argparse.ArgumentParser(
        description="Ingesta streaming del GeoJSON de construcciones")
    ap.add_argument("--max-lineas", type=int, default=None,
                    help="limitar features procesadas (pruebas rapidas)")
    ap.add_argument("--sample-frac", type=float, default=C.SAMPLE_FRAC)
    args = ap.parse_args()

    print("[01] Ingesta de %s" % C.GEOJSON.name)
    print("     tamano: %.2f GB" % (C.GEOJSON.stat().st_size / 1e9))
    manzanas, stats = ingerir(C.GEOJSON, args.max_lineas, args.sample_frac)

    stats["lotes_distintos"] = sum(len(a[LOTES]) for a in manzanas.values())
    n_manz = escribir_manzanas(manzanas)
    stats["manzanas"] = n_manz
    stats["sectores"] = escribir_sectores()

    with open(C.F_STATS, "w", encoding="utf-8") as fh:
        json.dump(stats, fh, indent=2, ensure_ascii=False)

    print("\n[01] Resultado")
    print("     features leidas   : %d" % stats["features_leidas"])
    print("     features validas  : %d" % stats["features_validas"])
    print("     manzanas          : %d" % n_manz)
    print("     sectores          : %d" % stats["sectores"])
    print("     lotes distintos   : %d" % stats["lotes_distintos"])
    print("     muestra guardada  : %d filas" % stats["muestra_filas"])
    print("     tiempo            : %.1f s" % stats["segundos"])
    print("     descartes -> geom %d | codigo %d | bbox %d | area %d" % (
        stats["geometria_invalida"], stats["codigo_invalido"],
        stats["fuera_de_bbox"], stats["area_fuera_de_rango"]))


if __name__ == "__main__":
    main()

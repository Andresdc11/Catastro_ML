# -*- coding: utf-8 -*-
"""02 - Construccion del target de valoracion y de las variables de ubicacion.

ADVERTENCIA METODOLOGICA
------------------------
El GeoJSON de construcciones NO contiene avaluo catastral ni ningun campo
monetario (sus atributos son: pisos, sotanos, semisotanos, altura, elevacion,
mejora, voladizo y geometria). Por lo tanto no es posible modelar el precio
observado del suelo. Lo que se construye aqui es un PROXY explicito:

    IVS - Indice de Valor del Suelo (por manzana catastral)

Se apoya en la teoria de la renta del suelo (bid-rent, Alonso 1964): alli donde
el suelo es caro, el mercado responde intensificando su uso -> mas metros
construidos por metro de suelo, mas altura, mas subterraneo. El IVS resume esa
INTENSIDAD EDIFICATORIA mediante la primera componente principal de cinco
variables morfologicas.

Separacion limpia target / predictores:
    - El IVS se calcula SOLO con morfologia construida.
    - Los predictores son SOLO variables de ubicacion (coordenadas, distancias a
      centralidades, densidad del entorno).
No hay fuga de informacion: el modelo debe inferir la intensidad edificatoria de
una manzana a partir de donde esta, que es exactamente la pregunta pedida
("valoracion del terreno segun su ubicacion").
"""
import os
import sys

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config as C
from geo_utils import M_POR_GRADO_LAT, factores_metricos

R_TIERRA_KM = 6371.0088


def haversine_vec(lon1, lat1, lon2, lat2):
    """Distancia en km entre arrays de puntos y un punto de referencia."""
    p1 = np.radians(lat1)
    p2 = np.radians(lat2)
    dp = p2 - p1
    dl = np.radians(lon2 - lon1)
    h = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * R_TIERRA_KM * np.arctan2(np.sqrt(h), np.sqrt(1 - h))


def cargar_manzanas():
    df = pd.read_csv(C.F_MANZANAS, dtype={"manzana": str, "sector": str})
    n0 = len(df)
    df = df[df["n_construcciones"] >= C.MIN_CONST_POR_MANZANA].copy()
    df = df[(df["bbox_area_m2"] > 0) & (df["area_huella_m2"] > 0)].copy()
    print("     manzanas: %d -> %d tras filtrar (>= %d construcciones)"
          % (n0, len(df), C.MIN_CONST_POR_MANZANA))
    return df.reset_index(drop=True)


def componentes_morfologicos(df):
    """Cinco variables de intensidad edificatoria que alimentan el IVS."""
    ic = df["area_construida_m2"] / df["bbox_area_m2"]
    tope = ic.quantile(0.995)
    df["indice_construccion"] = ic.clip(upper=tope)
    df["log_indice_construccion"] = np.log1p(df["indice_construccion"])
    df["log_huella_media"] = np.log1p(df["huella_media_m2"])
    df["densidad_lotes"] = df["n_lotes"] / (df["bbox_area_m2"] / 10000.0)
    return df


def construir_ivs(df):
    """IVS = indicador compuesto por PCA sobre las 5 variables morfologicas.

    Se retienen las componentes con autovalor > 1 (criterio de Kaiser) y se
    ponderan por su participacion en la varianza explicada, siguiendo el
    procedimiento estandar de indicadores compuestos (OECD/JRC, Handbook on
    Constructing Composite Indicators, cap. 'weighting based on PCA').

    Retener solo PC1 seria un error de medicion en Bogota: PC1 mide intensidad
    edificatoria bruta y confunde el barrio informal autoconstruido (cobertura
    total del lote, 2-3 pisos, sin sotanos, huellas de 30 m2) con el desarrollo
    formal en altura. PC2 es justamente el eje que los separa: carga positivo en
    tamano de huella y sotanos, y negativo en cobertura horizontal.
    """
    X = df[C.COMPONENTES_IVS].astype(float).values
    Xs = StandardScaler().fit_transform(X)

    pca = PCA(n_components=len(C.COMPONENTES_IVS), random_state=C.SEED)
    scores = pca.fit_transform(Xs)
    var = pca.explained_variance_ratio_
    autoval = pca.explained_variance_

    n_ret = max(int((autoval > 1.0).sum()), 1)
    # anclas de signo: cada componente debe crecer con un marcador de valor
    anclas = ["pisos_prom_pond", "log_huella_media", "log_huella_media",
              "log_huella_media", "log_huella_media"]
    cargas = pca.components_.copy()
    for j in range(n_ret):
        if np.corrcoef(scores[:, j], df[anclas[j]].values)[0, 1] < 0:
            scores[:, j] *= -1
            cargas[j] *= -1

    pesos = var[:n_ret] / var[:n_ret].sum()
    compuesto = scores[:, :n_ret] @ pesos

    for j in range(n_ret):
        df["pc%d" % (j + 1)] = scores[:, j]
    df["ivs_bruto"] = compuesto
    df["ivs"] = pd.Series(compuesto).rank(pct=True).values * 100.0
    # alternativa simple (promedio de z-scores) para chequeo de robustez
    df["ivs_zmean"] = pd.Series(Xs.mean(axis=1)).rank(pct=True).values * 100.0

    tabla = pd.DataFrame(cargas[:n_ret].T, index=C.COMPONENTES_IVS,
                         columns=["carga_pc%d" % (j + 1) for j in range(n_ret)])
    tabla["correlacion_con_ivs"] = [
        round(float(np.corrcoef(df[c].values, compuesto)[0, 1]), 4)
        for c in C.COMPONENTES_IVS
    ]
    tabla = tabla.round(4).reset_index().rename(columns={"index": "componente"})
    tabla.to_csv(C.TAB_DIR / "t02_pca_cargas_ivs.csv", index=False)

    pd.DataFrame({
        "componente": ["PC%d" % (i + 1) for i in range(len(var))],
        "autovalor": np.round(autoval, 4),
        "varianza_explicada": np.round(var, 4),
        "varianza_acumulada": np.round(np.cumsum(var), 4),
        "retenida": [i < n_ret for i in range(len(var))],
        "peso_en_ivs": [round(pesos[i], 4) if i < n_ret else 0.0
                        for i in range(len(var))],
    }).to_csv(C.TAB_DIR / "t02b_pca_varianza.csv", index=False)

    print("     PCA: %d componentes retenidas (autovalor > 1), varianza %.1f%%"
          % (n_ret, var[:n_ret].sum() * 100))
    print("     pesos:", dict(zip(["PC%d" % (i + 1) for i in range(n_ret)],
                                  np.round(pesos, 3))))
    print("     concordancia IVS vs promedio de z-scores: rho = %.3f"
          % df["ivs"].corr(df["ivs_zmean"], method="spearman"))
    return df, var, n_ret


def validar_zonas(df):
    """Validez externa: el IVS debe ordenar como lo hace el mercado en Bogota."""
    zonas = {
        "Chico - Calle 93": (-74.0470, 4.6760),
        "Salitre / Ciudad Empresarial": (-74.1050, 4.6570),
        "Chapinero - Calle 63": (-74.0640, 4.6480),
        "Centro Internacional": (-74.0680, 4.6150),
        "Usaquen": (-74.0310, 4.6950),
        "La Candelaria": (-74.0730, 4.5960),
        "Suba centro": (-74.0830, 4.7440),
        "Kennedy": (-74.1500, 4.6280),
        "Bosa": (-74.1900, 4.6180),
        "Usme": (-74.1200, 4.5100),
    }
    filas = []
    for nombre, (lo, la) in zonas.items():
        d = haversine_vec(df["lon"].values, df["lat"].values, lo, la)
        s = df[d < 1.2]
        if len(s) == 0:
            continue
        filas.append({
            "zona": nombre, "manzanas": len(s),
            "ivs_mediano": round(s["ivs"].median(), 1),
            "pisos_prom_pond": round(s["pisos_prom_pond"].median(), 2),
            "indice_construccion": round(s["indice_construccion"].median(), 2),
            "huella_media_m2": round(s["huella_media_m2"].median(), 1),
            "frac_subterraneo": round(s["frac_subterraneo"].median(), 2),
            "pct_alto_valor": round(s["alto_valor"].mean() * 100, 1),
        })
    tab = pd.DataFrame(filas).sort_values("ivs_mediano", ascending=False)
    tab.to_csv(C.TAB_DIR / "t08_validacion_zonas.csv", index=False)
    print("\n     Validacion contra zonas conocidas de Bogota:")
    print(tab.to_string(index=False))
    return tab


def categorizar(df):
    df["valor_cat"] = pd.qcut(df["ivs"], 4, labels=C.CLASES)
    df["valor_cod"] = df["valor_cat"].cat.codes
    df["alto_valor"] = (df["valor_cod"] == 3).astype(int)
    return df


def features_ubicacion(df, referencia=None):
    """Variables derivadas UNICAMENTE de la posicion geografica.

    referencia: si se pasa otro DataFrame con lon/lat (p. ej. las manzanas
    reales), las variables de vecindad se calculan contra el, lo que permite
    puntuar una malla regular con exactamente la misma definicion.
    """
    lon = df["lon"].values
    lat = df["lat"].values

    for nombre, (rlon, rlat) in C.PUNTOS_REFERENCIA.items():
        df["dist_%s_km" % nombre] = haversine_vec(lon, lat, rlon, rlat)

    kx_ref, ky_ref = factores_metricos(float(np.mean(lat)))
    df["dist_cerros_km"] = np.abs(lon - C.LON_CERROS) * kx_ref / 1000.0

    # rumbo respecto al centro historico (captura el gradiente norte-sur)
    dx = (lon - C.CENTRO_HISTORICO[0]) * kx_ref
    dy = (lat - C.CENTRO_HISTORICO[1]) * M_POR_GRADO_LAT
    az = np.degrees(np.arctan2(dx, dy))
    df["azimut"] = (az + 360.0) % 360.0
    df["azimut_sin"] = np.sin(np.radians(df["azimut"]))
    df["azimut_cos"] = np.cos(np.radians(df["azimut"]))

    # densidad urbana del entorno: cuantas manzanas hay alrededor
    ref = df if referencia is None else referencia
    propio = 1 if referencia is None else 0
    x_ref = ref["lon"].values * kx_ref / 1000.0
    y_ref = ref["lat"].values * ky_ref / 1000.0
    pts_ref = np.column_stack([x_ref, y_ref])
    pts = np.column_stack([lon * kx_ref / 1000.0, lat * ky_ref / 1000.0])
    tree = cKDTree(pts_ref)
    df["vecinos_500m"] = tree.query_ball_point(pts, 0.5, return_length=True) - propio
    df["vecinos_1km"] = tree.query_ball_point(pts, 1.0, return_length=True) - propio
    # 8o vecino mas cercano (si el propio punto esta en el arbol, se salta)
    dists, _ = tree.query(pts, k=8 + propio)
    df["dist_vecino_8_km"] = dists[:, 7 + propio]

    # apoyos descriptivos para el EDA (no entran al modelo)
    df["anillo_km"] = pd.cut(
        df["dist_centro_historico_km"],
        bins=[0, 2, 4, 6, 8, 10, 13, 16, 20, 100],
        labels=["0-2", "2-4", "4-6", "6-8", "8-10", "10-13", "13-16", "16-20", "20+"])
    df["cuadrante"] = pd.cut(
        df["azimut"], bins=[-0.01, 45, 135, 225, 315, 360.01],
        labels=["Norte", "Oriente", "Sur", "Occidente", "Norte2"]
    ).astype(str).replace({"Norte2": "Norte"})
    return df


def main():
    print("[02] Construccion del target (IVS) y de las variables de ubicacion")
    df = cargar_manzanas()
    df = componentes_morfologicos(df)
    df, var, n_ret = construir_ivs(df)
    df = categorizar(df)
    df = features_ubicacion(df)
    validar_zonas(df)

    faltantes = df[C.FEATURES_UBICACION + ["ivs"]].isna().sum()
    if faltantes.sum():
        print("     AVISO - nulos detectados:\n", faltantes[faltantes > 0])
        df = df.dropna(subset=C.FEATURES_UBICACION + ["ivs"]).reset_index(drop=True)

    df.to_csv(C.F_DATASET, index=False)

    print("     dataset final: %d manzanas x %d columnas" % df.shape)
    print("     clases:", df["valor_cat"].value_counts().sort_index().to_dict())
    print("     guardado en %s" % C.F_DATASET.name)

    resumen = df[C.COMPONENTES_IVS + ["ivs", "dist_centro_historico_km",
                                      "vecinos_1km"]].describe().T
    resumen.to_csv(C.TAB_DIR / "t01_resumen_variables.csv")


if __name__ == "__main__":
    main()

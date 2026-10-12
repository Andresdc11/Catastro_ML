# -*- coding: utf-8 -*-
"""03 - Analisis exploratorio (EDA) de la valoracion del terreno por ubicacion.

Genera figuras en outputs/figuras y tablas en outputs/tablas. El hilo conductor
es: como se distribuye el proxy de valor del suelo (IVS) en el espacio y que
variables de ubicacion lo explican.
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.spatial import cKDTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config as C

sns.set_theme(style="whitegrid", palette="deep")
plt.rcParams.update({
    "figure.dpi": 110, "savefig.dpi": 130, "savefig.bbox": "tight",
    "font.size": 9, "axes.titlesize": 10, "axes.titleweight": "bold",
})
CMAP = "viridis"


def guardar(fig, nombre):
    ruta = C.FIG_DIR / nombre
    fig.savefig(ruta, facecolor="white")
    plt.close(fig)
    print("     figura -> %s" % nombre)


def recorte_urbano(df):
    """Filtra al perimetro urbano para que los mapas no se deformen."""
    m = (df["lon"].between(*C.URB_LON)) & (df["lat"].between(*C.URB_LAT))
    return df[m]


def formato_mapa(ax, titulo=None):
    ax.set_xlim(*C.URB_LON)
    ax.set_ylim(*C.URB_LAT)
    ax.set_aspect(1 / np.cos(np.radians(4.65)))
    ax.set_xlabel("longitud")
    ax.grid(alpha=0.25)
    if titulo:
        ax.set_title(titulo)


# --------------------------------------------------------------------------
# 1. Calidad de datos y distribuciones a nivel de construccion
# --------------------------------------------------------------------------
def fig_calidad(stats, mues):
    fig, axes = plt.subplots(2, 2, figsize=(11, 7))

    ax = axes[0, 0]
    descartes = {
        "Validas": stats["features_validas"],
        "Area < 1 m2": stats["area_fuera_de_rango"],
        "Geometria nula": stats["geometria_invalida"],
        "Codigo invalido": stats["codigo_invalido"],
        "Fuera de Bogota": stats["fuera_de_bbox"],
    }
    k = list(descartes)
    v = [descartes[i] for i in k]
    barras = ax.barh(k, v, color=["#2a9d8f"] + ["#e76f51"] * 4)
    ax.set_xscale("log")
    ax.set_title("Depuracion de %s registros leidos" % f"{stats['features_leidas']:,}")
    ax.set_xlabel("registros (escala log)")
    for b, val in zip(barras, v):
        ax.text(max(val, 1) * 1.15, b.get_y() + b.get_height() / 2,
                f"{val:,}", va="center", fontsize=8)

    ax = axes[0, 1]
    tipos = pd.Series(stats["tipos_geometria"])
    ax.bar(tipos.index, tipos.values, color="#264653")
    ax.set_yscale("log")
    ax.set_title("Tipos de geometria")
    ax.set_ylabel("registros (log)")
    for i, val in enumerate(tipos.values):
        ax.text(i, val * 1.2, f"{val:,}", ha="center", fontsize=8)

    ax = axes[1, 0]
    nulos = pd.Series(stats["nulos_por_campo"])
    if len(nulos) == 0:
        ax.text(0.5, 0.5, "Sin valores nulos\nen los atributos",
                ha="center", va="center", fontsize=12, color="#2a9d8f")
        ax.set_axis_off()
    else:
        nulos.sort_values().plot.barh(ax=ax, color="#e9c46a")
    ax.set_title("Valores nulos por atributo")

    ax = axes[1, 1]
    ceros = pd.Series({
        "altura = 0": (mues["altura"] == 0).mean(),
        "sotanos = 0": (mues["sotanos"] == 0).mean(),
        "semisotanos = 0": (mues["semisotanos"] == 0).mean(),
        "mejora = 0": (mues["mejora"] == 0).mean(),
        "voladizo = 0": (mues["voladizo"] == 0).mean(),
        "area < 10 m2": (mues["area_m2"] < 10).mean(),
    }).sort_values()
    ax.barh(ceros.index, ceros.values * 100, color="#f4a261")
    ax.set_xlabel("% de construcciones")
    ax.set_title("Atributos poco informativos (mayoria en cero)")
    for i, val in enumerate(ceros.values):
        ax.text(val * 100 + 1, i, "%.1f%%" % (val * 100), va="center", fontsize=8)

    fig.suptitle("Calidad del dato catastral de construcciones", fontsize=12,
                 fontweight="bold")
    fig.tight_layout()
    guardar(fig, "fig01_calidad_datos.png")

    pd.DataFrame({"indicador": list(descartes), "registros": v}).to_csv(
        C.TAB_DIR / "t03_calidad_datos.csv", index=False)

    # utilidad real de cada atributo: que fraccion viene en cero
    pd.DataFrame({
        "atributo": ["CONALTURA", "CONNSOTANO", "CONTSEMIS", "CONMEJORA",
                     "CONVOLADIZ", "CONELEVACI"],
        "pct_sin_informacion": [
            round((mues["altura"] == 0).mean() * 100, 1),
            round((mues["sotanos"] == 0).mean() * 100, 1),
            round((mues["semisotanos"] == 0).mean() * 100, 1),
            round((mues["mejora"] == 0).mean() * 100, 1),
            round((mues["voladizo"] == 0).mean() * 100, 1),
            round((mues["elevacion"] == mues["n_pisos"]).mean() * 100, 1),
        ],
        "lectura": ["en cero", "en cero", "en cero", "en cero", "en cero",
                    "identico a CONNPISOS"],
    }).to_csv(C.TAB_DIR / "t03b_utilidad_atributos.csv", index=False)


def fig_distribuciones(mues):
    fig, axes = plt.subplots(2, 2, figsize=(11, 7))

    ax = axes[0, 0]
    ax.hist(np.log10(mues["area_m2"].clip(lower=0.1)), bins=80, color="#264653")
    ax.set_xlabel("log10 area de huella (m2)")
    ax.set_ylabel("construcciones")
    ax.set_title("Area de huella: mediana %.0f m2" % mues["area_m2"].median())

    ax = axes[0, 1]
    conteo = mues["n_pisos"].clip(upper=12).value_counts().sort_index()
    ax.bar(conteo.index, conteo.values, color="#2a9d8f")
    ax.set_xlabel("numero de pisos (12+ agrupado)")
    ax.set_title("Altura en pisos: %.1f%% tiene 1-2 pisos"
                 % ((mues["n_pisos"] <= 2).mean() * 100))

    ax = axes[1, 0]
    sub = mues[mues["altura"] > 0]
    ax.hist(sub["altura"].clip(upper=20), bins=40, color="#e76f51")
    ax.set_xlabel("altura declarada (m)")
    ax.set_title("Altura: solo %.1f%% de los registros la declara"
                 % ((mues["altura"] > 0).mean() * 100))

    ax = axes[1, 1]
    ax.hist(mues["compacidad"], bins=60, color="#e9c46a")
    ax.set_xlabel("compacidad  4*pi*A / P^2   (1 = circulo)")
    ax.set_title("Forma de la huella (mediana %.2f)" % mues["compacidad"].median())

    fig.suptitle("Distribuciones a nivel de construccion (muestra del %.0f%%)"
                 % (C.SAMPLE_FRAC * 100), fontsize=12, fontweight="bold")
    fig.tight_layout()
    guardar(fig, "fig02_distribuciones_construccion.png")


def fig_area_pisos(mues):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))

    ax = axes[0]
    sub = mues.sample(min(120000, len(mues)), random_state=C.SEED)
    hb = ax.hexbin(np.log10(sub["area_m2"].clip(lower=0.1)),
                   sub["n_pisos"].clip(upper=15), gridsize=45, bins="log",
                   cmap=CMAP, mincnt=1)
    ax.set_xlabel("log10 area de huella (m2)")
    ax.set_ylabel("pisos")
    ax.set_title("Huella vs altura (densidad log)")
    fig.colorbar(hb, ax=ax, label="log10 conteo")

    ax = axes[1]
    grp = mues.assign(pisos_g=mues["n_pisos"].clip(upper=10)).groupby("pisos_g")
    med = grp["area_m2"].median()
    q1 = grp["area_m2"].quantile(0.25)
    q3 = grp["area_m2"].quantile(0.75)
    ax.plot(med.index, med.values, "o-", color="#264653", label="mediana")
    ax.fill_between(med.index, q1.values, q3.values, alpha=0.25,
                    color="#2a9d8f", label="rango intercuartil")
    ax.set_xlabel("pisos (10+ agrupado)")
    ax.set_ylabel("area de huella (m2)")
    ax.set_title("Las construcciones altas ocupan huellas mayores")
    ax.legend()

    fig.tight_layout()
    guardar(fig, "fig03_area_vs_pisos.png")


def fig_mapa_construcciones(mues):
    sub = recorte_urbano(mues)
    sub = sub.sample(min(260000, len(sub)), random_state=C.SEED)
    fig, ax = plt.subplots(figsize=(7.2, 9))
    sc = ax.scatter(sub["lon"], sub["lat"], c=sub["n_pisos"].clip(upper=8),
                    s=0.12, cmap=CMAP, alpha=0.6, linewidths=0)
    formato_mapa(ax, "Huella construida de Bogota, coloreada por numero de pisos")
    ax.set_ylabel("latitud")
    fig.colorbar(sc, ax=ax, label="pisos (8+ agrupado)", shrink=0.6)
    for nom, (lo, la) in C.PUNTOS_REFERENCIA.items():
        ax.plot(lo, la, "*", color="red", markersize=12, markeredgecolor="white")
        ax.annotate(nom.replace("_", " "), (lo, la), fontsize=7.5, color="red",
                    fontweight="bold", xytext=(5, 5), textcoords="offset points")
    guardar(fig, "fig04_mapa_construcciones_pisos.png")


# --------------------------------------------------------------------------
# 2. El indice de valor del suelo
# --------------------------------------------------------------------------
def fig_componentes_ivs(df):
    cargas = pd.read_csv(C.TAB_DIR / "t02_pca_cargas_ivs.csv")
    varz = pd.read_csv(C.TAB_DIR / "t02b_pca_varianza.csv")
    fig, axes = plt.subplots(2, 4, figsize=(16, 7))
    ejes = axes.ravel()

    for ax, col in zip(ejes, C.COMPONENTES_IVS):
        ax.hist(df[col], bins=60, color="#2a9d8f")
        ax.set_title(col, fontsize=9)
        ax.set_ylabel("manzanas")

    ax = ejes[5]
    y = np.arange(len(cargas))
    ax.barh(y - 0.2, cargas["carga_pc1"], height=0.4, color="#264653",
            label="PC1 - intensidad")
    if "carga_pc2" in cargas:
        ax.barh(y + 0.2, cargas["carga_pc2"], height=0.4, color="#e76f51",
                label="PC2 - formalidad")
    ax.set_yticks(y)
    ax.set_yticklabels(cargas["componente"], fontsize=7)
    ax.axvline(0, color="k", lw=0.8)
    ax.legend(fontsize=7)
    ax.set_title("Cargas de las componentes retenidas")

    ax = ejes[6]
    ax.bar(varz["componente"], varz["varianza_explicada"] * 100,
           color=["#264653" if r else "#adb5bd" for r in varz["retenida"]])
    ax.axhline(100 / len(varz), color="#e76f51", ls="--", lw=1,
               label="autovalor = 1 (Kaiser)")
    ax.set_ylabel("% de varianza")
    ax.set_title("Sedimentacion: se retienen PC1 y PC2")
    ax.legend(fontsize=7)

    ax = ejes[7]
    sub = df.sample(min(12000, len(df)), random_state=C.SEED)
    sc = ax.scatter(sub["pc1"], sub["pc2"], c=sub["ivs"], s=3, cmap="YlOrRd",
                    alpha=0.7, linewidths=0)
    ax.set_xlabel("PC1: intensidad edificatoria")
    ax.set_ylabel("PC2: formalidad (huella grande, sotanos)")
    ax.set_title("Plano PC1-PC2 coloreado por IVS")
    fig.colorbar(sc, ax=ax, label="IVS", shrink=0.85)

    fig.suptitle("Componentes morfologicos del Indice de Valor del Suelo",
                 fontsize=12, fontweight="bold")
    fig.tight_layout()
    guardar(fig, "fig05_componentes_ivs.png")


def fig_ivs_distribucion(df):
    fig, axes = plt.subplots(1, 3, figsize=(13, 4))

    ax = axes[0]
    ax.hist(df["ivs_bruto"], bins=70, color="#264653")
    ax.set_title("IVS bruto (compuesto PC1+PC2)")
    ax.set_xlabel("score compuesto")

    ax = axes[1]
    colores = sns.color_palette("YlOrRd", 4)
    for i, cl in enumerate(C.CLASES):
        sub = df[df["valor_cat"] == cl]
        ax.hist(sub["ivs"], bins=25, color=colores[i], label=cl)
    ax.set_title("IVS 0-100 y corte en cuartiles")
    ax.set_xlabel("IVS (percentil)")
    ax.legend(title="categoria", fontsize=7)

    ax = axes[2]
    ax.scatter(df["ivs"], df["ivs_zmean"], s=1, alpha=0.15, color="#2a9d8f")
    rho = df["ivs"].corr(df["ivs_zmean"], method="spearman")
    ax.set_xlabel("IVS por PCA")
    ax.set_ylabel("IVS por promedio de z-scores")
    ax.set_title("Robustez del indice (Spearman = %.3f)" % rho)

    fig.tight_layout()
    guardar(fig, "fig06_ivs_distribucion.png")


def fig_mapa_ivs(df):
    urb = recorte_urbano(df)
    n_rural = len(df) - len(urb)
    fig, axes = plt.subplots(1, 3, figsize=(13, 8.5),
                             gridspec_kw={"width_ratios": [1, 0.04, 1]})

    ax = axes[0]
    sc = ax.scatter(urb["lon"], urb["lat"], c=urb["ivs"], s=3.2, cmap="RdYlBu_r",
                    alpha=0.9, linewidths=0)
    formato_mapa(ax, "IVS continuo por manzana (0 = bajo, 100 = alto)")
    fig.colorbar(sc, cax=axes[1], label="IVS")
    axes[1].grid(False)

    ax = axes[2]
    colores = dict(zip(C.CLASES, ["#4575b4", "#abd9e9", "#fdae61", "#d73027"]))
    mez = urb.sample(frac=1.0, random_state=C.SEED)   # evita que una clase tape a otra
    ax.scatter(mez["lon"], mez["lat"], s=3.2, linewidths=0, alpha=0.9,
               c=[colores[c] for c in mez["valor_cat"]])
    handles = [plt.Line2D([], [], marker="o", ls="", color=colores[c], label=c)
               for c in C.CLASES]
    ax.legend(handles=handles, title="categoria de valor", fontsize=8, loc="lower left")
    formato_mapa(ax, "Categoria de valor (cuartiles del IVS)")

    for a in (axes[0], axes[2]):
        a.plot(*C.CENTRO_HISTORICO, "k*", markersize=14, markeredgecolor="white")
    axes[0].set_ylabel("latitud")

    fig.suptitle("Distribucion espacial del valor del suelo estimado  "
                 "(%d manzanas urbanas; %d rurales fuera del encuadre)"
                 % (len(urb), n_rural), fontsize=12, fontweight="bold")
    fig.tight_layout()
    guardar(fig, "fig07_mapa_ivs.png")


def fig_gradiente(df):
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.4))

    ax = axes[0]
    bins = np.arange(0, 26, 0.5)
    df["_bin"] = pd.cut(df["dist_centro_historico_km"], bins)
    g = df.groupby("_bin", observed=True)["ivs"]
    centros = np.array([iv.mid for iv in g.median().index])
    ax.plot(centros, g.median().values, "-", color="#264653", lw=2, label="mediana")
    ax.fill_between(centros, g.quantile(0.25).values, g.quantile(0.75).values,
                    alpha=0.25, color="#2a9d8f", label="rango intercuartil")
    ax.set_xlabel("distancia a la Plaza de Bolivar (km)")
    ax.set_ylabel("IVS")
    ax.set_title("Curva de renta del suelo (bid-rent)")
    ax.legend()

    ax = axes[1]
    for cuad, color in zip(["Norte", "Oriente", "Sur", "Occidente"],
                           ["#e76f51", "#264653", "#2a9d8f", "#e9c46a"]):
        sub = df[df["cuadrante"] == cuad]
        gg = sub.groupby(pd.cut(sub["dist_centro_historico_km"], bins),
                         observed=True)["ivs"].median()
        cc = np.array([iv.mid for iv in gg.index])
        ax.plot(cc, gg.values, "-", lw=1.8, color=color, label=cuad)
    ax.set_xlabel("distancia a la Plaza de Bolivar (km)")
    ax.set_ylabel("IVS mediano")
    ax.set_title("El gradiente depende de la direccion, no solo de la distancia")
    ax.legend(title="cuadrante", fontsize=8)

    df.drop(columns=["_bin"], inplace=True)
    fig.tight_layout()
    guardar(fig, "fig08_gradiente_distancia.png")


def fig_cuadrante_anillo(df):
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.4))

    ax = axes[0]
    orden = df.groupby("cuadrante")["ivs"].median().sort_values(ascending=False).index
    sns.boxplot(data=df, x="cuadrante", y="ivs", order=orden, ax=ax,
                showfliers=False, palette="YlOrRd")
    ax.set_title("IVS por cuadrante de la ciudad")
    ax.set_xlabel("")

    ax = axes[1]
    tabla = (pd.crosstab(df["anillo_km"], df["valor_cat"], normalize="index") * 100)
    tabla.plot.bar(stacked=True, ax=ax, colormap="YlOrRd", width=0.85)
    ax.set_xlabel("anillo de distancia al centro (km)")
    ax.set_ylabel("% de manzanas")
    ax.set_title("Composicion de categorias de valor por anillo")
    ax.legend(title="categoria", fontsize=7, bbox_to_anchor=(1.01, 1))
    ax.tick_params(axis="x", rotation=0)

    fig.tight_layout()
    guardar(fig, "fig09_ivs_por_cuadrante_y_anillo.png")

    resumen = df.groupby("anillo_km", observed=True).agg(
        manzanas=("ivs", "size"), ivs_mediano=("ivs", "median"),
        pisos_prom=("pisos_prom_pond", "mean"),
        indice_construccion=("indice_construccion", "median"),
        pct_alto_valor=("alto_valor", lambda s: round(s.mean() * 100, 1)),
    ).round(2)
    resumen.to_csv(C.TAB_DIR / "t04_ivs_por_anillo.csv")
    return resumen


def fig_correlaciones(df):
    cols = C.FEATURES_UBICACION + ["ivs"]
    corr = df[cols].corr(method="spearman")
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.2),
                             gridspec_kw={"width_ratios": [1.25, 1]})
    sns.heatmap(corr, annot=True, fmt=".2f", cmap="RdBu_r", center=0,
                ax=axes[0], annot_kws={"size": 6.5}, cbar_kws={"shrink": 0.8})
    axes[0].set_title("Correlacion de Spearman entre variables de ubicacion e IVS")

    s = corr["ivs"].drop("ivs").sort_values()
    axes[1].barh(s.index, s.values,
                 color=["#e76f51" if v < 0 else "#2a9d8f" for v in s.values])
    axes[1].axvline(0, color="k", lw=0.8)
    axes[1].set_title("Correlacion de cada variable de ubicacion con el IVS")
    axes[1].set_xlabel("rho de Spearman")

    fig.tight_layout()
    guardar(fig, "fig10_correlaciones.png")
    corr["ivs"].drop("ivs").sort_values().to_csv(
        C.TAB_DIR / "t06_correlaciones_ubicacion_ivs.csv")
    return corr


def fig_top_sectores(df):
    g = df.groupby("sector").agg(
        manzanas=("ivs", "size"), ivs=("ivs", "median"),
        pisos=("pisos_prom_pond", "mean"),
        dist_centro=("dist_centro_historico_km", "mean")).round(2)
    g = g[g["manzanas"] >= 10]
    top = g.nlargest(15, "ivs")
    bot = g.nsmallest(15, "ivs")

    fig, axes = plt.subplots(1, 2, figsize=(12.5, 5))
    axes[0].barh(top.index[::-1], top["ivs"][::-1], color="#e76f51")
    axes[0].set_title("15 sectores catastrales con mayor IVS mediano")
    axes[0].set_xlabel("IVS")
    axes[1].barh(bot.index[::-1], bot["ivs"][::-1], color="#2a9d8f")
    axes[1].set_title("15 sectores catastrales con menor IVS mediano")
    axes[1].set_xlabel("IVS")
    for ax in axes:
        ax.tick_params(axis="y", labelsize=7)
    fig.tight_layout()
    guardar(fig, "fig11_top_sectores.png")

    pd.concat([top.assign(grupo="alto"), bot.assign(grupo="bajo")]).to_csv(
        C.TAB_DIR / "t05_top_sectores.csv")


def moran_i(df, k=8, n_perm=99):
    """Moran's I global con pesos de k vecinos mas cercanos, fila-estandarizados."""
    lon, lat = df["lon"].values, df["lat"].values
    x = (lon - lon.mean()) * 110.9
    y = (lat - lat.mean()) * 110.6
    tree = cKDTree(np.column_stack([x, y]))
    _, idx = tree.query(np.column_stack([x, y]), k=k + 1)
    vecinos = idx[:, 1:]

    z = df["ivs"].values - df["ivs"].values.mean()
    lag = z[vecinos].mean(axis=1)
    I = float((z * lag).sum() / (z * z).sum())

    rng = np.random.default_rng(C.SEED)
    nulos = np.empty(n_perm)
    for i in range(n_perm):
        zp = rng.permutation(z)
        nulos[i] = (zp * zp[vecinos].mean(axis=1)).sum() / (zp * zp).sum()
    p = (1 + (np.abs(nulos) >= abs(I)).sum()) / (n_perm + 1)
    return I, lag, z, nulos, p


def fig_autocorrelacion(df):
    I, lag, z, nulos, p = moran_i(df)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4))

    ax = axes[0]
    ax.scatter(z, lag, s=1.5, alpha=0.12, color="#264653")
    b = np.polyfit(z, lag, 1)
    xs = np.linspace(z.min(), z.max(), 50)
    ax.plot(xs, np.polyval(b, xs), color="#e76f51", lw=2)
    ax.axhline(0, color="grey", lw=0.7)
    ax.axvline(0, color="grey", lw=0.7)
    ax.set_xlabel("IVS centrado")
    ax.set_ylabel("IVS medio de las 8 manzanas vecinas")
    ax.set_title("Diagrama de Moran:  I = %.3f  (p = %.3f)" % (I, p))

    ax = axes[1]
    ax.hist(nulos, bins=25, color="#2a9d8f", label="I bajo aleatorizacion")
    ax.axvline(I, color="#e76f51", lw=2.5, label="I observado")
    ax.set_title("El valor del suelo NO se distribuye al azar")
    ax.set_xlabel("Moran's I")
    ax.legend(fontsize=8)

    fig.tight_layout()
    guardar(fig, "fig12_autocorrelacion_espacial.png")

    pd.DataFrame([{"moran_I": round(I, 4), "p_valor": round(p, 4),
                   "k_vecinos": 8, "permutaciones": len(nulos)}]).to_csv(
        C.TAB_DIR / "t07_autocorrelacion.csv", index=False)
    return I, p


def main():
    print("[03] EDA")
    mues = pd.read_csv(C.F_MUESTRA, dtype={"lote": str, "manzana": str, "sector": str})
    df = pd.read_csv(C.F_DATASET, dtype={"manzana": str, "sector": str})
    df["valor_cat"] = pd.Categorical(df["valor_cat"], categories=C.CLASES, ordered=True)
    anillos_ord = ["0-2", "2-4", "4-6", "6-8", "8-10", "10-13", "13-16", "16-20", "20+"]
    df["anillo_km"] = pd.Categorical(df["anillo_km"], categories=anillos_ord, ordered=True)
    with open(C.F_STATS, encoding="utf-8") as fh:
        stats = json.load(fh)

    print("     muestra construcciones: %d filas" % len(mues))
    print("     manzanas modelables   : %d filas" % len(df))

    fig_calidad(stats, mues)
    fig_distribuciones(mues)
    fig_area_pisos(mues)
    fig_mapa_construcciones(mues)
    fig_componentes_ivs(df)
    fig_ivs_distribucion(df)
    fig_mapa_ivs(df)
    fig_gradiente(df)
    anillos = fig_cuadrante_anillo(df)
    corr = fig_correlaciones(df)
    fig_top_sectores(df)
    I, p = fig_autocorrelacion(df)

    print("\n     --- Hallazgos cuantitativos ---")
    print("     IVS por anillo de distancia:")
    print(anillos[["manzanas", "ivs_mediano", "pct_alto_valor"]].to_string())
    print("\n     Correlacion |rho| mas alta con el IVS:")
    print(corr["ivs"].drop("ivs").abs().sort_values(ascending=False).head(5).round(3).to_string())
    print("\n     Autocorrelacion espacial: Moran I = %.3f (p = %.3f)" % (I, p))


if __name__ == "__main__":
    main()

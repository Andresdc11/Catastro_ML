# -*- coding: utf-8 -*-
"""04 - Modelado supervisado: valor del suelo a partir de la ubicacion.

Dos tareas:

  TAREA A (multiclase) - predecir la categoria de valor de una manzana
      (Bajo / Medio-Bajo / Medio-Alto / Alto) con seis algoritmos.
  TAREA B (binaria)    - "manzana de alto valor" (cuartil superior) con
      regresion logistica, con lectura interpretativa de odds ratios.

Validacion ESPACIAL. Las manzanas vecinas se parecen entre si (Moran I ~ 0.54),
asi que una particion aleatoria pondria manzanas de la misma cuadra a ambos
lados del split e inflaria la metrica. Se particiona por SECTOR CATASTRAL
(GroupShuffleSplit / GroupKFold): el modelo se evalua sobre barrios que nunca
vio. Se reporta tambien la CV aleatoria para cuantificar ese sesgo optimista.
"""
import json
import os
import sys
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from joblib import dump
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, average_precision_score,
                             balanced_accuracy_score, classification_report,
                             cohen_kappa_score, confusion_matrix, f1_score,
                             precision_recall_curve, roc_auc_score, roc_curve)
from sklearn.model_selection import (GridSearchCV, GroupKFold, GroupShuffleSplit,
                                     StratifiedKFold, cross_val_score)
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import PolynomialFeatures, StandardScaler
from sklearn.tree import DecisionTreeClassifier, plot_tree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config as C

sns.set_theme(style="whitegrid")
plt.rcParams.update({"figure.dpi": 110, "savefig.dpi": 130,
                     "savefig.bbox": "tight", "font.size": 9,
                     "axes.titlesize": 10, "axes.titleweight": "bold"})

COL_CLASE = ["#4575b4", "#abd9e9", "#fdae61", "#d73027"]


def guardar(fig, nombre):
    fig.savefig(C.FIG_DIR / nombre, facecolor="white")
    plt.close(fig)
    print("     figura -> %s" % nombre)


# --------------------------------------------------------------------------
# Datos
# --------------------------------------------------------------------------
def cargar():
    df = pd.read_csv(C.F_DATASET, dtype={"manzana": str, "sector": str})
    df["valor_cat"] = pd.Categorical(df["valor_cat"], categories=C.CLASES,
                                     ordered=True)
    X = df[C.FEATURES_UBICACION].astype(float)
    y = df["valor_cod"].astype(int).values
    grupos = df["sector"].values
    return df, X, y, grupos


def split_espacial(X, y, grupos, test_size=0.25):
    gss = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=C.SEED)
    tr, te = next(gss.split(X, y, groups=grupos))
    print("     train %d manzanas / %d sectores" % (len(tr), len(set(grupos[tr]))))
    print("     test  %d manzanas / %d sectores  (sectores disjuntos)"
          % (len(te), len(set(grupos[te]))))
    return tr, te


# --------------------------------------------------------------------------
# Modelos
# --------------------------------------------------------------------------
def definir_modelos():
    """Siete clasificadores: 1 baseline trivial + 6 algoritmos reales."""
    return {
        "Baseline (mayoritaria)": DummyClassifier(strategy="most_frequent"),
        "Regresion logistica": Pipeline([
            ("esc", StandardScaler()),
            ("clf", LogisticRegression(max_iter=2000, C=1.0,
                                       multi_class="multinomial",
                                       random_state=C.SEED)),
        ]),
        # el modelo lineal no puede describir la estructura radial de la ciudad;
        # con terminos cuadraticos e interacciones si captura la curvatura
        "Reg. logistica polinomica": Pipeline([
            ("poli", PolynomialFeatures(degree=2, include_bias=False)),
            ("esc", StandardScaler()),
            ("clf", LogisticRegression(max_iter=4000, C=0.5,
                                       multi_class="multinomial",
                                       random_state=C.SEED)),
        ]),
        "Arbol de decision": DecisionTreeClassifier(
            max_depth=12, min_samples_leaf=40, random_state=C.SEED),
        # hojas de 25: mejor F1 que hojas de 2 (que sobreajustaban) y un
        # modelo serializado 10 veces mas pequeno
        "Random Forest": RandomForestClassifier(
            n_estimators=400, min_samples_leaf=25, n_jobs=-1,
            random_state=C.SEED),
        "Gradient Boosting": HistGradientBoostingClassifier(
            max_iter=350, learning_rate=0.08, max_leaf_nodes=63,
            random_state=C.SEED),
        "KNN espacial (k=15)": Pipeline([
            ("esc", StandardScaler()),
            ("clf", KNeighborsClassifier(n_neighbors=15, weights="distance",
                                         n_jobs=-1)),
        ]),
    }


def ajustar_arbol(X, y, grupos):
    """Busqueda de hiperparametros del arbol con CV agrupada por sector."""
    grid = {
        "max_depth": [4, 6, 8, 10, 12, 16, None],
        "min_samples_leaf": [10, 25, 50, 100],
        "criterion": ["gini", "entropy"],
    }
    gs = GridSearchCV(DecisionTreeClassifier(random_state=C.SEED), grid,
                      scoring="f1_macro", cv=GroupKFold(n_splits=4),
                      n_jobs=-1, refit=True)
    gs.fit(X, y, groups=grupos)
    res = pd.DataFrame(gs.cv_results_)[
        ["param_max_depth", "param_min_samples_leaf", "param_criterion",
         "mean_test_score", "std_test_score"]].sort_values(
        "mean_test_score", ascending=False)
    res.to_csv(C.TAB_DIR / "t09_grid_arbol.csv", index=False)
    print("     arbol - mejores parametros: %s  (f1_macro CV = %.3f)"
          % (gs.best_params_, gs.best_score_))
    return gs.best_estimator_, gs.best_params_, res


# --------------------------------------------------------------------------
# Evaluacion
# --------------------------------------------------------------------------
def comparar_cv(modelos, X, y, grupos):
    """f1_macro con CV espacial (por sector) y con CV aleatoria."""
    filas = []
    for nombre, mod in modelos.items():
        t0 = time.time()
        esp = cross_val_score(mod, X, y, groups=grupos, cv=GroupKFold(5),
                              scoring="f1_macro", n_jobs=1)
        ale = cross_val_score(mod, X, y, cv=StratifiedKFold(5, shuffle=True,
                                                            random_state=C.SEED),
                              scoring="f1_macro", n_jobs=1)
        filas.append({
            "modelo": nombre,
            "f1_macro_cv_espacial": round(esp.mean(), 4),
            "sd_espacial": round(esp.std(), 4),
            "f1_macro_cv_aleatoria": round(ale.mean(), 4),
            "sd_aleatoria": round(ale.std(), 4),
            "sesgo_optimista": round(ale.mean() - esp.mean(), 4),
            "segundos": round(time.time() - t0, 1),
        })
        print("     %-24s espacial %.3f +- %.3f | aleatoria %.3f  (%.0fs)"
              % (nombre, esp.mean(), esp.std(), ale.mean(), time.time() - t0))
    tab = pd.DataFrame(filas).sort_values("f1_macro_cv_espacial", ascending=False)
    tab.to_csv(C.TAB_DIR / "t10_comparacion_cv.csv", index=False)
    return tab


def evaluar_test(modelos, X, y, tr, te):
    """Entrena en train y mide sobre sectores nunca vistos."""
    filas, ajustados, predicciones = [], {}, {}
    Xtr, Xte = X.iloc[tr], X.iloc[te]
    ytr, yte = y[tr], y[te]
    for nombre, mod in modelos.items():
        t0 = time.time()
        mod.fit(Xtr, ytr)
        pred = mod.predict(Xte)
        filas.append({
            "modelo": nombre,
            "exactitud": round(accuracy_score(yte, pred), 4),
            "exactitud_balanceada": round(balanced_accuracy_score(yte, pred), 4),
            "f1_macro": round(f1_score(yte, pred, average="macro"), 4),
            "f1_ponderado": round(f1_score(yte, pred, average="weighted"), 4),
            "kappa": round(cohen_kappa_score(yte, pred), 4),
            "error_1_categoria": round(float(np.mean(np.abs(pred - yte) <= 1)), 4),
            "seg_entrenamiento": round(time.time() - t0, 1),
        })
        ajustados[nombre] = mod
        predicciones[nombre] = pred
        print("     %-24s exactitud %.3f  f1_macro %.3f  kappa %.3f"
              % (nombre, filas[-1]["exactitud"], filas[-1]["f1_macro"],
                 filas[-1]["kappa"]))
    tab = pd.DataFrame(filas).sort_values("f1_macro", ascending=False)
    tab.to_csv(C.TAB_DIR / "t11_metricas_test.csv", index=False)
    return tab, ajustados, predicciones


# --------------------------------------------------------------------------
# Figuras
# --------------------------------------------------------------------------
def fig_comparacion(tab_cv, tab_test):
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.6))

    ax = axes[0]
    t = tab_test.set_index("modelo")
    y = np.arange(len(t))
    ax.barh(y - 0.2, t["exactitud"], height=0.38, color="#264653", label="exactitud")
    ax.barh(y + 0.2, t["f1_macro"], height=0.38, color="#e76f51", label="F1 macro")
    ax.set_yticks(y)
    ax.set_yticklabels(t.index, fontsize=8)
    ax.axvline(0.25, color="grey", ls="--", lw=1, label="azar (4 clases)")
    ax.invert_yaxis()
    ax.legend(fontsize=7)
    ax.set_title("Desempeno sobre sectores no vistos (conjunto de prueba)")
    for i, (a, f) in enumerate(zip(t["exactitud"], t["f1_macro"])):
        ax.text(a + 0.005, i - 0.2, "%.3f" % a, va="center", fontsize=7)
        ax.text(f + 0.005, i + 0.2, "%.3f" % f, va="center", fontsize=7)

    ax = axes[1]
    t2 = tab_cv.set_index("modelo")
    y = np.arange(len(t2))
    ax.barh(y - 0.2, t2["f1_macro_cv_aleatoria"], height=0.38, color="#f4a261",
            xerr=t2["sd_aleatoria"], label="CV aleatoria (optimista)")
    ax.barh(y + 0.2, t2["f1_macro_cv_espacial"], height=0.38, color="#2a9d8f",
            xerr=t2["sd_espacial"], label="CV espacial por sector")
    ax.set_yticks(y)
    ax.set_yticklabels(t2.index, fontsize=8)
    ax.invert_yaxis()
    ax.legend(fontsize=7)
    ax.set_xlabel("F1 macro")
    ax.set_title("La particion aleatoria sobreestima por autocorrelacion espacial")

    fig.tight_layout()
    guardar(fig, "fig13_comparacion_modelos.png")


def fig_matrices(predicciones, yte, orden):
    modelos = [m for m in orden if m in predicciones]
    ncol = 4
    nfil = int(np.ceil(len(modelos) / ncol))
    fig, axes = plt.subplots(nfil, ncol, figsize=(4.6 * ncol, 4.2 * nfil))
    for ax in axes.ravel()[len(modelos):]:
        ax.set_axis_off()
    for ax, nombre in zip(axes.ravel(), modelos):
        cm = confusion_matrix(yte, predicciones[nombre], normalize="true")
        sns.heatmap(cm * 100, annot=True, fmt=".0f", cmap="Blues", ax=ax,
                    cbar=False, vmin=0, vmax=100,
                    xticklabels=C.CLASES, yticklabels=C.CLASES,
                    annot_kws={"size": 8})
        ax.set_title("%s\nexactitud %.3f" % (nombre, accuracy_score(
            yte, predicciones[nombre])), fontsize=9)
        ax.set_xlabel("prediccion")
        ax.set_ylabel("real")
        ax.tick_params(labelsize=7)
    fig.suptitle("Matrices de confusion (% por fila = por clase real)",
                 fontsize=12, fontweight="bold")
    fig.tight_layout()
    guardar(fig, "fig14_matrices_confusion.png")


def fig_arbol(arbol, res_grid):
    fig = plt.figure(figsize=(17, 8))
    gs = fig.add_gridspec(2, 3, height_ratios=[2.1, 1])

    ax = fig.add_subplot(gs[0, :])
    superficial = DecisionTreeClassifier(max_depth=3, random_state=C.SEED)
    superficial.fit(arbol._X_tr, arbol._y_tr)
    plot_tree(superficial, feature_names=C.FEATURES_UBICACION,
              class_names=C.CLASES, filled=True, rounded=True, fontsize=7,
              impurity=False, proportion=True, ax=ax)
    ax.set_title("Arbol podado a profundidad 3: reglas de ubicacion legibles",
                 fontsize=11)

    ax = fig.add_subplot(gs[1, 0])
    prof = res_grid.copy()
    prof["param_max_depth"] = prof["param_max_depth"].astype(object).where(
        prof["param_max_depth"].notna(), 99).astype(float)
    curva = prof.groupby("param_max_depth")["mean_test_score"].max()
    ax.plot(curva.index, curva.values, "o-", color="#264653")
    ax.set_xlabel("max_depth (99 = sin limite)")
    ax.set_ylabel("F1 macro (CV espacial)")
    ax.set_title("Curva de complejidad")

    ax = fig.add_subplot(gs[1, 1])
    hoja = res_grid.groupby("param_min_samples_leaf")["mean_test_score"].max()
    ax.plot(hoja.index, hoja.values, "o-", color="#e76f51")
    ax.set_xlabel("min_samples_leaf")
    ax.set_title("Regularizacion por tamano de hoja")

    ax = fig.add_subplot(gs[1, 2])
    imp = pd.Series(arbol.feature_importances_,
                    index=C.FEATURES_UBICACION).sort_values()
    ax.barh(imp.index, imp.values, color="#2a9d8f")
    ax.tick_params(labelsize=7)
    ax.set_title("Importancia de variables (arbol ajustado)")

    fig.tight_layout()
    guardar(fig, "fig15_arbol_decision.png")


def fig_importancias(mejor_nombre, mejor, Xte, yte):
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.6))

    ax = axes[0]
    base = mejor[-1] if isinstance(mejor, Pipeline) else mejor
    if hasattr(base, "feature_importances_"):
        imp = pd.Series(base.feature_importances_,
                        index=C.FEATURES_UBICACION).sort_values()
        ax.barh(imp.index, imp.values, color="#264653")
        ax.set_title("Importancia interna - %s" % mejor_nombre)
    else:
        ax.set_axis_off()
        ax.text(0.5, 0.5, "El modelo no expone\nimportancias internas",
                ha="center", va="center")
    ax.tick_params(labelsize=7)

    ax = axes[1]
    pi = permutation_importance(mejor, Xte, yte, n_repeats=8,
                                random_state=C.SEED, scoring="f1_macro", n_jobs=-1)
    s = pd.Series(pi.importances_mean, index=C.FEATURES_UBICACION).sort_values()
    err = pd.Series(pi.importances_std, index=C.FEATURES_UBICACION)[s.index]
    ax.barh(s.index, s.values, xerr=err.values, color="#e76f51")
    ax.tick_params(labelsize=7)
    ax.set_xlabel("caida de F1 macro al permutar")
    ax.set_title("Importancia por permutacion (sobre el test)")

    fig.suptitle("Que variables de ubicacion determinan el valor",
                 fontsize=12, fontweight="bold")
    fig.tight_layout()
    guardar(fig, "fig16_importancias.png")

    pd.DataFrame({"variable": C.FEATURES_UBICACION,
                  "importancia_permutacion": np.round(pi.importances_mean, 5),
                  "sd": np.round(pi.importances_std, 5)}).sort_values(
        "importancia_permutacion", ascending=False).to_csv(
        C.TAB_DIR / "t12_importancias.csv", index=False)


# --------------------------------------------------------------------------
# TAREA B - regresion logistica binaria
# --------------------------------------------------------------------------
def diagnostico_colinealidad(X):
    """VIF de cada variable de ubicacion.

    Las variables geograficas son colineales por construccion (la longitud y la
    distancia a los cerros son casi la misma cosa). Eso no dana la prediccion,
    pero si vuelve inestable la lectura individual de los coeficientes de la
    regresion logistica, y hay que decirlo antes de interpretarlos.
    """
    from sklearn.linear_model import LinearRegression

    filas = []
    for col in C.FEATURES_UBICACION:
        otras = [c for c in C.FEATURES_UBICACION if c != col]
        r2 = LinearRegression().fit(X[otras], X[col]).score(X[otras], X[col])
        vif = np.inf if r2 >= 1 - 1e-12 else 1.0 / (1.0 - r2)
        filas.append({"variable": col, "r2_contra_las_demas": round(r2, 4),
                      "vif": round(vif, 2)})
    tab = pd.DataFrame(filas).sort_values("vif", ascending=False)
    tab.to_csv(C.TAB_DIR / "t13c_colinealidad.csv", index=False)
    graves = tab[tab["vif"] > 10]["variable"].tolist()
    print("     colinealidad: %d variables con VIF > 10 -> %s"
          % (len(graves), ", ".join(graves) if graves else "ninguna"))
    return tab


def tarea_binaria(df, X, tr, te):
    yb = df["alto_valor"].values
    modelo = Pipeline([
        ("esc", StandardScaler()),
        ("clf", LogisticRegression(max_iter=3000, C=1.0, random_state=C.SEED)),
    ])
    modelo.fit(X.iloc[tr], yb[tr])
    prob = modelo.predict_proba(X.iloc[te])[:, 1]
    pred = (prob >= 0.5).astype(int)

    auc = roc_auc_score(yb[te], prob)
    ap = average_precision_score(yb[te], prob)
    met = {
        "auc_roc": round(auc, 4),
        "average_precision": round(ap, 4),
        "exactitud": round(accuracy_score(yb[te], pred), 4),
        "f1": round(f1_score(yb[te], pred), 4),
        "kappa": round(cohen_kappa_score(yb[te], pred), 4),
        "prevalencia_test": round(float(yb[te].mean()), 4),
    }
    print("     binaria alto valor -> AUC %.3f | AP %.3f | F1 %.3f"
          % (auc, ap, met["f1"]))

    coef = modelo[-1].coef_[0]
    odds = pd.DataFrame({
        "variable": C.FEATURES_UBICACION,
        "coeficiente": np.round(coef, 4),
        "odds_ratio": np.round(np.exp(coef), 4),
        "efecto_pct_por_sd": np.round((np.exp(coef) - 1) * 100, 1),
    }).sort_values("coeficiente")
    odds.to_csv(C.TAB_DIR / "t13_odds_ratios.csv", index=False)

    fig, axes = plt.subplots(1, 3, figsize=(14, 4.3))

    ax = axes[0]
    fpr, tpr, _ = roc_curve(yb[te], prob)
    ax.plot(fpr, tpr, color="#264653", lw=2, label="AUC = %.3f" % auc)
    ax.plot([0, 1], [0, 1], "--", color="grey", lw=1, label="azar")
    ax.set_xlabel("tasa de falsos positivos")
    ax.set_ylabel("tasa de verdaderos positivos")
    ax.set_title("Curva ROC - manzana de alto valor")
    ax.legend(fontsize=8)

    ax = axes[1]
    pr, rc, _ = precision_recall_curve(yb[te], prob)
    ax.plot(rc, pr, color="#e76f51", lw=2, label="AP = %.3f" % ap)
    ax.axhline(yb[te].mean(), ls="--", color="grey", lw=1,
               label="prevalencia = %.2f" % yb[te].mean())
    ax.set_xlabel("sensibilidad (recall)")
    ax.set_ylabel("precision")
    ax.set_title("Precision-sensibilidad")
    ax.legend(fontsize=8)

    ax = axes[2]
    colores = ["#e76f51" if c < 0 else "#2a9d8f" for c in odds["coeficiente"]]
    ax.barh(odds["variable"], odds["coeficiente"], color=colores)
    ax.axvline(0, color="k", lw=0.8)
    ax.tick_params(labelsize=7)
    ax.set_xlabel("coeficiente (variables estandarizadas)")
    ax.set_title("Efecto de la ubicacion sobre el log-odds")

    fig.suptitle("Regresion logistica: probabilidad de que una manzana sea de alto valor",
                 fontsize=12, fontweight="bold")
    fig.tight_layout()
    guardar(fig, "fig17_regresion_logistica.png")

    with open(C.TAB_DIR / "t13b_metricas_binaria.json", "w", encoding="utf-8") as fh:
        json.dump(met, fh, indent=2)
    return modelo, met, odds, prob


# --------------------------------------------------------------------------
# Mapas de resultado
# --------------------------------------------------------------------------
def fig_mapas_prediccion(df, te, pred_mejor, nombre_mejor):
    sub = df.iloc[te].copy()
    sub["pred"] = pred_mejor
    sub["acierto"] = (sub["pred"] == sub["valor_cod"]).astype(int)
    sub["desvio"] = sub["pred"] - sub["valor_cod"]
    sub = sub[sub["lon"].between(*C.URB_LON) & sub["lat"].between(*C.URB_LAT)]

    fig, axes = plt.subplots(1, 3, figsize=(16, 7.5))
    for ax, col, titulo in [
        (axes[0], "valor_cod", "Categoria real"),
        (axes[1], "pred", "Categoria predicha por %s" % nombre_mejor),
    ]:
        ax.scatter(sub["lon"], sub["lat"], s=4, linewidths=0, alpha=0.9,
                   c=[COL_CLASE[int(v)] for v in sub[col]])
        ax.set_title(titulo)

    ax = axes[2]
    err = sub[sub["acierto"] == 0]
    ok = sub[sub["acierto"] == 1]
    ax.scatter(ok["lon"], ok["lat"], s=3, color="#cfd8dc", linewidths=0,
               label="acierto")
    sc = ax.scatter(err["lon"], err["lat"], s=5, c=err["desvio"], cmap="coolwarm",
                    vmin=-3, vmax=3, linewidths=0, label="error")
    ax.set_title("Errores (rojo = sobreestima, azul = subestima)")
    fig.colorbar(sc, ax=ax, label="categorias de desvio", shrink=0.6)

    for ax in axes:
        ax.set_xlim(*C.URB_LON)
        ax.set_ylim(*C.URB_LAT)
        ax.set_aspect(1 / np.cos(np.radians(4.65)))
        ax.set_xlabel("longitud")
        ax.grid(alpha=0.25)
    handles = [plt.Line2D([], [], marker="o", ls="", color=COL_CLASE[i],
                          label=c) for i, c in enumerate(C.CLASES)]
    axes[0].legend(handles=handles, fontsize=7, loc="lower left")
    axes[0].set_ylabel("latitud")

    fig.suptitle("Conjunto de prueba: sectores catastrales nunca vistos por el modelo",
                 fontsize=12, fontweight="bold")
    fig.tight_layout()
    guardar(fig, "fig18_mapas_prediccion.png")

    tabla = sub.groupby("valor_cat", observed=True).agg(
        manzanas=("acierto", "size"),
        exactitud=("acierto", "mean"),
        desvio_medio=("desvio", "mean")).round(3)
    tabla.to_csv(C.TAB_DIR / "t14_error_por_clase.csv")
    return tabla


def superficie_valor(df, modelo_bin, nombre):
    """Superficie continua de probabilidad de alto valor sobre una malla."""
    from scipy.spatial import cKDTree
    from features import features_ubicacion

    paso = 0.0022  # ~245 m
    lons = np.arange(C.URB_LON[0], C.URB_LON[1], paso)
    lats = np.arange(C.URB_LAT[0], C.URB_LAT[1], paso)
    LO, LA = np.meshgrid(lons, lats)
    malla = pd.DataFrame({"lon": LO.ravel(), "lat": LA.ravel()})

    # solo celdas dentro de la ciudad construida
    x_m = df["lon"].values * 110.9
    y_m = df["lat"].values * 110.6
    tree = cKDTree(np.column_stack([x_m, y_m]))
    d, _ = tree.query(np.column_stack([malla["lon"] * 110.9, malla["lat"] * 110.6]))
    dentro = d < 0.45
    malla = malla[dentro].reset_index(drop=True)

    # las variables de vecindad se calculan contra las manzanas reales
    malla = features_ubicacion(malla, referencia=df)
    prob = modelo_bin.predict_proba(malla[C.FEATURES_UBICACION])[:, 1]

    fig, ax = plt.subplots(figsize=(8, 9.5))
    sc = ax.scatter(malla["lon"], malla["lat"], c=prob, s=16, cmap="RdYlBu_r",
                    marker="s", linewidths=0, vmin=0, vmax=1)
    ax.set_xlim(*C.URB_LON)
    ax.set_ylim(*C.URB_LAT)
    ax.set_aspect(1 / np.cos(np.radians(4.65)))
    ax.set_xlabel("longitud")
    ax.set_ylabel("latitud")
    ax.set_title("Superficie modelada de valor del suelo\n"
                 "P(alto valor) segun %s, malla de ~245 m" % nombre)
    fig.colorbar(sc, ax=ax, label="probabilidad de alto valor", shrink=0.6)
    for nom, (lo, la) in C.PUNTOS_REFERENCIA.items():
        ax.plot(lo, la, "k*", markersize=12, markeredgecolor="white")
        ax.annotate(nom.replace("_", " "), (lo, la), fontsize=7.5,
                    fontweight="bold", xytext=(5, 5), textcoords="offset points")
    ax.grid(alpha=0.25)
    guardar(fig, "fig19_superficie_valor.png")

    malla["prob_alto_valor"] = np.round(prob, 4)
    malla[["lon", "lat", "prob_alto_valor"]].to_csv(
        C.TAB_DIR / "t15_superficie_valor.csv", index=False)


# --------------------------------------------------------------------------
def main():
    print("[04] Modelado supervisado")
    df, X, y, grupos = cargar()
    tr, te = split_espacial(X, y, grupos)

    print("\n     -- Ajuste de hiperparametros del arbol de decision --")
    arbol, mejores, res_grid = ajustar_arbol(X.iloc[tr], y[tr], grupos[tr])

    modelos = definir_modelos()
    modelos["Arbol de decision"] = DecisionTreeClassifier(
        random_state=C.SEED, **mejores)

    print("\n     -- Comparacion por validacion cruzada --")
    tab_cv = comparar_cv(modelos, X, y, grupos)

    print("\n     -- Evaluacion sobre sectores no vistos --")
    tab_test, ajustados, predicciones = evaluar_test(modelos, X, y, tr, te)

    nombre_mejor = tab_test.iloc[0]["modelo"]
    mejor = ajustados[nombre_mejor]
    print("\n     Mejor modelo: %s" % nombre_mejor)

    fig_comparacion(tab_cv, tab_test)
    fig_matrices(predicciones, y[te], list(tab_test["modelo"]))

    arbol_fit = ajustados["Arbol de decision"]
    arbol_fit._X_tr, arbol_fit._y_tr = X.iloc[tr], y[tr]
    fig_arbol(arbol_fit, res_grid)
    fig_importancias(nombre_mejor, mejor, X.iloc[te], y[te])

    print("\n     -- Tarea binaria: regresion logistica --")
    vif = diagnostico_colinealidad(X)
    modelo_bin, met_bin, odds, _ = tarea_binaria(df, X, tr, te)

    err_clase = fig_mapas_prediccion(df, te, predicciones[nombre_mejor], nombre_mejor)
    superficie_valor(df, modelo_bin, "regresion logistica")

    rep = classification_report(y[te], predicciones[nombre_mejor],
                                target_names=C.CLASES, digits=3)
    with open(C.TAB_DIR / "t16_reporte_clasificacion.txt", "w",
              encoding="utf-8") as fh:
        fh.write("Modelo: %s\n\n%s" % (nombre_mejor, rep))

    for nombre, mod in ajustados.items():
        slug = nombre.lower().replace(" ", "_").replace("(", "").replace(")", "")
        slug = slug.replace("=", "").replace(",", "")
        dump(mod, C.MOD_DIR / ("%s.joblib" % slug), compress=3)
    dump(modelo_bin, C.MOD_DIR / "logistica_binaria.joblib", compress=3)

    resumen = {
        "n_manzanas": int(len(df)),
        "n_train": int(len(tr)), "n_test": int(len(te)),
        "sectores_train": int(len(set(grupos[tr]))),
        "sectores_test": int(len(set(grupos[te]))),
        "mejor_modelo": nombre_mejor,
        "metricas_test": tab_test.to_dict("records"),
        "comparacion_cv": tab_cv.to_dict("records"),
        "arbol_mejores_parametros": {k: (None if v is None else v)
                                     for k, v in mejores.items()},
        "binaria": met_bin,
        "error_por_clase": err_clase.reset_index().to_dict("records"),
        "vif_max": float(vif["vif"].max()),
        "variables_vif_alto": vif[vif["vif"] > 10]["variable"].tolist(),
    }
    with open(C.OUT_DIR / "resumen_modelado.json", "w", encoding="utf-8") as fh:
        json.dump(resumen, fh, indent=2, ensure_ascii=False, default=str)

    print("\n     Reporte de clasificacion (%s):\n" % nombre_mejor)
    print(rep)
    print("     modelos guardados en outputs/modelos/")


if __name__ == "__main__":
    main()

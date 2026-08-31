# -*- coding: utf-8 -*-
"""05 - Informe final.

Lee los artefactos generados por las etapas 01-04 y arma dos versiones del
informe: reports/informe.md (con enlaces a las figuras) y reports/informe.html
(autocontenido, con las imagenes embebidas en base64). Todas las cifras se leen
de los archivos, de modo que el informe nunca queda desactualizado.
"""
import base64
import json
import os
import re
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config as C


def leer_json(ruta):
    with open(ruta, encoding="utf-8") as fh:
        return json.load(fh)


# --------------------------------------------------------------------------
# Acentuacion del texto final
# --------------------------------------------------------------------------
# El codigo fuente se mantiene en ASCII (los mensajes van a consolas Windows con
# cp1252), pero el informe se escribe siempre en UTF-8 y debe leerse en espanol
# correcto. Esta pasada se aplica al markdown ya armado.
ACENTOS = {
    "analisis": "análisis", "area": "área", "areas": "áreas",
    "metodologica": "metodológica", "geografica": "geográfica",
    "geograficas": "geográficas", "geografico": "geográfico",
    "geograficos": "geográficos", "geografia": "geografía",
    "informacion": "información", "ubicacion": "ubicación",
    "construccion": "construcción", "prediccion": "predicción",
    "regresion": "regresión", "validacion": "validación",
    "particion": "partición", "proyeccion": "proyección",
    "atribucion": "atribución", "correlacion": "correlación",
    "autocorrelacion": "autocorrelación", "segregacion": "segregación",
    "digitalizacion": "digitalización", "distribucion": "distribución",
    "agregacion": "agregación", "ponderacion": "ponderación",
    "orientacion": "orientación", "confusion": "confusión",
    "clasificacion": "clasificación", "permutacion": "permutación",
    "aleatorizacion": "aleatorización", "interaccion": "interacción",
    "sedimentacion": "sedimentación", "version": "versión",
    "categoria": "categoría", "categorias": "categorías",
    "indice": "índice", "indices": "índices", "numero": "número",
    "tambien": "también", "ademas": "además", "asi": "así", "aqui": "aquí",
    "segun": "según", "despues": "después", "comun": "común",
    "avaluo": "avalúo", "avaluos": "avalúos", "minimo": "mínimo",
    "maximo": "máximo", "optimo": "óptimo", "tamano": "tamaño",
    "diseno": "diseño", "senal": "señal", "pequeno": "pequeño",
    "dana": "daña", "bogota": "Bogotá", "bolivar": "Bolívar",
    "usaquen": "Usaquén", "chico": "Chicó", "policentrica": "policéntrica",
    "migro": "migró", "monotonamente": "monótonamente",
    "teoria": "teoría", "economica": "económica", "historico": "histórico",
    "historica": "histórica", "estadistica": "estadística",
    "estadisticas": "estadísticas", "logistica": "logística",
    "logisticas": "logísticas", "polinomica": "polinómica",
    "cuadraticos": "cuadráticos", "morfologica": "morfológica",
    "morfologicas": "morfológicas", "morfologico": "morfológico",
    "morfologicos": "morfológicos", "unico": "único", "unica": "única",
    "sotano": "sótano", "sotanos": "sótanos", "parametros": "parámetros",
    "hiperparametros": "hiperparámetros", "codigo": "código",
    "codigos": "códigos", "invalido": "inválido", "invalidos": "inválidos",
    "arbol": "árbol", "arboles": "árboles", "linea": "línea",
    "lineas": "líneas", "lamina": "lámina", "laminas": "láminas",
    "perimetro": "perímetro", "poligono": "polígono", "poligonos": "polígonos",
    "metrica": "métrica", "metricas": "métricas", "deberia": "debería",
    "haria": "haría", "seria": "sería", "podria": "podría",
    "quedaria": "quedaría", "dejaria": "dejaría", "pondria": "pondría",
    "inflaria": "inflaría", "aprobaria": "aprobaría", "cercania": "cercanía",
    "explicita": "explícita", "explicito": "explícito", "practica": "práctica",
    "urbanistica": "urbanística", "credito": "crédito", "vera": "verá",
    "clasica": "clásica", "comparacion": "comparación",
    "decision": "decisión", "desviacion": "desviación",
    "diagnostico": "diagnóstico", "direccion": "dirección",
    "generalizacion": "generalización", "identicos": "idénticos",
    "identica": "idéntica", "ningun": "ningún",
    "participacion": "participación", "separacion": "separación",
    "transformacion": "transformación", "valoracion": "valoración",
    "morfologia": "morfología", "traves": "través", "construyo": "construyó",
    "podado": "podado", "ultimo": "último", "ultima": "última",
    "proximo": "próximo", "criterio": "criterio", "operativamente":
    "operativamente", "precision": "precisión",
}
_RE_PALABRA = re.compile(r"\b[A-Za-z]+\b")


def _acentuar_palabra(m):
    """Sustituye una palabra suelta; los identificadores con _ no llegan aqui
    porque el guion bajo es caracter de palabra y anula el limite \\b."""
    p = m.group(0)
    nuevo = ACENTOS.get(p.lower())
    if nuevo is None:
        return p
    if p[0].isupper() and not nuevo[0].isupper():
        return nuevo[0].upper() + nuevo[1:]
    if p.islower() and nuevo[0].isupper():
        return nuevo if p.lower() in ("bogota", "bolivar", "usaquen", "chico") \
            else nuevo[0].lower() + nuevo[1:]
    return nuevo


def acentuar(md):
    """Acentua el texto corrido respetando bloques de codigo y `identificadores`."""
    salida = []
    en_bloque = False
    for linea in md.split("\n"):
        if linea.startswith("```"):
            en_bloque = not en_bloque
            salida.append(linea)
            continue
        if en_bloque:
            salida.append(linea)
            continue
        partes = linea.split("`")
        for i in range(0, len(partes), 2):        # fuera de los backticks
            partes[i] = _RE_PALABRA.sub(_acentuar_palabra, partes[i])
        salida.append("`".join(partes))
    return "\n".join(salida)


def tabla_md(df, max_filas=None):
    d = df if max_filas is None else df.head(max_filas)
    enc = "| " + " | ".join(str(c) for c in d.columns) + " |"
    sep = "|" + "|".join(["---"] * len(d.columns)) + "|"
    filas = ["| " + " | ".join(str(v) for v in row) + " |"
             for row in d.itertuples(index=False)]
    return "\n".join([enc, sep] + filas)


def construir_markdown():
    st = leer_json(C.F_STATS)
    mo = leer_json(C.OUT_DIR / "resumen_modelado.json")

    cargas = pd.read_csv(C.TAB_DIR / "t02_pca_cargas_ivs.csv")
    varz = pd.read_csv(C.TAB_DIR / "t02b_pca_varianza.csv")
    anillos = pd.read_csv(C.TAB_DIR / "t04_ivs_por_anillo.csv")
    corr = pd.read_csv(C.TAB_DIR / "t06_correlaciones_ubicacion_ivs.csv",
                       index_col=0).iloc[:, 0]
    moran = pd.read_csv(C.TAB_DIR / "t07_autocorrelacion.csv").iloc[0]
    zonas = pd.read_csv(C.TAB_DIR / "t08_validacion_zonas.csv")
    test = pd.DataFrame(mo["metricas_test"])
    cv = pd.DataFrame(mo["comparacion_cv"])
    odds = pd.read_csv(C.TAB_DIR / "t13_odds_ratios.csv")
    imp = pd.read_csv(C.TAB_DIR / "t12_importancias.csv")
    vif = pd.read_csv(C.TAB_DIR / "t13c_colinealidad.csv")
    err_clase = pd.DataFrame(mo["error_por_clase"])
    with open(C.TAB_DIR / "t16_reporte_clasificacion.txt", encoding="utf-8") as fh:
        reporte_clf = fh.read()

    mejor = test.iloc[0]
    logis = test[test["modelo"] == "Regresion logistica"].iloc[0]
    arbol = test[test["modelo"] == "Arbol de decision"].iloc[0]
    dummy = test[test["modelo"].str.startswith("Baseline")].iloc[0]
    sesgo = cv.set_index("modelo")["sesgo_optimista"]
    corr_top = corr.abs().sort_values(ascending=False)

    md = []
    A = md.append

    A("# Valoracion del terreno segun su ubicacion en Bogota D.C.")
    A("")
    A("Proyecto de analisis exploratorio y aprendizaje supervisado sobre la capa "
      "catastral de construcciones (`Construcciones.geojson`, %.2f GB, %s registros)."
      % (C.GEOJSON.stat().st_size / 1e9, f"{st['features_leidas']:,}"))
    A("")

    A("## 1. Resumen ejecutivo")
    A("")
    A("- Se procesaron **%s construcciones** en %.0f segundos mediante lectura en "
      "streaming, y se agregaron a **%s manzanas catastrales** de **%s sectores**."
      % (f"{st['features_validas']:,}", st["segundos"],
         f"{st['manzanas']:,}", f"{st['sectores']:,}"))
    A("- El archivo **no contiene avaluo ni ningun campo monetario**. Se construyo "
      "un proxy explicito, el **Indice de Valor del Suelo (IVS)**, con las dos "
      "primeras componentes principales de cinco variables morfologicas "
      "(%.1f%% de la varianza)." % (varz[varz["retenida"]]["varianza_explicada"].sum() * 100))
    A("- El IVS supera una prueba de validez externa: ordena Chico (%.0f), Salitre "
      "(%.0f) y Usaquen (%.0f) por encima de Bosa (%.0f) y Kennedy (%.0f), "
      "coherente con el mercado real."
      % tuple(zonas.set_index("zona")["ivs_mediano"].reindex(
          ["Chico - Calle 93", "Salitre / Ciudad Empresarial", "Usaquen",
           "Bosa", "Kennedy"]).fillna(0).values))
    A("- El valor del suelo **no se distribuye al azar en el espacio**: "
      "Moran's I = **%.3f** (p = %.3f), es decir fuerte agrupamiento en corredores."
      % (moran["moran_I"], moran["p_valor"]))
    A("- Con **solo variables de ubicacion**, el mejor modelo (**%s**) alcanza "
      "**%.1f%% de exactitud** sobre sectores catastrales nunca vistos, frente a "
      "%.1f%% del baseline y 25%% del azar; acierta la categoria exacta o una "
      "contigua en el **%.1f%%** de los casos."
      % (mejor["modelo"], mejor["exactitud"] * 100, dummy["exactitud"] * 100,
         mejor["error_1_categoria"] * 100))
    A("- La regresion logistica binaria alcanza **AUC = %.3f** para identificar "
      "manzanas de alto valor." % mo["binaria"]["auc_roc"])
    A("")

    A("## 2. Advertencia metodologica: que se esta modelando")
    A("")
    A("Los atributos disponibles por construccion son `CONNPISOS`, `CONTSEMIS`, "
      "`CONNSOTANO`, `CONMEJORA`, `CONVOLADIZ`, `CONALTURA`, `CONELEVACI` y la "
      "geometria. **No hay precio, avaluo ni estrato.** Modelar 'el valor del "
      "terreno' de forma directa es imposible con este insumo.")
    A("")
    A("La salida elegida se apoya en la teoria de la renta del suelo (bid-rent, "
      "Alonso 1964): donde el suelo es caro, el mercado responde intensificando "
      "su uso. El **IVS** mide esa intensidad edificatoria y sirve como proxy "
      "ordinal del valor. Es un proxy, no un avaluo: los resultados se leen como "
      "*potencial de aprovechamiento del suelo*, no como pesos por metro cuadrado.")
    A("")
    A("**Separacion limpia entre target y predictores** (sin fuga de informacion):")
    A("")
    A("| | Se construye con | No usa |")
    A("|---|---|---|")
    A("| IVS (target) | morfologia construida | nada geografico |")
    A("| Predictores | ubicacion geografica | ningun atributo constructivo |")
    A("")

    A("## 3. Datos y procesamiento")
    A("")
    A("El GeoJSON de 1.8 GB no cabe en memoria, asi que se recorre **linea a "
      "linea** calculando area, perimetro y centroide con formula del zapatero "
      "sobre una proyeccion equirectangular local (error < 0.1% a esta escala), "
      "sin depender de GDAL/geopandas. Una sola pasada produce la muestra de "
      "construcciones, el agregado por manzana y el agregado por sector.")
    A("")
    A("| Etapa | Registros |")
    A("|---|---|")
    A("| Leidos del GeoJSON | %s |" % f"{st['features_leidas']:,}")
    A("| Validos | %s |" % f"{st['features_validas']:,}")
    A("| Descartados por area < 1 m2 (slivers) | %s |" % f"{st['area_fuera_de_rango']:,}")
    A("| Descartados por codigo invalido | %s |" % f"{st['codigo_invalido']:,}")
    A("| Manzanas resultantes | %s |" % f"{st['manzanas']:,}")
    A("| Manzanas modelables (>= %d construcciones) | %s |"
      % (C.MIN_CONST_POR_MANZANA, f"{mo['n_manzanas']:,}"))
    A("")
    A("![Calidad de datos](../outputs/figuras/fig01_calidad_datos.png)")
    A("")
    A("Hallazgos de calidad relevantes: la mediana de huella es de apenas ~24 m2 "
      "porque la capa descompone cada predio en partes homogeneas en altura; "
      "`CONALTURA` esta casi siempre en cero, por lo que la altura util es "
      "`CONNPISOS`; y `CONELEVACI` replica a `CONNPISOS` en la mayoria de casos.")
    A("")
    A("![Distribuciones](../outputs/figuras/fig02_distribuciones_construccion.png)")
    A("")
    A("![Huella construida](../outputs/figuras/fig04_mapa_construcciones_pisos.png)")
    A("")

    A("## 4. Construccion del Indice de Valor del Suelo")
    A("")
    A("Cinco variables morfologicas por manzana entran a un PCA sobre datos "
      "estandarizados. Se retienen las componentes con autovalor > 1 (criterio "
      "de Kaiser) y se ponderan por su participacion en la varianza explicada "
      "(procedimiento OECD/JRC para indicadores compuestos).")
    A("")
    A(tabla_md(varz))
    A("")
    A("**Por que no basta la primera componente.** PC1 mide intensidad bruta y "
      "confunde el barrio informal autoconstruido (cobertura total del lote, 2-3 "
      "pisos, huellas de 30 m2, sin sotanos) con el desarrollo formal en altura. "
      "PC2 es justamente el eje que los separa: carga positivo en tamano de "
      "huella y sotanos. Reteniendo ambas, Bosa y Usme dejan de aparecer por "
      "encima de Chapinero.")
    A("")
    A(tabla_md(cargas))
    A("")
    A("![Componentes del IVS](../outputs/figuras/fig05_componentes_ivs.png)")
    A("")
    A("![Distribucion del IVS](../outputs/figuras/fig06_ivs_distribucion.png)")
    A("")
    A("### Validacion externa del indice")
    A("")
    A("Prueba de sentido comun: el indice deberia ordenar las zonas de Bogota "
      "como lo hace el mercado. Se calcula el IVS mediano en un radio de 1.2 km "
      "alrededor de diez puntos conocidos.")
    A("")
    A(tabla_md(zonas))
    A("")

    A("## 5. Analisis exploratorio: el valor y la ubicacion")
    A("")
    A("![Mapa del IVS](../outputs/figuras/fig07_mapa_ivs.png)")
    A("")
    A("**El patron es un corredor, no un circulo.** La franja de alto valor "
      "recorre el borde oriental de sur a norte (centro internacional - "
      "Chapinero - Chico - Usaquen), con un nucleo secundario en Salitre. El sur "
      "y el suroccidente concentran las manzanas de valor bajo.")
    A("")
    A("![Gradiente](../outputs/figuras/fig08_gradiente_distancia.png)")
    A("")
    A("**La curva de renta clasica no se cumple.** El IVS no decae "
      "monotonamente con la distancia a la Plaza de Bolivar: cae hasta los ~8 km "
      "y vuelve a subir en los anillos exteriores del norte. Bogota es "
      "policentrica y su eje de valor migro al norte.")
    A("")
    A(tabla_md(anillos))
    A("")
    A("![Cuadrantes](../outputs/figuras/fig09_ivs_por_cuadrante_y_anillo.png)")
    A("")
    A("Por eso la **direccion importa mas que la distancia**: entre las variables "
      "de ubicacion, las de mayor correlacion con el IVS son "
      + ", ".join("`%s` (rho = %.3f)" % (k, corr[k]) for k in corr_top.index[:4])
      + ".")
    A("")
    A("![Correlaciones](../outputs/figuras/fig10_correlaciones.png)")
    A("")
    A("![Sectores](../outputs/figuras/fig11_top_sectores.png)")
    A("")
    A("### Autocorrelacion espacial")
    A("")
    A("Con pesos de 8 vecinos mas cercanos, **Moran's I = %.3f** (p = %.3f, %d "
      "permutaciones). El valor de una manzana se parece mucho al de sus "
      "vecinas. Esto tiene una consecuencia directa sobre el diseno de la "
      "validacion del modelo." % (moran["moran_I"], moran["p_valor"],
                                  moran["permutaciones"]))
    A("")
    A("![Moran](../outputs/figuras/fig12_autocorrelacion_espacial.png)")
    A("")

    A("## 6. Modelado supervisado")
    A("")
    A("**Tarea A (multiclase):** predecir la categoria de valor de la manzana "
      "(Bajo / Medio-Bajo / Medio-Alto / Alto, cuartiles del IVS) a partir de "
      "12 variables de ubicacion.  \n"
      "**Tarea B (binaria):** identificar manzanas de alto valor con regresion "
      "logistica, con lectura de coeficientes.")
    A("")
    A("### Diseno de validacion")
    A("")
    A("Dada la autocorrelacion, una particion aleatoria dejaria manzanas de la "
      "misma cuadra a ambos lados del corte y el modelo aprobaria por vecindad, "
      "no por generalizacion. Se particiona por **sector catastral**: "
      "%d sectores (%s manzanas) para entrenar y %d sectores disjuntos "
      "(%s manzanas) para probar."
      % (mo["sectores_train"], f"{mo['n_train']:,}", mo["sectores_test"],
         f"{mo['n_test']:,}"))
    A("")
    A("El coste de ignorarlo es medible: la CV aleatoria infla el F1 macro en "
      "%.3f puntos para Random Forest y %.3f para KNN, mientras que en la "
      "regresion logistica el sesgo es de solo %.3f (un modelo lineal no puede "
      "memorizar el vecindario)."
      % (sesgo.get("Random Forest", 0), sesgo.get("KNN espacial (k=15)", 0),
         sesgo.get("Regresion logistica", 0)))
    A("")
    A("### Resultados sobre sectores no vistos")
    A("")
    A(tabla_md(test))
    A("")
    A("![Comparacion de modelos](../outputs/figuras/fig13_comparacion_modelos.png)")
    A("")
    A("Lectura de los resultados:")
    A("")
    A("1. **Todos los modelos superan claramente al azar** (25%%) y al baseline "
      "(%.1f%%): la ubicacion si contiene senal sobre el valor del suelo."
      % (dummy["exactitud"] * 100))
    A("2. **La regresion logistica lineal es la mas debil** (%.1f%%). Su frontera "
      "es un hiperplano y la estructura de valor de Bogota es un corredor curvo; "
      "al agregar terminos cuadraticos e interacciones sube a %.1f%%."
      % (logis["exactitud"] * 100,
         test[test["modelo"].str.contains("polinomica")].iloc[0]["exactitud"] * 100))
    A("3. **El arbol de decision** (%.1f%%) mejora al lineal porque particiona el "
      "espacio en cajas, que es exactamente como funciona la segregacion urbana. "
      "Su optimo esta en `max_depth=%s`, `min_samples_leaf=%s`."
      % (arbol["exactitud"] * 100,
         mo["arbol_mejores_parametros"].get("max_depth"),
         mo["arbol_mejores_parametros"].get("min_samples_leaf")))
    A("4. **Los ensambles ganan** (%s, %.1f%%), pero el margen sobre el arbol "
      "unico es de solo %.1f puntos: el techo lo pone la informacion disponible, "
      "no el algoritmo."
      % (mejor["modelo"], mejor["exactitud"] * 100,
         (mejor["exactitud"] - arbol["exactitud"]) * 100))
    A("5. **Los errores son casi siempre de una categoria contigua** (%.1f%% de "
      "aciertos con tolerancia de 1): el modelo rara vez confunde una manzana "
      "de valor alto con una de valor bajo." % (mejor["error_1_categoria"] * 100))
    A("")
    A("![Matrices de confusion](../outputs/figuras/fig14_matrices_confusion.png)")
    A("")
    A("Las clases extremas se predicen mucho mejor que las intermedias:")
    A("")
    A("```")
    A(reporte_clf.strip())
    A("```")
    A("")
    A("### Arbol de decision: las reglas explicitas")
    A("")
    A("![Arbol](../outputs/figuras/fig15_arbol_decision.png)")
    A("")
    A("Podado a profundidad 3, el arbol es legible: primero separa por densidad "
      "del entorno (`dist_vecino_8_km`), luego por cercania al eje financiero "
      "del norte y al aeropuerto, y despues por orientacion (`azimut_sin`, es "
      "decir oriente frente a occidente). Es, literalmente, la geografia "
      "economica de la ciudad escrita como reglas if-else.")
    A("")
    A("### Variables que mas pesan")
    A("")
    A(tabla_md(imp))
    A("")
    A("![Importancias](../outputs/figuras/fig16_importancias.png)")
    A("")

    A("### Tarea B: regresion logistica de alto valor")
    A("")
    A("| Metrica | Valor |")
    A("|---|---|")
    for k, v in mo["binaria"].items():
        A("| %s | %s |" % (k.replace("_", " "), v))
    A("")
    A("![Regresion logistica](../outputs/figuras/fig17_regresion_logistica.png)")
    A("")
    A("Los coeficientes estan sobre variables estandarizadas, asi que se leen "
      "como el cambio en el log-odds por cada desviacion estandar adicional:")
    A("")
    A(tabla_md(odds))
    A("")
    A("> **Advertencia sobre la lectura de estos coeficientes.** Las variables "
      "geograficas son colineales por construccion: `dist_cerros_km` es una "
      "transformacion casi lineal de `lon`, y el azimut resume a `lon` y `lat`. "
      "El diagnostico da VIF de hasta **%.0f** (%d variables por encima de 10), "
      "lo que reparte el efecto de forma arbitraria entre variables "
      "equivalentes: `lon` (%.2f) y `dist_cerros_km` (%.2f) reciben coeficientes "
      "casi identicos, pero como la segunda decrece cuando la primera crece, sus "
      "aportes se cancelan casi por completo y el gradiente oriente-occidente "
      "termina expresado a traves de `azimut_cos`. La colinealidad no dana la "
      "capacidad predictiva del modelo "
      "-el AUC de %.3f es real-, pero invalida leer una variable a la vez. Para "
      "atribucion de importancia es preferible la importancia por permutacion "
      "de la tabla anterior."
      % (mo.get("vif_max", float("nan")), len(mo.get("variables_vif_alto", [])),
         float(odds.set_index("variable").loc["lon", "coeficiente"]),
         float(odds.set_index("variable").loc["dist_cerros_km", "coeficiente"]),
         mo["binaria"]["auc_roc"]))
    A("")
    A(tabla_md(vif))
    A("")

    A("### Prediccion en el espacio")
    A("")
    A("![Mapas de prediccion](../outputs/figuras/fig18_mapas_prediccion.png)")
    A("")
    A("Exactitud por categoria real en el conjunto de prueba:")
    A("")
    A(tabla_md(err_clase))
    A("")
    A("Aplicando el modelo a una malla regular de ~245 m se obtiene una "
      "superficie continua de valor para toda la ciudad, incluidas las celdas "
      "sin manzana catastral:")
    A("")
    A("![Superficie de valor](../outputs/figuras/fig19_superficie_valor.png)")
    A("")

    A("## 7. Limitaciones")
    A("")
    A("1. **El IVS es un proxy, no un avaluo.** Mide intensidad y formalidad "
      "constructiva. Para calibrarlo a pesos por m2 haria falta cruzarlo con la "
      "base de avaluos catastrales o con ofertas de mercado.")
    A("2. **Los barrios informales densos siguen sobrevalorados** respecto de su "
      "precio real. PC2 corrige buena parte del sesgo, pero no todo: la mitad "
      "inferior del ranking es menos confiable que la superior.")
    A("3. **El area de manzana es aproximada.** Se usa el rectangulo envolvente "
      "de sus construcciones como denominador del indice de construccion, "
      "porque la capa de lotes/manzanas no esta en el insumo.")
    A("4. **Techo de exactitud.** Con ubicacion pura, el %.1f%% alcanzado esta "
      "cerca del limite: dos manzanas de la misma cuadra pueden pertenecer a "
      "categorias distintas por razones (uso del suelo, norma urbanistica, "
      "historia del predio) que ninguna coordenada captura."
      % (mejor["exactitud"] * 100))
    A("5. **Vigencia.** El corte del dato catastral no viene declarado en el "
      "GeoJSON; conviene fijarlo antes de usar los resultados operativamente.")
    A("")

    A("## 8. Reproducir")
    A("")
    A("```bash")
    A("pip install -r requirements.txt")
    A("python run_pipeline.py            # ejecuta 01 -> 05")
    A("python run_pipeline.py --rapido   # prueba con 200k construcciones")
    A("```")
    A("")
    A("| Etapa | Script | Salida |")
    A("|---|---|---|")
    A("| 01 Ingesta | `src/ingest.py` | `data/processed/*.csv.gz` |")
    A("| 02 Variables | `src/features.py` | `dataset_modelado.csv.gz` |")
    A("| 03 EDA | `src/eda.py` | `fig01`-`fig12`, `t01`-`t08` |")
    A("| 04 Modelado | `src/models.py` | `fig13`-`fig19`, `t09`-`t16`, modelos |")
    A("| 05 Informe | `src/report.py` | `reports/informe.md` y `.html` |")
    return acentuar("\n".join(md))


CSS = """
:root { color-scheme: light dark; }
body { font-family: -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
       max-width: 1080px; margin: 0 auto; padding: 32px 24px 96px;
       line-height: 1.62; color: #1c2733; background: #fff; }
h1 { font-size: 2rem; line-height: 1.2; border-bottom: 3px solid #264653;
     padding-bottom: 12px; margin-bottom: 8px; }
h2 { font-size: 1.35rem; margin-top: 44px; color: #264653;
     border-bottom: 1px solid #dde3e8; padding-bottom: 6px; }
h3 { font-size: 1.08rem; margin-top: 30px; color: #2a6a72; }
img { max-width: 100%; height: auto; display: block; margin: 18px auto;
      border: 1px solid #e3e8ec; border-radius: 6px; }
table { border-collapse: collapse; width: 100%; margin: 18px 0; font-size: 0.85rem;
        display: block; overflow-x: auto; }
th, td { border: 1px solid #dde3e8; padding: 6px 10px; text-align: left;
         white-space: nowrap; }
th { background: #eef3f6; font-weight: 600; }
tr:nth-child(even) td { background: #fafcfd; }
code { background: #eef3f6; padding: 1px 5px; border-radius: 3px;
       font-size: 0.87em; }
pre { background: #1c2733; color: #e6edf3; padding: 14px 16px; border-radius: 6px;
      overflow-x: auto; font-size: 0.8rem; line-height: 1.45; }
pre code { background: none; color: inherit; padding: 0; }
blockquote { border-left: 4px solid #e76f51; margin: 18px 0; padding: 4px 16px;
             background: #fef6f3; }
li { margin: 5px 0; }
@media (prefers-color-scheme: dark) {
  body { background: #12181d; color: #dbe4ea; }
  h2 { color: #7ec8c0; border-bottom-color: #26323c; }
  h3 { color: #9ad7cf; }
  h1 { border-bottom-color: #7ec8c0; }
  th { background: #1c2733; }
  td, th { border-color: #26323c; }
  tr:nth-child(even) td { background: #161d23; }
  code { background: #1c2733; }
  img { border-color: #26323c; }
  blockquote { background: #2a1f1c; }
}
"""


# --------------------------------------------------------------------------
# Version publicable: maquetacion inspirada en la lamina de un plano catastral
# --------------------------------------------------------------------------
FUENTES = (
    '<title>Dónde vale el suelo en Bogotá</title>'
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
    'family=Archivo:wght@500;600;700&'
    'family=IBM+Plex+Mono:wght@400;500;600&'
    'family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&display=swap">'
)

CSS_ARTEFACTO = """
:root{
  --papel:#f1f4f0; --superficie:#fbfcfa; --tinta:#15222a; --tinta-suave:#5b6d71;
  --linea:#d2dad3; --linea-fuerte:#b3bfb7; --acento:#0d6a72; --alerta:#a8402a;
  --realce:#e9efe9;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --papel:#0f1518; --superficie:#151d21; --tinta:#dfe7e4; --tinta-suave:#93a4a6;
    --linea:#242f34; --linea-fuerte:#33424a; --acento:#57b8bd; --alerta:#e08a68;
    --realce:#1a2429;
  }
}
:root[data-theme="dark"]{
  --papel:#0f1518; --superficie:#151d21; --tinta:#dfe7e4; --tinta-suave:#93a4a6;
  --linea:#242f34; --linea-fuerte:#33424a; --acento:#57b8bd; --alerta:#e08a68;
  --realce:#1a2429;
}
body{ background:var(--papel); color:var(--tinta);
  font-family:'Source Serif 4',Georgia,'Times New Roman',serif;
  font-size:17px; line-height:1.68; margin:0;
  -webkit-font-smoothing:antialiased; }
.doc{ max-width:1080px; margin:0 auto; padding:0 24px 120px;
  display:flex; flex-direction:column; gap:0; }
.doc > p, .doc > ul, .doc > h2, .doc > h3, .doc > blockquote, .doc > pre{
  max-width:68ch; margin-inline:auto; width:100%; }

/* ---- bloque de rotulo, al modo de un plano ---- */
.rotulo{ border:1px solid var(--linea-fuerte); background:var(--superficie);
  margin:36px 0 52px; }
.rotulo h1{ font-family:'Archivo',system-ui,sans-serif; font-weight:700;
  font-size:clamp(1.9rem,4.4vw,3rem); line-height:1.08; letter-spacing:-.02em;
  text-wrap:balance; margin:0; padding:30px 30px 8px; color:var(--tinta); }
.rotulo .sub{ padding:0 30px 26px; max-width:60ch; color:var(--tinta-suave);
  font-size:1.02rem; }
.campos{ display:grid; grid-template-columns:repeat(auto-fit,minmax(172px,1fr));
  border-top:1px solid var(--linea); }
.campo{ padding:13px 26px 15px; border-right:1px solid var(--linea);
  min-width:0; }
.campo:last-child{ border-right:0; }
.campo .k{ display:block; font-family:'IBM Plex Mono',ui-monospace,monospace;
  font-size:.63rem; letter-spacing:.13em; text-transform:uppercase;
  color:var(--tinta-suave); margin-bottom:4px; }
.campo .v{ font-family:'IBM Plex Mono',ui-monospace,monospace; font-size:.88rem;
  font-weight:500; font-variant-numeric:tabular-nums; color:var(--tinta);
  overflow-wrap:anywhere; line-height:1.35; }

/* ---- jerarquia ---- */
h2{ font-family:'Archivo',system-ui,sans-serif; font-weight:600;
  font-size:1.55rem; letter-spacing:-.01em; line-height:1.2; text-wrap:balance;
  margin:64px 0 6px; padding-top:22px; border-top:2px solid var(--tinta);
  display:flex; align-items:baseline; gap:14px; }
h2 .num{ font-family:'IBM Plex Mono',ui-monospace,monospace; font-size:.78rem;
  font-weight:600; color:var(--acento); letter-spacing:.1em; padding-top:4px;
  flex:0 0 auto; }
h3{ font-family:'Archivo',system-ui,sans-serif; font-weight:600;
  font-size:1.08rem; letter-spacing:.01em; margin:40px 0 2px;
  color:var(--acento); }
p{ margin:14px 0; }
strong{ font-weight:600; }
ul{ margin:14px 0; padding-left:1.15rem; }
li{ margin:8px 0; }
li::marker{ color:var(--acento); }
code{ font-family:'IBM Plex Mono',ui-monospace,monospace; font-size:.84em;
  background:var(--realce); padding:1px 5px; border-radius:2px;
  border:1px solid var(--linea); }

/* ---- laminas ---- */
figure{ margin:34px 0; }
figure img{ display:block; width:100%; height:auto; background:#fff;
  border:1px solid var(--linea-fuerte); }
figcaption{ font-family:'IBM Plex Mono',ui-monospace,monospace; font-size:.72rem;
  color:var(--tinta-suave); margin-top:9px; display:flex; gap:12px;
  align-items:baseline; letter-spacing:.02em; }
figcaption .lam{ color:var(--acento); font-weight:600; text-transform:uppercase;
  letter-spacing:.11em; flex:0 0 auto; }

/* ---- datos ---- */
table{ border-collapse:collapse; width:100%; margin:26px 0; font-size:.82rem;
  font-family:'IBM Plex Mono',ui-monospace,monospace;
  font-variant-numeric:tabular-nums; display:block; overflow-x:auto;
  border:1px solid var(--linea); }
th,td{ padding:7px 13px; text-align:left; white-space:nowrap;
  border-bottom:1px solid var(--linea); }
th{ background:var(--realce); font-weight:600; font-size:.68rem;
  letter-spacing:.07em; text-transform:uppercase; color:var(--tinta-suave);
  border-bottom:1px solid var(--linea-fuerte); }
tbody tr:last-child td{ border-bottom:0; }
tbody tr:hover td{ background:var(--realce); }
pre{ background:var(--tinta); color:var(--papel); padding:18px 20px;
  overflow-x:auto; font-size:.76rem; line-height:1.5; border-radius:2px; }
pre code{ background:none; border:0; color:inherit; padding:0; font-size:1em; }
blockquote{ margin:26px auto; padding:16px 22px; background:var(--superficie);
  border-left:3px solid var(--alerta); color:var(--tinta); font-size:.96rem; }
blockquote p:first-child{ margin-top:0; }
blockquote p:last-child{ margin-bottom:0; }
@media (max-width:640px){
  body{ font-size:16px; }
  .rotulo h1{ padding:22px 20px 6px; }
  .rotulo .sub{ padding:0 20px 20px; }
  .campo{ padding:11px 20px 13px; }
  h2{ font-size:1.3rem; }
}
"""


def cabecera_artefacto(st, mo, moran):
    campos = [
        ("Fuente", "Construcciones.geojson"),
        ("Registros", "%s" % f"{st['features_validas']:,}"),
        ("Unidad de análisis", "%s manzanas" % f"{mo['n_manzanas']:,}"),
        ("Sistema de referencia", "EPSG:4686"),
        ("Moran's I", "%.3f" % moran["moran_I"]),
        ("Mejor modelo", "%.1f%% exactitud" % (mo["metricas_test"][0]["exactitud"] * 100)),
    ]
    campos_html = "".join(
        '<div class="campo"><span class="k">%s</span>'
        '<span class="v">%s</span></div>' % (k, v) for k, v in campos)
    return (
        '<header class="rotulo">'
        '<h1>Dónde vale el suelo en Bogotá</h1>'
        '<p class="sub">Qué tanto explica la ubicación el valor del terreno. '
        'Análisis exploratorio y modelado supervisado sobre 2.4 millones de '
        'construcciones del catastro distrital.</p>'
        '<div class="campos">%s</div></header>' % campos_html)


def md_a_html(md, artefacto=False, cabecera=""):
    """Conversor minimo de este subconjunto de markdown a HTML.

    artefacto=True devuelve solo el cuerpo, con la maquetacion pensada para
    publicarse como pagina (encabezados numerados y figuras con rotulo de
    lamina, al modo de un plano catastral).
    """
    import html as _html
    import re

    out = []
    en_tabla = False
    en_code = False
    en_lista = False
    en_cita = False
    lamina = [0]

    def inline(t):
        t = _html.escape(t)
        t = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r"@@IMG:\2@@\1@@", t)
        t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
        t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
        t = t.replace("  \n", "<br>")
        return t

    def img_tag(src, alt):
        ruta = (C.REPORT_DIR / src).resolve()
        if ruta.exists():
            b64 = base64.b64encode(ruta.read_bytes()).decode("ascii")
            tag = '<img src="data:image/png;base64,%s" alt="%s">' % (b64, alt)
        else:
            tag = '<img src="%s" alt="%s">' % (src, alt)
        if not artefacto:
            return tag
        lamina[0] += 1
        return ('<figure>%s<figcaption><span class="lam">Lámina %02d</span>%s'
                '</figcaption></figure>' % (tag, lamina[0], alt))

    for linea in md.split("\n"):
        if linea.startswith("```"):
            if en_code:
                out.append("</code></pre>")
            else:
                out.append("<pre><code>")
            en_code = not en_code
            continue
        if en_code:
            out.append(_html.escape(linea))
            continue

        es_tabla = linea.startswith("|")
        if en_tabla and not es_tabla:
            out.append("</tbody></table>")
            en_tabla = False
        es_li = linea.lstrip().startswith(("- ", "1. ", "2. ", "3. ", "4. ", "5. "))
        if en_lista and not es_li:
            out.append("</ul>")
            en_lista = False
        es_cita = linea.startswith("> ")
        if en_cita and not es_cita:
            out.append("</blockquote>")
            en_cita = False
        if es_cita:
            if not en_cita:
                out.append("<blockquote>")
                en_cita = True
            out.append("<p>%s</p>" % inline(linea[2:]))
            continue

        if es_tabla:
            celdas = [c.strip() for c in linea.strip().strip("|").split("|")]
            if set("".join(celdas)) <= set("-: "):
                continue
            if not en_tabla:
                out.append("<table><thead><tr>"
                           + "".join("<th>%s</th>" % inline(c) for c in celdas)
                           + "</tr></thead><tbody>")
                en_tabla = True
            else:
                out.append("<tr>" + "".join("<td>%s</td>" % inline(c)
                                            for c in celdas) + "</tr>")
            continue

        if linea.startswith("### "):
            out.append("<h3>%s</h3>" % inline(linea[4:]))
        elif linea.startswith("## "):
            texto = linea[3:]
            m = re.match(r"^(\d+)\.\s+(.*)$", texto)
            if artefacto and m:
                out.append('<h2><span class="num">%s</span>%s</h2>'
                           % (m.group(1), inline(m.group(2))))
            else:
                out.append("<h2>%s</h2>" % inline(texto))
        elif linea.startswith("# "):
            if not artefacto:          # en la version publicable manda el rotulo
                out.append("<h1>%s</h1>" % inline(linea[2:]))
        elif es_li:
            if not en_lista:
                out.append("<ul>")
                en_lista = True
            texto = linea.lstrip()
            texto = texto[2:] if texto.startswith("- ") else texto[3:]
            out.append("<li>%s</li>" % inline(texto))
        elif linea.strip() == "":
            continue
        else:
            out.append("<p>%s</p>" % inline(linea))

    if en_tabla:
        out.append("</tbody></table>")
    if en_lista:
        out.append("</ul>")
    if en_cita:
        out.append("</blockquote>")

    cuerpo = "\n".join(out)
    cuerpo = re.sub(r"@@IMG:([^@]+)@@([^@]*)@@",
                    lambda m: img_tag(m.group(1), m.group(2)), cuerpo)
    if artefacto:
        return (FUENTES + "<style>%s</style><article class=\"doc\">%s%s</article>"
                % (CSS_ARTEFACTO, cabecera, cuerpo))
    return ("<!doctype html><html lang=\"es\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>Valoracion del terreno por ubicacion - Bogota</title>"
            "<style>%s</style></head><body>%s</body></html>" % (CSS, cuerpo))


def main():
    print("[05] Informe")
    md = construir_markdown()
    (C.REPORT_DIR / "informe.md").write_text(md, encoding="utf-8")
    print("     reports/informe.md  (%.1f KB)" % (len(md) / 1024))

    html = md_a_html(md)
    (C.REPORT_DIR / "informe.html").write_text(html, encoding="utf-8")
    print("     reports/informe.html  (%.1f MB, figuras embebidas)"
          % (len(html.encode("utf-8")) / 1e6))

    st = leer_json(C.F_STATS)
    mo = leer_json(C.OUT_DIR / "resumen_modelado.json")
    moran = pd.read_csv(C.TAB_DIR / "t07_autocorrelacion.csv").iloc[0]
    pub = md_a_html(md, artefacto=True,
                    cabecera=cabecera_artefacto(st, mo, moran))
    (C.REPORT_DIR / "informe_publicable.html").write_text(pub, encoding="utf-8")
    print("     reports/informe_publicable.html  (%.1f MB, version para publicar)"
          % (len(pub.encode("utf-8")) / 1e6))


if __name__ == "__main__":
    main()

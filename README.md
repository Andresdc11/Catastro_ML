# Catastro_ML — Valoración del terreno según su ubicación (Bogotá D.C.)

Proyecto de **análisis exploratorio (EDA)** y **aprendizaje supervisado** sobre
`Construcciones.geojson` (1.8 GB, 2.4 millones de construcciones catastrales).

El objetivo es responder: **¿cuánto explica la ubicación el valor del terreno?**

---

## ⚠️ Lo primero: qué se está modelando

El archivo **no contiene avalúo, precio ni estrato**. Sus atributos son
`CONNPISOS`, `CONTSEMIS`, `CONNSOTANO`, `CONMEJORA`, `CONVOLADIZ`, `CONALTURA`,
`CONELEVACI` y la geometría. Predecir un precio observado es imposible con este
insumo, así que el proyecto construye un **proxy explícito y documentado**:

> **IVS — Índice de Valor del Suelo.** Basado en la teoría de la renta del suelo
> (bid-rent, Alonso 1964): donde el suelo es caro, el mercado responde
> intensificando su uso. El IVS resume esa intensidad edificatoria por manzana
> mediante PCA sobre cinco variables morfológicas.

La separación entre target y predictores es estricta, de modo que **no hay fuga
de información**:

| | Se construye con | No usa |
|---|---|---|
| **IVS** (variable objetivo) | morfología construida | nada geográfico |
| **Predictores** | 12 variables de ubicación | ningún atributo constructivo |

El índice se somete a una **prueba de validez externa** contra diez zonas
conocidas de Bogotá: ordena Chicó (97), Salitre (96) y Usaquén (92) por encima
de Bosa (52) y Kennedy (29).

---

## Resultados principales

| | |
|---|---|
| Construcciones procesadas | 2 388 787 (66 s, lectura en streaming) |
| Manzanas modelables | 38 748 en 1 140 sectores catastrales |
| Autocorrelación espacial del valor | Moran's I = **0.541** (p = 0.010) |
| Mejor modelo (solo ubicación) | **Random Forest**, 44.5 % de exactitud en 4 clases |
| Aciertos con tolerancia de 1 categoría | **80.8 %** |
| Regresión logística binaria (alto valor) | **AUC = 0.704** |

Hallazgo central: **la dirección importa más que la distancia**. El valor no
decae de forma monótona desde la Plaza de Bolívar; se organiza en un corredor
que recorre el borde oriental hacia el norte. Bogotá es policéntrica.

---

## Modelos supervisados

Siete clasificadores sobre la misma tarea (categoría de valor en cuartiles):

| Modelo | Exactitud | F1 macro | Kappa |
|---|---|---|---|
| Baseline (clase mayoritaria) | 0.246 | 0.099 | 0.000 |
| **Regresión logística** (multinomial) | 0.384 | 0.375 | 0.178 |
| Regresión logística polinómica (grado 2) | 0.416 | 0.418 | 0.221 |
| **Árbol de decisión** (grid search) | 0.423 | 0.424 | 0.230 |
| KNN espacial (k=15) | 0.424 | 0.425 | 0.233 |
| Gradient Boosting | 0.440 | 0.442 | 0.253 |
| **Random Forest** | **0.445** | **0.445** | **0.261** |

Más una **tarea binaria** de alto valor con regresión logística, con curva ROC,
odds ratios y diagnóstico de colinealidad (VIF).

### Validación espacial, no aleatoria

Con Moran's I = 0.54, una partición aleatoria dejaría manzanas de la misma
cuadra a ambos lados del corte y el modelo aprobaría por vecindad. Se particiona
por **sector catastral** (`GroupShuffleSplit` / `GroupKFold`), y se reporta
también la CV aleatoria para cuantificar el sesgo: infla el F1 macro **0.124
puntos** en KNN y **0.104** en Gradient Boosting, pero solo **0.007** en la
regresión logística —un modelo lineal no puede memorizar el vecindario.

---

## Uso

```bash
pip install -r requirements.txt
python run_pipeline.py
```

```bash
python run_pipeline.py --rapido
```

Otras opciones: `--desde 3` reanuda desde el EDA, `--hasta 4` se detiene antes
del informe. Cada etapa también corre suelta (`python src/models.py`).

Tiempo total: **~5 minutos** en un portátil (la ingesta del GeoJSON completo
toma 66 s). Sin dependencias de GDAL, geopandas ni shapely: la geometría se
calcula con la fórmula del zapatero sobre una proyección equirectangular local.

---

## Estructura

```
Catastro_ML/
├── run_pipeline.py             orquestador de las 5 etapas
├── requirements.txt
├── src/
│   ├── config.py               rutas, parámetros, geografía de referencia
│   ├── geo_utils.py            área, perímetro, centroide, haversine, azimut
│   ├── ingest.py           01  streaming del GeoJSON -> agregados
│   ├── features.py         02  índice IVS + variables de ubicación (4 tablas)
│   ├── eda.py              03  12 figuras + 5 tablas
│   ├── models.py           04  7 clasificadores + 7 figuras + 10 tablas
│   └── report.py           05  informe .md y .html autocontenido
├── data/processed/             csv.gz intermedios
├── outputs/
│   ├── figuras/                fig01 … fig19 (png)
│   ├── tablas/                 t01 … t16 (19 csv)
│   ├── modelos/                *.joblib
│   └── resumen_modelado.json
└── reports/
    ├── informe.md
    └── informe.html            ← empezar por aquí
```

## Etapas

| # | Script | Qué hace |
|---|---|---|
| 01 | `ingest.py` | Recorre el GeoJSON línea a línea (no cabe en memoria). Calcula área/perímetro/centroide de cada polígono, valida, y produce en **una sola pasada**: muestra a nivel de construcción, agregado por manzana y agregado por sector. |
| 02 | `features.py` | Construye el IVS por PCA (criterio de Kaiser + ponderación por varianza) y las 12 variables de ubicación. Valida el índice contra zonas conocidas. |
| 03 | `eda.py` | Calidad de datos, distribuciones, mapas, curva de renta, análisis por cuadrante y anillo, correlaciones, Moran's I con test de permutación. |
| 04 | `models.py` | Split espacial, grid search del árbol, comparación de 7 modelos bajo dos esquemas de CV, matrices de confusión, importancias por permutación, tarea binaria, superficie continua de valor sobre malla de 245 m. |
| 05 | `report.py` | Informe final; todas las cifras se leen de los artefactos, nunca se escriben a mano. |

## Variables

**Componentes del IVS (morfológicas):** `log_indice_construccion`,
`pisos_prom_pond`, `frac_pisos_ge3`, `frac_subterraneo`, `log_huella_media`.

**Predictores (ubicación):** `lon`, `lat`, distancias a centro histórico / eje
financiero / aeropuerto / centralidad sur / cerros orientales, `azimut_sin`,
`azimut_cos`, `vecinos_500m`, `vecinos_1km`, `dist_vecino_8_km`.

## Limitaciones

1. El IVS es un proxy de intensidad y formalidad constructiva, **no un avalúo**.
2. Los barrios informales densos quedan algo sobrevalorados: PC2 corrige buena
   parte del sesgo, pero la mitad inferior del ranking es menos confiable.
3. El área de manzana se aproxima con el rectángulo envolvente de sus
   construcciones (la capa de lotes no viene en el insumo).
4. El techo de exactitud es estructural: dos manzanas de la misma cuadra pueden
   diferir por norma urbanística o historia del predio, que ninguna coordenada
   captura.
5. El GeoJSON no declara su fecha de corte; conviene fijarla antes de usar los
   resultados operativamente.

## Datos

`Construcciones.geojson` — capa CONST del catastro de Bogotá D.C.,
EPSG:4686 (MAGNA-SIRGAS). Código de lote de 12 dígitos: `SSSSSS MMM LLL`
(sector, manzana, predio).

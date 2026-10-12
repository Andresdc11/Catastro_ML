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

## Pronóstico del valor del suelo

Sobre el precio real de Catastro (2017-2026), validando **en el tiempo**:

| | |
|---|---|
| Deriva de la ciudad, mejor método | **deriva reciente (4 años)**, 1.6 % de error en el backtest |
| Rango defendible para 2027-2030 | **4.3 % a 14.5 %** anual nominal |
| Crecimiento relativo por manzana, mejor R² | ensamble de árboles, **R² = 0.136** |
| El mismo problema con partición aleatoria | R² = 0.712 — el autoengaño mide **0.62 puntos** |
| Modelos que le ganan a la línea base (bootstrap por sector) | **ninguno de 10** al 95 % |

Dos resultados que se sostienen. El primero: **el crecimiento es un fenómeno de
zona**, con el 93 % de su varianza entre sectores catastrales, y **no hay
momentum** —la autocorrelación anual es negativa, huella de que Catastro
actualiza por turnos—. El segundo: la única señal transversal fuerte es la
**reversión a la media**, el suelo barato se valoriza más rápido en porcentaje.

Y una advertencia metodológica que el notebook documenta con números: añadir
**una sola variable redundante** (una resta de dos columnas ya presentes) hunde
al Random Forest de R² 0.090 a −0.438, mientras Ridge no se mueve.

---

## Tipologías de mercado

Clustering sobre el comportamiento de precios, **sin usar la geografía**:

| | |
|---|---|
| Grupos, elegidos por estabilidad | **6** (ARI = 0.466) |
| Pureza espacial del resultado | **0.864** frente a 0.167 al azar |
| Separación entre grupos / dispersión total, `dist_eje_financiero_km` | **0.790** |
| Manzanas atípicas (dos o más detectores) | **488** (1.3 %) |

Los grupos se forman sin coordenadas y aun así se ordenan sobre el gradiente
urbano: el 58 % de las manzanas cae en un grupo caro que sigue el ritmo de la
ciudad, un 29 % en uno barato que crece algo más rápido, y en el extremo quedan
dos grupos pequeños y muy inestables (573 y 145 manzanas) que son revalúos
administrativos antes que mercado.

Dos trampas quedan documentadas con números. Los enlaces `average` y `complete`
sacan la **mejor silueta de toda la tabla** (0.78) con un grupo que se queda el
99 % de las manzanas: el índice premia una partición inútil. Y la lista de
"zonas que más crecen" es un ranking de pobreza mientras no se descuente la
reversión a la media; al descontarla, los sectores de mayor **oportunidad** van
de 1.2 M a 9.1 M COP/m².

---

## Detección de anomalías

Rarezas **de vecindario** y **de serie**, con el desempeño medido contra
anomalías sintéticas inyectadas:

| | |
|---|---|
| Vecindarios donde Catastro asigna el mismo valor a todas las manzanas | **69.8 %** |
| Mejor detector contra anomalías inyectadas | **LOF**, average precision 0.115 (azar 0.032) |
| Revisando las 187 primeras | **52 %** son anomalías reales |
| Manzanas marcadas por mayoría de los 7 detectores | **235** (0.6 %) |
| Transiciones (manzana, año) analizadas | **299 536** |

Tres cosas que el notebook deja medidas. La primera es un hecho sobre el dato:
como `V_REF` se asigna por zonas, en el **70 %** de los vecindarios la
desviación es exactamente cero, y una representación contextual ingenua divide
por cero y produce ranking de ruido de redondeo. La segunda es que
`average_precision` y `roc_auc` **ordenan los detectores al revés** —con 3 % de
positivos el ROC premia ordenar bien el montón, no la cabeza de la lista—. La
tercera: con anomalías sutiles **los siete detectores son igual de malos**, y la
diferencia entre ellos solo aparece cuando la anomalía es grande.

---

## Uso

**Si solo vas a abrir un archivo, abre
[`notebooks/consolidado_hallazgos.ipynb`](notebooks/consolidado_hallazgos.ipynb).**
Reúne los hallazgos de los cinco notebooks y del pipeline en un solo documento,
organizado en lo que se puede usar para decidir, lo que no funciona aunque lo
parezca, y las cinco trampas metodológicas que el proyecto documenta con
números. No escribe ninguna cifra a mano: todas las lee de `outputs/tablas/` y
de `data/processed/`, así que si se vuelve a correr cualquier notebook con
otros parámetros, el consolidado cambia solo. Si falta alguna tabla lo reporta
y sigue.

```bash
pip install -r requirements.txt
python run_pipeline.py
```

```bash
python run_pipeline.py --rapido
```

Otras opciones: `--desde 3` reanuda desde el EDA, `--hasta 4` se detiene antes
del informe. Cada etapa también corre suelta (`python src/models.py`).

Para explorar y ajustar el análisis a mano está
`notebooks/eda_valoracion_suelo.ipynb`: el mismo EDA con el código desplegado
celda a celda y una sección de parámetros editables al inicio (paleta, tamaños
de punto, cortes de anillos, zonas de validación, componentes del IVS). Si
faltan los datos procesados, la segunda celda lanza las etapas 01 y 02.

`notebooks/comparacion_modelos_pycaret.ipynb` enfrenta al Random Forest con toda
la batería de clasificadores de PyCaret (boosting, extra trees, lineales,
bayesianos), ajusta los mejores, arma un ensamble y decide con un bootstrap por
sector si alguno lo supera de verdad. Usa la misma partición espacial que
`src/models.py`. Resultado: Gradient Boosting ajustado, el ensamble, LightGBM y
CatBoost quedan hasta 0.007 de F1 macro por encima del Random Forest en
hold-out, pero ninguno se distingue de él en el bootstrap por sector (todos los
intervalos del 95 % cruzan el cero).

PyCaret exige versiones de scikit-learn y pandas distintas a las del pipeline,
así que corre en su propio entorno conda (`pycaret`) con el kernel
**Python (catastro-pycaret)**. Para recrearlo, desde Anaconda Prompt en la raíz
del repositorio:

```bash
conda create -n pycaret --override-channels -c conda-forge python=3.9.13 pip -y
conda activate pycaret
python -m pip install -r requirements-pycaret.txt
python -m ipykernel install --user --name catastro-pycaret --display-name "Python (catastro-pycaret)"
```

`notebooks/valor_suelo_pesos_m2.ipynb` es un flujo aparte que trae el **valor
comercial real del suelo** (COP/m² por manzana, 2017-2026) y el uso económico
predominante desde los servicios de Catastro Bogotá, unidos por código de
manzana. Sirve para tres cosas: calibrar el IVS contra el precio real —el
resultado es que **no le gana a usar la mediana de la ciudad**—, ver dónde se
valoriza Bogotá por encima del promedio, y ubicar las manzanas empresariales.
La primera ejecución descarga ~430 mil registros (unos 4 minutos) y los deja en
caché. Corre con el entorno principal del pipeline.

`notebooks/pronostico_valor_suelo.ipynb` lleva ese insumo al terreno predictivo:
**¿cuánto costará el m² de terreno en los próximos años y dónde subirá más que
en el resto de la ciudad?** Separa el problema en dos —la deriva de la ciudad,
que son diez puntos anuales y se ataca con series de tiempo (caminata aleatoria,
deriva histórica y reciente, tendencia lineal, Holt, ARIMA), y el término
relativo por manzana, que son 37 442 filas y se ataca con once métodos
supervisados— y dedica una sección entera a las **métricas**, porque no dan el
mismo ganador. Valida en el tiempo, no al azar: se ajusta prediciendo 2020→2023
y se evalúa prediciendo 2023→2026. Deja
`data/processed/pronostico_manzanas.csv.gz` con el precio proyectado a 2030 en
tres escenarios. Reutiliza la caché del notebook anterior; corre en ~1 minuto.

`notebooks/clusters_comportamiento_mercado.ipynb` cierra la serie con
aprendizaje **no supervisado**: **¿cuántas maneras distintas de comportarse
tiene el suelo de Bogotá?** Agrupa las manzanas usando **solo su comportamiento
de mercado** —precio, valorización, volatilidad, inercia y pronóstico— y deja
fuera la ubicación, la morfología y el uso, que quedan como validación externa:
así la pregunta "¿estos grupos coinciden con zonas reales de la ciudad?" tiene
una respuesta que significa algo. Compara seis algoritmos (K-Means, mezcla
gaussiana, jerárquico, BIRCH, DBSCAN y una variante espacialmente contigua),
elige `k` con cinco criterios incluida la **estabilidad por remuestreo**, y
recorre las rejillas de hiperparámetros de cada uno. Termina señalando las zonas
que destacan en dos sentidos: **oportunidad** (crecen más que sus pares de
precio, no más que la ciudad) y **atípicas** (ningún grupo las explica). Deja
`data/processed/clusters_manzanas.csv.gz`. Corre en ~2½ minutos.

`notebooks/anomalias_suelo.ipynb` busca **rarezas**, pero no las que ya marcaba
el notebook anterior. Dos preguntas nuevas: ¿esta manzana es rara **para su
vecindario** —aunque sea corrientísima a escala de ciudad— y **en qué año** se
rompió su serie? Lo primero se resuelve en la representación más que en el
algoritmo: se da a los detectores el **residuo frente a los vecinos** en vez del
dato crudo, y con eso siete detectores estándar (Isolation Forest, LOF,
One-Class SVM, Elliptic Envelope, reconstrucción por PCA, mezcla gaussiana y
distancia al k-ésimo vecino) pasan a responder una pregunta contextual. Lo
segundo cambia la unidad de análisis a la transición (manzana, año): 300 mil
filas, con búsqueda exhaustiva del punto de quiebre. Como no hay etiquetas, el
desempeño se mide **inyectando anomalías sintéticas** de magnitud conocida.
Entrega una lista priorizada con el motivo de cada marca y la separación entre
**artefacto administrativo** y **rareza aislada**. Corre en ~1½ minutos.

Tiempo total: **~5 minutos** en un portátil (la ingesta del GeoJSON completo
toma 66 s). Sin dependencias de GDAL, geopandas ni shapely: la geometría se
calcula con la fórmula del zapatero sobre una proyección equirectangular local.

---

## Estructura

```
Catastro_ML/
├── run_pipeline.py             orquestador de las 5 etapas
├── requirements.txt
├── requirements-pycaret.txt    lista congelada del entorno conda de PyCaret
├── src/
│   ├── config.py               rutas, parámetros, geografía de referencia
│   ├── geo_utils.py            área, perímetro, centroide, haversine, azimut
│   ├── ingest.py           01  streaming del GeoJSON -> agregados
│   ├── features.py         02  índice IVS + variables de ubicación (4 tablas)
│   ├── eda.py              03  12 figuras + 5 tablas
│   ├── models.py           04  7 clasificadores + 7 figuras + 10 tablas
│   └── report.py           05  informe .md y .html autocontenido
├── notebooks/
│   ├── consolidado_hallazgos.ipynb        ← empezar por aquí: todo el proyecto
│   ├── eda_valoracion_suelo.ipynb         EDA interactivo, código desplegado
│   ├── comparacion_modelos_pycaret.ipynb  Random Forest contra PyCaret
│   ├── valor_suelo_pesos_m2.ipynb         precio real del suelo y calibración
│   ├── pronostico_valor_suelo.ipynb       pronóstico a 2030 y análisis de métricas
│   ├── clusters_comportamiento_mercado.ipynb  tipologías de mercado y zonas que destacan
│   └── anomalias_suelo.ipynb              rarezas de vecindario y quiebres de serie
├── data/processed/             csv.gz intermedios
├── outputs/
│   ├── figuras/                fig01 … fig19 (png)
│   ├── tablas/                 t01 … t62 (68 csv)
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
   Contrastado con el valor de referencia de Catastro (ver
   `notebooks/valor_suelo_pesos_m2.ipynb`), su correlación de Spearman con el
   precio del suelo es 0.33, y convertirlo a pesos se equivoca más que usar la
   mediana de la ciudad. Sirve para ordenar manzanas, no para estimar precios.
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

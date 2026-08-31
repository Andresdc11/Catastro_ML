# Valoración del terreno según su ubicación en Bogotá D.C.

Proyecto de análisis exploratorio y aprendizaje supervisado sobre la capa catastral de construcciones (`Construcciones.geojson`, 1.80 GB, 2,401,061 registros).

## 1. Resumen ejecutivo

- Se procesaron **2,388,787 construcciones** en 84 segundos mediante lectura en streaming, y se agregaron a **40,581 manzanas catastrales** de **1,173 sectores**.
- El archivo **no contiene avalúo ni ningún campo monetario**. Se construyó un proxy explícito, el **Índice de Valor del Suelo (IVS)**, con las dos primeras componentes principales de cinco variables morfológicas (75.2% de la varianza).
- El IVS supera una prueba de validez externa: ordena Chicó (97), Salitre (96) y Usaquén (92) por encima de Bosa (52) y Kennedy (29), coherente con el mercado real.
- El valor del suelo **no se distribuye al azar en el espacio**: Moran's I = **0.541** (p = 0.010), es decir fuerte agrupamiento en corredores.
- Con **solo variables de ubicación**, el mejor modelo (**Random Forest**) alcanza **44.5% de exactitud** sobre sectores catastrales nunca vistos, frente a 24.6% del baseline y 25% del azar; acierta la categoría exacta o una contigua en el **80.8%** de los casos.
- La regresión logística binaria alcanza **AUC = 0.704** para identificar manzanas de alto valor.

## 2. Advertencia metodológica: que se esta modelando

Los atributos disponibles por construcción son `CONNPISOS`, `CONTSEMIS`, `CONNSOTANO`, `CONMEJORA`, `CONVOLADIZ`, `CONALTURA`, `CONELEVACI` y la geometria. **No hay precio, avalúo ni estrato.** Modelar 'el valor del terreno' de forma directa es imposible con este insumo.

La salida elegida se apoya en la teoría de la renta del suelo (bid-rent, Alonso 1964): donde el suelo es caro, el mercado responde intensificando su uso. El **IVS** mide esa intensidad edificatoria y sirve como proxy ordinal del valor. Es un proxy, no un avalúo: los resultados se leen como *potencial de aprovechamiento del suelo*, no como pesos por metro cuadrado.

**Separación limpia entre target y predictores** (sin fuga de información):

| | Se construye con | No usa |
|---|---|---|
| IVS (target) | morfología construida | nada geográfico |
| Predictores | ubicación geográfica | ningún atributo constructivo |

## 3. Datos y procesamiento

El GeoJSON de 1.8 GB no cabe en memoria, así que se recorre **línea a línea** calculando área, perímetro y centroide con formula del zapatero sobre una proyección equirectangular local (error < 0.1% a esta escala), sin depender de GDAL/geopandas. Una sola pasada produce la muestra de construcciones, el agregado por manzana y el agregado por sector.

| Etapa | Registros |
|---|---|
| Leidos del GeoJSON | 2,401,061 |
| Validos | 2,388,787 |
| Descartados por área < 1 m2 (slivers) | 12,260 |
| Descartados por código inválido | 14 |
| Manzanas resultantes | 40,581 |
| Manzanas modelables (>= 5 construcciones) | 38,748 |

![Calidad de datos](../outputs/figuras/fig01_calidad_datos.png)

Hallazgos de calidad relevantes: la mediana de huella es de apenas ~24 m2 porque la capa descompone cada predio en partes homogeneas en altura; `CONALTURA` esta casi siempre en cero, por lo que la altura util es `CONNPISOS`; y `CONELEVACI` replica a `CONNPISOS` en la mayoria de casos.

![Distribuciones](../outputs/figuras/fig02_distribuciones_construccion.png)

![Huella construida](../outputs/figuras/fig04_mapa_construcciones_pisos.png)

## 4. Construcción del Índice de Valor del Suelo

Cinco variables morfológicas por manzana entran a un PCA sobre datos estandarizados. Se retienen las componentes con autovalor > 1 (criterio de Kaiser) y se ponderan por su participación en la varianza explicada (procedimiento OECD/JRC para indicadores compuestos).

| componente | autovalor | varianza_explicada | varianza_acumulada | retenida | peso_en_ivs |
|---|---|---|---|---|---|
| PC1 | 2.5042 | 0.5008 | 0.5008 | True | 0.6656 |
| PC2 | 1.2581 | 0.2516 | 0.7525 | True | 0.3344 |
| PC3 | 0.5587 | 0.1117 | 0.8642 | False | 0.0 |
| PC4 | 0.4234 | 0.0847 | 0.9489 | False | 0.0 |
| PC5 | 0.2557 | 0.0511 | 1.0 | False | 0.0 |

**Por que no basta la primera componente.** PC1 mide intensidad bruta y confunde el barrio informal autoconstruido (cobertura total del lote, 2-3 pisos, huellas de 30 m2, sin sótanos) con el desarrollo formal en altura. PC2 es justamente el eje que los separa: carga positivo en tamaño de huella y sótanos. Reteniendo ambas, Bosa y Usme dejan de aparecer por encima de Chapinero.

| componente | carga_pc1 | carga_pc2 | correlacion_con_ivs |
|---|---|---|---|
| log_indice_construccion | 0.4824 | -0.2275 | 0.6335 |
| pisos_prom_pond | 0.5605 | -0.1227 | 0.7894 |
| frac_pisos_ge3 | 0.4744 | -0.4019 | 0.556 |
| frac_subterraneo | 0.4202 | 0.4823 | 0.8079 |
| log_huella_media | 0.2269 | 0.7342 | 0.6144 |

![Componentes del IVS](../outputs/figuras/fig05_componentes_ivs.png)

![Distribución del IVS](../outputs/figuras/fig06_ivs_distribucion.png)

### Validación externa del índice

Prueba de sentido común: el índice debería ordenar las zonas de Bogotá como lo hace el mercado. Se calcula el IVS mediano en un radio de 1.2 km alrededor de diez puntos conocidos.

| zona | manzanas | ivs_mediano | pisos_prom_pond | indice_construccion | huella_media_m2 | frac_subterraneo | pct_alto_valor |
|---|---|---|---|---|---|---|---|
| Chicó - Calle 93 | 277 | 97.1 | 4.39 | 2.66 | 144.4 | 0.52 | 96.8 |
| Salitre / Ciudad Empresarial | 114 | 96.0 | 2.72 | 1.8 | 260.9 | 0.26 | 63.2 |
| Usaquén | 250 | 92.0 | 2.92 | 1.6 | 105.6 | 0.27 | 75.6 |
| Chapinero - Calle 63 | 484 | 86.9 | 2.69 | 1.7 | 70.7 | 0.06 | 68.2 |
| Centro Internacional | 318 | 83.5 | 2.61 | 1.45 | 76.3 | 0.03 | 67.0 |
| Suba centro | 289 | 64.1 | 2.33 | 1.05 | 45.8 | 0.0 | 37.0 |
| La Candelaria | 377 | 60.9 | 1.98 | 1.14 | 79.8 | 0.03 | 41.9 |
| Usme | 616 | 53.5 | 2.42 | 1.62 | 31.5 | 0.0 | 18.2 |
| Bosa | 1038 | 52.5 | 2.49 | 1.47 | 30.9 | 0.0 | 15.0 |
| Kennedy | 415 | 29.4 | 2.15 | 1.08 | 39.0 | 0.0 | 13.7 |

## 5. Análisis exploratorio: el valor y la ubicación

![Mapa del IVS](../outputs/figuras/fig07_mapa_ivs.png)

**El patron es un corredor, no un circulo.** La franja de alto valor recorre el borde oriental de sur a norte (centro internacional - Chapinero - Chicó - Usaquén), con un nucleo secundario en Salitre. El sur y el suroccidente concentran las manzanas de valor bajo.

![Gradiente](../outputs/figuras/fig08_gradiente_distancia.png)

**La curva de renta clásica no se cumple.** El IVS no decae monótonamente con la distancia a la Plaza de Bolívar: cae hasta los ~8 km y vuelve a subir en los anillos exteriores del norte. Bogotá es policéntrica y su eje de valor migró al norte.

| anillo_km | manzanas | ivs_mediano | pisos_prom | indice_construccion | pct_alto_valor |
|---|---|---|---|---|---|
| 0-2 | 1106 | 64.24 | 2.5 | 1.17 | 40.6 |
| 2-4 | 2447 | 56.84 | 2.34 | 1.17 | 29.6 |
| 4-6 | 4239 | 49.67 | 2.39 | 1.28 | 24.0 |
| 6-8 | 4670 | 45.05 | 2.35 | 1.21 | 20.4 |
| 8-10 | 6368 | 44.64 | 2.43 | 1.25 | 21.6 |
| 10-13 | 11220 | 45.26 | 2.36 | 1.24 | 21.0 |
| 13-16 | 5651 | 57.4 | 2.73 | 1.31 | 30.5 |
| 16-20 | 2881 | 65.86 | 2.73 | 1.45 | 37.0 |
| 20+ | 166 | 8.2 | 1.44 | 0.02 | 11.4 |

![Cuadrantes](../outputs/figuras/fig09_ivs_por_cuadrante_y_anillo.png)

Por eso la **dirección importa mas que la distancia**: entre las variables de ubicación, las de mayor correlación con el IVS son `dist_eje_financiero_km` (rho = -0.303), `azimut_cos` (rho = 0.300), `lat` (rho = 0.290), `dist_aeropuerto_km` (rho = -0.215).

![Correlaciones](../outputs/figuras/fig10_correlaciones.png)

![Sectores](../outputs/figuras/fig11_top_sectores.png)

### Autocorrelación espacial

Con pesos de 8 vecinos mas cercanos, **Moran's I = 0.541** (p = 0.010, 99 permutaciones). El valor de una manzana se parece mucho al de sus vecinas. Esto tiene una consecuencia directa sobre el diseño de la validación del modelo.

![Moran](../outputs/figuras/fig12_autocorrelacion_espacial.png)

## 6. Modelado supervisado

**Tarea A (multiclase):** predecir la categoría de valor de la manzana (Bajo / Medio-Bajo / Medio-Alto / Alto, cuartiles del IVS) a partir de 12 variables de ubicación.  
**Tarea B (binaria):** identificar manzanas de alto valor con regresión logística, con lectura de coeficientes.

### Diseño de validación

Dada la autocorrelación, una partición aleatoria dejaría manzanas de la misma cuadra a ambos lados del corte y el modelo aprobaría por vecindad, no por generalización. Se particiona por **sector catastral**: 855 sectores (28,538 manzanas) para entrenar y 285 sectores disjuntos (10,210 manzanas) para probar.

El coste de ignorarlo es medible: la CV aleatoria infla el F1 macro en 0.092 puntos para Random Forest y 0.124 para KNN, mientras que en la regresión logística el sesgo es de solo 0.007 (un modelo lineal no puede memorizar el vecindario).

### Resultados sobre sectores no vistos

| modelo | exactitud | exactitud_balanceada | f1_macro | f1_ponderado | kappa | error_1_categoria | seg_entrenamiento |
|---|---|---|---|---|---|---|---|
| Random Forest | 0.4454 | 0.4453 | 0.4454 | 0.4455 | 0.2606 | 0.8079 | 2.3 |
| Gradient Boosting | 0.4397 | 0.4395 | 0.4422 | 0.4423 | 0.2529 | 0.8083 | 5.9 |
| KNN espacial (k=15) | 0.4244 | 0.4243 | 0.4249 | 0.425 | 0.2325 | 0.782 | 0.2 |
| Árbol de decisión | 0.4228 | 0.4227 | 0.4244 | 0.4245 | 0.2304 | 0.7775 | 0.7 |
| Reg. logística polinómica | 0.4161 | 0.4159 | 0.4184 | 0.4185 | 0.2213 | 0.7934 | 7.2 |
| Regresión logística | 0.3838 | 0.3828 | 0.375 | 0.3757 | 0.1777 | 0.7461 | 0.5 |
| Baseline (mayoritaria) | 0.2459 | 0.25 | 0.0987 | 0.0971 | 0.0 | 0.7503 | 0.0 |

![Comparación de modelos](../outputs/figuras/fig13_comparacion_modelos.png)

Lectura de los resultados:

1. **Todos los modelos superan claramente al azar** (25%) y al baseline (24.6%): la ubicación si contiene señal sobre el valor del suelo.
2. **La regresión logística lineal es la mas debil** (38.4%). Su frontera es un hiperplano y la estructura de valor de Bogotá es un corredor curvo; al agregar terminos cuadráticos e interacciones sube a 41.6%.
3. **El árbol de decisión** (42.3%) mejora al lineal porque particiona el espacio en cajas, que es exactamente como funciona la segregación urbana. Su óptimo esta en `max_depth=12`, `min_samples_leaf=50`.
4. **Los ensambles ganan** (Random Forest, 44.5%), pero el margen sobre el árbol único es de solo 2.3 puntos: el techo lo pone la información disponible, no el algoritmo.
5. **Los errores son casi siempre de una categoría contigua** (80.8% de aciertos con tolerancia de 1): el modelo rara vez confunde una manzana de valor alto con una de valor bajo.

![Matrices de confusión](../outputs/figuras/fig14_matrices_confusion.png)

Las clases extremas se predicen mucho mejor que las intermedias:

```
Modelo: Random Forest

              precision    recall  f1-score   support

        Bajo      0.512     0.510     0.511      2562
  Medio-Bajo      0.342     0.351     0.347      2511
  Medio-Alto      0.368     0.359     0.364      2588
        Alto      0.559     0.561     0.560      2549

    accuracy                          0.445     10210
   macro avg      0.445     0.445     0.445     10210
weighted avg      0.446     0.445     0.445     10210
```

### Árbol de decisión: las reglas explicitas

![Árbol](../outputs/figuras/fig15_arbol_decision.png)

Podado a profundidad 3, el árbol es legible: primero separa por densidad del entorno (`dist_vecino_8_km`), luego por cercanía al eje financiero del norte y al aeropuerto, y después por orientación (`azimut_sin`, es decir oriente frente a occidente). Es, literalmente, la geografía económica de la ciudad escrita como reglas if-else.

### Variables que mas pesan

| variable | importancia_permutacion | sd |
|---|---|---|
| dist_vecino_8_km | 0.03359 | 0.00245 |
| dist_eje_financiero_km | 0.01403 | 0.00398 |
| dist_aeropuerto_km | 0.01342 | 0.00214 |
| lat | 0.01092 | 0.00243 |
| vecinos_500m | 0.00951 | 0.00188 |
| azimut_cos | 0.00827 | 0.00101 |
| dist_cerros_km | 0.00754 | 0.00086 |
| dist_centro_historico_km | 0.00736 | 0.00154 |
| lon | 0.0072 | 0.00144 |
| vecinos_1km | 0.0036 | 0.00203 |
| dist_centro_sur_km | 0.00328 | 0.00174 |
| azimut_sin | 0.00199 | 0.00191 |

![Importancias](../outputs/figuras/fig16_importancias.png)

### Tarea B: regresión logística de alto valor

| Métrica | Valor |
|---|---|
| auc roc | 0.7035 |
| average precisión | 0.4735 |
| exactitud | 0.783 |
| f1 | 0.3995 |
| kappa | 0.2898 |
| prevalencia test | 0.2497 |

![Regresión logística](../outputs/figuras/fig17_regresion_logistica.png)

Los coeficientes estan sobre variables estandarizadas, así que se leen como el cambio en el log-odds por cada desviación estandar adicional:

| variable | coeficiente | odds_ratio | efecto_pct_por_sd |
|---|---|---|---|
| lon | -0.8994 | 0.4068 | -59.3 |
| dist_cerros_km | -0.884 | 0.4131 | -58.7 |
| dist_centro_sur_km | -0.6072 | 0.5449 | -45.5 |
| vecinos_500m | -0.268 | 0.7649 | -23.5 |
| dist_centro_historico_km | -0.2117 | 0.8092 | -19.1 |
| dist_eje_financiero_km | 0.0909 | 1.0952 | 9.5 |
| vecinos_1km | 0.1226 | 1.1304 | 13.0 |
| dist_vecino_8_km | 0.1308 | 1.1397 | 14.0 |
| azimut_sin | 0.3068 | 1.3591 | 35.9 |
| dist_aeropuerto_km | 0.7119 | 2.0379 | 103.8 |
| lat | 0.7839 | 2.1899 | 119.0 |
| azimut_cos | 0.9393 | 2.5582 | 155.8 |

> **Advertencia sobre la lectura de estos coeficientes.** Las variables geográficas son colineales por construcción: `dist_cerros_km` es una transformación casi lineal de `lon`, y el azimut resume a `lon` y `lat`. El diagnóstico da VIF de hasta **100** (8 variables por encima de 10), lo que reparte el efecto de forma arbitraria entre variables equivalentes: `lon` (-0.90) y `dist_cerros_km` (-0.88) reciben coeficientes casi idénticos, pero como la segunda decrece cuando la primera crece, sus aportes se cancelan casi por completo y el gradiente oriente-occidente termina expresado a través de `azimut_cos`. La colinealidad no daña la capacidad predictiva del modelo -el AUC de 0.704 es real-, pero invalida leer una variable a la vez. Para atribución de importancia es preferible la importancia por permutación de la tabla anterior.

| variable | r2_contra_las_demas | vif |
|---|---|---|
| lon | 0.99 | 99.74 |
| dist_cerros_km | 0.9897 | 96.87 |
| dist_eje_financiero_km | 0.9718 | 35.51 |
| dist_centro_sur_km | 0.9611 | 25.7 |
| lat | 0.9572 | 23.35 |
| dist_aeropuerto_km | 0.9544 | 21.93 |
| dist_centro_historico_km | 0.9303 | 14.34 |
| azimut_cos | 0.9198 | 12.47 |
| azimut_sin | 0.868 | 7.57 |
| vecinos_1km | 0.8017 | 5.04 |
| vecinos_500m | 0.7938 | 4.85 |
| dist_vecino_8_km | 0.5289 | 2.12 |

### Predicción en el espacio

![Mapas de predicción](../outputs/figuras/fig18_mapas_prediccion.png)

Exactitud por categoría real en el conjunto de prueba:

| valor_cat | manzanas | exactitud | desvio_medio |
|---|---|---|---|
| Bajo | 2551 | 0.508 | 0.855 |
| Medio-Bajo | 2510 | 0.351 | 0.296 |
| Medio-Alto | 2588 | 0.359 | -0.38 |
| Alto | 2549 | 0.561 | -0.776 |

Aplicando el modelo a una malla regular de ~245 m se obtiene una superficie continua de valor para toda la ciudad, incluidas las celdas sin manzana catastral:

![Superficie de valor](../outputs/figuras/fig19_superficie_valor.png)

## 7. Limitaciones

1. **El IVS es un proxy, no un avalúo.** Mide intensidad y formalidad constructiva. Para calibrarlo a pesos por m2 haría falta cruzarlo con la base de avalúos catastrales o con ofertas de mercado.
2. **Los barrios informales densos siguen sobrevalorados** respecto de su precio real. PC2 corrige buena parte del sesgo, pero no todo: la mitad inferior del ranking es menos confiable que la superior.
3. **El área de manzana es aproximada.** Se usa el rectangulo envolvente de sus construcciones como denominador del índice de construcción, porque la capa de lotes/manzanas no esta en el insumo.
4. **Techo de exactitud.** Con ubicación pura, el 44.5% alcanzado esta cerca del limite: dos manzanas de la misma cuadra pueden pertenecer a categorías distintas por razones (uso del suelo, norma urbanística, historia del predio) que ninguna coordenada captura.
5. **Vigencia.** El corte del dato catastral no viene declarado en el GeoJSON; conviene fijarlo antes de usar los resultados operativamente.

## 8. Reproducir

```bash
pip install -r requirements.txt
python run_pipeline.py            # ejecuta 01 -> 05
python run_pipeline.py --rapido   # prueba con 200k construcciones
```

| Etapa | Script | Salida |
|---|---|---|
| 01 Ingesta | `src/ingest.py` | `data/processed/*.csv.gz` |
| 02 Variables | `src/features.py` | `dataset_modelado.csv.gz` |
| 03 EDA | `src/eda.py` | `fig01`-`fig12`, `t01`-`t08` |
| 04 Modelado | `src/models.py` | `fig13`-`fig19`, `t09`-`t16`, modelos |
| 05 Informe | `src/report.py` | `reports/informe.md` y `.html` |
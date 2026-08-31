# -*- coding: utf-8 -*-
"""Configuracion central del proyecto Catastro_ML.

Todas las rutas se resuelven a partir de la raiz del repositorio para que los
scripts funcionen sin importar desde donde se invoquen.
"""
from pathlib import Path

# --------------------------------------------------------------------------
# Rutas
# --------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]

GEOJSON = ROOT / "Construcciones.geojson"

DATA_DIR = ROOT / "data"
PROC_DIR = DATA_DIR / "processed"

OUT_DIR = ROOT / "outputs"
FIG_DIR = OUT_DIR / "figuras"
TAB_DIR = OUT_DIR / "tablas"
MOD_DIR = OUT_DIR / "modelos"

REPORT_DIR = ROOT / "reports"

for _d in (PROC_DIR, FIG_DIR, TAB_DIR, MOD_DIR, REPORT_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# Artefactos generados por 01_ingest
F_MUESTRA = PROC_DIR / "construcciones_muestra.csv.gz"   # nivel construccion
F_MANZANAS = PROC_DIR / "manzanas_agregado.csv.gz"       # nivel manzana (universo completo)
F_SECTORES = PROC_DIR / "sectores_agregado.csv.gz"       # nivel sector catastral
F_STATS = PROC_DIR / "ingest_stats.json"

# Artefactos generados por 02_features
F_DATASET = PROC_DIR / "dataset_modelado.csv.gz"

# --------------------------------------------------------------------------
# Parametros de ingesta
# --------------------------------------------------------------------------
SEED = 42
SAMPLE_FRAC = 0.15          # fraccion de construcciones guardadas para EDA fino
MIN_CONST_POR_MANZANA = 5   # manzanas con menos construcciones se descartan del modelado
MIN_AREA_M2 = 1.0           # por debajo de 1 m2 la geometria es un sliver de digitalizacion
MAX_AREA_M2 = 200_000.0     # huellas mayores se consideran error de digitalizacion
MAX_PISOS = 60              # tope razonable para Bogota

# --------------------------------------------------------------------------
# Geografia de referencia (Bogota D.C., EPSG:4686 ~ WGS84)
# Puntos usados para construir variables de UBICACION (no de valor).
# --------------------------------------------------------------------------
CENTRO_HISTORICO = (-74.0761, 4.5981)    # Plaza de Bolivar
EJE_FINANCIERO = (-74.0530, 4.6860)      # Calle 100 con Cra 15 (centro de negocios norte)
AEROPUERTO = (-74.1469, 4.7016)          # El Dorado
CENTRO_SUR = (-74.1600, 4.5900)          # Kennedy / Bosa (centralidad del sur-occidente)
LON_CERROS = -74.0400                    # aproximacion de la linea de los cerros orientales

PUNTOS_REFERENCIA = {
    "centro_historico": CENTRO_HISTORICO,
    "eje_financiero": EJE_FINANCIERO,
    "aeropuerto": AEROPUERTO,
    "centro_sur": CENTRO_SUR,
}

# Recorte de coordenadas plausibles para Bogota D.C. (incluye area rural)
LON_MIN, LON_MAX = -74.55, -73.95
LAT_MIN, LAT_MAX = 3.70, 4.85

# --------------------------------------------------------------------------
# Variables morfologicas que componen el Indice de Valor del Suelo (IVS)
# --------------------------------------------------------------------------
COMPONENTES_IVS = [
    "log_indice_construccion",   # intensidad edificatoria (m2 construidos / m2 de manzana)
    "pisos_prom_pond",           # altura media ponderada por area
    "frac_pisos_ge3",            # consolidacion en altura
    "frac_subterraneo",          # sotanos/semisotanos (construccion costosa)
    "log_huella_media",          # tamano medio de la construccion
]

# Variables de UBICACION usadas como predictores
FEATURES_UBICACION = [
    "lon", "lat",
    "dist_centro_historico_km",
    "dist_eje_financiero_km",
    "dist_aeropuerto_km",
    "dist_centro_sur_km",
    "dist_cerros_km",
    "azimut_sin", "azimut_cos",
    "vecinos_500m", "vecinos_1km", "dist_vecino_8_km",
]

CLASES = ["Bajo", "Medio-Bajo", "Medio-Alto", "Alto"]

# Encuadre para los mapas: perimetro urbano de Bogota. Las manzanas rurales
# (Sumapaz, lat < 4.44) existen en el dato pero deformarian la escala del mapa.
URB_LON = (-74.26, -73.98)
URB_LAT = (4.44, 4.84)

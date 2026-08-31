# -*- coding: utf-8 -*-
"""Utilidades geometricas sin dependencias de GDAL/shapely.

El GeoJSON viene en coordenadas geograficas (EPSG:4686, equivalente practico a
WGS84 para este uso). Para calcular areas y perimetros en metros se proyecta
cada poligono a un plano local equirectangular centrado en el propio poligono;
para figuras de pocas decenas de metros el error es despreciable (<0.1%).
"""
from math import atan2, cos, degrees, hypot, radians, sin, sqrt

M_POR_GRADO_LAT = 110_574.0
M_POR_GRADO_LON_ECU = 111_320.0
R_TIERRA_KM = 6371.0088


def factores_metricos(lat_deg):
    """Metros por grado de longitud y latitud en una latitud dada."""
    return M_POR_GRADO_LON_ECU * cos(radians(lat_deg)), M_POR_GRADO_LAT


def _anillo_metrico(anillo, lon0, lat0, kx, ky):
    """Area con signo (m2), perimetro (m) y centroide de un anillo."""
    n = len(anillo)
    if n < 3:
        return 0.0, 0.0, 0.0, 0.0

    xs = [0.0] * n
    ys = [0.0] * n
    for i, pt in enumerate(anillo):
        xs[i] = (pt[0] - lon0) * kx
        ys[i] = (pt[1] - lat0) * ky

    a2 = 0.0      # 2 * area con signo
    cx = 0.0
    cy = 0.0
    perim = 0.0
    for i in range(n - 1):
        x1, y1, x2, y2 = xs[i], ys[i], xs[i + 1], ys[i + 1]
        cross = x1 * y2 - x2 * y1
        a2 += cross
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross
        perim += hypot(x2 - x1, y2 - y1)

    # cierre explicito si el anillo no venia cerrado
    if xs[0] != xs[-1] or ys[0] != ys[-1]:
        x1, y1, x2, y2 = xs[-1], ys[-1], xs[0], ys[0]
        cross = x1 * y2 - x2 * y1
        a2 += cross
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross
        perim += hypot(x2 - x1, y2 - y1)

    area = a2 / 2.0
    if abs(a2) < 1e-12:
        # poligono degenerado: se usa el promedio simple de vertices
        mx = sum(xs) / n
        my = sum(ys) / n
    else:
        mx = cx / (3.0 * a2)
        my = cy / (3.0 * a2)
    return area, perim, mx, my


def metricas_poligono(coords, lat_ref):
    """Metricas de un Polygon GeoJSON (lista de anillos: exterior + huecos)."""
    if not coords or len(coords[0]) < 3:
        return 0.0, 0.0, None, None
    lon0, lat0 = coords[0][0][0], coords[0][0][1]
    kx, ky = factores_metricos(lat_ref)

    area_ext, perim, mx, my = _anillo_metrico(coords[0], lon0, lat0, kx, ky)
    area = abs(area_ext)
    for hueco in coords[1:]:
        a_h, p_h, _, _ = _anillo_metrico(hueco, lon0, lat0, kx, ky)
        area -= abs(a_h)
        perim += p_h
    if area < 0:
        area = 0.0
    return area, perim, lon0 + mx / kx, lat0 + my / ky


def metricas_geometria(geom):
    """Area (m2), perimetro (m) y centroide (lon, lat) de Polygon/MultiPolygon."""
    if not geom:
        return None
    tipo = geom.get("type")
    coords = geom.get("coordinates")
    if not coords:
        return None

    if tipo == "Polygon":
        lat_ref = coords[0][0][1]
        area, perim, lon, lat = metricas_poligono(coords, lat_ref)
        if lon is None:
            return None
        return area, perim, lon, lat

    if tipo == "MultiPolygon":
        lat_ref = coords[0][0][0][1]
        area_t = perim_t = 0.0
        sx = sy = 0.0
        for poly in coords:
            a, p, lo, la = metricas_poligono(poly, lat_ref)
            if lo is None:
                continue
            area_t += a
            perim_t += p
            sx += lo * max(a, 1e-9)
            sy += la * max(a, 1e-9)
        if area_t <= 0:
            return None
        return area_t, perim_t, sx / area_t, sy / area_t

    return None


def haversine_km(lon1, lat1, lon2, lat2):
    """Distancia sobre la esfera en kilometros."""
    p1, p2 = radians(lat1), radians(lat2)
    dp = p2 - p1
    dl = radians(lon2 - lon1)
    h = sin(dp / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    return 2 * R_TIERRA_KM * atan2(sqrt(h), sqrt(1 - h))


def azimut_grados(lon0, lat0, lon1, lat1):
    """Rumbo en grados (0 = norte, 90 = este) desde un origen hacia un punto."""
    kx, ky = factores_metricos(lat0)
    dx = (lon1 - lon0) * kx
    dy = (lat1 - lat0) * ky
    return (degrees(atan2(dx, dy)) + 360.0) % 360.0

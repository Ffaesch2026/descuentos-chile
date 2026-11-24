"""Utilidades compartidas por todos los scrapers de bancos.

Cada módulo en scraper/bancos/<id>.py expone:
    BANCO = {"id": ..., "nombre": ..., "sitio": ...}
    def scrape() -> list[dict]   # lista de descuentos creados con nuevo_descuento()
"""
from __future__ import annotations

import hashlib
import os
import re
import unicodedata
from contextlib import contextmanager

import requests

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)
TIMEOUT = 30

RUBROS = {
    "restaurantes": "Restaurantes",
    "supermercados": "Supermercados",
    "combustible": "Combustible",
    "farmacias": "Salud y farmacias",
    "viajes": "Viajes y transporte",
    "entretencion": "Entretención",
    "vestuario": "Vestuario y hogar",
    "delivery": "Delivery",
    "otros": "Otros",
}

# Palabras clave -> rubro. El orden importa: el primero que coincide gana.
_RUBRO_KW = [
    ("delivery", ["delivery", "rappi", "pedidosya", "uber eats", "cornershop", "justo", "despacho de comida"]),
    ("combustible", ["combustible", "bencina", "copec", "shell", "aramco", "petrobras", "enex", "estacion de servicio", "estaciones de servicio", "gasolina", "diesel"]),
    ("supermercados", ["supermercado", "super 10", "super10", "jumbo", "lider express", "express de lider", "supermercado lider", "supermercados lider", "lider.cl", "santa isabel", "unimarc", "tottus", "acuenta", "mayorista", "alvi", "ok market", "botilleria", "almacen", "feria"]),
    ("farmacias", ["farmacia", "salcobrand", "cruz verde", "ahumada", "dr. simi", "optica", "clinica", "dental", "salud", "bienestar", "gimnasio", "smartfit", "sportlife", "belleza", "peluqueria", "spa"]),
    ("viajes", ["viaje", "hotel", "aerolinea", "latam", "sky airline", "jetsmart", "turismo", "turbus", "pullman", "uber", "cabify", "didi", "arriendo de auto", "rent a car", "transporte", "metro", "estacionamiento", "peaje", "vuelo", "hostal", "lodge"]),
    ("restaurantes", ["restaurant*", "restoran*", "gastronom*", "pizzeria", "coffee", "dulceria", "chocolat*", "bakery", "panader*", "pasteler*", "empanada", "cocina", "food", "cafe", "cafeteria", "sushi", "pizza", "burger", "hamburgues*", "comida", "bar ", "heladeria", "helado", "pasteleria", "panaderia", "starbucks", "juan maestro", "dominos", "mcdonald", "kfc", "bistro", "parrilla", "cerveceria", "brunch"]),
    ("entretencion", ["cine", "cinemark", "cineplanet", "teatro", "concierto", "entretencion", "streaming", "spotify", "netflix", "videojuego", "juego", "parque", "museo", "evento", "ticket", "puntoticket", "musica", "libreria", "libro", "vina", "tour", "kidzania", "ticketmaster", "cinepolis", "cineplanet", "entradas"]),
    ("vestuario", ["vestuario", "ropa", "boutique", "jeans", "lenceria", "joyeria", "accesorios", "carteras", "maletas", "equipaje", "zapat*", "calzado", "moda", "tienda", "falabella", "ripley", "paris", "hites", "la polar", "hogar", "sodimac", "easy", "construccion", "decoracion", "muebles", "tecnologia", "electro*", "deporte", "outdoor", "mascota", "jugueteria", "retail", "mall"]),
]

_DIAS = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]


def sin_tildes(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn")


def limpiar(s: str | None) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def _kw_regex(kw: str) -> re.Pattern:
    """Palabra completa (admite plural: "farmacias", "hoteles"). Con "*" al final es
    un prefijo ("gastronom*" -> gastronomía, gastronómico)."""
    kw = kw.strip()
    if kw.endswith("*"):
        return re.compile(r"(?<![a-z0-9])" + re.escape(kw[:-1]))
    return re.compile(r"(?<![a-z0-9])" + re.escape(kw) + r"(?:s|es)?(?![a-z0-9])")


# Palabras demasiado genéricas para usarlas en descripciones ("compra en nuestra tienda",
# "válido para compras mayoristas", "la plataforma de tecnología..."): solo cuentan en nombre o título
_KW_DEBILES = {"tienda", "tecnologia", "mayorista", "supermercado", "mall", "retail", "moda", "hogar", "salud",
               "bienestar", "evento", "juego", "parque", "transporte", "comida", "musica", "deporte", "viaje",
               "belleza", "ticket", "tour", "bar", "metro", "cocina", "food", "accesorios"}
_RUBRO_RX = [(r, [_kw_regex(k) for k in kws]) for r, kws in _RUBRO_KW]
_RUBRO_RX_DESC = [(r, [_kw_regex(k) for k in kws if k.strip() not in _KW_DEBILES]) for r, kws in _RUBRO_KW]


def _rubro_texto(texto: str, tabla=None) -> str:
    t = " " + sin_tildes(texto).lower() + " "
    for rubro, rxs in tabla or _RUBRO_RX:
        if any(rx.search(t) for rx in rxs):
            return rubro
    return "otros"


def adivinar_rubro(comercio: str = "", titulo: str = "", *otros: str) -> str:
    """Primero el nombre del comercio y el título; la descripción solo si no alcanzan
    (suele traer frases de marketing como "plataforma líder")."""
    r = _rubro_texto(f"{comercio or ''} {titulo or ''}")
    if r != "otros" or not any(otros):
        return r
    return _rubro_texto(" ".join(x or "" for x in otros), _RUBRO_RX_DESC)


def extraer_pct(*textos: str) -> int | None:
    """Mayor porcentaje mencionado (ej. 'hasta 40% dcto' -> 40)."""
    vals = [int(m) for t in textos if t for m in re.findall(r"(\d{1,3})\s?%", t)]
    vals = [v for v in vals if 0 < v <= 100]
    return max(vals) if vals else None


def extraer_dias(*textos: str) -> list[int]:
    """Días de la semana (0=lunes … 6=domingo). Lista vacía = no se pudo determinar."""
    t = sin_tildes(" ".join(x or "" for x in textos)).lower()
    if re.search(r"todos los dias|todos los días|lunes a domingo|7 dias|toda la semana", t):
        return list(range(7))
    dias: set[int] = set()
    # Rangos: "lunes a viernes", "de martes a jueves"
    for a, b in re.findall(r"(" + "|".join(_DIAS) + r")\s+(?:a|al)\s+(" + "|".join(_DIAS) + r")", t):
        i, j = _DIAS.index(a), _DIAS.index(b)
        rng = range(i, j + 1) if i <= j else list(range(i, 7)) + list(range(0, j + 1))
        dias.update(rng)
    for i, d in enumerate(_DIAS):
        if re.search(r"\b" + d + r"s?\b", t):
            dias.add(i)
    if "fin de semana" in t or "fines de semana" in t:
        dias.update({5, 6})
    return sorted(dias)


_COMBUSTIBLE_RX = re.compile(r"(?<![a-z])(combustible|bencina|copec|shell|aramco|petrobras|enex|gasolina|diesel|"
                             r"estacion(?:es)? de servicio)(?![a-z])")
_POR_LITRO_RX = re.compile(r"(por|/|x)\s*(litro|lt)\b")


def _rubro_final(rubro: str | None, comercio: str, titulo: str, descripcion: str) -> str:
    """Rubro del banco si lo informa, si no el deducido; con dos correcciones para Combustible:
    un descuento "por litro" de una bencinera es Combustible aunque el banco lo ponga en otro
    rubro, y Combustible exige que el comercio o el título hablen de combustible
    (mantenciones o arriendo de autos no lo son)."""
    r = rubro if rubro in RUBROS else adivinar_rubro(comercio, titulo, descripcion)
    ct = sin_tildes(f"{comercio} {titulo}").lower()
    # Los bancos usan "Vestuario/Hogar" u "Otros" como categoría amplia: si el nombre del comercio
    # indica claramente otro rubro (un cine, una boletería, una farmacia...), gana el nombre
    if r == "vestuario" and re.search(r"(?<![a-z])(lipigas|abastible|gasco|prosegur)(?![a-z])", sin_tildes(comercio).lower()):
        return "otros"  # gas licuado y seguridad: no son vestuario ni hogar
    if r in ("vestuario", "otros"):
        por_nombre = _rubro_texto(comercio, _RUBRO_RX_DESC)
        if por_nombre not in ("otros", "vestuario", r):
            r = por_nombre
    if _COMBUSTIBLE_RX.search(ct) and (_POR_LITRO_RX.search(ct) or "dcto combustible" in ct or "descuento en combustible" in ct):
        return "combustible"
    if r == "combustible" and not _COMBUSTIBLE_RX.search(ct):
        r2 = adivinar_rubro(comercio, titulo)
        return r2 if r2 != "combustible" else "otros"
    return r


def monto_por_litro(*textos: str) -> int | None:
    """Descuento en pesos por litro ("$100 dcto. por litro", "$$100 dcto/litro") -> 100."""
    t = sin_tildes(" ".join(x or "" for x in textos)).lower()
    m = re.search(r"\$+\s?(\d{2,4})\s*(?:de\s*)?(?:dcto\.?|descuento|dto\.?)?\s*(?:por|/|x)\s*(?:litro|lt)", t)
    return int(m.group(1)) if m else None


def es_solo_cuotas(titulo: str) -> bool:
    """Ofertas de cuotas sin interés (no son descuentos): "Paga hasta en 24 cuotas sin interés"."""
    t = sin_tildes(titulo or "").lower()
    if re.search(r"cuotas? con tasa preferencial|tasa preferencial|credito de consumo|avance en efectivo", t):
        return True
    return bool(re.search(r"cuotas? sin interes", t)) and not re.search(r"\d\s?%|dcto|dto|descuento", t)


def tipo_tarjeta(nombre: str) -> str:
    n = sin_tildes(nombre).lower()
    if "prepago" in n:
        return "prepago"
    if "debito" in n or "cuentarut" in n or "cuenta rut" in n or "cuenta vista" in n:
        return "debito"
    return "credito"


def nuevo_descuento(
    *,
    banco: str,
    comercio: str,
    titulo: str = "",
    descripcion: str = "",
    pct: int | None = None,
    rubro: str | None = None,
    dias: list[int] | None = None,
    tarjetas: list[str] | None = None,
    tope: str | None = None,
    modalidad: str | None = None,
    vigencia_desde: str | None = None,
    vigencia_hasta: str | None = None,
    url: str | None = None,
    imagen: str | None = None,
    ubicaciones: list[str] | None = None,
    regiones: list[str] | None = None,
) -> dict:
    """ubicaciones: textos que son direcciones o lugares ("Av. X 123, Las Condes",
    "Región de Valparaíso"); de ahí se deducen región y comuna.
    regiones: ids de región ya conocidos (ver scraper/regiones.json, ej. "RM", "VS").
    Sin ubicación = descuento válido en todo Chile u online."""
    from scraper import geo

    regs, coms = geo.ubicar([limpiar(u) for u in (ubicaciones or [])])
    validas = {r["id"] for r in geo.regiones()}
    regs = sorted(set(regs) | {r for r in (regiones or []) if r in validas},
                  key=[r["id"] for r in geo.regiones()].index)
    comercio = limpiar(comercio)
    titulo = limpiar(titulo)
    descripcion = limpiar(descripcion)
    tarjetas = [limpiar(t) for t in (tarjetas or []) if limpiar(t)]
    if pct is None:
        pct = extraer_pct(titulo, descripcion)
    if dias is None:
        dias = extraer_dias(titulo, descripcion)
    uid = hashlib.sha1(f"{banco}|{comercio}|{titulo}|{url}".encode()).hexdigest()[:12]
    return {
        "id": f"{banco}-{uid}",
        "banco": banco,
        "comercio": comercio,
        "titulo": titulo,
        "descripcion": descripcion[:600],
        "pct": pct,
        "rubro": _rubro_final(rubro, comercio, titulo, descripcion),
        "dias": sorted(set(dias)),
        "tarjetas": tarjetas,
        "tipos": sorted({tipo_tarjeta(t) for t in tarjetas}) or ["credito"],
        "tope": limpiar(tope) or None,
        "modalidad": limpiar(modalidad) or None,
        "vigencia_desde": vigencia_desde,
        "vigencia_hasta": vigencia_hasta,
        "url": url,
        "imagen": imagen,
        "regiones": regs,
        "comunas": coms,
    }


def sesion() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "es-CL,es;q=0.9"})
    ca = os.environ.get("REQUESTS_CA_BUNDLE") or os.environ.get("SSL_CERT_FILE")
    if ca:
        s.verify = ca
    return s


def chromium_path() -> str | None:
    """Ruta opcional a un Chromium preinstalado (CHROMIUM_PATH)."""
    return os.environ.get("CHROMIUM_PATH") or None


@contextmanager
def navegador():
    """Página de Playwright lista para usar, para sitios que necesitan JavaScript."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        # NAVEGADOR_VISIBLE=1 (computador local): algunos sitios bloquean el navegador invisible
        kw = {"headless": os.environ.get("NAVEGADOR_VISIBLE", "") not in ("1", "true", "si")}
        if chromium_path():
            kw["executable_path"] = chromium_path()
        b = p.chromium.launch(**kw)
        ctx = b.new_context(user_agent=UA, locale="es-CL", viewport={"width": 1366, "height": 900})
        try:
            yield ctx.new_page()
        finally:
            b.close()

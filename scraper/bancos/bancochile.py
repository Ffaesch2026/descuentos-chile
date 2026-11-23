"""Banco de Chile: beneficios desde la API de contenidos que usa sitiospublicos.bancochile.cl.

GET https://sitiospublicos.bancochile.cl/api/content/spaces/personas/types/beneficios/entries
    ?per_page=100&page=N   (JSON paginado, ~900 beneficios, no requiere navegador)
"""
from __future__ import annotations

import html
import re
import time
from datetime import datetime, timedelta, timezone

from scraper import common

BANCO = {
    "id": "bancochile",
    "nombre": "Banco de Chile",
    "sitio": "https://sitiospublicos.bancochile.cl/personas/beneficios",
}

API = "https://sitiospublicos.bancochile.cl/api/content/spaces/personas/types/beneficios/entries"
DETALLE = "https://sitiospublicos.bancochile.cl/personas/beneficios/detalle/"

TARJETAS = {
    "visa-credito-infinite": "Visa Infinite crédito",
    "visa-credito-signature": "Visa Signature crédito",
    "visa-credito-platinum": "Visa Platinum crédito",
    "visa-credito-gold": "Visa Gold crédito",
    "visa-fan-credito": "Visa FAN crédito",
    "mastercard-credito-black": "Mastercard Black crédito",
    "mastercard-credito-platinum": "Mastercard Platinum crédito",
    "mastercard-credito-dorada": "Mastercard Dorada crédito",
    "visa-debito-infinite": "Visa Infinite débito",
    "visa-debito-signature": "Visa Signature débito",
    "visa-debito-bch": "Visa débito Banco de Chile",
    "visa-cuenta-fan": "Visa Cuenta FAN débito",
    "All": "Tarjetas Banco de Chile",
}

# Prefijo de categoría -> rubro (None = adivinar por texto)
CATEGORIAS = [
    ("beneficios/sabores", "restaurantes"),
    ("beneficios/delivery", "delivery"),
    ("beneficios/bienestar", "farmacias"),
    ("beneficios/panoramas", "entretencion"),
    ("beneficios/viajes", "viajes"),
]

DIAS_TAG = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]


def _texto(h: str | None) -> str:
    t = re.sub(r"<(br|/p|/li|li)[^>]*>", " . ", h or "")
    return common.limpiar(html.unescape(re.sub(r"<[^>]+>", " ", t))).replace(" . .", " .")


def _fecha_es(texto: str) -> str | None:
    t = common.sin_tildes(texto).lower()
    m = re.search(r"hasta el (\d{1,2}) de (" + "|".join(MESES) + r")(?: (?:de|del) (\d{4}))?", t)
    if not m:
        return None
    d, mes, a = int(m.group(1)), MESES.index(m.group(2)) + 1, m.group(3)
    if not a:
        return None
    try:
        return datetime(int(a), mes, d).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _desde_utc(iso: str | None) -> str | None:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    # Hora de Chile (aprox. UTC-3/-4): unpublish 02:45Z = 23:45 del día anterior
    return (dt.astimezone(timezone(timedelta(hours=-4)))).strftime("%Y-%m-%d")


def _tope(texto: str) -> str | None:
    m = re.search(r"(tope[^;()$]{0,50}?\$\s?\d[\d.]*\d)", texto, re.I)
    if m:
        return m.group(1)
    m = re.search(r"(tope de (?:dto|dcto|descuento)[^.;()]{0,40})", texto, re.I)
    return m.group(1) if m else None


def _modalidad(texto: str) -> str | None:
    t = common.sin_tildes(texto).lower()
    pres = "presencial" in t
    onl = "online" in t or "on line" in t or "sitio web" in t or "compra web" in t
    if pres and onl:
        return "Presencial y Online"
    if onl:
        return "Online"
    if pres:
        return "Presencial"
    return None


def _rubro(cat: str, tags: list[str]) -> str | None:
    for pref, r in CATEGORIAS:
        if cat.startswith(pref):
            return r
    if "vestuario-y-calzado" in tags or "hogar" in tags:
        return "vestuario"
    return None


def scrape() -> list[dict]:
    s = common.sesion()
    entradas, page, total = [], 1, 1
    while page <= total and page <= 30:
        r = s.get(API, params={"per_page": 100, "page": page}, timeout=common.TIMEOUT)
        r.raise_for_status()
        d = r.json()
        entradas.extend(d.get("entries", []))
        total = d.get("meta", {}).get("total_pages", 1)
        page += 1
        time.sleep(0.3)

    out = []
    for e in entradas:
        meta, f = e.get("meta", {}), e.get("fields", {})
        tipo = common.limpiar(f.get("Tipo Beneficio")).replace(";", "")
        extracto = common.limpiar(f.get("Extracto"))
        desc = _texto(f.get("Descripcion"))
        cond = common.limpiar(f.get("Condiciones Comerciales"))
        pct = common.extraer_pct(tipo) or common.extraer_pct(desc)
        if not pct:
            continue  # cuotas sin interés, canje de puntos, etc.
        tags = [common.sin_tildes(t).lower() for t in meta.get("tags", [])]
        dias = [i for i, d in enumerate(DIAS_TAG) if d in tags]
        if not dias:
            dias = common.extraer_dias(extracto) or common.extraer_dias(desc)
        tarjetas = [TARJETAS.get(t, t) for t in f.get("Tarjetas Permitidas") or []]
        if "Tarjetas Banco de Chile" in tarjetas and len(tarjetas) > 1:
            tarjetas.remove("Tarjetas Banco de Chile")
        comercio = f.get("Titulo") or meta.get("name") or ""
        vigencia = common.limpiar(f.get("Vigencia"))
        out.append(common.nuevo_descuento(
            banco=BANCO["id"],
            comercio=comercio,
            titulo=f"{tipo} {extracto}".strip() if tipo else extracto,
            descripcion=f"{desc} {cond}",
            pct=pct,
            rubro=_rubro(meta.get("category") or "", tags),
            dias=dias,
            tarjetas=tarjetas,
            tope=_tope(f"{desc} {cond}"),
            modalidad=_modalidad(f"{extracto} {desc}"),
            vigencia_desde=None,
            vigencia_hasta=_fecha_es(vigencia) or _fecha_es(cond) or _desde_utc(meta.get("unpublish_at")),
            url=DETALLE + meta["slug"] if meta.get("slug") else BANCO["sitio"],
            imagen=(f.get("Logo") or {}).get("url"),
        ))
    return out

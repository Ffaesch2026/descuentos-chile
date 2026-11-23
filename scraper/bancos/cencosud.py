"""Tarjeta Cencosud Scotiabank — https://www.tarjetacencosud.cl/publico/beneficios/landing/inicio

La landing de beneficios trae embebido (en `window.CardsAPI.getCards`) un arreglo JSON
con todos los beneficios: título, descripciones, texto legal, categorías y URL de detalle.
No hay campos estructurados de % / días / vigencia, así que se extraen del título,
la descripción corta y el texto legal.
"""
from __future__ import annotations

import html as htmlmod
import json
import re
from datetime import date

from scraper import common

SITIO = "https://www.tarjetacencosud.cl/publico/beneficios/landing/inicio"
BANCO = {"id": "cencosud", "nombre": "Tarjeta Cencosud Scotiabank", "sitio": SITIO}

# Categorías del sitio que no son descuentos en comercios.
_NO_DESCUENTO = {"cuotas", "seguros", "donaciones", "beneficio-usabilidad"}
_CAT_RUBRO = {"comida": "restaurantes", "salud": "farmacias", "viajes": "viajes"}
_MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre"]
_MES = "(" + "|".join(_MESES) + ")"


def _texto(h: str) -> str:
    return common.limpiar(htmlmod.unescape(re.sub(r"<[^>]+>", " ", h or "")))


def _beneficios(page: str) -> list[dict]:
    for m in re.finditer(r'\[\{"id":\d+,"is_active"', page):
        try:
            arr, _ = json.JSONDecoder().raw_decode(page, m.start())
        except ValueError:
            continue
        if isinstance(arr, list) and arr and isinstance(arr[0], dict) and "title" in arr[0]:
            return arr
    return []


def _d(dia: str, mes: str, anio: str) -> date | None:
    try:
        return date(int(anio), _MESES.index(mes) + 1, int(dia))
    except ValueError:
        return None


def _vigencia(legal: str) -> tuple[date | None, date | None]:
    t = common.sin_tildes(legal).lower()
    m = re.search(r"(?:desde el|desde|del|entre el)\s+(\d{1,2})(?: de " + _MES + r")?(?: de(?:l)? \d{4})?\s+(?:al|y el|hasta el)\s+(\d{1,2}) de "
                  + _MES + r",? de(?:l)? (\d{4})", t)
    if m:
        return _d(m.group(1), m.group(2) or m.group(4), m.group(5)), _d(m.group(3), m.group(4), m.group(5))
    m = re.search(r"hasta el (\d{1,2}) de " + _MES + r",? de(?:l)? (\d{4})", t)
    if m:
        return None, _d(m.group(1), m.group(2), m.group(3))
    m = re.search(r"(?:mes de|durante|dias de|miercoles de|lunes de|martes de|jueves de|viernes de|sabados? de|domingos? de|de) "
                  + _MES + r",? (?:de |del )?(\d{4})", t)
    if m:
        mes, anio = _MESES.index(m.group(1)) + 1, int(m.group(2))
        fin = date(anio + (mes == 12), mes % 12 + 1, 1)
        return date(anio, mes, 1), date.fromordinal(fin.toordinal() - 1)
    return None, None


def _comercio(b: dict) -> str:
    titulo = common.limpiar(b.get("title"))
    m = re.search(r"\ben ((?:[A-ZÁÉÍÓÚÑ0-9][\w'’&.\-]*)(?: (?:de |y |a )?[A-ZÁÉÍÓÚÑ0-9][\w'’&.\-]*)*)", titulo)
    genericos = ("tarjeta", "chile", "restaurantes", "clinicas", "clinicas dentales", "farmacias", "tiendas")
    if m and common.sin_tildes(m.group(1)).lower().split(" de ")[0] not in genericos:
        return m.group(1).rstrip(".")
    kw = (b.get("keywords") or [None])[0] or (b.get("url") or "").rstrip("/").rsplit("/", 1)[-1]
    if kw:
        return " ".join(w.capitalize() for w in kw.split("-"))
    return titulo


def _tarjetas(cats: list[str], texto: str) -> list[str]:
    t = common.sin_tildes(texto).lower()
    out = []
    if "black" in cats or "mastercard black" in t:
        out.append("Tarjeta Cencosud Scotiabank Mastercard Black")
    if set(cats) - {"black"} or not out:
        if "mastercard" in t or "mastercard" in cats or not out:
            out.append("Tarjeta Cencosud Scotiabank Mastercard")
        if re.search(r"\bvisa\b", t):
            out.append("Tarjeta Cencosud Scotiabank Visa")
    return out


def _modalidad(texto: str) -> str | None:
    t = common.sin_tildes(texto).lower()
    partes = []
    if re.search(r"presencial|en locales|en tiendas|en tienda|mes[oó]n|en cajas", t):
        partes.append("Presencial")
    if re.search(r"online|sitio web|pagina web|\.cl\b|\.com\b|www\.", t):
        partes.append("Online")
    if re.search(r"\bapp\b", t):
        partes.append("App")
    return " / ".join(partes) or None


_REGION_TXT = re.compile(r"\b(?:[IVX]{1,4} regi[oó]n|regi[oó]n (?:de |del |de la )?[A-ZÁÉÍÓÚÑ][\w'’]+(?: (?:de |y )?[A-ZÁÉÍÓÚÑ][\w'’]+)*)", re.I)


def _ubicacion(b: dict, cab: str, modalidad: str | None) -> tuple[list[str], list[str]]:
    """(ubicaciones, regiones) del beneficio. `locations` es una lista de ciudades
    (hoy solo "Santiago", que como ciudad equivale a la RM y no a la comuna).
    Ofertas solo online/app no se restringen a la ciudad declarada."""
    ubic, regs = [], []
    if modalidad is None or "Presencial" in modalidad:
        for l in b.get("locations") or []:
            l = common.limpiar(l if isinstance(l, str) else (l or {}).get("name") or "")
            if not l:
                continue
            if common.sin_tildes(l).lower() == "santiago":
                regs.append("RM")
            else:
                ubic.append(l)
    # Menciones explícitas de región en título/bajada ("¡Atención V Región!")
    ubic += [m.group(0) for m in _REGION_TXT.finditer(cab)]
    return ubic, regs


def scrape() -> list[dict]:
    s = common.sesion()
    r = s.get(SITIO, timeout=common.TIMEOUT)
    r.raise_for_status()
    beneficios = _beneficios(r.text)
    if not beneficios:
        raise RuntimeError("no se encontró el JSON de beneficios (CardsAPI) en la landing de Tarjeta Cencosud")
    hoy = date.today()
    items = []
    for b in beneficios:
        if not b.get("is_active", True):
            continue
        cats = [c for c in b.get("categories") or [] if isinstance(c, str)]
        titulo = common.limpiar(b.get("title"))
        corta = common.limpiar(b.get("short_description"))
        larga = common.limpiar(b.get("long_description"))
        legal = _texto(b.get("legal_text"))
        cab = f"{titulo} {corta}"
        if re.search(r"cuotas? (sin inter|precio contado)|^seguro", titulo, re.I):
            continue
        pct = common.extraer_pct(cab)
        monto = re.search(r"\$\s?[\d.]+ de (?:dcto|descuento)|descuento (?:de )?\$\s?[\d.]+|(?:dcto|descuento) por litro", cab, re.I)
        if pct is None and not monto:
            # Beneficios sin descuento explícito (puntos, seguros, despacho gratis…) se omiten,
            # salvo que el texto legal deje claro un % de descuento.
            if set(cats) & _NO_DESCUENTO or not re.search(r"descuento|dcto", cab + " " + legal, re.I):
                continue
            pct = common.extraer_pct(legal)
            if pct is None:
                continue
        desde, hasta = _vigencia(legal)
        if hasta and hasta < hoy:
            continue
        dias = common.extraer_dias(cab)
        if not dias:
            dias = common.extraer_dias(legal)
        tope = None
        mt = re.search(r"(sin tope|tope[^$.]{0,30}\$\s?\d[\d.]*\d)", f"{cab} {legal}", re.I)
        if mt:
            tope = mt.group(1)
        comercio = _comercio(b)
        rubro = common.adivinar_rubro(comercio, titulo, corta)
        if rubro == "otros":
            rubro = next((_CAT_RUBRO[c] for c in cats if c in _CAT_RUBRO), None)
        modalidad = _modalidad(f"{cab} {legal}")
        ubic, regs = _ubicacion(b, cab, modalidad)
        desc = " ".join(x for x in (corta, larga if larga != corta else "", legal) if x)
        items.append(common.nuevo_descuento(
            banco=BANCO["id"],
            comercio=comercio,
            titulo=titulo,
            descripcion=desc,
            pct=pct,
            rubro=rubro,
            dias=dias,
            tarjetas=_tarjetas(cats, f"{cab} {legal}"),
            tope=tope,
            modalidad=modalidad,
            vigencia_desde=desde.isoformat() if desde else None,
            vigencia_hasta=hasta.isoformat() if hasta else None,
            url=b.get("url") or SITIO,
            imagen=b.get("logo_card") or b.get("card_img"),
            ubicaciones=ubic,
            regiones=regs,
        ))
    return items

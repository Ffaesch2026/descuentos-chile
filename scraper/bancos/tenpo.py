"""Tenpo: beneficios publicados en tenpo.cl/beneficios (sitio Webflow).

El listado es HTML servidor (colección CMS de Webflow, paginada con ?ca01dc3d_page=N).
Cada tarjeta trae nombre, categoría, tipo de tarjeta y días; la página de detalle
trae la descripción completa (condiciones, topes, vigencia).
"""
from __future__ import annotations

import calendar
import html
import re
import time

from scraper import common

BANCO = {"id": "tenpo", "nombre": "Tenpo", "sitio": "https://www.tenpo.cl/beneficios"}

BASE = "https://www.tenpo.cl"
CREDITO = "Tenpo Mastercard Crédito"
PREPAGO = "Tenpo Mastercard Prepago"

_MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre"]

_CATEGORIA_RUBRO = {
    "foodie": "restaurantes", "restobares": "restaurantes", "combustibles": "combustible",
    "automotriz": "combustible", "farmacias": "farmacias", "salud": "farmacias",
    "deporte": "farmacias", "viajes": "viajes", "entretenimiento": "entretencion",
    "mascotas": "vestuario",
}


def _texto(fragmento: str) -> str:
    t = re.sub(r"<br\s*/?>|</p>|</li>", " ", fragmento)
    return common.limpiar(html.unescape(re.sub(r"<[^>]+>", " ", t)))


def _campo(card: str, nombre: str) -> list[str]:
    pat = r'fs-cmsfilter-field="' + nombre + r'"[^>]*>([^<]*)<'
    return [common.limpiar(html.unescape(v)) for v in re.findall(pat, card) if common.limpiar(v)]


def _clase(bloque: str, clase: str) -> str:
    m = re.search(r'class="[^"]*\b' + re.escape(clase) + r'\b[^"]*"[^>]*>(.*?)</div>', bloque, re.S)
    return _texto(m.group(1)) if m else ""


def _listado(s) -> list[dict]:
    cards, vistos = [], set()
    for page in range(1, 30):
        url = BANCO["sitio"] + (f"?ca01dc3d_page={page}" if page > 1 else "")
        r = s.get(url, timeout=common.TIMEOUT)
        r.raise_for_status()
        partes = r.text.split('class="beneficio-collection-item')[1:]
        nuevos = 0
        for p in partes:
            href = re.search(r'href="(/beneficios/[^"]+)"', p)
            if not href or href.group(1) in vistos:
                continue
            vistos.add(href.group(1))
            nuevos += 1
            img = re.search(r'background-image:url\(&quot;([^&]+)&quot;\)', p)
            cards.append({
                "href": href.group(1),
                "nombre": (_campo(p, "Name") or [""])[0],
                "categoria": (_campo(p, "Categoria") or [""])[0],
                "tipos": _campo(p, "Tipo"),
                "dias": _campo(p, "días"),
                "titulo": _clase(p, "titulo-beneficio-all"),
                "bajada": _clase(p, "p-text-beneficio-copy"),
                "imagen": img.group(1) if img else None,
            })
        if not nuevos or f"ca01dc3d_page={page + 1}" not in r.text:
            break
        time.sleep(0.5)
    return cards


def _detalle(s, href: str) -> tuple[str, list[str]]:
    try:
        r = s.get(BASE + href, timeout=common.TIMEOUT)
        r.raise_for_status()
    except Exception:  # noqa: BLE001
        return "", []
    t = r.text
    m = re.search(r'class="all-text-beneficios[^"]*">(.*?)</div>', t, re.S)
    desc = _texto(m.group(1)) if m else ""
    extras = []
    m = re.search(r'class="lista-destacada-beneficios"(.*?)class="interes"', t, re.S)
    if m:
        for li in re.findall(r"<li(?![^>]*w-condition-invisible)[^>]*>(.*?)</li>", m.group(1), re.S):
            x = _texto(li)
            if x and "términos y condiciones" not in x.lower():
                extras.append(x)
    return desc, extras


def _tarjetas(tipos: list[str], texto: str) -> list[str]:
    tt = common.sin_tildes(" ".join(tipos)).lower()
    tx = common.sin_tildes(texto).lower()
    if "debito" in tt or "prepago" in tt:
        return [CREDITO, PREPAGO]
    if re.search(r"prepago|debito|debido", tx) and "credito" in tx:
        return [CREDITO, PREPAGO]
    if "credito" in tt:
        return [CREDITO]
    if re.search(r"tarjetas? de credito", tx) and not re.search(r"prepago|debito", tx):
        return [CREDITO]
    if re.search(r"prepago|debito", tx) and "credito" not in tx:
        return [PREPAGO]
    return [CREDITO, PREPAGO]


def _vigencia(href: str, texto: str) -> tuple[str | None, str | None]:
    t = common.sin_tildes(texto).lower()
    meses = "|".join(_MESES)
    # "del 25 al 30 de noviembre de 2026" / "25 a 30 de noviembre"
    m = re.search(r"(\d{1,2})\s+(?:de\s+(" + meses + r")\s+)?(?:a|al|hasta(?: el)?)\s+(?:el\s+)?(\d{1,2})\s+de\s+(" + meses + r")(?:\s+(?:de|del)\s+(\d{4}))?", t)
    anio_slug = re.search(r"(" + meses + r")-(\d{4})", href)
    if m:
        anio = int(m.group(5) or (anio_slug.group(2) if anio_slug else time.strftime("%Y")))
        m1 = _MESES.index(m.group(2) or m.group(4)) + 1
        m2 = _MESES.index(m.group(4)) + 1
        try:
            return (f"{anio:04d}-{m1:02d}-{int(m.group(1)):02d}", f"{anio:04d}-{m2:02d}-{int(m.group(3)):02d}")
        except ValueError:
            pass
    m = re.search(r"(?:hasta|vigente hasta)\s+el\s+(\d{1,2})\s+de\s+(" + meses + r")(?:\s+(?:de|del)\s+(\d{4}))?", t)
    if m:
        anio = int(m.group(3) or (anio_slug.group(2) if anio_slug else time.strftime("%Y")))
        mes = _MESES.index(m.group(2)) + 1
        desde = f"{anio:04d}-{mes:02d}-01" if anio_slug and _MESES.index(anio_slug.group(1)) + 1 == mes else None
        return desde, f"{anio:04d}-{mes:02d}-{int(m.group(1)):02d}"
    m = re.match(r"(\d{1,2}) de (" + meses + r")\b", t)
    if m:  # fecha única (ej. "09 de Noviembre")
        anio = int(anio_slug.group(2)) if anio_slug else int(time.strftime("%Y"))
        f = f"{anio:04d}-{_MESES.index(m.group(2)) + 1:02d}-{int(m.group(1)):02d}"
        return f, f
    if anio_slug:  # la ficha es la campaña de ese mes (ej. ".../papa-johns-noviembre-2026")
        mes, anio = _MESES.index(anio_slug.group(1)) + 1, int(anio_slug.group(2))
        return f"{anio:04d}-{mes:02d}-01", f"{anio:04d}-{mes:02d}-{calendar.monthrange(anio, mes)[1]:02d}"
    return None, None


def _tope(texto: str) -> str | None:
    m = re.search(r"(tope[^.;]*?\$\s?[\d.]+[^.;]*|m[aá]ximo de \$\s?[\d.]+[^.;]*|hasta \$\s?[\d.]+[^.;]*)", texto, re.I)
    return m.group(1)[:120] if m else None


def _modalidad(texto: str) -> str | None:
    t = common.sin_tildes(texto).lower()
    t = re.sub(r"no (aplica|valido|es valido)[^.]{0,40}(presencial|tienda fisica|online|app)\w*", " ", t)
    online = bool(re.search(r"online|pagina web|sitio web|ecommerce|\bweb\b|www\.|codigo|cupon", t))
    app = bool(re.search(r"\bapp\b|aplicacion", t))
    presencial = bool(re.search(r"presencial|en tienda|en local|locales|sucursal|restoran|en el local", t))
    if presencial and not (online or app):
        return "Presencial"
    if app and not (online or presencial):
        return "App"
    if online and not presencial:
        return "Online"
    return None


def _es_descuento(texto: str) -> bool:
    t = common.sin_tildes(texto).lower()
    if re.search(r"\b0\s?% (de )?comision", t):
        return False
    if "%" in t:
        return True
    return bool(re.search(r"\$\s?[\d.]+.{0,40}(dcto|descuento|devolucion)|(dcto|descuento|devolucion).{0,30}\$\s?[\d.]+", t))


def scrape() -> list[dict]:
    s = common.sesion()
    cards = _listado(s)
    if not cards:
        raise RuntimeError("tenpo.cl/beneficios no devolvió tarjetas de beneficios (¿cambió el HTML?)")
    out = []
    for c in cards:
        time.sleep(0.3)
        desc, extras = _detalle(s, c["href"])
        texto = " ".join([c["titulo"], c["bajada"], desc] + extras)
        if not _es_descuento(" ".join([c["titulo"], c["bajada"], desc])):
            continue  # cuotas sin interés, sorteos, 0% comisión, etc.
        dias_txt = " ".join(c["dias"] + extras)
        dias = common.extraer_dias(dias_txt) or common.extraer_dias(c["titulo"], desc)
        comercio = re.sub(r"\s*-\s*mastercard\s*$", "", c["nombre"], flags=re.I) or c["titulo"]
        desde, hasta = _vigencia(c["href"], " ".join(c["dias"] + extras + [desc]))
        cat = common.sin_tildes(c["categoria"]).lower()
        out.append(common.nuevo_descuento(
            banco=BANCO["id"],
            comercio=comercio,
            titulo=c["titulo"],
            descripcion=" ".join(x for x in [c["bajada"], desc, " ".join(extras)] if x),
            pct=common.extraer_pct(c["titulo"], c["bajada"], desc),
            rubro=_CATEGORIA_RUBRO.get(cat),
            dias=dias,
            tarjetas=_tarjetas(c["tipos"], " ".join([c["titulo"], c["bajada"], desc])),
            tope=_tope(" ".join([desc, c["titulo"]])),
            modalidad=_modalidad(texto),
            vigencia_desde=desde,
            vigencia_hasta=hasta,
            url=BASE + c["href"],
            imagen=c["imagen"],
        ))
    return out

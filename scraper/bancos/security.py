"""Banco Security: beneficios en personas.bancosecurity.cl/beneficios (Drupal).

www.bancosecurity.cl/beneficios es una página de error; el catálogo real vive en
personas.bancosecurity.cl/beneficios, un listado Drupal paginado (?page=N, "Cargar más").
Cada tarjeta trae categoría, etiqueta de descuento, comercio, descripción, ubicación y días.
La ficha de cada beneficio agrega condiciones (tope), tarjetas aplicables y vigencia.
"""
from __future__ import annotations

import html
import re
import time
from datetime import date

from scraper import common

BANCO = {"id": "security", "nombre": "Banco Security", "sitio": "https://personas.bancosecurity.cl/beneficios"}

BASE = "https://personas.bancosecurity.cl"
LISTADO = BASE + "/beneficios?combine=&sort_bef_combine=field_vigencia_beneficio_value_DESC" \
                 "&sort_by=field_vigencia_beneficio_value&sort_order=DESC&page={}"
PRESUPUESTO_DETALLE = 120  # segundos máximos dedicados a fichas de detalle

CREDITO = "Security Tarjeta de Crédito One"
BLACK = "Security Tarjeta de Crédito Black One"
DEBITO = "Security Tarjeta de Débito Debit"

_CAT_RUBRO = {"gourmet": "restaurantes", "viajes": "viajes", "bienestar": "farmacias",
              "entretencion y deportes": "entretencion", "hogar y tecnologia": "vestuario"}


def _t(fragmento: str) -> str:
    t = re.sub(r"<br\s*/?>|</p>|</div>|</li>", " ", fragmento or "")
    return common.limpiar(html.unescape(re.sub(r"<[^>]+>", " ", t)))


def _cards(s) -> list[dict]:
    cards, vistos = [], set()
    for page in range(0, 60):
        r = s.get(LISTADO.format(page), timeout=common.TIMEOUT)
        r.raise_for_status()
        t = r.text
        nuevos = 0
        for art in re.findall(r"<article\b.*?</article>", t, re.S):
            if "item-card" not in art:
                continue  # sliders de destacados (repiten tarjetas con otro formato)
            href = re.search(r'href="(https://personas\.bancosecurity\.cl/beneficios/[^"]+)"', art)
            if not href or href.group(1) in vistos:
                continue
            vistos.add(href.group(1))
            nuevos += 1
            cat = re.search(r'<span class="coh-inline-element[^"]*">([^<]+)</span>', art)
            label = re.search(r'beneficio-label">\s*<div>(.*?)</div>', art, re.S)
            data = re.search(r'data-container[^>]*>\s*<div>(.*?)</div>', art, re.S)
            desc = re.search(r'class="coh-container description[^>]*>\s*<div>(.*?)</div>', art, re.S)
            lugar = re.search(r'la-map-marker"></i>(.*?)</div>', art, re.S)
            dias = re.search(r'la-calendar-day"></i>(.*?)</div>', art, re.S)
            img = re.search(r'<img[^>]+src="([^"]+)"', art)
            cards.append({
                "url": href.group(1),
                "categoria": _t(cat.group(1)) if cat else "",
                "label": _t(label.group(1)) if label else "",
                "comercio": _t(data.group(1)) if data else "",
                "desc": _t(desc.group(1)) if desc else "",
                "lugar": _t(lugar.group(1)) if lugar else "",
                "dias": _t(dias.group(1)) if dias else "",
                "imagen": BASE + html.unescape(img.group(1)) if img and img.group(1).startswith("/") else None,
            })
        if not nuevos or f"page={page + 1}\" title" not in t:
            break
        time.sleep(0.3)
    return cards


def _detalle(s, url: str) -> dict:
    r = s.get(url, timeout=common.TIMEOUT)
    r.raise_for_status()
    t = r.text
    out = {}
    m = re.search(r'class="coh-container benefit .*?<h1[^>]*>.*?</h1>(.*?)la-credit-card', t, re.S)
    if m:
        cuerpo = re.sub(r"<a\b.*?</a>", " ", m.group(1), flags=re.S)
        out["texto"] = _t(re.split(r'<i class="coh-inline-element las la-map-marker', cuerpo)[0])
    m = re.search(r'la-credit-card[^>]*></i>\s*<div>(.*?)</div>', t, re.S)
    out["tarjetas"] = _t(m.group(1)) if m else ""
    m = re.search(r'beneficio-label">\s*<div>.*?</div>.*?coh-container-boxed"\s*>\s*<div>(.*?)</div>', t, re.S)
    out["legal"] = _t(m.group(1)) if m else ""
    return out


def _tarjetas(campo: str, texto: str) -> list[str]:
    c = common.sin_tildes(campo).lower()
    t = common.sin_tildes(texto).lower()
    if "black" in c or (re.search(r"black one", t) and not re.search(r"tarjetas? one\b|debit", t.replace("black one", ""))):
        return [BLACK]
    out = []
    if re.search(r"\bone\b|credito|mastercard", t):
        out += [CREDITO, BLACK]
    if re.search(r"\bdebit\b|debito", t):
        out.append(DEBITO)
    return out


def _fecha(s: str) -> str | None:
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat() if m else None
    except ValueError:
        return None


def _vigencia(legal: str) -> tuple[str | None, str | None]:
    f = r"(\d{1,2}/\d{1,2}/\d{4})"
    m = re.search(r"(?:desde el|del) " + f + r" (?:hasta el|al) " + f, legal)
    if m:
        return _fecha(m.group(1)), _fecha(m.group(2))
    m = re.search(r"hasta el " + f, legal)
    return (None, _fecha(m.group(1))) if m else (None, None)


def _tope(texto: str) -> str | None:
    m = re.search(r"tope(?: de descuento)?(?: de)?:? ?\$\s?[\d.]+[^.]*", texto, re.I)
    if m:
        return m.group(0)[:120]
    return "Sin tope" if re.search(r"\bsin tope\b", texto, re.I) else None


def _modalidad(texto: str) -> str | None:
    t = common.sin_tildes(texto).lower()
    fis = bool(re.search(r"tienda(s)? fisica|presencial|local(es)?\b|restaurante|en el local", t))
    onl = bool(re.search(r"online|sitio web|pagina web|\bweb\b|cupon|codigo", t))
    app = bool(re.search(r"\bapp\b", t))
    if fis and not (onl or app):
        return "Presencial"
    if app and not fis and not onl:
        return "App"
    if onl and not fis:
        return "Online"
    if fis and (onl or app):
        return "Presencial y Online"
    return None


# Sectores/localidades que no son comunas -> nombre que geo.ubicar() reconoce
_SECTORES = {"chicureo": "Colina", "la dehesa": "Lo Barnechea", "chiloe": "Región de Los Lagos",
             "los rios": "Región de Los Ríos", "valle colchagua": "Región de O'Higgins"}
_ONLINE = re.compile(r"\bweb\b|\bapp\b|online|\.(?:cl|com|life)\b|https?:|www\.", re.I)


def _ubicaciones(lugar: str) -> list[str]:
    """Ubicaciones a partir del campo "lugar" (ícono de mapa) de la tarjeta: comunas
    ("Vitacura, Lo Barnechea y Providencia.") o direcciones separadas por " | ".
    Si el beneficio también vale online/app, aplica en todo Chile -> sin ubicación."""
    if not lugar or _ONLINE.search(lugar):
        return []
    out = []
    for loc in lugar.split("|"):
        partes = [p.strip(" .") for p in loc.split(",") if p.strip(" .")]
        # "Av Padre Hurtado Sur 875, Local C 1057, Las Condes": la calle (con número) puede
        # llamarse como una comuna, así que se descarta y se usa solo lo que sigue.
        if len(partes) > 1 and re.search(r"\d|\bs/n\b", partes[0], re.I):
            partes = partes[1:]
        for p in partes:
            for sector, nombre in _SECTORES.items():
                if re.search(r"(?<!\w)" + sector + r"(?!\w)", common.sin_tildes(p), re.I):
                    p += ", " + nombre
            out.append(p)
    return out


def scrape() -> list[dict]:
    s = common.sesion()
    cards = _cards(s)
    if not cards:
        raise RuntimeError("personas.bancosecurity.cl/beneficios no devolvió tarjetas (¿cambió el HTML?)")
    hoy = date.today().isoformat()
    inicio = time.monotonic()
    out = []
    for c in cards:
        base_txt = " ".join([c["label"], c["desc"]])
        if re.search(r"cuotas sin inter|tasa preferencial|\bCAE\b", base_txt + " " + c["comercio"], re.I) \
                and "%" not in c["label"]:
            continue  # cuotas sin interés / tasas: no son descuentos
        pct = common.extraer_pct(c["label"]) or common.extraer_pct(c["desc"])
        es_monto = re.search(r"\$\s?[\d.]+\s*(de )?(dcto|descuento)|(dcto|descuento) de \$", base_txt, re.I)
        if pct is None and not es_monto:
            continue  # cuotas sin interés, canjes de Security Pesos, etc.
        det = {}
        if time.monotonic() - inicio < PRESUPUESTO_DETALLE:
            try:
                det = _detalle(s, c["url"])
            except Exception:  # noqa: BLE001
                det = {}
            time.sleep(0.15)
        legal = det.get("legal", "")
        desde, hasta = _vigencia(legal)
        if hasta and hasta < hoy:
            continue
        texto = " ".join(x for x in [c["desc"], det.get("texto", ""), legal] if x)
        dias = common.extraer_dias(c["dias"]) or common.extraer_dias(c["desc"])
        cat = common.sin_tildes(c["categoria"]).lower()
        comercio = re.sub(r"\s+[-–]\s+(Mastercard|Visa|Justo)$|^(Mastercard|Visa)\s+[-–]\s+", "", c["comercio"]) or c["comercio"]
        out.append(common.nuevo_descuento(
            banco=BANCO["id"],
            comercio=comercio,
            titulo=c["label"] + (f" en {c['comercio']}" if c["comercio"] else ""),
            descripcion=" ".join(x for x in [c["desc"], c["lugar"], det.get("texto", "")] if x),
            pct=pct,
            rubro=_CAT_RUBRO.get(cat) or common.adivinar_rubro(comercio, c["label"], c["desc"]),
            dias=dias,
            tarjetas=_tarjetas(det.get("tarjetas", ""), " ".join([c["desc"], det.get("texto", ""), legal])),
            tope=_tope(det.get("texto", "") + " " + c["desc"]),
            modalidad=_modalidad(c["desc"] + " " + det.get("texto", "")[:300]),
            vigencia_desde=desde,
            vigencia_hasta=hasta,
            url=c["url"],
            imagen=c["imagen"],
            ubicaciones=_ubicaciones(c["lugar"]),
        ))
    return out

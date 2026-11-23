"""BancoEstado — beneficios "Todo Suma" (bancoestado.cl).

El sitio (AEM detrás de Akamai) devuelve 404 a clientes sin JavaScript, así que se usa
un navegador. Las páginas de beneficios traen todas las tarjetas renderizadas en el HTML
(`div.card-beneficios` con atributos data-*), incluidos los filtros (`data-subfiltros`:
día, modalidad, tipo, medio de pago). Los detalles de cada beneficio "normal" (vigencia,
tope, medios de pago) se piden con fetch() desde la misma página para reutilizar las
cookies de Akamai.
"""
from __future__ import annotations

import html as htmlmod
import json
import re
import time

from bs4 import BeautifulSoup

from scraper import common

BASE = "https://www.bancoestado.cl"
RAIZ = BASE + "/content/bancoestado-public/cl/es/home/home/todosuma---bancoestado-personas"
TODOS = RAIZ + "/todos-beneficios.html"
SABORES = RAIZ + "/un-mes-de-sabores---bancoestado-personas.html"
ENTRETENCION = RAIZ + "/con-bancoestado-la-entretencion-es-para-todo-el-ano---bancoestado-pers.html"

BANCO = {"id": "bancoestado", "nombre": "BancoEstado", "sitio": TODOS}

_MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre"]
_MES_RE = "(" + "|".join(_MESES) + ")"
_DIAS_FILTRO = {"lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3, "viernes": 4,
                "sabado": 5, "sabados": 5, "domingo": 6, "domingos": 6}

# Categoría de la página -> rubro (None = adivinar)
_CAT_RUBRO = {"viajes": "viajes", "bienestar": "farmacias", "vestuario": "vestuario",
              "hogar": "vestuario", "panoramas": "entretencion"}

# Valor del filtro "medio"/"tarjeta" -> nombres de tarjeta
_TARJETAS = {
    "todas las tarjetas": ["Tarjetas de Crédito BancoEstado", "Tarjetas de Débito BancoEstado"],
    "tarjetas de credito": ["Tarjetas de Crédito BancoEstado"],
    "tarjeta cuentarut": ["CuentaRUT débito"],
    "exclusivo tarjeta visa": ["Tarjeta de Crédito Visa BancoEstado"],
    "solo tarjeta de credito visa": ["Tarjeta de Crédito Visa BancoEstado"],
    "exclusivo tarjeta visa platinum": ["Tarjeta de Crédito Visa Platinum BancoEstado"],
    "exclusivo tarjetas de credito mastercard": ["Tarjeta de Crédito Mastercard BancoEstado"],
    "exclusivo cuenta corriente digital": ["Cuenta Corriente Digital débito"],
}


def _norm(s: str) -> str:
    return common.sin_tildes(common.limpiar(s)).lower()


def _tarjetas(valores: list[str], texto_medios: str = "") -> list[str]:
    out: list[str] = []
    for v in valores:
        for t in _TARJETAS.get(_norm(v), [common.limpiar(v)]):
            if t not in out:
                out.append(t)
    if not out and texto_medios:
        t = _norm(texto_medios)
        if "credito" in t:
            out.append("Tarjetas de Crédito BancoEstado")
        if "debito" in t:
            out.append("Tarjetas de Débito BancoEstado")
        if "cuentarut" in t:
            out.append("CuentaRUT débito")
    return out


def _dias_filtro(valores: list[str]) -> list[int] | None:
    vals = [_norm(v) for v in valores]
    if not vals:
        return None
    if "todos los dias" in vals:
        return list(range(7))
    dias = {_DIAS_FILTRO[v] for v in vals if v in _DIAS_FILTRO}
    return sorted(dias) if dias else None


def _modalidad(valores: list[str]) -> str | None:
    vals = {common.limpiar(v) for v in valores if common.limpiar(v)}
    return vals.pop() if len(vals) == 1 else None


def _modalidad_texto(t: str) -> str | None:
    t = _norm(t)
    m = []
    if re.search(r"tienda|local|presencial|sucursal|centro|clinica", t):
        m.append("Presencial")
    if re.search(r"online|sitio web|pagina web|\.cl|\.com|e-commerce|web", t):
        m.append("Online")
    if re.search(r"\bapp\b|aplicacion", t):
        m.append("App")
    return m[0] if len(m) == 1 else None


def _vigencia(texto: str) -> tuple[str | None, str | None]:
    t = _norm(texto)
    m = re.search(
        r"(\d{1,2})\s*(?:de\s+)?" + _MES_RE + r"?\s*(?:de\s+|del\s+)?(\d{4})?\s*(?:al|hasta(?:\s+el)?)\s+"
        r"(\d{1,2})\s*(?:de\s+)?" + _MES_RE + r"\s*(?:de\s+|del\s+)?(\d{4})", t)
    if not m:
        m2 = re.search(r"hasta\s+el\s+(\d{1,2})\s*(?:de\s+)?" + _MES_RE + r"\s*(?:de\s+|del\s+)?(\d{4})", t)
        if m2:
            return None, f"{m2.group(3)}-{_MESES.index(m2.group(2)) + 1:02d}-{int(m2.group(1)):02d}"
        return None, None
    d1, mes1, a1, d2, mes2, a2 = m.groups()
    mes1 = mes1 or mes2
    a1 = a1 or a2
    i1, i2 = _MESES.index(mes1) + 1, _MESES.index(mes2) + 1
    if not m.group(3) and i1 > i2:  # "1 de diciembre al 31 de enero 2027"
        a1 = str(int(a2) - 1)
    return f"{a1}-{i1:02d}-{int(d1):02d}", f"{a2}-{i2:02d}-{int(d2):02d}"


def _tope(texto: str) -> str | None:
    m = re.search(r"(tope[^.$]{0,60}\$\s?[\d.]+(?:[^.]{0,40}?(?:por|mensual|diario|al mes)[^.]{0,30})?)", texto, re.I)
    return common.limpiar(m.group(1)) if m else None


def _subfiltros(card) -> dict:
    raw = card.get("data-subfiltros") or "{}"
    try:
        return json.loads(htmlmod.unescape(raw))
    except ValueError:
        return {}


def _abs(href: str | None) -> str | None:
    if not href:
        return None
    return href if href.startswith("http") else BASE + href


def _detalle(page, url: str) -> dict:
    """Lee las secciones Detalle/Dónde/Medios de Pago/Vigencia de una ficha de beneficio."""
    try:
        h = page.evaluate("u => fetch(u, {credentials: 'include'}).then(r => r.ok ? r.text() : '')", url)
    except Exception:  # noqa: BLE001
        return {}
    if not h:
        return {}
    s = BeautifulSoup(h, "lxml")
    secciones = {}
    for bloque in s.select(".msd-tarifa"):
        tit = bloque.select_one(".msd-title-tarifa")
        txt = bloque.select_one(".msd-text-tarifa")
        if tit and txt:
            secciones[_norm(tit.get_text(" "))] = common.limpiar(txt.get_text(" "))
    for x in s(["script", "style", "header", "footer", "nav"]):
        x.decompose()
    cuerpo = common.limpiar(s.get_text(" "))
    return {"secciones": secciones, "texto": cuerpo}


def _cards(html: str):
    s = BeautifulSoup(html, "lxml")
    return s, s.select("div.card-beneficios[data-card-id]")


def _cargar(page, url: str) -> str:
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    try:
        page.wait_for_selector("div.card-beneficios[data-card-id]", state="attached", timeout=30000)
    except Exception:  # noqa: BLE001
        pass
    page.wait_for_timeout(1500)
    return page.content()


def _desde_ficha(page, card, categoria: str, sub: dict, vistos: set) -> dict | None:
    nombre = common.limpiar(card.get("data-name"))
    a = card.select_one("a.button-card")
    url = _abs(a.get("href")) if a else None
    if not nombre or (url and url in vistos):
        return None
    if url:
        vistos.add(url)
    oferta = common.limpiar(card.get("data-oferta"))
    desc = common.limpiar(card.get("data-descripcion"))
    if "cuotas" in _norm(oferta) and not common.extraer_pct(oferta):
        return None  # cuotas sin interés: no es un descuento
    det =_detalle(page, url) if url and "bancoestado.cl" in url else {}
    if det:
        time.sleep(0.3)
    sec = det.get("secciones", {})
    detalle = sec.get("detalle", "")
    donde = sec.get("donde", "")
    medios = sec.get("medios de pago", "")
    vig = sec.get("vigencia", "")
    texto = det.get("texto", "")

    pct = common.extraer_pct(oferta, desc, detalle)
    dias = _dias_filtro(sub.get("dia", []))
    if dias is None:
        dias = common.extraer_dias(vig, oferta, desc, detalle)
        if not dias and vig and re.search(r"\d{1,2}\s.*\d{4}", vig):
            # Vigencia por rango de fechas sin restricción de día de la semana.
            dias = list(range(7))
    desde, hasta = _vigencia(vig or texto)
    descripcion = " ".join(x for x in [desc, detalle, ("Dónde: " + donde) if donde else "",
                                        ("Vigencia: " + vig) if vig else ""] if x)
    return common.nuevo_descuento(
        banco=BANCO["id"],
        comercio=nombre,
        titulo=f"{oferta} {desc}".strip() if not desc.lower().startswith(oferta.lower()) else desc,
        descripcion=descripcion,
        pct=pct,
        rubro=_CAT_RUBRO.get(categoria),
        dias=dias,
        tarjetas=_tarjetas(sub.get("medio", []) + sub.get("tarjeta", []), medios),
        tope=_tope(" ".join([detalle, texto])),
        modalidad=_modalidad(sub.get("modalidad", [])) or _modalidad_texto(donde),
        vigencia_desde=desde,
        vigencia_hasta=hasta,
        url=url,
        imagen=_abs((card.select_one("img") or {}).get("src")),
    )


def scrape() -> list[dict]:
    out: list[dict] = []
    vistos: set[str] = set()
    with common.navegador() as page:
        # 1) Sabores: restaurantes (tarjetas con modal) + fichas normales de comida.
        soup, cards = _cards(_cargar(page, SABORES))
        for card in cards:
            sub = _subfiltros(card)
            clase = " ".join(card.get("class", []))
            if "--sabores" not in clase:
                tipo = [_norm(t) for t in sub.get("tipo", [])]
                d = _desde_ficha(page, card, "sabores", sub, vistos)
                if d:
                    d["rubro"] = "delivery" if "delivery" in tipo else (
                        "restaurantes" if tipo and "vinos" not in tipo else d["rubro"])
                    out.append(d)
                continue
            nombre = common.limpiar(card.get("data-name"))
            cuando = common.limpiar(card.get("data-oferta"))
            oferta = common.limpiar(card.get("data-tarjeta"))
            zona = ", ".join(sub.get("zona", []))
            modal = soup.find(id=f"modal-ubicacion-{card.get('data-card-id')}")
            condiciones, vig_txt, locales, link = "", "", [], None
            if modal:
                cond = modal.select_one(".modal-body-tarjeta")
                condiciones = common.limpiar(cond.get_text(" ")) if cond else ""
                for p in modal.select(".modal-body > p"):
                    t = common.limpiar(p.get_text(" "))
                    if "vigen" in _norm(t) or "valido desde" in _norm(t):
                        vig_txt = t
                locales = [common.limpiar(li.get_text(" ")) for li in modal.select("li")]
                a = modal.select_one("a.button-card")
                link = a.get("href") if a else None
            dias = _dias_filtro(sub.get("dia", [])) or common.extraer_dias(cuando)
            tipo = [_norm(t) for t in sub.get("tipo", [])]
            desde, hasta = _vigencia(vig_txt)
            desc = " ".join(x for x in [f"{cuando}.", f"Zona: {zona}." if zona else "", condiciones, vig_txt,
                                         ("Locales: " + "; ".join(locales)) if locales else ""] if x)
            out.append(common.nuevo_descuento(
                banco=BANCO["id"],
                comercio=nombre,
                titulo=f"{oferta} en {nombre}",
                descripcion=desc,
                pct=common.extraer_pct(oferta),
                rubro="delivery" if "delivery" in tipo else "restaurantes",
                dias=dias,
                tarjetas=_tarjetas(sub.get("tarjeta", []), condiciones),
                tope=_tope(condiciones),
                modalidad=_modalidad(sub.get("modalidad", [])),
                vigencia_desde=desde,
                vigencia_hasta=hasta,
                url=SABORES + "#" + (card.get("data-card-id") or ""),
                imagen=_abs((card.select_one("img") or {}).get("src")),
            ))

        # 2) Entretención: eventos y panoramas activos (se omiten preventas agotadas).
        try:
            _, cards = _cards(_cargar(page, ENTRETENCION))
        except Exception:  # noqa: BLE001
            cards = []
        for card in cards:
            sub = _subfiltros(card)
            if "Evento Activo" not in sub.get("opciones", []):
                continue
            if not common.extraer_pct(card.get("data-oferta") or ""):
                continue
            d = _desde_ficha(page, card, "panoramas", sub, vistos)
            if d:
                out.append(d)

        # 3) Todos los beneficios (viajes, bienestar, hogar, vestuario, impacto verde, otros).
        _, cards = _cards(_cargar(page, TODOS))
        for card in cards:
            cats = [c for c in (card.get("data-category") or "").split(",") if c and c != "todos"]
            cat = cats[0] if cats else ""
            if cat in ("cuotas", "inicio"):
                continue  # cuotas sin interés: no son descuentos
            d = _desde_ficha(page, card, cat, _subfiltros(card), vistos)
            if d:
                out.append(d)
    if not out:
        raise RuntimeError("BancoEstado: no se encontraron tarjetas de beneficios en las páginas")
    return out

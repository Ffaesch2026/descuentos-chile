"""MACH (MACHBANK, de Bci): beneficios de machbank.cl/beneficios.

La página carga los beneficios desde el CMS de Bci:
    https://www.bci.cl/api/content/spaces/mach/types/beneficios/entries?per_page=10000&meta.tag=beneficios
Cada entrada trae empresa, título, descripción, días (dia_de_promo), medio de pago,
tipo (online/presencial) y un bloque HTML con las bases (vigencia, topes).
"""
from __future__ import annotations

import html
import re
from datetime import date

from scraper import common

BANCO = {"id": "mach", "nombre": "MACH", "sitio": "https://www.machbank.cl/beneficios"}

API = "https://www.bci.cl/api/content/spaces/mach/types/beneficios/entries"
DETALLE = "https://www.machbank.cl/beneficios/detalle/"

CREDITO = "MACHBANK Tarjeta de Crédito"
DEBITO = "MACHBANK Tarjeta Débito"
PREPAGO = "MACHBANK Tarjeta Prepago"
QR = "MACHBANK QR / Botón de pago (cuenta débito)"

_MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre"]
_DIAS = {"lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3, "viernes": 4, "sabado": 5, "domingo": 6}
_CAT_RUBRO = {"restaurantes": "restaurantes", "salud": "farmacias", "transporte": "viajes",
              "entretencion": "entretencion", "mascotas": "vestuario", "retail": "vestuario"}
_NO_DESCUENTO = re.compile(r"pronostic|sorteo|gratis desde|costo \$0|pide tu tarjeta|unicef|donaci", re.I)


def _texto(h: str | None) -> str:
    t = re.sub(r"<[^>]+>", " ", h or "")
    return common.limpiar(html.unescape(t))


def _fecha(s: str) -> str | None:
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{2}|\d{4})", s)
    if not m:
        return None
    d, mth, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    y = y + 2000 if y < 100 else y
    try:
        return date(y, mth, d).isoformat()
    except ValueError:
        return None


def _vigencia(texto: str) -> tuple[str | None, str | None]:
    f = r"(\d{1,2}/\d{1,2}/\d{2,4})"
    m = re.search(r"(?:desde|entre)(?: el)? " + f + r"(?: hasta| al| y)(?: el)? " + f, texto, re.I) \
        or re.search(r"del " + f + r" al " + f, texto, re.I)
    if m:
        return _fecha(m.group(1)), _fecha(m.group(2))
    m = re.search(r"hasta(?: el)? " + f, texto, re.I)
    if m:
        return None, _fecha(m.group(1))
    # "entre el 1 y el 31 de agosto de 2025", "desde el 15 de julio hasta el 30 de septiembre de 2026"
    meses = "|".join(_MESES)
    m = re.search(r"(?:entre|desde) el (\d{1,2})(?: de (" + meses + r"))? (?:y|hasta) el (\d{1,2}) de (" + meses + r") de (\d{4})",
                  common.sin_tildes(texto).lower())
    if m:
        y, m2 = int(m.group(5)), _MESES.index(m.group(4)) + 1
        m1 = _MESES.index(m.group(2)) + 1 if m.group(2) else m2
        try:
            return date(y, m1, int(m.group(1))).isoformat(), date(y, m2, int(m.group(3))).isoformat()
        except ValueError:
            pass
    return None, None


def _tarjetas(medios: list[str], texto: str) -> list[str]:
    out = []
    ms = [common.sin_tildes(m).lower() for m in medios]
    t = common.sin_tildes(texto).lower()
    if "credito" in ms:
        out.append(CREDITO)
    if "debito" in ms:
        out.append(DEBITO)
        if "prepago" in t:
            out.append(PREPAGO)
    if "qr" in ms or "boton" in ms:
        out.append(QR)
    if out:
        return out
    if re.search(r"tarjeta(s)? (de )?credito", t):
        out.append(CREDITO)
    if re.search(r"debito", t):
        out.append(DEBITO)
    if "prepago" in t:
        out.append(PREPAGO)
    if re.search(r"boton (de pago )?machbank|qr machbank|app machbank|selecciona .?(app )?machbank\b|pagando solo con machbank", t):
        out.append(QR)
    if not out and re.search(r"tarjetas machbank", t):
        out = [CREDITO, DEBITO, PREPAGO]
    return out


def _tope(texto: str) -> str | None:
    if re.search(r"\bsin tope\b", texto, re.I):
        return "Sin tope"
    m = re.search(r"tope (?:de )?(?:cashback |descuento )?(?:de )?\$\s?[\d.]+(?: [a-z ]{0,30}?(?:por [a-z]+|mensual(?:es)?))?", texto, re.I)
    return m.group(0) if m else None


def _rubro(cat: str | None, comercio: str, titulo: str, desc: str, bases: str) -> str:
    if cat in _CAT_RUBRO:
        return _CAT_RUBRO[cat]
    r = common.adivinar_rubro(comercio, titulo, desc)
    if r == "otros" and re.search(r"papa ?john|pizz|sushi|burger|restaur", f"{comercio} {titulo}", re.I):
        r = "restaurantes"
    return r if r != "otros" else common.adivinar_rubro(comercio, titulo, desc, bases[:600])


def scrape() -> list[dict]:
    s = common.sesion()
    r = s.get(API, params={"per_page": 10000, "meta.tag": "beneficios"}, timeout=common.TIMEOUT,
              headers={"Accept": "application/json", "Referer": BANCO["sitio"]})
    r.raise_for_status()
    entries = r.json().get("entries", [])
    if not entries:
        raise RuntimeError("la API de beneficios MACH no devolvió entradas")
    hoy = date.today().isoformat()
    out = []
    for e in entries:
        meta, f = e.get("meta", {}), e.get("fields", {})
        if meta.get("unpublish_at") and meta["unpublish_at"][:10] < hoy:
            continue
        titulo = common.limpiar(f.get("titulo") or meta.get("name"))
        desc = _texto(f.get("descripcion"))
        bases = _texto(f.get("conoce_el_beneficio"))
        texto = " ".join([titulo, desc, bases])
        if _NO_DESCUENTO.search(" ".join([titulo, desc])):
            continue
        pct = common.extraer_pct(titulo, desc) or common.extraer_pct(bases)
        if pct is None and not re.search(r"\$\s?[\d.]+\s*(de )?(cashback|dcto|descuento)|(cashback|descuento) de \$", texto, re.I):
            continue  # promos de precio fijo, despacho gratis, etc.
        desde, hasta = _vigencia(bases)
        if hasta and hasta[:4] < hoy[:4]:
            continue  # campaña de un año anterior que sigue publicada
        if hasta and hasta < hoy:
            # Las bases suelen quedar desactualizadas aunque la promo siga en el listado
            # (ej. JetSMART o Restaurantes MACHBANK30 del PDF del mes): no se usan esas fechas.
            desde = hasta = None
        dias = sorted({_DIAS[k] for d in f.get("dia_de_promo") or []
                       if (k := common.sin_tildes(d).lower().strip()) in _DIAS})
        if not dias:
            dias = common.extraer_dias(titulo, desc)
        tipos = [common.sin_tildes(t).lower() for t in f.get("tipo_de_beneficio") or []]
        modalidad = None
        if tipos == ["online"]:
            modalidad = "App" if re.search(r"\bapp\b", titulo + " " + desc, re.I) else "Online"
        elif tipos == ["presencial"]:
            modalidad = "Presencial"
        elif set(tipos) == {"online", "presencial"}:
            modalidad = "Presencial y Online"
        comercio = common.limpiar(f.get("nombre_de_empresa"))
        if not comercio or common.sin_tildes(comercio).lower() in _DIAS or comercio.lower() == "machbank":
            m = re.match(r"Conoce el (?:beneficio|descuento) (?:en|con) ([^:]+?)(?::| Conoce)", bases)
            comercio = common.limpiar(m.group(1)) if m else titulo
        img = (f.get("imagen") or {}).get("url") or (f.get("imagen_banner") or {}).get("url")
        out.append(common.nuevo_descuento(
            banco=BANCO["id"],
            comercio=comercio,
            titulo=titulo,
            descripcion=" ".join([desc, bases]),
            pct=pct,
            rubro=_rubro(meta.get("category_slug"), comercio, titulo, desc, bases),
            dias=dias,
            tarjetas=_tarjetas(f.get("medio_de_pago") or [], " ".join([titulo, desc, bases])),
            tope=_tope(" ".join([desc, bases])),
            modalidad=modalidad,
            vigencia_desde=desde,
            vigencia_hasta=hasta,
            url=DETALLE + meta["slug"] if meta.get("slug") else BANCO["sitio"],
            imagen=img,
        ))
    return out

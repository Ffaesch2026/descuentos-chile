"""BCI: beneficios desde la API de BciPlus que usa www.bci.cl/beneficios/beneficios-bci.

GET https://api.bciplus.cl/bff-loyalty-beneficios/v1/offers?itemsPorPagina=100&pagina=N
La API exige la cabecera pública `ocp-apim-subscription-key` que envía el propio sitio.
Si la clave fija deja de funcionar, se abre la página en Chromium para leerla de nuevo.
"""
from __future__ import annotations

import re
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from scraper import common

BANCO = {
    "id": "bci",
    "nombre": "BCI",
    "sitio": "https://www.bci.cl/beneficios/beneficios-bci",
}

API = "https://api.bciplus.cl/bff-loyalty-beneficios/v1/offers"
DETALLE = "https://www.bci.cl/beneficios/beneficios-bci/detalle/"
CLAVE = "fa981752762743668413b68821a43840"  # clave pública del front de bci.cl
TZ = ZoneInfo("America/Santiago")

DIAS = {"LUNES": 0, "MARTES": 1, "MIERCOLES": 2, "JUEVES": 3, "VIERNES": 4, "SABADO": 5, "DOMINGO": 6}

RUBROS_CAT = [
    ({"Restaurantes", "Antojos", "Comida y bebidas"}, "restaurantes"),
    ({"Supermercados"}, "supermercados"),
    ({"Entretención"}, "entretencion"),
    ({"Viajes"}, "viajes"),
    ({"Wellness", "Bienestar"}, "farmacias"),
    ({"Moda y Vestuario", "Moda", "Hogar", "Mall Sport", "Tecnología y Marketplace", "Deportes", "Deporte"}, "vestuario"),
]

MODELOS = [
    ("mastercard black", "Mastercard Black"),
    ("black", "Mastercard Black"),
    ("signature", "Visa Signature"),
    ("infinite", "Visa Infinite"),
    ("infinte", "Visa Infinite"),
    ("platinum", "Platinum"),
]


def _clave_desde_navegador() -> str | None:
    clave = {}
    with common.navegador() as page:
        def on_request(req):
            k = req.headers.get("ocp-apim-subscription-key")
            if k and "bciplus" in req.url:
                clave["k"] = k
        page.on("request", on_request)
        page.goto(BANCO["sitio"], wait_until="domcontentloaded", timeout=90000)
        for _ in range(20):
            if clave:
                break
            page.wait_for_timeout(1000)
    return clave.get("k")


def _fecha(iso: str | None) -> str | None:
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(TZ).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _tarjetas(subtitulo: str, desc: str) -> list[str]:
    t = common.sin_tildes(subtitulo).lower()
    if "tarjeta" not in t and "credito" not in t and "debito" not in t:
        m = re.search(r"tarjetas? (?:de )?(?:credito|debito)[^.\n]{0,80}", common.sin_tildes(desc).lower())
        t = m.group(0) if m else ""
    out = []
    modelos = []
    for kw, nombre in MODELOS:
        if kw in t and nombre not in modelos:
            modelos.append(nombre)
    if "credito" in t:
        if modelos:
            out += [f"Bci {m} crédito" for m in modelos]
        else:
            out.append("Tarjetas de Crédito Bci")
    if "debito" in t:
        out.append("Tarjetas de Débito Bci")
    if not out and "boton de pago app bci" in t:
        out.append("Botón de Pago App Bci")
    return out


def _tope(texto: str) -> str | None:
    m = re.search(r"(tope[^;()$\n]{0,50}?\$\s?\d[\d.]*\d)", texto, re.I)
    if m:
        return m.group(1)
    m = re.search(r"(sin tope[^.;\n]{0,40})", texto, re.I)
    return m.group(1) if m else None


def _descargar(clave: str) -> list[dict]:
    s = common.sesion()
    s.headers.update({"ocp-apim-subscription-key": clave, "Referer": "https://www.bci.cl/",
                      "Accept": "application/json, text/plain, */*"})
    ofertas, pagina, total = [], 1, 1
    while pagina <= total and pagina <= 30:
        r = s.get(API, params={"itemsPorPagina": 100, "pagina": pagina}, timeout=common.TIMEOUT)
        if r.status_code in (401, 403):
            raise PermissionError(f"HTTP {r.status_code}")
        r.raise_for_status()
        d = r.json()
        ofertas.extend(d.get("ofertas", []))
        total = (d.get("paginado") or {}).get("totalPaginas", 1)
        pagina += 1
        time.sleep(0.3)
    return ofertas


def scrape() -> list[dict]:
    try:
        ofertas = _descargar(CLAVE)
    except PermissionError:
        clave = _clave_desde_navegador()
        if not clave:
            raise RuntimeError("No se pudo obtener la clave de la API de beneficios Bci")
        ofertas = _descargar(clave)

    out = []
    for o in ofertas:
        if not o.get("visibleWeb", True):
            continue
        titulo = common.limpiar(o.get("titulo"))
        subt = common.limpiar(o.get("subtitulo"))
        desc = common.limpiar(o.get("descripcion"))
        legal = common.limpiar(o.get("legal"))
        pct = ((o.get("beneficio") or {}).get("discount") or {}).get("porcentajeDescuento") or None
        if o.get("tipoOfertaPrincipal") != "DISCOUNT":
            continue  # cashback, etc.
        if not pct:
            # sin decimales: "tasa preferencial de 0,49%" no es un 49% de descuento
            sin_dec = [re.sub(r"\d+[.,]\d+\s?%", "", x) for x in (titulo, desc)]
            if "tasa preferencial" not in common.sin_tildes(" ".join(sin_dec)).lower():
                pct = common.extraer_pct(*sin_dec)
        if not pct:
            continue  # cuotas sin interés, montos fijos, cupones en pesos
        pct = int(round(pct))
        sched = o.get("scheduling") or {}
        dias = sorted({DIAS[d] for d in sched.get("dayRecurrence") or [] if d in DIAS})
        tags = [t.get("nombre", "") for t in o.get("tags") or []]
        if not dias:
            dias = common.extraer_dias(" ".join(tags)) or common.extraer_dias(titulo, desc)
        cats = {c.get("titulo") for c in o.get("categorias") or []}
        rubro = next((r for ks, r in RUBROS_CAT if ks & cats), None)
        tl = {common.sin_tildes(t).lower() for t in tags} | {common.sin_tildes(c or "").lower() for c in cats}
        modalidad = ("Presencial y Online" if {"presencial", "online"} <= tl else
                     "Online" if "online" in tl else "Presencial" if "presencial" in tl else None)
        comercio = (o.get("comercio") or {}).get("nombre") or titulo
        dias_txt = sched.get("recurrenceLabel") or ""
        out.append(common.nuevo_descuento(
            banco=BANCO["id"],
            comercio=comercio,
            titulo=f"{titulo} {dias_txt}".strip() if dias_txt and dias_txt.lower() not in titulo.lower() else titulo,
            descripcion=f"{subt} {desc}",
            pct=pct,
            rubro=rubro,
            dias=dias,
            tarjetas=_tarjetas(subt, f"{desc} {legal}"),
            tope=_tope(f"{desc} {legal}"),
            modalidad=modalidad,
            vigencia_desde=_fecha(o.get("fechaInicio")),
            vigencia_hasta=_fecha(o.get("fechaTermino")) if o.get("tieneFechaTermino", True) else None,
            url=DETALLE + o["slug"] if o.get("slug") else BANCO["sitio"],
            imagen=(o.get("imagenes") or {}).get("imagen1"),
        ))
    return out

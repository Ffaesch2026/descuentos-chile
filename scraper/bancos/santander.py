"""Santander Chile: beneficios desde el JSON que usa banco.santander.cl/beneficios.

GET https://banco.santander.cl/beneficios/promociones.json
    ?per_page=500&tags=home-disfrutadores&custom_fields=true
El sitio está detrás de Akamai Bot Manager (curl/requests reciben 403), así que se abre
la página en Chromium y se hace el fetch desde dentro de ella con las cookies obtenidas.
"""
from __future__ import annotations

import html
import re
from datetime import datetime

from scraper import common, geo

BANCO = {
    "id": "santander",
    "nombre": "Santander Chile",
    "sitio": "https://banco.santander.cl/beneficios",
}

API = "/beneficios/promociones.json?per_page=500&page={page}&tags=home-disfrutadores&custom_fields=true&order_by=updated_at&desc=true"

DIAS_TAG = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]

RUBRO_TAG = {"cat-sabores": "restaurantes", "cat-musica": "entretencion"}

_JS_FETCH = """async (u) => {
  const r = await fetch(u, {headers: {'Accept': 'application/json'}, credentials: 'include'});
  return [r.status, await r.text()];
}"""


def _texto(h: str | None) -> str:
    t = re.sub(r"<(br|/p|/li)[^>]*>", ". ", h or "")
    t = common.limpiar(html.unescape(re.sub(r"<[^>]+>", " ", t)).replace("​", ""))
    t = re.sub(r"CAE:?\s*\d+(?:,\d+)?\s?%", "CAE", t)  # tasas, no descuentos
    return re.sub(r"(\s*\.\s*){2,}", ". ", t)


def _fecha(texto: str, palabra: str, anio_def: int | None) -> str | None:
    t = common.sin_tildes(texto).lower()
    m = re.search(palabra + r" (?:el )?(\d{1,2}) de (" + "|".join(MESES) + r")(?:,? (?:de |del )?(\d{4}))?", t)
    if not m:
        return None
    a = int(m.group(3)) if m.group(3) else anio_def
    if not a:
        return None
    try:
        return datetime(a, MESES.index(m.group(2)) + 1, int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _tarjetas(desc: str, tags: list[str]) -> list[str]:
    t = common.sin_tildes(desc).lower()
    m = re.search(r"tarjetas?\s+([^.]{0,80}?santander[^.]{0,40})", t)
    frase = m.group(1) if m else ""
    amex = "amex" in tags or "exclusivo-amex" in tags or "american express" in frase
    limited = "wm-limited" in tags or "exclusivo-limited" in tags or "limited" in frase
    credito = "credito" in frase or any(x in tags for x in ("tarjetas-credito", "tarjeta-credito", "todas-las-tarjetas"))
    debito = "debito" in frase or any(x in tags for x in ("life-y-debito", "tarjetas-debito", "todas-las-tarjetas"))
    if m and ("credito" in frase or "debito" in frase):
        # La frase del beneficio manda por sobre las etiquetas
        credito, debito = "credito" in frase, "debito" in frase
    out = []
    if limited:
        out.append("WorldMember Limited Santander crédito")
    if amex:
        out.append("American Express Santander crédito")
    if credito and not (limited or amex):
        out.append("Tarjetas de Crédito Santander")
    if debito:
        out.append("Tarjetas Débito Santander")
    if "empresas" in tags and not out:
        out.append("Tarjetas de Crédito Santander Empresas")
    return out


def _modalidad(texto: str) -> str | None:
    t = common.sin_tildes(texto).lower().replace("cmfchile.cl", "")
    pres = any(k in t for k in ("presencial", "en local", "tiendas fisicas", "tienda fisica", "consumo en local", "en el establecimiento"))
    onl = any(k in t for k in ("online", "www.", ".cl", "codigo de descuento", "cupon", "sitio web", "app "))
    if pres and onl:
        return "Presencial y Online"
    if onl:
        return "Online"
    if pres:
        return "Presencial"
    return None


def _tope(texto: str) -> str | None:
    m = re.search(r"(tope[^;()$]{0,50}?\$\s?\d[\d.]*\d)", texto, re.I)
    return m.group(1) if m else None


def _ubicacion(cf: dict, tags: list[str]) -> tuple[list[str], list[str]]:
    """(ubicaciones, regiones) desde los campos "Región cobertura" y "Comuna cobertura"
    (listas separadas por comas) o, si faltan, el tag "metropolitana" (sin "regiones"). Vacío = todo Chile."""
    regs, ubic = [], []
    for x in re.split(r",|\s+y\s+", cf.get("Región cobertura") or ""):
        x = x.strip(" .")
        rid = geo.region_por_nombre(x) if x else None
        if rid:
            regs.append(rid)
        elif x:
            ubic.append(f"Región de {x}")
    for x in re.split(r",|\s+y\s+", cf.get("Comuna cobertura") or ""):
        x = x.strip(" .")
        if not x:
            continue
        rid = None if geo.ubicar([x])[1] else geo.region_por_nombre(x)
        if rid:
            regs.append(rid)  # a veces trae regiones: "Metropolitana, O'Higgins"
        else:
            ubic.append(x)
    if not regs and not ubic and "metropolitana" in tags and "regiones" not in tags:
        regs.append("RM")
    return ubic, regs


def _descargar() -> list[dict]:
    import json

    with common.navegador() as page:
        page.goto(BANCO["sitio"], wait_until="domcontentloaded", timeout=90000)
        promos, n, total = [], 1, 1
        for intento in range(6):
            page.wait_for_timeout(4000)
            status, txt = page.evaluate(_JS_FETCH, API.format(page=1))
            if status == 200:
                break
        else:
            raise RuntimeError(f"Santander bloqueó la consulta a promociones.json (HTTP {status})")
        while True:
            d = json.loads(txt)
            promos.extend(d.get("promociones", []))
            total = d.get("meta", {}).get("total_pages", 1)
            n += 1
            if n > total or n > 20:
                break
            page.wait_for_timeout(500)
            status, txt = page.evaluate(_JS_FETCH, API.format(page=n))
            if status != 200:
                raise RuntimeError(f"Santander respondió HTTP {status} en la página {n}")
    return promos


def scrape() -> list[dict]:
    out = []
    hoy = datetime.now()
    for p in _descargar():
        cf = {k: common.limpiar((v or {}).get("value")) for k, v in (p.get("custom_fields") or {}).items()}
        tags = [common.sin_tildes(t).lower() for t in p.get("tags", [])]
        bajada = cf.get("Bajada interna") or cf.get("Bajada externa") or ""
        desc = _texto(p.get("description"))
        cond = _texto(p.get("conditions"))
        pct = common.extraer_pct(bajada) or common.extraer_pct(desc) or common.extraer_pct(cond)
        if not pct or (not common.extraer_pct(bajada) and "cuotas" in bajada.lower()):
            continue  # cuotas sin interés, millas, etc.
        dias: set[int] = set()
        for t in tags:
            for i, d in enumerate(DIAS_TAG):
                if t == d or t.endswith("-" + d):
                    dias.add(i)
            if t in ("todos-los-dias", "todos los dias", "cuarenta-todos-los-dias"):
                dias.update(range(7))
        if not dias:
            dias.update(common.extraer_dias(bajada) or common.extraer_dias(desc))
        rubro = next((RUBRO_TAG[t] for t in tags if t in RUBRO_TAG), None)
        vig = cf.get("Vigencia", "")
        hasta = _fecha(vig, "hasta", hoy.year) or _fecha(cond, "hasta", None)
        desde = _fecha(vig, "desde", hoy.year) or _fecha(cond, "desde", None)
        ubic, regs = _ubicacion(cf, tags)
        out.append(common.nuevo_descuento(
            banco=BANCO["id"],
            comercio=p.get("title") or "",
            titulo=bajada,
            descripcion=f"{desc} {cond}",
            pct=pct,
            rubro=rubro,
            dias=sorted(dias),
            tarjetas=_tarjetas(desc, tags),
            tope=_tope(f"{desc} {cond}"),
            modalidad=_modalidad(desc),
            vigencia_desde=desde,
            vigencia_hasta=hasta,
            url=p.get("url") or BANCO["sitio"],
            imagen=(p.get("covers") or [None])[0],
            ubicaciones=ubic,
            regiones=regs,
        ))
    return out

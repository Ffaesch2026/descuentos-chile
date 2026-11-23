"""Banco Ripley — https://www.bancoripley.cl/beneficios-y-promociones

La página (Angular) consulta un proxy JSON propio: POST /api/call-sp-api con el
header `x-path-api` indicando el endpoint real:
  - /api/sp/beneficios/get-sections-beneficios    -> secciones (Restaurantes, Delivery, …)
  - /api/sp/beneficios/get-activeBox-beneficio     -> secciones "box" (Restofans), idSection=<page>
  - /api/sp/beneficios/get-active-beneficio        -> resto de secciones, idSection=<page>
"""
from __future__ import annotations

import re
import time
from datetime import date

from scraper import common

SITIO = "https://www.bancoripley.cl/beneficios-y-promociones"
API = "https://www.bancoripley.cl/api/call-sp-api"
BANCO = {"id": "ripley", "nombre": "Banco Ripley", "sitio": SITIO}

TARJETAS = {
    "creditBlack": "Tarjeta de Crédito Banco Ripley Mastercard Black",
    "credit": "Tarjeta de Crédito Banco Ripley Mastercard",
    "debit": "Tarjeta de Débito Banco Ripley",
    "prepaid": "Tarjeta Prepago Banco Ripley",
}

SECCION_RUBRO = {
    "restofans": "restaurantes",
    "bienestar-belleza": "farmacias",
    "viajes-y-transportes": "viajes",
}


def _call(s, path: str, data: dict | None = None, method: str = "POST"):
    r = s.post(API, data=data or {}, timeout=common.TIMEOUT, headers={
        "x-path-api": path,
        "x-method-api": method,
        "content-type": "application/x-www-form-urlencoded",
        "accept": "application/json, text/plain, */*",
        "referer": SITIO,
        "origin": "https://www.bancoripley.cl",
    })
    r.raise_for_status()
    j = r.json()
    return j.get("data") or []


def _v(params: dict, key: str) -> str:
    x = params.get(key)
    if isinstance(x, dict):
        x = x.get("value")
    return x if isinstance(x, str) else ""


def _html(t: str) -> str:
    return common.limpiar(re.sub(r"<[^>]+>", " ", t or "").replace("&nbsp;", " "))


def _fecha(v: str) -> date | None:
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", v or "")
    if not m:
        return None
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


_MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre"]


def _hasta_texto(t: str, hoy: date) -> date | None:
    """'Hasta el 30 de noviembre' -> fecha (año actual, o el siguiente si el mes ya pasó hace tiempo)."""
    m = re.search(r"hasta el (\d{1,2}) de (" + "|".join(_MESES) + r")(?: de(?:l)? (\d{4}))?",
                  common.sin_tildes(t).lower())
    if not m:
        return None
    mes = _MESES.index(m.group(2)) + 1
    anio = int(m.group(3)) if m.group(3) else hoy.year + (1 if mes < hoy.month - 6 else 0)
    try:
        return date(anio, mes, int(m.group(1)))
    except ValueError:
        return None


def _tope(*textos: str) -> str | None:
    t = " ".join(textos)
    m = re.search(r"(sin tope|tope[^$.]{0,30}\$\s?\d[\d.]*\d)", t, re.I)
    return m.group(1) if m else None


def _rubro(route: str, *textos: str) -> str | None:
    if route in SECCION_RUBRO:
        return SECCION_RUBRO[route]
    if route == "comidadelivery":
        g = common.adivinar_rubro(*textos)
        return g if g in ("restaurantes", "delivery") else "restaurantes"
    return None


def _lista(details: dict, key: str) -> list[str]:
    x = details.get(key) or {}
    if not isinstance(x, dict) or not (x.get("config") or {}).get("active"):
        return []
    return [common.limpiar(a.get("txtItem", {}).get("value")) for a in x.get("array") or []
            if common.limpiar(a.get("txtItem", {}).get("value"))]


def scrape() -> list[dict]:
    s = common.sesion()
    secciones = _call(s, "/api/sp/beneficios/get-sections-beneficios", method="GET")
    if not secciones:
        raise RuntimeError("la API de Banco Ripley no devolvió secciones")
    hoy = date.today()
    vistos: set[str] = set()
    items = []
    for sec in secciones:
        if not sec.get("active", True):
            continue
        page, route = sec.get("page"), sec.get("route") or ""
        time.sleep(0.3)
        if sec.get("isCreate"):
            beneficios = _call(s, "/api/sp/beneficios/get-active-beneficio", {"idSection": page})
        else:
            cajas = _call(s, "/api/sp/beneficios/get-activeBox-beneficio", {"idSection": page})
            beneficios = [i for c in cajas if (c.get("config") or {}).get("active", True) for i in c.get("items") or []]
        for b in beneficios:
            cfg, p = b.get("config") or {}, b.get("params") or {}
            if not cfg.get("active", True) or cfg.get("id") in vistos:
                continue
            prog = cfg.get("programarDateTime") or {}
            desde = hasta = None
            if prog.get("active"):
                desde = _fecha((prog.get("fechaInicioProgramacion") or {}).get("value"))
                hasta = _fecha((prog.get("fechaFinProgramacion") or {}).get("value"))
                if (hasta and hasta < hoy) or (desde and desde > hoy):
                    continue
            comercio = _v(p, "txtNameComercio")
            vig_txt = common.limpiar(_v(p, "txtVigenciaDetalle") or _v(p, "txtVigenciaCard"))
            dcto = common.limpiar(_v(p, "txtDescuento"))
            if (not comercio or re.search(r"cuotas? sin inter", f"{dcto} {comercio}", re.I)
                    or common.sin_tildes(comercio).lower() == "restofans"):
                continue
            pct = common.extraer_pct(dcto)
            # La sección Mastercard Black mezcla seguros y asistencias: solo se toman descuentos.
            if route == "mastercardblack" and pct is None:
                continue
            if not hasta and vig_txt:
                hasta = _hasta_texto(vig_txt, hoy)
                if hasta and hasta < hoy:
                    continue
            vistos.add(cfg.get("id"))
            validez = common.limpiar(_v(p, "txtValidezBeneficio"))
            corta = common.limpiar(_v(p, "txtDetalleCard"))
            detalle = _html(_v(p, "txtDetalle"))
            sub = common.limpiar(_v(p, "txtSubtitulo"))
            det = p.get("details") or {}
            legal = _html(_v(det, "txtLegal"))
            restr = p.get("boxRestricciones") or {}
            consumo = (restr.get("boxConsumo") or {}).get("valueBox") or ""
            modal = []
            if "consumo_local" in consumo:
                modal.append("Presencial")
            if "online" in consumo or "web" in consumo:
                modal.append("Online")
            if "delivery" in consumo:
                modal.append("Delivery")
            tarj_vals = ((restr.get("boxTarjetas") or {}).get("valueBox") or "").split(",")
            tarjetas = [TARJETAS.get(t.strip(), "") for t in tarj_vals if t.strip()]
            dias = common.extraer_dias(validez)
            if not dias:
                dias = common.extraer_dias(detalle)
            partes = [sub, corta, detalle]
            if validez:
                partes.append(f"Días: {validez}.")
            if vig_txt:
                partes.append(f"Vigencia: {vig_txt}.")
            direcciones = _lista(det, "arrDireccion")
            if direcciones:
                partes.append("Locales: " + "; ".join(direcciones[:5]) + ".")
            link = _v(p, "redirectBeneficio") or ""
            items.append(common.nuevo_descuento(
                banco=BANCO["id"],
                comercio=comercio,
                titulo=f"{dcto} en {comercio}" if dcto else comercio,
                descripcion=" ".join(x for x in partes if x),
                pct=pct,
                rubro=_rubro(route, comercio, sub, corta, detalle),
                dias=dias,
                tarjetas=tarjetas,
                tope=_tope(detalle, legal, corta),
                modalidad=" / ".join(modal) or None,
                vigencia_desde=desde.isoformat() if desde else None,
                vigencia_hasta=hasta.isoformat() if hasta else None,
                url=link if link.startswith("http") else f"{SITIO}#nav-{route}",
                imagen=_v(p, "imgLogo") or _v(p, "imgBackground") or None,
            ))
    return items

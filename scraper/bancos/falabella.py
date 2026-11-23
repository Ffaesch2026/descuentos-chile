"""Banco Falabella / CMR — https://www.bancofalabella.cl/descuentos

El sitio es Next.js (App Router): el listado completo de beneficios viene embebido
en el payload RSC (`self.__next_f.push(...)`) como `benefitCardsData`. Las páginas
de categoría (/descuentos/<slug>) traen el mismo arreglo filtrado, y se usan para
asignar el rubro de cada beneficio.
"""
from __future__ import annotations

import json
import re
import time

from scraper import common

BASE = "https://www.bancofalabella.cl"
BANCO = {"id": "falabella", "nombre": "Banco Falabella / CMR", "sitio": f"{BASE}/descuentos"}

# slug de categoría del sitio -> rubro común (None = dejar que se adivine)
CATEGORIAS = {
    "restaurantes": "restaurantes",
    "antojos": "restaurantes",
    "viajes": "viajes",
    "transporte": "viajes",
    "entretencion": "entretencion",
    "salud": "farmacias",
    "belleza": "farmacias",
    "mercado": "vestuario",
    "hogar": "vestuario",
    "mascotas": "vestuario",
}

_DIAS = {"lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3, "viernes": 4, "sabado": 5, "domingo": 6}


def _rsc(html: str) -> str:
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)</script>', html, re.S)
    return "".join(json.loads('"' + c + '"') for c in chunks)


def _cards(html: str) -> list[dict]:
    s = _rsc(html)
    i = s.find('"benefitCardsData":')
    if i < 0:
        return []
    arr, _ = json.JSONDecoder().raw_decode(s, i + len('"benefitCardsData":'))
    if not isinstance(arr, list):
        return []

    # Referencias RSC del tipo "$78:props:benefitCardsData:12:region" apuntan dentro del mismo arreglo.
    def resolver(v):
        if isinstance(v, str):
            m = re.match(r"^\$[0-9a-f]+:props:benefitCardsData:(.+)$", v)
            if m:
                cur = arr
                try:
                    for k in m.group(1).split(":"):
                        cur = cur[int(k)] if isinstance(cur, list) else cur[k]
                    return resolver(cur)
                except (KeyError, IndexError, ValueError, TypeError):
                    return None
        return v

    out = []
    for a in arr:
        if not isinstance(a, dict) or not isinstance(a.get("benefitCard"), dict):
            continue
        a = {k: resolver(v) for k, v in a.items()}
        a["benefitCard"] = {k: resolver(v) for k, v in a["benefitCard"].items()}
        out.append(a)
    return out


def _fecha(v) -> str | None:
    return v[:10] if isinstance(v, str) and re.match(r"\d{4}-\d{2}-\d{2}", v) else None


def _modalidad(texto: str) -> str | None:
    t = common.sin_tildes(texto).lower()
    pres = "presencial" in t or "totem" in t
    onl = "online" in t or "falabella.com" in t
    app = re.search(r"\bapp\b", t) is not None
    partes = [n for n, ok in (("Presencial", pres), ("Online", onl), ("App", app)) if ok]
    return " / ".join(partes) or None


def scrape() -> list[dict]:
    s = common.sesion()
    r = s.get(BANCO["sitio"], timeout=common.TIMEOUT)
    r.raise_for_status()
    cards = _cards(r.text)
    if not cards:
        raise RuntimeError("no se encontró benefitCardsData en la página de descuentos")

    rubro_por_link: dict[str, str] = {}
    for slug, rubro in CATEGORIAS.items():
        time.sleep(0.3)
        try:
            rc = s.get(f"{BASE}/descuentos/{slug}", timeout=common.TIMEOUT)
            if rc.status_code != 200:
                continue
            for c in _cards(rc.text):
                link = c["benefitCard"].get("linkUrl")
                if link:
                    rubro_por_link.setdefault(link, rubro)
        except Exception:  # noqa: BLE001 — la categoría solo mejora el rubro
            continue

    items = []
    for c in cards:
        bc = c["benefitCard"]
        centro = common.limpiar(str(bc.get("centerDiscountText") or "")).replace("$$", "$")
        abajo = common.limpiar(str(bc.get("bottomDiscountText") or ""))
        arriba = common.limpiar(str(bc.get("topDiscountText") or ""))
        t_low = common.sin_tildes(f"{centro} {abajo}").lower()
        # Canjes de Fpuntos y cuotas sin interés no son descuentos.
        if "fpuntos" in t_low or "cuota" in t_low:
            continue
        comercio = c.get("benefitTitle") or bc.get("title") or ""
        titulo = common.limpiar(bc.get("title") or "")
        desc = common.limpiar(bc.get("description") or "")
        resumen = " ".join(x for x in (arriba, centro, abajo) if x)
        pct = None
        m = re.match(r"^(\d{1,3})\s*%", centro) or (re.match(r"^(\d{1,3})$", centro) if "tope" in abajo.lower() else None)
        if m and 0 < int(m.group(1)) <= 100:
            pct = int(m.group(1))
        dias = sorted({_DIAS[common.sin_tildes(d).lower()] for d in (bc.get("discountDays") or c.get("discountDays") or [])
                       if isinstance(d, str) and common.sin_tildes(d).lower() in _DIAS})
        tarjetas = [t for t in (c.get("creditCards") or []) if isinstance(t, str) and len(t) > 2]
        tope = "Sin tope" if "sin tope" in abajo.lower() or "sin tope" in centro.lower() else None
        link = bc.get("linkUrl") or ""
        url = (BASE + link) if link.startswith("/") else (link or BANCO["sitio"])
        img = bc.get("logoCard") or bc.get("imageCard")
        if isinstance(img, str) and img.startswith("//"):
            img = "https:" + img
        regiones = c.get("region") if isinstance(c.get("region"), list) else []
        extra = ""
        if regiones and len(regiones) < 5:
            extra = " Regiones: " + ", ".join(regiones) + "."
        items.append(common.nuevo_descuento(
            banco=BANCO["id"],
            comercio=comercio,
            titulo=f"{titulo}: {resumen}" if resumen else titulo,
            descripcion=f"{desc}.{extra}" if desc else extra,
            pct=pct,
            rubro=rubro_por_link.get(link),
            dias=dias,
            tarjetas=tarjetas,
            tope=tope,
            modalidad=_modalidad(desc),
            vigencia_desde=_fecha(bc.get("initDate")),
            vigencia_hasta=_fecha(bc.get("endDate") or c.get("limitDate")),
            url=url,
            imagen=img,
        ))
    return items

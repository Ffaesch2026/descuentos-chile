"""Banco BICE.

El sitio de beneficios de BICE (banco.bice.cl) bloquea la lectura automática (Cloudflare),
así que los descuentos en restaurantes se toman de tarjetiando.cl, que publica el listado de
BICE con día, %, tarjeta, tope, comuna y el enlace a la página oficial de cada beneficio
(ese enlace es el que se guarda en `url`). Los descuentos de otros rubros (combustible,
delivery…) se ingresan a mano en data/manuales.json y run.py los agrega.
"""
from __future__ import annotations

import re
import time
from datetime import date

from bs4 import BeautifulSoup

from scraper import common

BANCO = {"id": "bice", "nombre": "Banco BICE", "sitio": "https://banco.bice.cl/personas/beneficios"}
LISTADO = "https://tarjetiando.cl/banco/banco-bice"

_DIAS = {"lun": 0, "mar": 1, "mie": 2, "jue": 3, "vie": 4, "sab": 5, "dom": 6}
_MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre"]


def _dias(linea: str, condiciones: str) -> list[int]:
    t = common.sin_tildes(linea).lower()
    if "todos" in t:
        return list(range(7))
    dias = sorted({_DIAS[m] for m in re.findall(r"\b(lun|mar|mie|jue|vie|sab|dom)\b", t)})
    return dias or common.extraer_dias(condiciones)


def _vigencia(texto: str) -> str | None:
    m = re.search(r"vigente hasta el (\d{1,2}) de (" + "|".join(_MESES) + r")", common.sin_tildes(texto).lower())
    if not m:
        return None
    hoy = date.today()
    mes = _MESES.index(m.group(2)) + 1
    anio = hoy.year + (1 if mes < hoy.month - 6 else 0)
    try:
        return date(anio, mes, int(m.group(1))).isoformat()
    except ValueError:
        return None


def _tarjetas(texto: str) -> list[str]:
    """"Tarjeta Visa Limitless, Tarjeta Visa Infinite, Tarjeta Visa… BICE" -> ["Visa Limitless crédito BICE", …].
    Los nombres cortados ("Tarjeta Visa…") se descartan."""
    t = re.sub(r"\s*\(.*?\)", "", texto).replace("BICE", "").strip(" ,")
    t = re.sub(r"(?i)\s*(de\s+)?banco\s*$", "", t).strip(" ,")
    if re.search(r"(?i)cr[eé]dito y d[eé]bito", t):
        return ["Tarjeta de crédito BICE", "Tarjeta de débito BICE"]
    if re.fullmatch(r"(?i)tarjetas? de cr[eé]dito", t) or not t:
        return ["Tarjeta de crédito BICE"]
    out = []
    for parte in t.split(","):
        parte = parte.strip()
        if not parte or "…" in parte or parte.endswith("..."):
            continue
        parte = re.sub(r"(?i)^tarjetas?\s+", "", parte)
        parte = re.sub(r"(?i)\bcr[eé]dito\b\s*", "", parte).strip()
        out.append(f"{parte} crédito BICE")
    return out or ["Tarjeta de crédito BICE"]


def _parsear(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for a in soup.select("a[data-fuente-oficial]"):
        card = a
        while card.parent is not None and len(card.parent.select("a[data-fuente-oficial]")) == 1:
            card = card.parent
        lineas = [common.limpiar(x) for x in card.get_text("\n").split("\n") if common.limpiar(x)]
        if len(lineas) < 5:
            continue
        comercio = lineas[0]
        # Tras "Banco BICE" viene "·" y el nombre de la tarjeta (a veces en la misma línea)
        tarjeta = "Tarjeta de crédito BICE"
        i_b = next((i for i, l in enumerate(lineas) if l.startswith("Banco BICE")), None)
        if i_b is not None:
            cab = " ".join(lineas[i_b:i_b + 3])
            if "·" in cab:
                tarjeta = cab.split("·", 1)[1].strip()
                tarjeta = re.split(r"\s\d{1,3}\s%", tarjeta)[0].strip()
        idx_pct = next((i for i, l in enumerate(lineas) if re.fullmatch(r"\d{1,3}", l)), None)
        pct = int(lineas[idx_pct]) if idx_pct is not None else None
        resto = lineas[idx_pct + 3:] if idx_pct is not None else lineas[2:]  # tras "50" "%" "dcto."
        dia_linea = resto[0] if resto else ""
        tope = next((l for l in resto if l.lower().startswith("tope")), None)
        cond = card.select_one("p.whitespace-pre-line")
        condiciones = common.limpiar(cond.get_text(" ")) if cond else ""
        # La línea tras el tope (o tras el día) es la comuna y, a veces, el tipo de comida
        i_ver = next((i for i, l in enumerate(resto) if l == "Ver condiciones"), len(resto))
        lugar = [l for l in resto[1:i_ver] if l != tope and not l.lower().startswith("tope")]
        ubicaciones = [l for l in lugar[:1] if "internacional" not in l.lower() and "otro" != l.lower()]
        out.append(common.nuevo_descuento(
            banco=BANCO["id"],
            comercio=comercio,
            titulo=f"{pct}% dcto. en {comercio}" if pct else comercio,
            descripcion=condiciones,
            pct=pct,
            rubro="restaurantes",
            dias=_dias(dia_linea, condiciones),
            tarjetas=_tarjetas(tarjeta),
            tope=tope,
            modalidad="Online" if re.search(r"app|web|online", condiciones.lower()) else "Presencial",
            vigencia_hasta=_vigencia(card.get_text(" ")),
            url=a.get("href"),
            ubicaciones=ubicaciones,
        ))
    return out


def scrape() -> list[dict]:
    s = common.sesion()
    out: list[dict] = []
    for pagina in range(1, 11):
        url = LISTADO if pagina == 1 else f"{LISTADO}/pagina/{pagina}"
        r = s.get(url, timeout=common.TIMEOUT)
        if r.status_code == 404:
            break
        r.raise_for_status()
        items = _parsear(r.text)
        if not items:
            break
        out.extend(items)
        time.sleep(1)
    return out

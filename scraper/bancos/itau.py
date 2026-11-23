"""Itaú Chile — itaubeneficios.cl (WordPress detrás de Cloudflare).

Cloudflare responde 403 a clientes sin JavaScript y también bloquea /wp-json/. Con un
navegador real la primera página de cada sesión carga bien, pero navegar a más páginas
(o pedir fichas con fetch) dispara un desafío interactivo que no se resuelve solo. Por
eso se abre una sesión de navegador corta por cada página de listado (son pocas) y se
usa sólo la información de los listados:
  * /beneficios/beneficios-y-descuentos/  (todas las tarjetas; categoría "Lunes Gourmet",
    etc. indica el día), /beneficios/beneficios-legend/, /beneficios/beneficios-black/
  * /ruta-gourmet/ (redirige a la Ruta Gourmet Black)
  * portada: sección "Días Itaú" (día de la semana en el título) y promociones del mes.
Las fichas individuales (vigencia, tope, días de beneficios no gourmet) no se leen.
"""
from __future__ import annotations

import re
import time

from bs4 import BeautifulSoup

from scraper import common, geo

BASE = "https://itaubeneficios.cl"
BANCO = {"id": "itau", "nombre": "Itaú", "sitio": BASE + "/beneficios/"}

LISTADOS = [
    # (url, tarjetas que el sitio indica para ese grupo)
    (BASE + "/beneficios/beneficios-y-descuentos/", ["Tarjetas Itaú (todas)"]),
    (BASE + "/beneficios/beneficios-legend/", ["Tarjeta de Crédito Itaú Legend"]),
    (BASE + "/beneficios/beneficios-black/", ["Tarjeta de Crédito Itaú Black"]),
    (BASE + "/ruta-gourmet/", ["Tarjeta de Crédito Itaú Black"]),
]
PORTADA = BASE + "/"
PROMOCIONES = BASE + "/promociones-del-mes/"

_CAT_RUBRO = {
    "restaurantes": "restaurantes", "salud y belleza": "farmacias", "hogar": "vestuario",
    "tiempo libre": "entretencion", "viajes": "viajes", "mascotas": "vestuario",
}
_DESAFIO = ("Just a moment...", "Un momento…", "Un momento...")


def _norm(s: str | None) -> str:
    return common.sin_tildes(common.limpiar(s)).lower()


def _cargar(url: str, selector: str) -> str | None:
    """Abre una sesión nueva, carga la página y devuelve el HTML (None si Cloudflare la bloquea)."""
    with common.navegador() as page:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        try:
            page.wait_for_selector(selector, state="attached", timeout=25000)
        except Exception:  # noqa: BLE001
            return None
        page.wait_for_timeout(1000)
        if page.title() in _DESAFIO:
            return None
        return page.content()


def _rubro(categoria: str, comercio: str) -> str | None:
    c = _norm(categoria)
    if "gourmet" in c:
        return "restaurantes"
    return _CAT_RUBRO.get(c) or (common.adivinar_rubro(comercio) if common.adivinar_rubro(comercio) != "otros" else None)


def _items_listado(html: str) -> list[dict]:
    s = BeautifulSoup(html, "lxml")
    out = []
    for a in s.select("a.beneficio__item"):
        href = a.get("href")
        nombre = a.select_one(".beneficio__item__info-location__title")
        nombre = common.limpiar(nombre.get_text(" ") if nombre else a.get("title"))
        lugar = a.select_one(".beneficio__item__info-location__address")
        modo = a.select_one(".beneficio__item__info-location__details")
        cat = a.select_one(".beneficio__item__category__name")
        desc_el = a.select_one(".beneficio__item__info-discount-only__info") or a.select_one(
            "[class*=beneficio__item__info-discount]")
        oferta = common.limpiar(desc_el.get_text(" ") if desc_el else "")
        logo = a.select_one(".beneficio__item__logo img")
        out.append({
            "url": href, "nombre": nombre,
            "lugar": common.limpiar(lugar.get_text(" ") if lugar else ""),
            "modalidad": common.limpiar(modo.get_text(" ") if modo else ""),
            "categoria": common.limpiar(cat.get_text(" ") if cat else ""),
            "oferta": oferta.replace("Adic", "Adicional "),
            "imagen": logo.get("src") if logo else None,
        })
    return out


def _ubicacion(lugar: str) -> tuple[list[str], list[str]]:
    """(ubicaciones, regiones) desde la línea de ubicación del listado: "Vitacura, RM",
    "Chillán, VII Región", "RM", "Todas las regiones". Se usa la comuna y no el número de
    región, que en el sitio a veces está mal ("Punta Arenas, XIV Región")."""
    n = _norm(lugar)
    if not n or "todas las regiones" in n or n in ("regiones", "rm y regiones"):
        return [], []
    partes = [common.limpiar(x) for x in lugar.split(",", 1)]
    comuna, region = partes[0], (partes[1] if len(partes) > 1 else "")
    if _norm(comuna) == "santiago" and _norm(region) == "rm":
        return [], ["RM"]  # "Santiago, RM" se usa para la ciudad completa, no la comuna
    if geo.ubicar([comuna])[1]:
        return [comuna], []
    for x in (region, comuna):
        rid = geo.region_por_nombre(x) or next(iter(geo.ubicar([x])[0]), None) if x else None
        if rid:
            return [], [rid]
    return [], []


def _promos(html: str) -> list[dict]:
    s = BeautifulSoup(html, "lxml")
    out = []
    for it in s.select(".promocion__item"):
        h = it.select_one("h2")
        d = it.select_one(".promocion__item__details")
        a = it.select_one(".promocion__item__btn-more a") or it.select_one("a[href]")
        sec = it.find_parent(class_="promociones-mes-featured-home")
        tsec = sec.select_one(".promociones-mes-featured-home__title") if sec else None
        out.append({
            "titulo": common.limpiar(h.get_text(" ") if h else ""),
            "detalle": common.limpiar(d.get_text(" ") if d else ""),
            "url": a.get("href") if a else None,
            "seccion": common.limpiar(tsec.get_text(" ") if tsec else ""),
        })
    return out


def _comercio_promo(titulo: str) -> str:
    t = re.sub(r"^(lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo)\s+(de\s+)?", "", titulo, flags=re.I)
    t = re.sub(r"^(hasta\s+)?\d+\s?%\s*(de\s+)?(dcto\.?|descuento)\s*(en\s+)?", "", t, flags=re.I)
    t = re.sub(r"^.*?\b(?:dcto\.?|descuento)\s+en\s+", "", t, flags=re.I)
    return common.limpiar(t) or titulo


def scrape() -> list[dict]:
    por_url: dict[str, dict] = {}
    bloqueadas = []
    for i, (url, tarjetas) in enumerate(LISTADOS):
        if i:
            time.sleep(2)
        html = _cargar(url, "a.beneficio__item")
        if not html:
            bloqueadas.append(url)
            continue
        for it in _items_listado(html):
            prev = por_url.get(it["url"])
            if prev:
                for t in tarjetas:
                    if t not in prev["tarjetas"]:
                        prev["tarjetas"].append(t)
                continue
            it["tarjetas"] = list(tarjetas)
            it["listado"] = url
            por_url[it["url"]] = it

    promos: list[dict] = []
    for url in (PORTADA, PROMOCIONES):
        time.sleep(2)
        html = _cargar(url, ".promocion__item")
        if not html:
            bloqueadas.append(url)
            continue
        vistos = {p["url"] for p in promos}
        promos.extend(p for p in _promos(html) if p["url"] not in vistos)

    out: list[dict] = []
    comercios_promo: dict[str, list[int]] = {}
    for p in promos:
        texto = f"{p['titulo']} {p['detalle']}"
        pct = common.extraer_pct(texto)
        if not pct:
            continue  # cuotas sin interés, canjes de puntos, preventas, etc.
        dias = common.extraer_dias(texto)
        comercio = _comercio_promo(p["titulo"])
        n = _norm(texto)
        tarjetas = []
        if "legend" in n:
            tarjetas.append("Tarjeta de Crédito Itaú Legend")
        if "black" in n or "signature" in n:
            tarjetas.append("Tarjeta de Crédito Itaú Black")
        if not tarjetas and ("credito" in n or _norm(p["seccion"]) == "dias itau"):
            # la sección "Días Itaú" dice "Pagando con tus tarjetas de crédito Itaú"
            tarjetas.append("Tarjetas de Crédito Itaú")
        if dias:
            comercios_promo[_norm(comercio)] = dias
        out.append(common.nuevo_descuento(
            banco=BANCO["id"],
            comercio=comercio,
            titulo=p["titulo"],
            descripcion=p["detalle"],
            pct=pct,
            dias=dias,
            tarjetas=tarjetas,
            url=p["url"],
        ))

    for it in por_url.values():
        cat = it["categoria"]
        n_nombre = _norm(it["nombre"])
        if any(n_nombre and (n_nombre in c or c in n_nombre) for c in comercios_promo):
            continue  # ya incluido desde "Días Itaú" con su día
        dias = common.extraer_dias(cat)  # "Lunes Gourmet" -> [0]
        modalidad = it["modalidad"] if it["modalidad"] in ("Presencial", "Online") else None
        # Los beneficios solo online valen en todo Chile aunque el listado muestre una ciudad
        ubic, regs = _ubicacion(it["lugar"]) if it["modalidad"] != "Online" else ([], [])
        out.append(common.nuevo_descuento(
            banco=BANCO["id"],
            comercio=it["nombre"],
            titulo=f"{it['oferta']} de descuento en {it['nombre']}" if it["oferta"] else it["nombre"],
            descripcion=" · ".join(x for x in [cat, it["lugar"], it["modalidad"]] if x),
            pct=common.extraer_pct(it["oferta"]),
            rubro=_rubro(cat, it["nombre"]),
            dias=dias,
            tarjetas=it["tarjetas"],
            modalidad=modalidad,
            url=it["url"],
            imagen=it["imagen"],
            ubicaciones=ubic,
            regiones=regs,
        ))
    if not out:
        raise RuntimeError("Itaú: itaubeneficios.cl bloqueó el acceso (desafío de Cloudflare) en: "
                           + ", ".join(bloqueadas))
    return out

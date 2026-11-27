"""Genera las imágenes de un carrusel de Instagram (1080x1350) con los descuentos de un rubro y región.

Uso:
    python -m instagram.generar --rubro restaurantes --region RM
    python -m instagram.generar --rubro restaurantes --region RM --por-banco 20 --salida instagram/salida

Crea en la carpeta de salida: 01.png, 02.png, … y texto.txt (descripción sugerida del post).
"""
from __future__ import annotations

import argparse
import html
import json
import os
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "descuentos.json"
REGIONES = json.loads((ROOT / "scraper" / "regiones.json").read_text("utf-8"))["regiones"]

CUENTA = "@descuentosalmes"
W, H = 1080, 1350
FILAS_COLUMNA = 21          # filas de descuentos por columna (2 columnas por imagen)
ENCABEZADO = 2              # un encabezado de banco ocupa lo mismo que ~2 filas
MAX_IMAGENES = 10           # límite de un carrusel de Instagram

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]
RUBROS = {"restaurantes": "Restaurantes", "supermercados": "Supermercados", "combustible": "Combustible",
          "farmacias": "Salud y farmacias", "viajes": "Viajes y transporte", "entretencion": "Entretención",
          "vestuario": "Vestuario y hogar", "delivery": "Delivery", "otros": "Otros"}
# Mismo orden, nombre y color que la web
BANCOS = [
    ("bancochile", "Banco de Chile", "#1b3f8b"), ("santander", "Santander", "#c8102e"), ("bci", "BCI", "#2f2f2f"),
    ("bancoestado", "BancoEstado", "#e05a00"), ("scotiabank", "Scotiabank", "#b01d2b"), ("itau", "Itaú", "#ec6608"),
    ("falabella", "Banco Falabella", "#3a8f2a"), ("ripley", "Banco Ripley", "#5b2a86"),
    ("cencosud", "Tarjeta Cencosud", "#0068b3"), ("security", "Banco Security", "#6d1f6b"),
    ("tenpo", "Tenpo", "#00a88a"), ("mach", "MACH", "#6c2bd9"), ("bice", "Banco BICE", "#0a2d6e"),
]
# Filas cuyo "comercio" es en realidad una categoría (ej. MACH publica "Restaurantes")
GENERICOS = {"restaurantes", "restaurant", "cuponera generica", "cuponera genérica", "restaurantes adheridos", "comercios adheridos", "supermercados", "farmacias"}
HASHTAG_REGION = {"AP": "arica", "TA": "iquique", "AN": "antofagasta", "AT": "copiapo", "CO": "laserena",
                  "VS": "valparaiso", "RM": "santiago", "LI": "rancagua", "ML": "talca", "NB": "chillan",
                  "BI": "concepcion", "AR": "temuco", "LR": "valdivia", "LL": "puertomontt", "AI": "coyhaique",
                  "MA": "puntaarenas"}
EMOJI = {"restaurantes": "🍽️", "supermercados": "🛒", "combustible": "⛽", "farmacias": "💊", "viajes": "✈️",
         "entretencion": "🎬", "vestuario": "🛍️", "delivery": "🛵", "otros": "💳"}
DSHORT = ["LUN", "MAR", "MIÉ", "JUE", "VIE", "SÁB", "DOM"]
TIPOS = {"credito": "Crédito", "debito": "Débito", "prepago": "Prepago"}

e = html.escape


def fmt_dias(dias: list[int]) -> str:
    if not dias:
        return "VER COND."
    if len(dias) == 7:
        return "TODOS"
    ds = sorted(dias)
    if len(ds) >= 3 and all(b == a + 1 for a, b in zip(ds, ds[1:])):
        return f"{DSHORT[ds[0]]}–{DSHORT[ds[-1]]}"
    faltan = [d for d in range(7) if d not in ds]
    if len(faltan) <= 2:
        return "SALVO " + " ".join(DSHORT[d] for d in faltan)
    if len(ds) >= 3:
        return " ".join(DSHORT[d] for d in ds[:2]) + "<br>" + " ".join(DSHORT[d] for d in ds[2:])
    return " ".join(DSHORT[d] for d in ds)


# ---- Agrupación por tipo de tarjeta ----
# Gamas "de entrada": si una oferta las incluye, vale para casi todos los clientes del banco
_GAMA_BASE = {"fan", "gold", "dorada", "clasica", "one", "platinum", "cuentarut", "cuenta rut"}
# Gamas premium, en el orden en que se muestran
_GAMA_PREMIUM = ["limitless", "black", "infinite", "signature", "singular", "legend", "elite", "worldmember limited",
                 "premium", "wealth management", "air"]
_ORDEN_TIPOS = {("credito", "debito"): 0, ("credito", "debito", "prepago"): 0, ("credito",): 1,
                ("credito", "prepago"): 1, ("debito",): 2, ("debito", "prepago"): 2, ("prepago",): 3}
_NOMBRE_TIPOS = {("credito", "debito"): "Crédito y débito", ("credito", "debito", "prepago"): "Crédito, débito y prepago",
                 ("credito",): "Solo crédito", ("credito", "prepago"): "Crédito y prepago", ("debito",): "Solo débito",
                 ("debito", "prepago"): "Débito y prepago", ("prepago",): "Solo prepago"}


def _norm(t: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")


def grupo_tarjetas(d: dict) -> tuple[int, str]:
    """(orden, etiqueta) del grupo de tarjetas al que aplica el descuento.
    Ej.: "Crédito y débito", "Solo crédito", "Solo Black · Infinite · Signature"."""
    nombres = [_norm(t) for t in d.get("tarjetas") or []]
    tipos = tuple(sorted(set(d.get("tipos") or ["credito"])))
    general = not nombres or any(
        any(b in n for b in _GAMA_BASE) or not any(g in n for g in _GAMA_PREMIUM) for n in nombres)
    if general:
        return _ORDEN_TIPOS.get(tipos, 4), _NOMBRE_TIPOS.get(tipos, "Otras tarjetas")
    gamas = [g for g in _GAMA_PREMIUM if any(g in n for n in nombres)]
    nombre = " · ".join(g.title() if g != "worldmember limited" else "WorldMember Limited" for g in gamas[:3])
    return 10 + len(gamas), f"Solo {nombre}"


def nombre_comercio(d: dict) -> str:
    """Nombre limpio para mostrar ("Shell Dcto Combustible" -> "Shell")."""
    import re as _re
    return _re.sub(r"\s*(dcto\.?|descuento)\s+(en\s+)?combustible\s*$", "", d["comercio"], flags=_re.I).strip() or d["comercio"]


def valor(d: dict) -> tuple[str, float] | None:
    """(texto, orden) del beneficio: "40%" o "$100/L". None si no hay un valor que mostrar."""
    if d.get("pct"):
        return f"{d['pct']}%", float(d["pct"])
    from scraper.common import monto_por_litro
    m = monto_por_litro(d.get("comercio", ""), d.get("titulo", ""))
    if m:
        return f"${m}/L", m / 10  # $100/L se ordena como un 10 %, solo para ordenar dentro de un banco
    import re as _re
    t = f'{d.get("comercio", "")} {d.get("titulo", "")}'.lower()
    if _re.search(r"(?<!\d)2\s?x\s?1(?!\d)", t):
        return "2x1", 50.0
    if _re.search(r"(?<!\d)3\s?x\s?2(?!\d)", t):
        return "3x2", 33.0
    mf = _re.search(r"\$\s?(\d{1,3}(?:\.\d{3})+|\d{4,6})\s*(?:de\s*)?(?:dto|dcto|descuento)", t)
    if mf:
        n = int(mf.group(1).replace(".", ""))
        return f"${n:,}".replace(",", "."), 15.0  # monto fijo: se ordena después de los % altos
    return None


def seleccionar(descuentos, rubro, region, por_banco, incluir_nacionales, por_tarjeta=False):
    seleccionar.recortado = False
    out = {}
    for bid, _, _ in BANCOS:
        items = [d for d in descuentos if d["banco"] == bid and d["rubro"] == rubro and valor(d)
                 and d["comercio"].strip().lower() not in GENERICOS
                 and (region == "CL" or (region in d.get("regiones", [])) or (incluir_nacionales and not d.get("regiones")))]
        # Un mismo comercio una sola vez por banco (el de mayor %)
        mejor = {}
        for d in items:
            d["_valor"], d["_orden"] = valor(d)
        for d in sorted(items, key=lambda d: -d["_orden"]):
            mejor.setdefault(d["comercio"].strip().lower(), d)
        if len(mejor) > por_banco:
            seleccionar.recortado = True
        top = sorted(mejor.values(), key=lambda d: -d["_orden"])[:por_banco]
        for d in top:
            d["_grupo"] = grupo_tarjetas(d) if por_tarjeta else (0, "")
        top.sort(key=lambda d: (d["_grupo"], min(d["dias"]) if d["dias"] else 9, -d["_orden"], d["comercio"].lower()))
        if top:
            out[bid] = top
    return out


BLOQUE_EXTRA = 0.4          # espacio entre bloques y bordes, en filas


def _grupos(filas) -> int:
    return len({d["_grupo"] for d in filas if d["_grupo"][1]})


def _alto(filas) -> float:
    """Alto de un bloque de banco en filas: encabezado + franjas de tarjeta + descuentos + margen."""
    return len(filas) + _grupos(filas) + ENCABEZADO + BLOQUE_EXTRA


def paginar(sel):
    """Reparte los bancos en columnas: cada banco va a la primera columna donde cabe
    completo (así los bancos chicos comparten columna); si no cabe en ninguna, abre una
    nueva y, si es más largo que una columna, sigue en la próxima. Devuelve
    imágenes = [[columna1, columna2], ...]."""
    cap = FILAS_COLUMNA + ENCABEZADO + BLOQUE_EXTRA
    columnas: list[list] = []
    libre: list[float] = []
    for bid, filas in sel.items():
        alto = _alto(filas)
        k = next((i for i, l in enumerate(libre) if l >= alto - 1e-9), None)
        if k is not None:
            columnas[k].append((bid, filas, False)); libre[k] -= alto
            continue
        resto, cont = list(filas), False
        while resto:
            n = len(resto)
            while n > 1 and _alto(resto[:n]) > cap:
                n -= 1
            columnas.append([(bid, resto[:n], cont)]); libre.append(cap - _alto(resto[:n]))
            resto, cont = resto[n:], True
    return [columnas[i:i + 2] for i in range(0, len(columnas), 2)]


CSS = """
@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,600;12..96,800&family=Instrument+Sans:wght@500;600;700&display=swap');
*{box-sizing:border-box;margin:0;padding:0}
body{width:1080px;height:1350px;background:var(--fondo);color:var(--tinta);font-family:'Instrument Sans',system-ui,sans-serif;overflow:hidden}
.slide{position:relative;width:1080px;height:1350px;display:flex;flex-direction:column;padding:56px 52px 40px}
.deco{position:absolute;inset:0;pointer-events:none;z-index:0}
.slide > *:not(.deco){position:relative;z-index:1}
.top{display:flex;justify-content:space-between;align-items:flex-end;border-bottom:5px solid var(--tinta);padding-bottom:18px;margin-bottom:22px}
.top h2{font-family:'Bricolage Grotesque',sans-serif;font-weight:800;font-size:46px;letter-spacing:-.02em;line-height:1}
.top h2 small{display:block;font-family:'Instrument Sans';font-weight:600;font-size:22px;letter-spacing:.1em;text-transform:uppercase;color:var(--etiqueta);margin-bottom:8px}
.top .pg{font-size:24px;font-weight:600;color:var(--suave)}
.cols{flex:1;display:grid;grid-template-columns:1fr 1fr;gap:22px;align-content:start}
.col{display:flex;flex-direction:column;gap:14px}
.blk{background:#fff;color:#15201d;border-radius:14px;overflow:hidden;border:2px solid #dbe2df}
.bh{background:var(--c);color:#fff;padding:10px 16px;display:flex;justify-content:space-between;gap:10px;height:72px;align-items:center}
.bh b{font-family:'Bricolage Grotesque',sans-serif;font-weight:800;font-size:28px;letter-spacing:-.01em}
.bh span{font-size:18px;font-weight:600;opacity:.9;text-align:right;line-height:1.1}
.grp{background:color-mix(in srgb,var(--c) 16%,#fff);color:color-mix(in srgb,var(--c) 75%,#000);font-size:17px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;height:46px;display:flex;align-items:center;padding:0 14px;border-top:2px solid color-mix(in srgb,var(--c) 35%,#fff)}
.grp::before{content:"";width:10px;height:10px;border-radius:2px;background:var(--c);margin-right:10px;flex:none}
.row{display:grid;grid-template-columns:104px 1fr auto;align-items:center;height:46px;padding:0 14px;border-top:1px solid #e6ebe9;font-size:26px}
.row:nth-child(even of .row){background:color-mix(in srgb,var(--c) 6%,#fff)}
.d{font-size:17px;font-weight:700;color:#5d6a66;letter-spacing:.02em;line-height:1.2}
.m{font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;padding-right:8px}
.p{font-family:'Bricolage Grotesque',sans-serif;font-weight:800;font-size:29px;min-width:72px;text-align:right;color:var(--c)}
.foot{display:flex;justify-content:space-between;align-items:center;margin-top:16px;font-size:21px;color:var(--suave);font-weight:600}
.foot b{color:var(--tinta);font-size:24px}
/* portada y cierre */
.cover{background:var(--c-fondo);color:var(--c-tinta);justify-content:space-between;padding:80px 72px}
.cover .k{font-size:28px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--c-acento)}
.cover h1{font-family:'Bricolage Grotesque',sans-serif;font-weight:800;font-size:150px;line-height:.92;letter-spacing:-.04em;margin:26px 0 30px}
.cover .reg{font-family:'Bricolage Grotesque',sans-serif;font-weight:600;font-size:58px;line-height:1.05}
.cover .big{display:flex;gap:56px;margin-top:56px}
.cover .big div b{display:block;font-family:'Bricolage Grotesque',sans-serif;font-weight:800;font-size:96px;line-height:1;color:var(--c-acento)}
.cover .big div span{font-size:26px;font-weight:600;color:var(--c-suave)}
.chips{display:flex;flex-wrap:wrap;gap:12px}
.chips span{border:2px solid var(--c-borde);border-radius:999px;padding:8px 18px;font-size:24px;font-weight:600}
.cover .lead{font-size:32px;color:var(--c-suave);margin-top:40px;max-width:820px;line-height:1.3}
.cover .bottom{display:flex;justify-content:space-between;align-items:center;font-size:30px;font-weight:700}
.cover .swipe{background:var(--c-acento);color:var(--c-boton);border-radius:999px;padding:14px 30px}
.end h1{font-size:110px}
.end p{font-size:34px;line-height:1.35;color:var(--c-suave);max-width:860px}
.end .note{font-size:24px;color:var(--c-nota);line-height:1.4}
"""


# Un color por mes, para distinguir de un vistazo la información de un mes y la del otro.
# fondo/tinta/etiqueta/suave: imágenes con tablas; c-*: portada y cierre.
_BASE = {"fondo": "#f3f5f4", "tinta": "#15201d", "etiqueta": "#0b7a5c", "suave": "#5d6a66",
         "c-fondo": "#15201d", "c-tinta": "#f3f5f4", "c-acento": "#3ccf9f", "c-suave": "#c9d3cf",
         "c-borde": "#3a4743", "c-boton": "#0b1411", "c-nota": "#97a49f"}


def _tema_color(fondo: str, oscuro: str, acento: str) -> dict:
    """Tema de color de fondo intenso: tablas sobre el color y portada en su tono oscuro."""
    return {"fondo": fondo, "tinta": "#ffffff", "etiqueta": acento, "suave": "#ffffffd9",
            "c-fondo": oscuro, "c-tinta": "#ffffff", "c-acento": acento, "c-suave": "#ffffffcc",
            "c-borde": "#ffffff55", "c-boton": oscuro, "c-nota": "#ffffffa6"}


TEMAS_MES = {
    1: _tema_color("#1d4ed8", "#132f80", "#fde68a"),   # enero: azul
    2: _tema_color("#7c3aed", "#4c1d95", "#fde68a"),   # febrero: morado
    3: _tema_color("#c2410c", "#7c2d12", "#fef08a"),   # marzo: naranjo
    4: _tema_color("#0f766e", "#134e4a", "#fde68a"),   # abril: verde azulado
    5: _tema_color("#be185d", "#831843", "#fde68a"),   # mayo: fucsia
    6: _tema_color("#1e40af", "#172554", "#a5f3fc"),   # junio: azul marino
    7: _tema_color("#15803d", "#14532d", "#fef08a"),   # julio: verde
    8: _tema_color("#b45309", "#78350f", "#fef3c7"),   # agosto: ámbar
    9: _tema_color("#0e7490", "#164e63", "#fde68a"),   # septiembre: cian
    10: _tema_color("#6d28d9", "#3b0764", "#bbf7d0"),  # octubre: violeta
    11: _BASE,                                         # noviembre: claro (diseño original)
    12: _tema_color("#c1121f", "#7f0d16", "#ffd166"),  # diciembre: rojo
}
MES_TEMA = 11  # se fija en main() según el mes de los datos


# ---- Decoración por mes: dibujos de línea blanca, sobrios (diciembre: Navidad) ----
_LINEA = 'fill="none" stroke="#ffffff" stroke-linecap="round" stroke-linejoin="round"'


def _copo(x, y, r, op=.5, sw=3) -> str:
    """Copo de nieve de 6 brazos con pequeñas ramas."""
    import math
    partes = []
    for i in range(6):
        a = math.pi / 3 * i
        ex, ey = x + math.cos(a) * r, y + math.sin(a) * r
        partes.append(f"M{x:.0f} {y:.0f}L{ex:.0f} {ey:.0f}")
        for f in (.55, .8):
            bx, by = x + math.cos(a) * r * f, y + math.sin(a) * r * f
            for s_ in (-1, 1):
                b = a + s_ * math.pi / 4
                partes.append(f"M{bx:.0f} {by:.0f}L{bx + math.cos(b) * r * .22:.0f} {by + math.sin(b) * r * .22:.0f}")
    return f'<path d="{" ".join(partes)}" {_LINEA} stroke-width="{sw}" opacity="{op}"/>'


def _adorno(x, largo, r, op=.75) -> str:
    """Esfera colgando de un hilo desde el borde superior, con franjas."""
    cy = largo + r
    return (f'<g {_LINEA} stroke-width="3.5" opacity="{op}"><path d="M{x} 0V{largo}"/>'
            f'<rect x="{x - r * .28:.0f}" y="{largo - 6}" width="{r * .56:.0f}" height="12" rx="3"/>'
            f'<circle cx="{x}" cy="{cy:.0f}" r="{r}"/>'
            f'<path d="M{x - r * .92:.0f} {cy - r * .3:.0f}Q{x} {cy - r * .05:.0f} {x + r * .92:.0f} {cy - r * .3:.0f}'
            f'M{x - r * .92:.0f} {cy + r * .3:.0f}Q{x} {cy + r * .55:.0f} {x + r * .92:.0f} {cy + r * .3:.0f}"/></g>')


def _estrella(x, y, r, op=.8) -> str:
    import math
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * .45
        pts.append(f"{x + math.cos(a) * rr:.0f},{y + math.sin(a) * rr:.0f}")
    return f'<polygon points="{" ".join(pts)}" {_LINEA} stroke-width="3.5" opacity="{op}"/>'


def _rama(x, y, largo, ang, op=.6) -> str:
    """Rama de pino: eje y agujas en ángulo."""
    import math
    a = math.radians(ang)
    partes = [f"M{x} {y}L{x + math.cos(a) * largo:.0f} {y + math.sin(a) * largo:.0f}"]
    for i in range(1, 9):
        px, py = x + math.cos(a) * largo * i / 9, y + math.sin(a) * largo * i / 9
        for s_ in (-1, 1):
            b = a + s_ * math.radians(38) + math.radians(180)
            l = 46 * (1 - i / 14)
            partes.append(f"M{px:.0f} {py:.0f}L{px + math.cos(b) * l:.0f} {py + math.sin(b) * l:.0f}")
    return f'<path d="{" ".join(partes)}" {_LINEA} stroke-width="3" opacity="{op}"/>'


def _esfera(x, y, r, hilo=40, op=.8) -> str:
    """Esfera colgando de un hilo corto (desde una rama), con franjas."""
    cy = y + hilo + r
    return (f'<g {_LINEA} stroke-width="3.5" opacity="{op}"><path d="M{x} {y}V{y + hilo}"/>'
            f'<rect x="{x - r * .28:.0f}" y="{y + hilo - 6}" width="{r * .56:.0f}" height="12" rx="3"/>'
            f'<circle cx="{x}" cy="{cy:.0f}" r="{r}"/>'
            f'<path d="M{x - r * .92:.0f} {cy - r * .3:.0f}Q{x} {cy - r * .05:.0f} {x + r * .92:.0f} {cy - r * .3:.0f}'
            f'M{x - r * .92:.0f} {cy + r * .3:.0f}Q{x} {cy + r * .55:.0f} {x + r * .92:.0f} {cy + r * .3:.0f}"/></g>')


def _franja_superior(op=.55) -> str:
    """Copos y estrellas pequeños en el margen superior (y < 46), sin tocar textos."""
    el = ""
    for k, x in enumerate(range(90, 1060, 110)):
        el += _estrella(x, 24, 9, op) if k % 3 == 1 else _copo(x, 24, 13, op * .9, 2.5)
    return el


def _deco_diciembre(tipo: str) -> str:
    if tipo == "portada":
        # Rama de pino con esferas en la esquina inferior derecha (sobre "Desliza"), copos arriba y al borde
        el = (_rama(1110, 1110, 290, 186, .6) + _rama(1110, 1160, 200, 180, .45)
              + _esfera(930, 1092, 26, 30) + _esfera(1015, 1100, 22, 20) + _esfera(855, 1085, 18, 20, .65)
              + _franja_superior(.5)
              + _copo(1040, 420, 18, .4) + _copo(1020, 560, 12, .35) + _estrella(1040, 690, 12, .6))
    elif tipo == "cierre":
        el = (_rama(1110, 1010, 420, 200, .55) + _rama(1110, 1090, 260, 190, .4)
              + _esfera(860, 960, 34, 60) + _esfera(960, 1000, 26, 34) + _esfera(760, 1000, 22, 26, .65)
              + _franja_superior(.5)
              + _estrella(930, 520, 30, .75) + _copo(820, 600, 26, .45) + _copo(1000, 640, 18, .4))
    else:  # imágenes con tablas: solo el margen superior
        el = _franja_superior(.5)
    return f'<svg class="deco" viewBox="0 0 {W} {H}">{el}</svg>'


DECORACION_MES = {12: _deco_diciembre}


def pagina(cuerpo: str) -> str:
    t = TEMAS_MES.get(MES_TEMA, _BASE)
    variables = ":root{" + ";".join(f"--{k}:{v}" for k, v in t.items()) + "}"
    deco = DECORACION_MES.get(MES_TEMA)
    if deco:
        import re as _re
        tipo = "cierre" if 'class="slide cover end"' in cuerpo else "portada" if 'class="slide cover"' in cuerpo else "tabla"
        cuerpo = _re.sub(r'(<div class="slide[^"]*">)', lambda m: m.group(1) + deco(tipo), cuerpo, count=1)
    return f"<!doctype html><html lang='es'><head><meta charset='utf-8'><style>{CSS}</style><style>{variables}</style></head><body>{cuerpo}</body></html>"


def encabezado(mes_txt: str) -> str:
    """Encabezado de la primera imagen de TODOS los carruseles: "Descuentos con tarjeta - Diciembre 2026"
    (se muestra en mayúsculas)."""
    return f"Descuentos con tarjeta - {mes_txt}"


def mes_actual_txt() -> str:
    """Mes y año en curso en Chile, p. ej. "Diciembre 2026"."""
    from zoneinfo import ZoneInfo
    hoy = datetime.now(ZoneInfo("America/Santiago"))
    return f"{MESES[hoy.month - 1].capitalize()} {hoy.year}"


def html_portada(rubro_txt, region_txt, mes_txt, total, nbancos, bancos, todos=False):
    chips = "".join(f"<span>{e(n)}</span>" for n in bancos)
    return pagina(f"""<div class="slide cover">
  <div><div class="k">{e(encabezado(mes_txt))}</div>
  <h1>{e(rubro_txt)}</h1><div class="reg">{e(region_txt)}</div>
  <div class="big"><div><b>{total}</b><span>descuentos</span></div><div><b>{nbancos}</b><span>bancos y tarjetas</span></div></div>
  <p class="lead">{"Todos los descuentos del mes" if todos else "Los mejores de cada banco"}, ordenados por día de la semana.</p></div>
  <div class="chips">{chips}</div>
  <div class="bottom"><span>{CUENTA}</span><span class="swipe">Desliza →</span></div>
</div>""")


def html_tabla(cols, sel_tipos, titulo, sub, n, total):
    nombres = {b: (n_, c) for b, n_, c in BANCOS}
    def bloque(bid, filas, cont):
        nombre, color = nombres[bid]
        partes, previo = [], None
        for d in filas:
            if d["_grupo"] != previo and d["_grupo"][1]:
                partes.append(f'<div class="grp">{e(d["_grupo"][1])}</div>')
                previo = d["_grupo"]
            partes.append(f'<div class="row"><span class="d">{fmt_dias(d["dias"])}</span><span class="m">{e(nombre_comercio(d))}</span><span class="p">{e(d["_valor"])}</span></div>')
        return (f'<div class="blk" style="--c:{color}"><div class="bh"><b>{e(nombre)}{" (cont.)" if cont else ""}</b></div>'
                f'{"".join(partes)}</div>')
    columnas = "".join(f'<div class="col">{"".join(bloque(*b) for b in col)}</div>' for col in cols)
    return pagina(f"""<div class="slide">
  <div class="top"><h2><small>{e(sub)}</small>{e(titulo)}</h2><span class="pg">{n}/{total}</span></div>
  <div class="cols">{columnas}</div>
  <div class="foot"><b>{CUENTA}</b><span>Revisa topes y condiciones en el sitio de cada banco</span></div>
</div>""")


def html_cierre(mes_txt, fecha_txt):
    return pagina(f"""<div class="slide cover end">
  <div><div class="k">Descuentos con tarjeta</div>
  <h1>Guarda este post</h1>
  <p>Cada mes publicamos los descuentos de los bancos y tarjetas de Chile por rubro y región.</p></div>
  <div class="reg">Síguenos en<br>{CUENTA}</div>
  <div class="note">Información tomada de los sitios oficiales de cada banco el {e(fecha_txt)}. Los descuentos, topes, días y vigencias pueden cambiar: confírmalos en el sitio de tu banco antes de usarlos. Cuenta no afiliada a ningún banco.</div>
</div>""")


LIMITE_TEXTO = 2200   # máximo de caracteres de una descripción de Instagram
DIAS_LARGOS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def _dias_texto(dias: list[int]) -> str:
    if not dias:
        return "ver condiciones"
    if len(dias) == 7:
        return "todos los días"
    ds = sorted(dias)
    if len(ds) >= 3 and all(b == a + 1 for a, b in zip(ds, ds[1:])):
        return f"{DIAS_LARGOS[ds[0]]} a {DIAS_LARGOS[ds[-1]]}"
    faltan = [d for d in range(7) if d not in ds]
    if len(faltan) <= 2:
        return "todos los días salvo " + " y ".join(DIAS_LARGOS[d] for d in faltan)
    nombres = [DIAS_LARGOS[d] for d in ds]
    return nombres[0] if len(nombres) == 1 else ", ".join(nombres[:-1]) + " y " + nombres[-1]


def _valor_texto(v: str) -> str:
    """Valor para la descripción: "$100/L" -> "$100 por litro", "$7.000" -> "$7.000 de descuento"."""
    if v.endswith("/L"):
        return v.replace("/L", " por litro")
    if v.startswith("$"):
        return f"{v} de descuento"
    return v


def _link(url: str | None) -> str:
    return (url or "").replace("https://", "").replace("http://", "").rstrip("/")


def descripcion(sel, data, a, rubro_txt, region_txt, mes_txt, gen) -> str:
    """Descripción del post (máx. 2200 caracteres): resumen, el mejor descuento de cada
    banco, cómo leer las imágenes, links a la página de beneficios de cada banco y hashtags."""
    nombres = {b: n for b, n, _ in BANCOS}
    total = sum(len(f) for f in sel.values())
    cab = (f"{EMOJI[a.rubro]} {rubro_txt} {a.region_en} · {mes_txt}\n\n"
           f"{total} descuentos con tarjeta de {len(sel)} bancos y tarjetas{'' if seleccionar.recortado else ' (todos los del mes)'}, ordenados por día de la semana. "
           f"👉 Desliza para verlos todos y guarda el post para usarlo durante el mes.")
    destacados = []
    for bid, filas in sel.items():
        d = max(filas, key=lambda x: (x["_orden"], -len(x["dias"])))
        destacados.append(f"• {nombres[bid]}: {_valor_texto(d['_valor'])} en {nombre_comercio(d)} ({_dias_texto(d['dias'])})")
    codigos_txt = "🎟️ En la penúltima imagen están los códigos de descuento de cada banco para PedidosYa, Rappi y Justo." \
        if a.rubro == "delivery" else ""
    lectura = ("💳 Cómo leerlo: en cada banco, la franja de color indica a qué tarjetas aplica "
               "(crédito y débito, solo crédito o solo tarjetas premium como Black o Infinite)."
               if a.por_tarjeta else "")
    links = [f"{nombres[b]}: {_link(data['bancos'].get(b, {}).get('sitio'))}" for b in sel
             if data["bancos"].get(b, {}).get("sitio")]
    aviso = (f"⚠️ Información de los sitios oficiales de cada banco al {gen:%d-%m-%Y}. Descuentos, topes, días "
             f"y vigencias pueden cambiar: confírmalos antes de usarlos. Cuenta no afiliada a ningún banco.")
    extra = {"combustible": " #bencina #copec #shell #aramco"}.get(a.rubro, "")
    tags = (f"#descuentos #descuentoschile #{a.rubro} #{HASHTAG_REGION.get(a.region, 'chile')} "
            f"{'' if a.region == 'CL' else '#chile '}#tarjetadecredito #tarjetadedebito #ahorro #ofertas #beneficios{extra}")

    def armar(n_dest: int, con_links: bool) -> str:
        partes = [cab]
        if n_dest:
            partes.append("🔥 El mejor de cada banco:\n" + "\n".join(destacados[:n_dest]))
        if codigos_txt:
            partes.append(codigos_txt)
        if lectura:
            partes.append(lectura)
        if con_links and links:
            partes.append("🔗 Condiciones en el sitio de cada banco:\n" + "\n".join(links))
        partes += [aviso, tags]
        return "\n\n".join(partes)

    # Si no cabe, primero se acortan los destacados y, en último caso, se quitan los links
    for con_links in (True, False):
        for n in range(len(destacados), -1, -1):
            t = armar(n, con_links)
            if len(t) <= LIMITE_TEXTO:
                return t
    return armar(0, False)[:LIMITE_TEXTO]


# ---- Delivery: imagen con los códigos de descuento (PedidosYa, Rappi, Justo…) ----
PLATAFORMAS = [("pedidosya", "PedidosYa", "#fa0050", r"pedidos ?ya"), ("rappi", "Rappi", "#ff441f", r"rappi"),
               ("justo", "Justo", "#0f9d58", r"\bjusto\b"), ("ubereats", "Uber Eats", "#06a35a", r"uber ?eats"),
               ("didi", "DiDi Food", "#ff7d41", r"didi ?food")]
_CODIGO_RX = __import__("re").compile(r"\b[A-Z][A-Z0-9]{5,20}\b")


def codigos(d: dict) -> list[str]:
    """Códigos de descuento que aparecen en el título o la descripción (ej. BCHPEYA1126)."""
    import re as _re
    vistos = []
    for c in _CODIGO_RX.findall(f'{d.get("titulo", "")} {d.get("descripcion", "")}'):
        if _re.search(r"\d", c) and len(_re.findall(r"[A-Z]", c)) >= 3 and c not in vistos:
            vistos.append(c)
    return vistos[:4]


def _tope_corto(t: str) -> str:
    """"Tope de $5.000 y tres usos al mes" -> "Tope $5.000 · 3 usos"."""
    import re as _re
    m = _re.search(r"\$\s?\d[\d.]*", t)
    if not m:
        return ""
    out = "Tope " + m.group(0).replace(" ", "")
    u = _re.search(r"(?i)(\d+|uno|dos|tres|cuatro|cinco) usos?", t)
    if u:
        n = {"uno": "1", "dos": "2", "tres": "3", "cuatro": "4", "cinco": "5"}.get(u.group(1).lower(), u.group(1))
        out += f" · {n} uso{'s' if n != '1' else ''}"
    return out


def filas_codigos(descuentos) -> list[tuple]:
    """[(plataforma, nombre, color, [filas])] con una fila por banco y código (Justo: una sola fila)."""
    import re as _re
    grupos = {}
    for d in descuentos:
        cs = codigos(d)
        if not cs:
            continue
        txt = f'{d["comercio"]} {d.get("titulo", "")}'.lower()
        plat = next((p for p in PLATAFORMAS if _re.search(p[3], txt)), None)
        if not plat:
            continue
        com = nombre_comercio(d)
        resto = _re.sub(r"(?i)\s*[-–]?\s*(pedidos ?ya|rappi|justo|uber ?eats|didi ?food)\s*", " ", com).strip(" -–")
        detalle = resto if resto and plat[0] != "justo" else ("Restaurantes adheridos" if plat[0] == "justo" else "")
        clave = (d["banco"], tuple(cs))
        g = grupos.setdefault(plat[0], {"plat": plat, "filas": {}})
        if clave not in g["filas"]:
            v = valor(d)
            g["filas"][clave] = {"banco": d["banco"], "tarjeta": _tarjeta_corta(d), "valor": v[0] if v else "",
                                 "detalle": detalle, "codigos": list(cs), "dias": fmt_dias(d.get("dias") or []),
                                 "tope": _tope_corto(d.get("tope") or "")}
    orden = [p[0] for p in PLATAFORMAS]
    return [(g["plat"][0], g["plat"][1], g["plat"][2], list(g["filas"].values()))
            for k, g in sorted(grupos.items(), key=lambda kv: orden.index(kv[0]))]


CSS_COD = """
.crow{display:grid;grid-template-columns:150px 92px 1fr;align-items:center;gap:10px;padding:10px 16px;border-top:1px solid #e6ebe9;min-height:66px}
.crow:nth-child(even of .crow){background:#f6f7f7}
.crow .bk b{font-size:19px}.crow .bk i{font-size:13px}
.crow .v{font-family:'Bricolage Grotesque',sans-serif;font-weight:800;font-size:30px;color:var(--pc);text-align:center}
.crow .cods{display:flex;flex-direction:column;gap:5px;min-width:0}
.crow .cods div{display:flex;flex-wrap:wrap;gap:6px}
.code{font-family:ui-monospace,'SFMono-Regular',Menlo,Consolas,monospace;font-weight:700;font-size:21px;letter-spacing:.04em;
  color:#15201d;background:#fff;border:2px dashed var(--pc);border-radius:8px;padding:3px 9px}
.crow small{font-size:15px;font-weight:600;color:#5d6a66;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ph{background:var(--pc);color:#fff;height:62px;padding:0 18px;display:flex;align-items:center;justify-content:space-between}
.ph b{font-family:'Bricolage Grotesque',sans-serif;font-weight:800;font-size:30px}
.ph span{font-size:16px;font-weight:700;opacity:.9;text-transform:uppercase;letter-spacing:.08em}
.cgrid{flex:1;display:grid;grid-template-columns:1fr 1fr;gap:20px;align-content:start}
.cgrid.una{grid-template-columns:1fr;gap:18px}
.una .crow{grid-template-columns:190px 104px 1fr;min-height:74px;padding:10px 20px}
.una .crow .bk b{font-size:22px}.una .crow .bk i{font-size:14px}
.una .crow .v{font-size:34px}
.una .code{font-size:25px;padding:4px 12px}
.una .crow small{font-size:17px}
.una .ph{height:64px}
"""


def html_codigos(plataformas, mes_txt, n, total) -> str:
    colores = {b: c for b, _, c in BANCOS}
    def fila(f):
        extra = " · ".join(x for x in [f["detalle"], f["dias"] if f["dias"] not in ("TODOS", "VER COND.") else "", f["tope"]] if x)
        return (f'<div class="crow"><span class="bk" style="--bc:{colores.get(f["banco"], "#333")}">'
                f'<b>{e(BANCO_CORTO.get(f["banco"], f["banco"]))}</b><i>{e(f["tarjeta"])}</i></span>'
                f'<span class="v">{e(f["valor"])}</span><span class="cods"><div>'
                + "".join(f'<span class="code">{e(c)}</span>' for c in f["codigos"]) +
                f'</div>{f"<small>{e(extra)}</small>" if extra else ""}</span></div>')
    # Pocas filas: una sola columna a todo el ancho; muchas: dos columnas equilibradas
    una = sum(len(p[3]) for p in plataformas) + 1.4 * len(plataformas) <= 15
    cols, altos = ([[]], [0]) if una else ([[], []], [0, 0])
    for pid, nombre, color, filas in (plataformas if una else sorted(plataformas, key=lambda p: -len(p[3]))):
        k = altos.index(min(altos))
        cols[k].append((pid, nombre, color, filas)); altos[k] += len(filas) + 1.4
    bloques = "".join(
        '<div class="col">' + "".join(
            f'<div class="blk" style="--pc:{color}"><div class="ph"><b>{e(nombre)}</b><span>Ingresa el código en la app</span></div>'
            + "".join(fila(f) for f in filas) + "</div>" for _, nombre, color, filas in col) + "</div>"
        for col in cols)
    return pagina(f"""<style>{CSS_REG}{CSS_COD}</style><div class="slide">
  <div class="top"><h2><small>{e(mes_txt)}</small>Códigos de descuento · Delivery</h2><span class="pg">{n}/{total}</span></div>
  <div class="cgrid{' una' if una else ''}">{bloques}</div>
  <div class="foot"><b>{CUENTA}</b><span>Los códigos cambian cada mes: revísalos en el sitio de tu banco</span></div>
</div>""")


def renderizar(htmls: list[str], out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for f in out.glob("*.png"):
        f.unlink()
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        kw = {"executable_path": os.environ["CHROMIUM_PATH"]} if os.environ.get("CHROMIUM_PATH") else {}
        b = p.chromium.launch(**kw)
        pg = b.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        for i, h in enumerate(htmls, start=1):
            pg.set_content(h, wait_until="networkidle")
            pg.screenshot(path=str(out / f"{i:02d}.png"))
        b.close()


# ---- Regiones: tabla por comuna (fuera de la Región Metropolitana), de norte a sur ----
MAX_COMUNAS_LOCAL = 4   # un descuento con locales en más comunas es una cadena: va en los posts generales
BANCO_CORTO = {"bancochile": "B. de Chile", "santander": "Santander", "bci": "BCI", "bancoestado": "BancoEstado",
               "scotiabank": "Scotiabank", "itau": "Itaú", "falabella": "Falabella", "ripley": "Ripley",
               "cencosud": "Cencosud", "security": "Security", "tenpo": "Tenpo", "mach": "MACH", "bice": "BICE"}
CSS_REG = """
.rrow{display:grid;grid-template-columns:64px 112px 1fr auto;align-items:center;height:40px;padding:0 10px;border-top:1px solid #e6ebe9;font-size:22px;gap:6px}
.rrow:nth-child(even of .rrow){background:#f4f6f5}
.rrow .d{font-size:13px;letter-spacing:0}
.bk{display:flex;flex-direction:column;line-height:1.05;min-width:0}
.bk b{font-size:15px;font-weight:800;color:var(--bc);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.bk i{font-style:normal;font-size:11px;font-weight:600;color:#5d6a66;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.rrow .m{font-size:19px;letter-spacing:-.01em}
.rrow .p{font-size:23px;color:#15201d;min-width:54px}
.ch{background:#15201d;color:#fff;height:58px;padding:0 14px;display:flex;align-items:baseline;justify-content:space-between;gap:10px}
.ch{align-items:center}
.ch b{font-family:'Bricolage Grotesque',sans-serif;font-weight:800;font-size:26px}
.ch span{font-size:15px;font-weight:600;opacity:.8;text-transform:uppercase;letter-spacing:.06em}
"""
FILA_REG = 40 / 46       # alto de una fila de regiones en "filas" del diseño normal
CAB_REG = 58 / 46


def _tarjeta_corta(d: dict) -> str:
    g = grupo_tarjetas(d)[1]
    return {"Crédito y débito": "Créd. y déb.", "Solo crédito": "Crédito", "Solo débito": "Débito",
            "Crédito y prepago": "Créd. y prep.", "Crédito, débito y prepago": "Todas"}.get(g, g.replace("Solo ", ""))


def seleccionar_regiones(descuentos, rubro, por_comuna):
    rm = {c for r in REGIONES if r["id"] == "RM" for c in r["comunas"]}
    orden_reg = [r["id"] for r in REGIONES]
    region_de = {c: r for r in REGIONES for c in r["comunas"]}
    por = {}
    for d in descuentos:
        if d["rubro"] != rubro or d["comercio"].strip().lower() in GENERICOS:
            continue
        v = valor(d)
        coms = [c for c in d.get("comunas", []) if c not in rm]
        if not v or not coms or len(d.get("comunas", [])) > MAX_COMUNAS_LOCAL:
            continue
        d["_valor"], d["_orden"] = v
        for c in coms:
            por.setdefault(c, {})
            k = (d["banco"], d["comercio"].strip().lower())
            if k not in por[c] or por[c][k]["_orden"] < d["_orden"]:
                por[c][k] = d
    out = []
    for c, items in por.items():
        top = sorted(items.values(), key=lambda d: (-d["_orden"], d["comercio"].lower()))[:por_comuna]
        top.sort(key=lambda d: (min(d["dias"]) if d["dias"] else 9, -d["_orden"], d["comercio"].lower()))
        out.append((c, region_de[c]["id"], region_de[c]["nombre"], top, len(items)))
    out.sort(key=lambda x: (orden_reg.index(x[1]), -x[4], x[0]))
    return out


def paginar_regiones(comunas):
    """Columnas de comunas; una comuna puede seguir en la columna siguiente."""
    cap = (FILAS_COLUMNA + ENCABEZADO + BLOQUE_EXTRA)
    cols, actual, libre = [], [], cap
    for c, rid, rnom, filas, _ in comunas:
        resto, cont = list(filas), False
        while resto:
            if libre < CAB_REG + 2 * FILA_REG + BLOQUE_EXTRA:
                cols.append(actual); actual, libre = [], cap
            n = min(len(resto), int((libre - CAB_REG - BLOQUE_EXTRA) / FILA_REG))
            actual.append((c, rnom, resto[:n], cont))
            libre -= CAB_REG + n * FILA_REG + BLOQUE_EXTRA
            resto, cont = resto[n:], True
    if actual:
        cols.append(actual)
    return [cols[i:i + 2] for i in range(0, len(cols), 2)]


def _sin_comuna(nombre: str) -> str:
    """"Roof Burger - Concón" -> "Roof Burger" (la comuna ya está en el encabezado del bloque)."""
    import re as _re
    from scraper import geo
    m = _re.match(r"^(.+?)\s+[-–]\s+(.+)$", nombre)
    if m and (geo.ubicar([m.group(2)])[1] or geo.ubicar([m.group(2)])[0]):
        return m.group(1)
    return nombre


def html_tabla_regiones(cols, titulo, sub, n, total):
    colores = {b: c for b, _, c in BANCOS}
    def bloque(c, rnom, filas, cont):
        filas_html = "".join(
            f'<div class="rrow"><span class="d">{fmt_dias(d["dias"])}</span>'
            f'<span class="bk" style="--bc:{colores.get(d["banco"], "#333")}"><b>{e(BANCO_CORTO.get(d["banco"], d["banco"]))}</b>'
            f'<i>{e(_tarjeta_corta(d))}</i></span>'
            f'<span class="m">{e(_sin_comuna(nombre_comercio(d)))}</span><span class="p">{e(d["_valor"])}</span></div>' for d in filas)
        return (f'<div class="blk"><div class="ch"><b>{e(c)}{" (cont.)" if cont else ""}</b><span>{e(rnom)}</span></div>'
                f'{filas_html}</div>')
    columnas = "".join(f'<div class="col">{"".join(bloque(*b) for b in col)}</div>' for col in cols)
    return pagina(f"""<style>{CSS_REG}</style><div class="slide">
  <div class="top"><h2><small>{e(sub)}</small>{e(titulo)}</h2><span class="pg">{n}/{total}</span></div>
  <div class="cols">{columnas}</div>
  <div class="foot"><b>{CUENTA}</b><span>Revisa en el sitio de tu banco qué locales aplican</span></div>
</div>""")


def armar_regiones(data, a, rubro_txt, mes_txt, gen):
    # La mayor cantidad por comuna que cabe en un carrusel (máx. 10 imágenes)
    for por_comuna in range(10, 2, -1):
        comunas = seleccionar_regiones(data["descuentos"], a.rubro, por_comuna)
        paginas = paginar_regiones(comunas)
        if len(paginas) + 2 <= MAX_IMAGENES:
            break
    if not comunas:
        raise SystemExit("No hay descuentos por comuna fuera de la Región Metropolitana.")
    print(f"Regiones: {len(comunas)} comunas, hasta {por_comuna} descuentos por comuna.")
    total_img = len(paginas) + 2
    filas = [d for _, _, _, f, _ in comunas for d in f]
    bancos = sorted({d["banco"] for d in filas}, key=[b for b, _, _ in BANCOS].index)
    nombres = {b: n for b, n, _ in BANCOS}
    regiones_txt = []
    for _, rid, rnom, _, _ in comunas:
        if rnom not in regiones_txt:
            regiones_txt.append(rnom)
    portada = html_portada(rubro_txt, "Regiones", mes_txt, len(filas), len(bancos), regiones_txt, todos=False)
    # En la portada: "Regiones" como título grande y el rubro debajo; los chips son las regiones
    portada = portada.replace(f"<h1>{e(rubro_txt)}</h1><div class=\"reg\">Regiones</div>",
                              f"<h1>Regiones</h1><div class=\"reg\">{e(rubro_txt)} · {len({c for c, *_ in comunas})} comunas de norte a sur</div>")
    portada = portada.replace("Los mejores de cada banco", "Los mejores de cada comuna")
    htmls = [portada]
    for i, cols in enumerate(paginas, start=2):
        htmls.append(html_tabla_regiones(cols, f"{rubro_txt} · Regiones", mes_txt, i, total_img))
    htmls.append(html_cierre(mes_txt, gen.strftime("%d-%m-%Y")))

    # Descripción: el mejor descuento de las comunas con más opciones y links de los bancos
    destacados = []
    for c, rid, rnom, f, n in sorted(comunas, key=lambda x: -x[4])[:12]:
        d = max(f, key=lambda x: x["_orden"])
        destacados.append(f"• {c}: {_valor_texto(d['_valor'])} en {_sin_comuna(nombre_comercio(d))} con {nombres[d['banco']]} ({_dias_texto(d['dias'])})")
    links = [f"{nombres[b]}: {_link(data['bancos'].get(b, {}).get('sitio'))}" for b in bancos
             if data["bancos"].get(b, {}).get("sitio")]
    cab = (f"{EMOJI[a.rubro]} {rubro_txt} en regiones · {mes_txt}\n\n"
           f"{len(filas)} descuentos con tarjeta en {len({c for c, *_ in comunas})} comunas, de Arica a Punta Arenas, "
           f"ordenados por comuna y día. 👉 Desliza, busca tu comuna y guarda el post.")
    aviso = (f"⚠️ Información de los sitios oficiales de cada banco al {gen:%d-%m-%Y}. Revisa qué locales aplican, "
             f"topes y condiciones antes de ir. Cuenta no afiliada a ningún banco.")
    tags = ("#descuentos #descuentoschile #regiones #restaurantes #vinadelmar #concepcion #temuco #antofagasta "
            "#laserena #puertomontt #tarjetadecredito #ahorro")
    for n_dest in range(len(destacados), -1, -1):
        partes = [cab]
        if n_dest:
            partes.append("🔥 El mejor de cada comuna:\n" + "\n".join(destacados[:n_dest]))
        partes += ["🔗 Condiciones en el sitio de cada banco:\n" + "\n".join(links), aviso, tags]
        texto = "\n\n".join(partes)
        if len(texto) <= LIMITE_TEXTO:
            break
    return htmls, texto


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rubro", default="restaurantes", choices=list(RUBROS))
    ap.add_argument("--region", default="RM",
                    help='id de región (RM, VS…), CL para todo Chile o REG para regiones (por comuna, sin la RM)')
    ap.add_argument("--por-banco", type=int, default=20)
    ap.add_argument("--por-tarjeta", action="store_true",
                    help="dentro de cada banco, agrupar por tipo de tarjeta (crédito y débito, solo crédito, solo Black…)")
    ap.add_argument("--sin-nacionales", action="store_true", help="excluir descuentos válidos en todo Chile/online")
    ap.add_argument("--salida", default=None)
    ap.add_argument("--mes-color", type=int, help="usar los colores de otro mes (1-12), para probar")
    a = ap.parse_args()

    data = json.loads(DATA.read_text("utf-8"))
    gen = datetime.fromisoformat(data["generado"])
    global MES_TEMA
    MES_TEMA = a.mes_color or gen.month
    # Bancos que no se actualizaron este mes (p. ej. Santander o BancoEstado si no corrió el
    # computador local) se dejan fuera: no se publican descuentos de un mes anterior
    mes = data["generado"][:7]
    viejos = {b for b, info in data.get("bancos", {}).items() if (info.get("actualizado") or "")[:7] != mes}
    if viejos:
        print(f"Se omiten por no estar actualizados este mes: {', '.join(sorted(viejos))}")
        data["descuentos"] = [d for d in data["descuentos"] if d["banco"] not in viejos]
    mes_txt = f"{MESES[gen.month - 1].capitalize()} {gen.year}"
    if a.region == "CL":
        region_txt, region_en = "Todo Chile", "en todo Chile"
    elif a.region == "REG":
        region_txt, region_en = "Regiones", "en regiones"
    else:
        region = next(r for r in REGIONES if r["id"] == a.region)
        region_txt = "Región Metropolitana" if a.region == "RM" else f"Región de {region['nombre']}"
        region_en = f"en la {region_txt}"
    a.region_en = region_en
    rubro_txt = RUBROS[a.rubro]
    out = Path(a.salida or ROOT / "instagram" / "salida" / f"{gen:%Y-%m}-{a.rubro}-{a.region}")

    if a.region == "REG":
        htmls, texto = armar_regiones(data, a, rubro_txt, mes_txt, gen)
        renderizar(htmls, out)
        (out / "texto.txt").write_text(texto, "utf-8")
        print(f"{len(htmls)} imágenes en {out}")
        return

    # Si no cabe en un carrusel (máx. 10 imágenes), se muestran menos descuentos por banco
    por_banco = a.por_banco
    while True:
        sel = seleccionar(data["descuentos"], a.rubro, a.region, por_banco, not a.sin_nacionales, a.por_tarjeta)
        if not sel:
            raise SystemExit("No hay descuentos para ese rubro y región.")
        if len(paginar(sel)) + 2 <= MAX_IMAGENES or por_banco <= 5:
            break
        por_banco -= 1
    # Entre la cantidad pedida y 6 menos, elige la que no corta bancos entre columnas y deja el
    # carrusel en 8 imágenes o menos, mostrando la mayor cantidad de descuentos posible
    def cortes(sl):
        return sum(1 for img in paginar(sl) for col in img for b in col if b[2])
    mejor = None
    for n in range(por_banco, max(por_banco - 7, 4), -1):
        alt = sel if n == por_banco else seleccionar(data["descuentos"], a.rubro, a.region, n, not a.sin_nacionales, a.por_tarjeta)
        imgs = len(paginar(alt)) + 2
        if imgs > MAX_IMAGENES:
            continue
        clave = (cortes(alt) > 0, max(imgs, 8), -n)
        if mejor is None or clave < mejor[0]:
            mejor = (clave, alt, n)
    if mejor:
        _, sel, por_banco = mejor
    # Se vuelve a seleccionar con la cantidad elegida (deja bien la marca de "todos los del mes")
    sel = seleccionar(data["descuentos"], a.rubro, a.region, por_banco, not a.sin_nacionales, a.por_tarjeta)
    if por_banco != a.por_banco:
        print(f"Se muestran {por_banco} descuentos por banco (para que quepa en {MAX_IMAGENES} imágenes sin cortar bancos).")
    tipos = {b: " / ".join(TIPOS[t] for t in ("credito", "debito", "prepago")
                           if any(t in d["tipos"] for d in filas)) for b, filas in sel.items()}
    paginas = paginar(sel)
    total_img = len(paginas) + 2
    if total_img > MAX_IMAGENES:
        raise SystemExit(f"Saldrían {total_img} imágenes (máximo {MAX_IMAGENES}). Usa un --por-banco menor.")

    nombres = {b: n for b, n, _ in BANCOS}
    htmls = [html_portada(rubro_txt, region_txt, mes_txt, sum(len(f) for f in sel.values()), len(sel),
                          [nombres[b] for b in sel], todos=not seleccionar.recortado)]
    plats = filas_codigos(data["descuentos"]) if a.rubro == "delivery" else []
    if plats:
        total_img += 1
    for i, cols in enumerate(paginas, start=2):
        htmls.append(html_tabla(cols, tipos, f"{rubro_txt} · {region_txt}", mes_txt, i, total_img))
    if plats:
        htmls.append(html_codigos(plats, mes_txt, total_img - 1, total_img))
        print(f"Códigos de descuento: {sum(len(p[3]) for p in plats)} en {len(plats)} apps")
    htmls.append(html_cierre(mes_txt, gen.strftime("%d-%m-%Y")))

    renderizar(htmls, out)

    total = sum(len(f) for f in sel.values())
    texto = descripcion(sel, data, a, rubro_txt, region_txt, mes_txt, gen)
    (out / "texto.txt").write_text(texto, "utf-8")
    print(f"{total_img} imágenes en {out}")


if __name__ == "__main__":
    main()

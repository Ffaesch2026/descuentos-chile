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
.slide{width:1080px;height:1350px;display:flex;flex-direction:column;padding:56px 52px 40px}
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


def pagina(cuerpo: str) -> str:
    t = TEMAS_MES.get(MES_TEMA, _BASE)
    variables = ":root{" + ";".join(f"--{k}:{v}" for k, v in t.items()) + "}"
    return f"<!doctype html><html lang='es'><head><meta charset='utf-8'><style>{CSS}</style><style>{variables}</style></head><body>{cuerpo}</body></html>"


def html_portada(rubro_txt, region_txt, mes_txt, total, nbancos, bancos, todos=False):
    chips = "".join(f"<span>{e(n)}</span>" for n in bancos)
    return pagina(f"""<div class="slide cover">
  <div><div class="k">Descuentos con tarjeta · {e(mes_txt)}</div>
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rubro", default="restaurantes", choices=list(RUBROS))
    ap.add_argument("--region", default="RM", help='id de región (RM, VS…) o CL para todo Chile')
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
    else:
        region = next(r for r in REGIONES if r["id"] == a.region)
        region_txt = "Región Metropolitana" if a.region == "RM" else f"Región de {region['nombre']}"
        region_en = f"en la {region_txt}"
    a.region_en = region_en
    rubro_txt = RUBROS[a.rubro]

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
    for i, cols in enumerate(paginas, start=2):
        htmls.append(html_tabla(cols, tipos, f"{rubro_txt} · {region_txt}", mes_txt, i, total_img))
    htmls.append(html_cierre(mes_txt, gen.strftime("%d-%m-%Y")))

    out = Path(a.salida or ROOT / "instagram" / "salida" / f"{gen:%Y-%m}-{a.rubro}-{a.region}")
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

    total = sum(len(f) for f in sel.values())
    texto = descripcion(sel, data, a, rubro_txt, region_txt, mes_txt, gen)
    (out / "texto.txt").write_text(texto, "utf-8")
    print(f"{total_img} imágenes en {out}")


if __name__ == "__main__":
    main()

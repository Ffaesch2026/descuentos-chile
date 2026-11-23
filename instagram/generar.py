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
FILAS_COLUMNA = 20          # filas de descuentos por columna (2 columnas por imagen)
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
    ("tenpo", "Tenpo", "#00a88a"), ("mach", "MACH", "#6c2bd9"),
]
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
    if len(ds) >= 3:
        return " ".join(DSHORT[d] for d in ds[:2]) + "<br>" + " ".join(DSHORT[d] for d in ds[2:])
    return " ".join(DSHORT[d] for d in ds)


def seleccionar(descuentos, rubro, region, por_banco, incluir_nacionales):
    out = {}
    for bid, _, _ in BANCOS:
        items = [d for d in descuentos if d["banco"] == bid and d["rubro"] == rubro and d.get("pct")
                 and ((region in d.get("regiones", [])) or (incluir_nacionales and not d.get("regiones")))]
        # Un mismo comercio una sola vez por banco (el de mayor %)
        mejor = {}
        for d in sorted(items, key=lambda d: -d["pct"]):
            mejor.setdefault(d["comercio"].strip().lower(), d)
        top = sorted(mejor.values(), key=lambda d: -d["pct"])[:por_banco]
        top.sort(key=lambda d: (min(d["dias"]) if d["dias"] else 9, -d["pct"], d["comercio"].lower()))
        if top:
            out[bid] = top
    return out


def paginar(sel):
    """Reparte los bancos en columnas: cada banco va a la primera columna donde cabe
    completo (así los bancos chicos comparten columna); si no cabe en ninguna, abre una
    nueva y, si es más largo que una columna, sigue en la próxima. Devuelve
    imágenes = [[columna1, columna2], ...]."""
    cap = FILAS_COLUMNA + ENCABEZADO
    columnas: list[list] = []
    libre: list[int] = []
    for bid, filas in sel.items():
        alto = len(filas) + ENCABEZADO
        k = next((i for i, l in enumerate(libre) if l >= alto), None)
        if k is not None:
            columnas[k].append((bid, filas, False)); libre[k] -= alto
            continue
        resto, cont = list(filas), False
        while resto:
            n = min(len(resto), cap - ENCABEZADO)
            columnas.append([(bid, resto[:n], cont)]); libre.append(cap - n - ENCABEZADO)
            resto, cont = resto[n:], True
    return [columnas[i:i + 2] for i in range(0, len(columnas), 2)]


CSS = """
@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,600;12..96,800&family=Instrument+Sans:wght@500;600;700&display=swap');
*{box-sizing:border-box;margin:0;padding:0}
body{width:1080px;height:1350px;background:#f3f5f4;color:#15201d;font-family:'Instrument Sans',system-ui,sans-serif;overflow:hidden}
.slide{width:1080px;height:1350px;display:flex;flex-direction:column;padding:56px 52px 40px}
.top{display:flex;justify-content:space-between;align-items:flex-end;border-bottom:5px solid #15201d;padding-bottom:18px;margin-bottom:22px}
.top h2{font-family:'Bricolage Grotesque',sans-serif;font-weight:800;font-size:46px;letter-spacing:-.02em;line-height:1}
.top h2 small{display:block;font-family:'Instrument Sans';font-weight:600;font-size:22px;letter-spacing:.1em;text-transform:uppercase;color:#0b7a5c;margin-bottom:8px}
.top .pg{font-size:24px;font-weight:600;color:#5d6a66}
.cols{flex:1;display:grid;grid-template-columns:1fr 1fr;gap:22px;align-content:start}
.col{display:flex;flex-direction:column;gap:14px}
.blk{background:#fff;border-radius:14px;overflow:hidden;border:2px solid #dbe2df}
.bh{background:var(--c);color:#fff;padding:10px 16px;display:flex;justify-content:space-between;gap:10px;height:72px;align-items:center}
.bh b{font-family:'Bricolage Grotesque',sans-serif;font-weight:800;font-size:28px;letter-spacing:-.01em}
.bh span{font-size:18px;font-weight:600;opacity:.9;text-align:right;line-height:1.1}
.row{display:grid;grid-template-columns:104px 1fr 80px;align-items:center;height:46px;padding:0 14px;border-top:1px solid #e6ebe9;font-size:26px}
.row:nth-child(odd){background:color-mix(in srgb,var(--c) 6%,#fff)}
.d{font-size:17px;font-weight:700;color:#5d6a66;letter-spacing:.02em;line-height:1.2}
.m{font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;padding-right:8px}
.p{font-family:'Bricolage Grotesque',sans-serif;font-weight:800;font-size:29px;text-align:right;color:var(--c)}
.foot{display:flex;justify-content:space-between;align-items:center;margin-top:16px;font-size:21px;color:#5d6a66;font-weight:600}
.foot b{color:#15201d;font-size:24px}
/* portada y cierre */
.cover{background:#15201d;color:#f3f5f4;justify-content:space-between;padding:80px 72px}
.cover .k{font-size:28px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:#3ccf9f}
.cover h1{font-family:'Bricolage Grotesque',sans-serif;font-weight:800;font-size:150px;line-height:.92;letter-spacing:-.04em;margin:26px 0 30px}
.cover .reg{font-family:'Bricolage Grotesque',sans-serif;font-weight:600;font-size:58px;line-height:1.05}
.cover .big{display:flex;gap:56px;margin-top:56px}
.cover .big div b{display:block;font-family:'Bricolage Grotesque',sans-serif;font-weight:800;font-size:96px;line-height:1;color:#3ccf9f}
.cover .big div span{font-size:26px;font-weight:600;color:#c9d3cf}
.chips{display:flex;flex-wrap:wrap;gap:12px}
.chips span{border:2px solid #3a4743;border-radius:999px;padding:8px 18px;font-size:24px;font-weight:600}
.cover .lead{font-size:32px;color:#c9d3cf;margin-top:40px;max-width:820px;line-height:1.3}
.cover .bottom{display:flex;justify-content:space-between;align-items:center;font-size:30px;font-weight:700}
.cover .swipe{background:#3ccf9f;color:#0b1411;border-radius:999px;padding:14px 30px}
.end h1{font-size:110px}
.end p{font-size:34px;line-height:1.35;color:#c9d3cf;max-width:860px}
.end .note{font-size:24px;color:#97a49f;line-height:1.4}
"""


def pagina(cuerpo: str) -> str:
    return f"<!doctype html><html lang='es'><head><meta charset='utf-8'><style>{CSS}</style></head><body>{cuerpo}</body></html>"


def html_portada(rubro_txt, region_txt, mes_txt, total, nbancos, bancos):
    chips = "".join(f"<span>{e(n)}</span>" for n in bancos)
    return pagina(f"""<div class="slide cover">
  <div><div class="k">Descuentos con tarjeta · {e(mes_txt)}</div>
  <h1>{e(rubro_txt)}</h1><div class="reg">{e(region_txt)}</div>
  <div class="big"><div><b>{total}</b><span>descuentos</span></div><div><b>{nbancos}</b><span>bancos y tarjetas</span></div></div>
  <p class="lead">Los mejores de cada banco, ordenados por día de la semana.</p></div>
  <div class="chips">{chips}</div>
  <div class="bottom"><span>{CUENTA}</span><span class="swipe">Desliza →</span></div>
</div>""")


def html_tabla(cols, sel_tipos, titulo, sub, n, total):
    nombres = {b: (n_, c) for b, n_, c in BANCOS}
    def bloque(bid, filas, cont):
        nombre, color = nombres[bid]
        filas_html = "".join(
            f'<div class="row"><span class="d">{fmt_dias(d["dias"])}</span><span class="m">{e(d["comercio"])}</span><span class="p">{d["pct"]}%</span></div>'
            for d in filas)
        return (f'<div class="blk" style="--c:{color}"><div class="bh"><b>{e(nombre)}{" (cont.)" if cont else ""}</b>'
                f'<span>{e(sel_tipos[bid])}</span></div>{filas_html}</div>')
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rubro", default="restaurantes", choices=list(RUBROS))
    ap.add_argument("--region", default="RM")
    ap.add_argument("--por-banco", type=int, default=20)
    ap.add_argument("--sin-nacionales", action="store_true", help="excluir descuentos válidos en todo Chile/online")
    ap.add_argument("--salida", default=None)
    a = ap.parse_args()

    data = json.loads(DATA.read_text("utf-8"))
    gen = datetime.fromisoformat(data["generado"])
    mes_txt = f"{MESES[gen.month - 1].capitalize()} {gen.year}"
    region = next(r for r in REGIONES if r["id"] == a.region)
    region_txt = "Región Metropolitana" if a.region == "RM" else f"Región de {region['nombre']}"
    rubro_txt = RUBROS[a.rubro]

    sel = seleccionar(data["descuentos"], a.rubro, a.region, a.por_banco, not a.sin_nacionales)
    if not sel:
        raise SystemExit("No hay descuentos para ese rubro y región.")
    tipos = {b: " / ".join(TIPOS[t] for t in ("credito", "debito", "prepago")
                           if any(t in d["tipos"] for d in filas)) for b, filas in sel.items()}
    paginas = paginar(sel)
    total_img = len(paginas) + 2
    if total_img > MAX_IMAGENES:
        raise SystemExit(f"Saldrían {total_img} imágenes (máximo {MAX_IMAGENES}). Usa un --por-banco menor.")

    nombres = {b: n for b, n, _ in BANCOS}
    htmls = [html_portada(rubro_txt, region_txt, mes_txt, sum(len(f) for f in sel.values()), len(sel),
                          [nombres[b] for b in sel])]
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
    texto = (f"🍽️ {total} descuentos en {rubro_txt.lower()} con tarjeta en la {region_txt} · {mes_txt}\n\n"
             f"Los mejores descuentos de {len(sel)} bancos y tarjetas, ordenados por día. "
             f"Desliza para ver todos y guarda el post para tenerlo a mano.\n\n"
             f"Los descuentos pueden cambiar: revisa topes y condiciones en el sitio de tu banco antes de usarlos.\n\n"
             f"#descuentos #descuentoschile #{a.rubro} #santiago #tarjetadecredito #ahorro #chile")
    (out / "texto.txt").write_text(texto, "utf-8")
    print(f"{total_img} imágenes en {out}")


if __name__ == "__main__":
    main()

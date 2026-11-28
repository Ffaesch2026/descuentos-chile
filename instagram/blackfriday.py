"""Carrusel de Instagram: ofertas de Black Friday verificadas (data/blackfriday-2026.json).

Uso:  python -m instagram.blackfriday [--datos data/blackfriday-2026.json] [--salida carpeta]

Estilo Black Friday: fondo negro, tipografía blanca condensada y amarillo de acento.
Cada oferta muestra la foto, la tienda, el precio de Black Friday, el precio habitual
de las semanas anteriores (tachado) y el descuento REAL calculado contra ese precio.
"""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CUENTA = "@descuentosalmes"
MAX_IMAGENES = 15
e = html.escape


def pesos(n: float) -> str:
    return "$" + f"{round(n):,}".replace(",", ".")


CSS = """
@import url('https://fonts.googleapis.com/css2?family=Anton&family=Instrument+Sans:wght@500;600;700&display=swap');
*{box-sizing:border-box;margin:0;padding:0}
body{width:1080px;height:1350px;overflow:hidden;background:#0a0a0a;color:#fff;font-family:'Instrument Sans',system-ui,sans-serif}
.slide{position:relative;width:1080px;height:1350px;overflow:hidden;display:flex;flex-direction:column;padding:64px 60px 48px}
.slide > *{position:relative;z-index:1}
.fondo{position:absolute;inset:0;z-index:0}
.anton{font-family:'Anton',Impact,sans-serif;text-transform:uppercase;letter-spacing:.01em}
.tag{display:inline-flex;align-items:center;gap:12px;background:#ffd600;color:#0a0a0a;font-weight:800;border-radius:8px;padding:10px 20px}
/* portada */
.p-k{font-weight:700;font-size:26px;letter-spacing:.3em;text-transform:uppercase;color:#bdbdbd}
.p-bf{font-family:'Anton',Impact,sans-serif;font-size:250px;line-height:.84;text-transform:uppercase;margin-top:30px}
.p-bf span{display:block}
.p-bf .amarillo{color:#ffd600}
.p-fechas{margin-top:34px;font-size:46px;font-family:'Anton',Impact,sans-serif;letter-spacing:.02em;align-self:flex-start}
.p-lead{font-size:34px;line-height:1.3;color:#e6e6e6;margin-top:30px;max-width:860px;font-weight:600}
.p-lead b{color:#ffd600}
.p-rubros{display:flex;flex-wrap:wrap;gap:12px;margin-top:30px}
.p-rubros span{border:2px solid #4a4a4a;border-radius:999px;padding:6px 16px;font-size:21px;font-weight:700}
.pie{margin-top:auto;display:flex;justify-content:space-between;align-items:center;font-weight:700;font-size:28px}
.btn{background:#ffd600;color:#0a0a0a;border-radius:999px;padding:14px 30px}
/* ofertas */
.cab{display:flex;justify-content:space-between;align-items:flex-end;border-bottom:4px solid #ffd600;padding-bottom:16px;margin-bottom:22px}
.cab h2{font-family:'Anton',Impact,sans-serif;font-size:72px;line-height:.95;text-transform:uppercase}
.cab h2 small{display:block;font-family:'Instrument Sans',sans-serif;font-size:21px;letter-spacing:.24em;color:#ffd600;margin-bottom:10px;font-weight:700}
.cab .pg{font-weight:700;font-size:24px;color:#9e9e9e}
.lista{display:flex;flex-direction:column;gap:16px;flex:1}
.of{display:grid;grid-template-columns:150px 1fr 230px;align-items:center;gap:22px;background:#171717;border:2px solid #2b2b2b;border-radius:20px;padding:14px 22px 14px 14px;height:190px}
.of .foto{width:150px;height:150px;border-radius:14px;background:#fff;display:flex;align-items:center;justify-content:center;overflow:hidden}
.of .foto img{max-width:92%;max-height:92%;object-fit:contain}
.of .info{min-width:0;display:flex;flex-direction:column;gap:8px}
.of .nom{font-size:29px;font-weight:700;line-height:1.12;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.of .tienda{font-size:21px;font-weight:600;color:#bdbdbd}
.of .min{align-self:flex-start;font-size:16px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:#0a0a0a;background:#fff;border-radius:6px;padding:4px 10px}
.of .precios{text-align:right;display:flex;flex-direction:column;align-items:flex-end;gap:6px}
.of .real{font-family:'Anton',Impact,sans-serif;font-size:30px;background:#ffd600;color:#0a0a0a;border-radius:8px;padding:2px 12px;line-height:1.2}
.of .ahora{font-family:'Anton',Impact,sans-serif;font-size:50px;line-height:1}
.of .antes{font-size:20px;color:#9e9e9e;font-weight:600}
.of .antes s{text-decoration-thickness:2px}
.nota{margin-top:20px;display:flex;justify-content:space-between;font-size:20px;font-weight:600;color:#9e9e9e}
.nota b{color:#fff;font-size:24px}
/* vuelos */
.vu{display:grid;grid-template-columns:120px 1fr 200px 150px;align-items:center;gap:18px;background:#171717;border:2px solid #2b2b2b;border-radius:18px;padding:0 22px;height:84px}
.vu .air{font-weight:800;font-size:22px;border-radius:8px;padding:6px 10px;text-align:center}
.vu .air.JetSMART{background:#1d4ed8;color:#fff}.vu .air.LATAM{background:#e5004b;color:#fff}
.vu .ruta{font-size:30px;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.vu .ahora{font-family:'Anton',Impact,sans-serif;font-size:44px;text-align:right}
.vu .inf{font-family:'Anton',Impact,sans-serif;font-size:26px;background:#fff;color:#0a0a0a;border-radius:8px;padding:2px 10px;text-align:center}
.vlista{display:flex;flex-direction:column;gap:11px}
.vnota{font-size:21px;color:#bdbdbd;font-weight:600;margin-top:18px;line-height:1.4}
/* cierre */
.c-h{font-family:'Anton',Impact,sans-serif;font-size:120px;line-height:.92;text-transform:uppercase;margin-top:20px}
.c-h .amarillo{color:#ffd600}
.c-p{font-size:32px;line-height:1.4;color:#e6e6e6;margin-top:34px;max-width:900px;font-weight:500}
.c-p b{color:#fff}
.c-seg{font-family:'Anton',Impact,sans-serif;font-size:64px;text-transform:uppercase;margin-top:auto;line-height:1}
.c-av{font-size:22px;line-height:1.45;color:#9e9e9e;margin-top:30px}
"""


def fondo_rayas(op=.07) -> str:
    """Franjas diagonales sutiles y una etiqueta de precio gigante de fondo."""
    rayas = "".join(f'<rect x="{x}" y="-200" width="60" height="1900" fill="#ffffff" opacity="{op}" transform="rotate(25 {x} 675)"/>'
                    for x in range(-400, 1500, 240))
    etiqueta = ('<g transform="translate(640 820) rotate(-18)" opacity=".16" fill="none" stroke="#ffd600" stroke-width="10">'
                '<path d="M0 0 h420 l90 120 l-90 120 h-420 z"/><circle cx="410" cy="120" r="22"/></g>')
    return f'<svg class="fondo" viewBox="0 0 1080 1350">{rayas}{etiqueta}</svg>'


def pagina(cuerpo: str) -> str:
    return f"<!doctype html><html lang='es'><head><meta charset='utf-8'><style>{CSS}</style></head><body>{cuerpo}</body></html>"


def portada(d) -> str:
    total = sum(len(g["productos"]) for g in d["grupos"])
    rubros = "".join(f"<span>{e(n)}</span>" for n in (["Vuelos"] if d.get("viajes") else []) + [g["nombre"] for g in d["grupos"]])
    return pagina(f"""<div class="slide">{fondo_rayas()}
  <div class="p-k">{e(d.get("parte", "Ofertas verificadas · Chile"))}</div>
  <div class="p-bf"><span>Black</span><span class="amarillo">Friday</span></div>
  <div class="p-fechas tag">{e(d['fechas'].upper())}</div>
  <div class="p-lead">{total} ofertas con <b>descuento real</b> (comparamos cada precio con lo que costaba en octubre y noviembre){f" + {len(d['viajes']['vuelos'])} vuelos" if d.get("viajes") else ""}.</div>
  <div class="p-rubros">{rubros}</div>
  <div class="pie"><span>{CUENTA}</span><span class="btn">Desliza →</span></div>
</div>""")


def oferta(x) -> str:
    foto = f'<img src="{e(x["foto"])}" alt="">' if x.get("foto") else ""
    minimo = '<span class="min">Precio más bajo desde octubre</span>' if x.get("nuevo_minimo") else ""
    return (f'<div class="of"><div class="foto">{foto}</div><div class="info"><div class="nom">{e(x["producto"])}</div>'
            f'<div class="tienda">en {e(x["tienda"])}</div>{minimo}</div>'
            f'<div class="precios"><span class="real">-{x["descuento_real"]}% REAL</span><span class="ahora">{pesos(x["precio"])}</span>'
            f'<span class="antes">Habitual <s>{pesos(x["precio_habitual"])}</s></span></div></div>')


def lamina(g, n, total) -> str:
    return pagina(f"""<div class="slide">{fondo_rayas(.04)}
  <div class="cab"><h2><small>Black Friday · ofertas reales</small>{e(g['nombre'])}</h2><span class="pg">{n}/{total}</span></div>
  <div class="lista">{''.join(oferta(x) for x in g['productos'])}</div>
  <div class="nota"><b>{CUENTA}</b><span>Precios revisados el 28-11 · pueden cambiar o agotarse</span></div>
</div>""")


def lamina_vuelos(v, n, total) -> str:
    filas = "".join(f'<div class="vu"><span class="air {e(x["aerolinea"])}">{e(x["aerolinea"])}</span><span class="ruta">{e(x["ruta"])}</span>'
                    f'<span class="ahora">{pesos(x["precio"])}</span><span class="inf">-{x["descuento_informado"]}%</span></div>' for x in v["vuelos"])
    return pagina(f"""<div class="slide">{fondo_rayas(.04)}
  <div class="cab"><h2><small>Black Friday · viajes</small>{e(v['nombre'])}</h2><span class="pg">{n}/{total}</span></div>
  <div class="vlista">{filas}</div>
  <div class="vnota">Precio por tramo, más tasas. Viajes entre diciembre 2026 y junio 2027. El % lo informa la aerolínea (no hay historial público de pasajes para verificarlo).</div>
  <div class="nota"><b>{CUENTA}</b><span>Revisa disponibilidad y precio final en la web de cada aerolínea</span></div>
</div>""")


def cierre(d) -> str:
    return pagina(f"""<div class="slide">{fondo_rayas()}
  <div class="p-k">Antes de comprar</div>
  <div class="c-h">Que no te<br><span class="amarillo">engañen</span></div>
  <div class="c-p">De <b>{d['revisados']} productos populares</b> que revisamos, solo <b>{d.get('verificadas', sum(len(g['productos']) for g in d['grupos']))}</b> tenían un descuento real de 15% o más.
  Compara siempre con el precio de las semanas anteriores, no con el "precio antes" que muestra la tienda.</div>
  <div class="c-seg">Síguenos en<br>{CUENTA}</div>
  <div class="c-av">Descuento real = precio Black Friday comparado con el precio habitual entre el {e(d['periodo_comparacion'])}, según el historial de precios de SoloTodo.
  Precios revisados el {e(d['fecha_revision'][8:10])}-{e(d['fecha_revision'][5:7])}; pueden cambiar o agotarse. Cuenta no afiliada a ninguna tienda.</div>
</div>""")


def descripcion(d, max_por_grupo: int = 2) -> str:
    lineas = [f"🖤 Black Friday Chile · {d['fechas']}" + (f" · {d['parte']}" if d.get("parte") else ""), "",
              f"Lo mejor de cada rubro 👇 (todas las ofertas, en las imágenes)", "",
              "Ofertas con DESCUENTO REAL: comparamos cada precio de hoy con lo que costaba entre octubre y noviembre "
              "(no con el \"precio antes\" de la tienda). 👉 Desliza y guarda el post.", ""]
    if d.get("viajes"):
        lineas.append("✈️ Vuelos (precio por tramo + tasas)")
        for x in d["viajes"]["vuelos"][:6]:
            lineas.append(f"• {x['aerolinea']} {x['ruta']}: {pesos(x['precio'])} (-{x['descuento_informado']}%)")
        lineas.append("")
    for g in d["grupos"]:
        lineas.append(f"▪️ {g['nombre']}")
        for x in g["productos"][:max_por_grupo]:
            lineas.append(f"• {x['producto']}: {pesos(x['precio'])} en {x['tienda']} (-{x['descuento_real']}% real)")
        lineas.append("")
    lineas += [f"🔎 De {d['revisados']} productos populares revisados, solo {d.get('verificadas', sum(len(g['productos']) for g in d['grupos']))} tenían "
               "un descuento real de 15% o más. Precios revisados el "
               f"{d['fecha_revision'][8:10]}-{d['fecha_revision'][5:7]}: pueden cambiar o agotarse. Fuente del historial: SoloTodo. "
               "Cuenta no afiliada a ninguna tienda.", "",
               "#blackfriday #blackfridaychile #blackfriday2026 #ofertas #descuentos #descuentoschile #chile #ahorro"]
    texto = "\n".join(lineas)
    if len(texto) > 2200 and max_por_grupo > 1:
        return descripcion(d, max_por_grupo - 1)
    return texto


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--datos", default=str(ROOT / "data" / "blackfriday-2026.json"))
    ap.add_argument("--salida", default=None)
    ap.add_argument("--parte", type=int, choices=[0, 1, 2], default=0,
                    help="0 = todo; 1 = vuelos y tecnología; 2 = hogar, cocina y belleza (para no pasar de 10 imágenes)")
    a = ap.parse_args()
    d = json.loads(Path(a.datos).read_text("utf-8"))
    d["verificadas"] = sum(len(g["productos"]) for g in d["grupos"])
    if a.parte:
        tecno = {"tecnologia", "monitores", "audifonos", "parlantes", "gamer"}
        d["grupos"] = [g for g in d["grupos"] if (g["id"] in tecno) == (a.parte == 1)]
        if a.parte == 2:
            d.pop("viajes", None)
        d["parte"] = "Parte 1 · Viajes y tecnología" if a.parte == 1 else "Parte 2 · Hogar, cocina y belleza"
    ap_max = MAX_IMAGENES
    vuelos = 1 if d.get("viajes") else 0
    grupos = [g for g in d["grupos"] if g["productos"]][:ap_max - 2 - vuelos]
    total = len(grupos) + 2 + vuelos
    htmls = [portada(d)]
    if vuelos:
        htmls.append(lamina_vuelos(d["viajes"], 2, total))
    htmls += [lamina(g, i, total) for i, g in enumerate(grupos, start=2 + vuelos)] + [cierre(d)]
    out = Path(a.salida or ROOT / "instagram" / "salida" / "blackfriday")
    from instagram.generar import renderizar
    renderizar(htmls, out)
    (out / "texto.txt").write_text(descripcion(d), "utf-8")
    print(f"{len(htmls)} imágenes en {out}")


if __name__ == "__main__":
    main()

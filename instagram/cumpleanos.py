"""Carrusel de Instagram: beneficios de cumpleaños (datos en data/cumpleanos.json).

Uso:
    python -m instagram.cumpleanos                       # instagram/salida/cumpleanos/
    python -m instagram.cumpleanos --salida carpeta

Diseño propio, más colorido que el de los descuentos con tarjeta: portada con una torta,
globos y confeti dibujados en SVG; tarjetas por categoría; cierre "¡Feliz cumpleaños!".
"""
from __future__ import annotations

import argparse
import html
import json
import os
import random
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "cumpleanos.json"
CUENTA = "@descuentosalmes"
W, H = 1080, 1350
POR_IMAGEN = 6
e = html.escape

CUANDO = {"día": "Tu día", "dia": "Tu día", "semana": "Hasta 1 semana", "mes": "Todo tu mes"}
CONFETI = ["#ff3e7f", "#ffd23f", "#00b3a6", "#7b2ff7", "#ff8c1a", "#1f7aff", "#ffffff"]

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Fredoka:wght@500;600;700&family=Instrument+Sans:wght@500;600;700&display=swap');
*{box-sizing:border-box;margin:0;padding:0}
body{width:1080px;height:1350px;overflow:hidden;font-family:'Instrument Sans',system-ui,sans-serif;color:#2a1a3a}
.slide{position:relative;width:1080px;height:1350px;overflow:hidden}
.confeti{position:absolute;inset:0;pointer-events:none}
.capa{position:relative;z-index:1;height:100%;display:flex;flex-direction:column}
.fredoka{font-family:'Fredoka','Instrument Sans',sans-serif}

/* Portada */
.portada{background:linear-gradient(160deg,#ff3e7f 0%,#ff7a59 45%,#ffc93c 100%)}
.portada .capa{padding:70px 70px 56px;align-items:center;text-align:center}
.eyebrow{font-weight:700;font-size:26px;letter-spacing:.18em;text-transform:uppercase;color:#fff;background:#2a1a3a;border-radius:999px;padding:10px 26px}
.titulo{font-family:'Fredoka',sans-serif;font-weight:700;color:#fff;font-size:132px;line-height:.92;margin-top:34px;
  text-shadow:0 6px 0 #c2185b,0 10px 24px rgba(80,0,40,.35);letter-spacing:-.01em}
.sub{font-family:'Fredoka',sans-serif;font-weight:600;font-size:38px;color:#2a1a3a;margin-top:26px;background:#fff;border-radius:22px;padding:12px 28px;box-shadow:0 6px 0 #2a1a3a}
.ilus{margin-top:auto;width:100%;display:flex;justify-content:center}
.pie{display:flex;justify-content:space-between;align-items:center;width:100%;margin-top:18px;font-weight:700;font-size:30px;color:#2a1a3a}
.btn{background:#2a1a3a;color:#ffd23f;border-radius:999px;padding:14px 30px}

/* Tarjetas */
.lista{background:#fff6e9}
.lista .capa{padding:60px 56px 44px;justify-content:flex-start}
.cab{display:flex;justify-content:space-between;align-items:center;margin-bottom:30px}
.cab h2{font-family:'Fredoka',sans-serif;font-weight:700;font-size:54px;line-height:1;color:#2a1a3a}
.cab h2 small{display:block;font-family:'Instrument Sans',sans-serif;font-size:22px;letter-spacing:.14em;text-transform:uppercase;color:#ff3e7f;margin-bottom:8px}
.pg{font-family:'Fredoka',sans-serif;font-weight:600;font-size:26px;color:#fff;background:#2a1a3a;border-radius:999px;padding:6px 18px}
.cat{display:inline-flex;align-items:center;gap:12px;font-family:'Fredoka',sans-serif;font-weight:700;font-size:34px;color:#fff;background:var(--c);
  border-radius:16px;padding:8px 20px;margin:6px 0 16px;box-shadow:0 5px 0 rgba(42,26,58,.85)}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:24px;margin-bottom:26px}
.card{background:#fff;border-radius:26px;padding:24px 26px 22px;border:4px solid #2a1a3a;box-shadow:8px 8px 0 var(--c);display:flex;flex-direction:column;gap:12px;min-height:262px}
.marca{font-family:'Fredoka',sans-serif;font-weight:700;font-size:46px;line-height:1;color:#2a1a3a}
.regalo{font-family:'Fredoka',sans-serif;font-weight:600;font-size:36px;line-height:1.08;color:var(--c)}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:auto}
.chip{display:inline-flex;align-items:center;gap:7px;font-size:21px;font-weight:700;border-radius:999px;padding:6px 13px;background:#f3ecff;color:#2a1a3a}
.chip.cuando{background:var(--c);color:#fff}
.chip svg{width:22px;height:22px;flex:none}
/* Imágenes con 4 filas de tarjetas (dos categorías con número impar): tarjetas más compactas */
.compacta .cat{font-size:28px;padding:6px 18px;margin:2px 0 12px}
.compacta .grid{gap:18px;margin-bottom:18px}
.compacta .card{min-height:0;padding:18px 22px 16px;gap:8px}
.compacta .marca{font-size:38px}
.compacta .regalo{font-size:30px}
.compacta .chip{font-size:19px;padding:5px 12px}
.nota{margin-top:auto;display:flex;justify-content:space-between;align-items:center;font-weight:700;font-size:22px;color:#2a1a3a}
.nota span{font-weight:600;color:#6b5a7b}

/* Cierre */
.cierre{background:linear-gradient(200deg,#7b2ff7 0%,#ff3e7f 60%,#ff8c1a 100%)}
.cierre .capa{padding:90px 76px 64px;color:#fff}
.cierre h1{font-family:'Fredoka',sans-serif;font-weight:700;font-size:118px;line-height:.95;text-shadow:0 6px 0 #4b1a8f}
.cierre p{font-size:36px;line-height:1.35;margin-top:30px;max-width:880px;font-weight:600}
.cierre .seg{font-family:'Fredoka',sans-serif;font-weight:700;font-size:56px;margin-top:auto}
.cierre .aviso{font-size:23px;line-height:1.4;opacity:.9;margin-top:34px}
"""

ICONO_CAL = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round">'
             '<rect x="3" y="5" width="18" height="16" rx="3"/><path d="M3 10h18M8 3v4M16 3v4"/></svg>')
ICONO_REQ = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round">'
             '<rect x="3" y="6" width="18" height="13" rx="2.5"/><circle cx="9" cy="12" r="2.4"/><path d="M14 11h4M14 15h3"/></svg>')


def confeti(semilla: int, n: int = 70, zona_libre=None) -> str:
    """Confeti al azar (rectángulos, círculos y serpentinas) como SVG de fondo."""
    rnd = random.Random(semilla)
    piezas = []
    for _ in range(n):
        x, y = rnd.uniform(0, W), rnd.uniform(0, H)
        if zona_libre and zona_libre[0] < x < zona_libre[2] and zona_libre[1] < y < zona_libre[3]:
            continue
        c = rnd.choice(CONFETI)
        r = rnd.uniform(0, 180)
        t = rnd.random()
        if t < 0.45:
            piezas.append(f'<rect x="{x:.0f}" y="{y:.0f}" width="{rnd.uniform(10, 20):.0f}" height="{rnd.uniform(5, 9):.0f}" '
                          f'rx="2" fill="{c}" transform="rotate({r:.0f} {x:.0f} {y:.0f})" opacity=".9"/>')
        elif t < 0.8:
            piezas.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{rnd.uniform(4, 8):.0f}" fill="{c}" opacity=".9"/>')
        else:
            piezas.append(f'<path d="M{x:.0f} {y:.0f} q10 -12 20 0 t20 0 t20 0" fill="none" stroke="{c}" stroke-width="5" '
                          f'stroke-linecap="round" transform="rotate({r:.0f} {x:.0f} {y:.0f})" opacity=".9"/>')
    return f'<svg class="confeti" viewBox="0 0 {W} {H}">{"".join(piezas)}</svg>'


def ilustracion() -> str:
    """Torta de dos pisos con velas encendidas, globos y una caja de regalo."""
    globo = lambda cx, cy, c, rot: (  # noqa: E731
        f'<g transform="rotate({rot} {cx} {cy + 120})">'
        f'<path d="M{cx} {cy + 92} q-14 60 8 120 q18 50 -6 110" fill="none" stroke="#2a1a3a" stroke-width="3"/>'
        f'<ellipse cx="{cx}" cy="{cy}" rx="70" ry="86" fill="{c}" stroke="#2a1a3a" stroke-width="5"/>'
        f'<path d="M{cx - 10} {cy + 84} l10 14 l10 -14 z" fill="{c}" stroke="#2a1a3a" stroke-width="4" stroke-linejoin="round"/>'
        f'<ellipse cx="{cx - 26}" cy="{cy - 34}" rx="14" ry="24" fill="#fff" opacity=".55" transform="rotate(-20 {cx - 26} {cy - 34})"/></g>')
    velas = []
    for i, c in enumerate(["#7b2ff7", "#00b3a6", "#ff3e7f", "#1f7aff", "#ff8c1a"]):
        x = 380 + i * 52
        velas.append(
            f'<rect x="{x}" y="250" width="22" height="78" rx="6" fill="{c}" stroke="#2a1a3a" stroke-width="4"/>'
            f'<path d="M{x} 268 l22 -10 M{x} 290 l22 -10 M{x} 312 l22 -10" stroke="#fff" stroke-width="4" opacity=".7"/>'
            f'<path d="M{x + 11} 206 q-20 26 0 42 q20 -16 0 -42 z" fill="#ffb703" stroke="#2a1a3a" stroke-width="3.5"/>'
            f'<path d="M{x + 11} 224 q-8 12 0 20 q8 -8 0 -20 z" fill="#fff3b0"/>')
    chispas = "".join(f'<rect x="{x}" y="{y}" width="14" height="6" rx="3" fill="{c}" transform="rotate({r} {x} {y})"/>'
                      for x, y, c, r in [(330, 470, "#7b2ff7", 20), (420, 500, "#00b3a6", -30), (520, 468, "#1f7aff", 40),
                                         (620, 505, "#ff8c1a", -10), (700, 470, "#7b2ff7", 60), (365, 540, "#ffd23f", -40),
                                         (470, 560, "#ff3e7f", 15), (580, 545, "#00b3a6", -55), (680, 555, "#ffd23f", 25),
                                         (455, 372, "#ff3e7f", 30), (560, 360, "#00b3a6", -20), (620, 388, "#7b2ff7", 45)])
    torta = f"""
  <ellipse cx="540" cy="650" rx="330" ry="40" fill="#2a1a3a" opacity=".18"/>
  <ellipse cx="540" cy="632" rx="320" ry="36" fill="#fff" stroke="#2a1a3a" stroke-width="5"/>
  <!-- piso de abajo -->
  <path d="M260 450 h560 v150 q0 30 -30 30 h-500 q-30 0 -30 -30 z" fill="#ff7aa8" stroke="#2a1a3a" stroke-width="6"/>
  <path d="M260 450 h560 v36 q-24 34 -48 0 q-24 44 -52 0 q-26 30 -52 0 q-26 46 -54 0 q-26 30 -52 0 q-26 44 -54 0
           q-26 30 -52 0 q-26 40 -52 0 q-26 30 -52 0 q-24 38 -46 0 z" fill="#fff6e9" stroke="#2a1a3a" stroke-width="6" stroke-linejoin="round"/>
  <!-- piso de arriba -->
  <path d="M350 330 h380 v120 h-380 z" fill="#ffd23f" stroke="#2a1a3a" stroke-width="6" stroke-linejoin="round"/>
  <path d="M350 330 h380 v30 q-22 32 -44 0 q-22 40 -46 0 q-24 28 -48 0 q-24 42 -50 0 q-24 28 -48 0 q-24 40 -48 0
           q-24 28 -50 0 q-22 34 -46 0 z" fill="#ff3e7f" stroke="#2a1a3a" stroke-width="6" stroke-linejoin="round"/>
  {''.join(velas)}
  {chispas}"""
    regalo = """
  <g transform="translate(830 470) rotate(8)">
    <rect x="0" y="40" width="150" height="120" rx="10" fill="#00b3a6" stroke="#2a1a3a" stroke-width="5"/>
    <rect x="-10" y="18" width="170" height="40" rx="8" fill="#00d1c1" stroke="#2a1a3a" stroke-width="5"/>
    <rect x="62" y="18" width="26" height="142" fill="#ffd23f" stroke="#2a1a3a" stroke-width="5"/>
    <path d="M75 18 q-48 -48 -60 -8 q-4 22 60 8 z M75 18 q48 -48 60 -8 q4 22 -60 8 z" fill="#ffd23f" stroke="#2a1a3a" stroke-width="5" stroke-linejoin="round"/>
  </g>"""
    return (f'<svg viewBox="0 0 1080 700" width="1000" height="648">'
            f'{globo(150, 190, "#7b2ff7", -8)}{globo(260, 120, "#00b3a6", 6)}{globo(930, 150, "#1f7aff", 8)}'
            f'{torta}{regalo}</svg>')


def pagina(cuerpo: str) -> str:
    return f"<!doctype html><html lang='es'><head><meta charset='utf-8'><style>{CSS}</style></head><body>{cuerpo}</body></html>"


def html_portada(total: int) -> str:
    return pagina(f"""<div class="slide portada">{confeti(1, 90, (90, 40, 990, 1320))}<div class="capa">
  <div class="eyebrow">Solo por cumplir años</div>
  <div class="titulo">Beneficios<br>de cumpleaños</div>
  <div class="sub">{total} regalos y descuentos en tu día 🎉</div>
  <div class="ilus">{ilustracion()}</div>
  <div class="pie"><span>{CUENTA}</span><span class="btn">Desliza →</span></div>
</div></div>""".replace(" 🎉", ""))


def tarjeta(b: dict, color: str) -> str:
    cuando = CUANDO.get(b.get("cuando", ""), b.get("cuando", ""))
    return (f'<div class="card" style="--c:{color}"><div class="marca">{e(b["marca"])}</div>'
            f'<div class="regalo">{e(b["regalo"])}</div><div class="chips">'
            f'<span class="chip cuando">{ICONO_CAL}{e(cuando)}</span>'
            f'<span class="chip">{ICONO_REQ}{e(b["requisito"])}</span></div></div>')


def paginar(categorias: list[dict]) -> list[list[tuple[dict, list[dict]]]]:
    """Hasta POR_IMAGEN tarjetas y 2 categorías por imagen. Las categorías van enteras y las
    chicas se combinan para llenar cada imagen (primero las más grandes)."""
    paginas: list[list] = []
    libres: list[int] = []
    for cat in sorted(categorias, key=lambda c: -len(c["beneficios"])):
        bs = list(cat["beneficios"])
        k = next((i for i, l in enumerate(libres) if l >= len(bs) and len(paginas[i]) < 2), None)
        if k is not None:
            paginas[k].append((cat, bs)); libres[k] -= len(bs)
            continue
        while bs:
            paginas.append([(cat, bs[:POR_IMAGEN])]); libres.append(POR_IMAGEN - len(bs[:POR_IMAGEN]))
            bs = bs[POR_IMAGEN:]
    orden = {c["id"]: i for i, c in enumerate(categorias)}
    paginas.sort(key=lambda p: min(orden[c["id"]] for c, _ in p))
    return paginas


def html_lista(bloques, n: int, total: int, semilla: int) -> str:
    cuerpo = ""
    for cat, bs in bloques:
        cuerpo += (f'<div class="cat" style="--c:{cat["color"]}">{e(cat["nombre"])}</div>'
                   f'<div class="grid">{"".join(tarjeta(b, cat["color"]) for b in bs)}</div>')
    filas = sum((len(bs) + 1) // 2 for _, bs in bloques)
    clase = "lista compacta" if filas > 3 else "lista"
    return pagina(f"""<div class="slide {clase}">{confeti(semilla, 26, (40, 180, 1040, 1250))}<div class="capa">
  <div class="cab"><h2><small>Beneficios de cumpleaños</small>Qué te regalan</h2><span class="pg">{n}/{total}</span></div>
  {cuerpo}
  <div class="nota">{CUENTA}<span>Confirma condiciones con cada marca antes de ir</span></div>
</div></div>""")


def html_cierre(fecha: str) -> str:
    return pagina(f"""<div class="slide cierre">{confeti(99, 80, (40, 40, 1040, 1310))}<div class="capa">
  <h1>¡Feliz<br>cumpleaños!</h1>
  <p>Guarda este post y compártelo con quien está de cumpleaños este mes.</p>
  <div class="seg">Síguenos en<br>{CUENTA}</div>
  <div class="aviso">Información tomada de medios y sitios de cada marca al {e(fecha)}. Los beneficios, requisitos y fechas
  pueden cambiar: confírmalos con cada empresa antes de ir. Cuenta no afiliada a ninguna marca.</div>
</div></div>""")


def descripcion(cats: list[dict], total: int) -> str:
    lineas = ["🎂 Beneficios de cumpleaños en Chile",
              "",
              f"{total} marcas que te regalan algo o te hacen descuento por cumplir años. 👉 Desliza, guárdalo y "
              "compártelo con quien está de cumpleaños.",
              ""]
    iconos = {"comida": "🍩", "cines": "🎬", "panoramas": "🎢", "tiendas": "🛍️", "bencina": "⛽"}
    for c in cats:
        lineas.append(f"{iconos.get(c['id'], '🎁')} {c['nombre']}")
        for b in c["beneficios"]:
            lineas.append(f"• {b['marca']}: {b['regalo']} ({CUANDO.get(b['cuando'], b['cuando']).lower()}; {b['requisito'].lower()})")
        lineas.append("")
    lineas += ["📌 Casi todos piden la cédula o estar inscrito en el club o la app de la marca. Los beneficios y "
               "requisitos cambian seguido: confírmalos antes de ir. Cuenta no afiliada a ninguna marca.",
               "",
               "#cumpleaños #feliZcumpleaños #regalosdecumpleaños #gratis #descuentos #descuentoschile #chile #panoramas"]
    t = "\n".join(lineas).replace("#feliZcumpleaños", "#felizcumpleaños")
    return t[:2200]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--salida", default=None)
    a = ap.parse_args()
    data = json.loads(DATA.read_text("utf-8"))
    cats = [c for c in data["categorias"] if c["beneficios"]]
    total = sum(len(c["beneficios"]) for c in cats)
    paginas = paginar(cats)
    total_img = len(paginas) + 2
    htmls = [html_portada(total)]
    for i, bloques in enumerate(paginas, start=2):
        htmls.append(html_lista(bloques, i, total_img, semilla=i * 7))
    fecha = date.fromisoformat(data.get("actualizado", date.today().isoformat())).strftime("%d-%m-%Y")
    htmls.append(html_cierre(fecha))

    out = Path(a.salida or ROOT / "instagram" / "salida" / "cumpleanos")
    from instagram.generar import renderizar
    renderizar(htmls, out)
    (out / "texto.txt").write_text(descripcion(cats, total), "utf-8")
    print(f"{total_img} imágenes en {out}")


if __name__ == "__main__":
    main()

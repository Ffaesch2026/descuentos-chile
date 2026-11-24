"""Lee los beneficios del sitio de Banco BICE desde un computador personal.

El sitio banco.bice.cl bloquea a los servidores (GitHub, nubes) con Cloudflare, pero suele
dejar pasar un navegador visible desde una conexión de casa. Este programa abre el listado
de beneficios, recorre cada beneficio y guarda en data/bice_sitio.json los que NO son de
restaurantes (los restaurantes de BICE ya se leen automáticamente vía tarjetiando.cl).

run.py incorpora data/bice_sitio.json en cada actualización, igual que data/manuales.json.

Uso (lo ejecuta scripts/actualizar-local.ps1):  python -m scraper.bice_sitio
"""
from __future__ import annotations

import json
import re
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

from scraper import common

ROOT = Path(__file__).resolve().parent.parent
SALIDA = ROOT / "data" / "bice_sitio.json"
LISTADO = "https://banco.bice.cl/personas/beneficios"
MAX_BENEFICIOS = 250
_MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre"]


def _esperar_cloudflare(pg, segundos: int = 90) -> None:
    for _ in range(segundos // 3):
        if "momento" not in (pg.title() or "").lower() and "just a moment" not in (pg.title() or "").lower():
            return
        pg.wait_for_timeout(3000)
    raise RuntimeError("El sitio de BICE no dejó pasar el navegador (protección Cloudflare).")


def _vigencia(texto: str) -> str | None:
    t = common.sin_tildes(texto).lower()
    m = re.search(r"hasta(?: el)? (\d{1,2}) de (" + "|".join(_MESES) + r")(?: de)? (\d{4})", t)
    if not m:
        return None
    try:
        return date(int(m.group(3)), _MESES.index(m.group(2)) + 1, int(m.group(1))).isoformat()
    except ValueError:
        return None


def _tarjetas(texto: str) -> list[str]:
    t = common.sin_tildes(texto).lower()
    out = [f"Visa {g.title()} crédito BICE" for g in ("limitless", "infinite", "signature", "platinum")
           if re.search(rf"\b{g}\b", t)]
    if not out:
        out.append("Tarjeta de crédito BICE")
    if re.search(r"debito", t):
        out.append("Tarjeta de débito BICE")
    return out


def _leer_beneficio(pg, url: str) -> dict | None:
    pg.goto(url, wait_until="domcontentloaded", timeout=60000)
    _esperar_cloudflare(pg, 30)
    pg.wait_for_timeout(1200)
    titulo = common.limpiar(pg.title() or "")
    h1 = pg.locator("h1")
    nombre = common.limpiar(h1.first.inner_text()) if h1.count() else titulo
    try:
        texto = common.limpiar(pg.locator("main").first.inner_text())
    except Exception:  # noqa: BLE001
        texto = common.limpiar(pg.inner_text("body"))
    texto = texto[:2500]
    # "Ruta 41 / Miércoles - Banca Joven - Banco BICE" -> "Ruta 41"
    comercio = re.split(r"\s+/\s+|\s+-\s+", nombre or titulo)[0].strip() or nombre
    resumen = " ".join([nombre, texto[:500]])
    pct = common.extraer_pct(resumen)
    litro = common.monto_por_litro(resumen)
    if not pct and not litro and not re.search(r"(?i)2\s?x\s?1|\$\s?\d", resumen):
        return None
    rubro = common.adivinar_rubro(comercio, nombre, texto)
    if rubro == "restaurantes":
        return None  # ya vienen de tarjetiando.cl
    return {
        "comercio": comercio,
        "titulo": (f"${litro} de dcto. por litro en {comercio}" if litro and not pct else nombre)[:160],
        "descripcion": texto[:600],
        "pct": pct,
        "rubro": None if rubro == "otros" else rubro,
        "dias": common.extraer_dias(resumen) or None,
        "tarjetas": _tarjetas(resumen),
        "vigencia_hasta": _vigencia(texto),
        "url": url,
        "fuente": url,
    }


def main() -> int:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        # Navegador visible: Cloudflare bloquea con más frecuencia el modo invisible
        b = p.chromium.launch(headless=False, args=["--start-minimized"])
        pg = b.new_context(locale="es-CL", viewport={"width": 1280, "height": 900}).new_page()
        try:
            pg.goto(LISTADO, wait_until="domcontentloaded", timeout=60000)
            _esperar_cloudflare(pg)
            pg.wait_for_timeout(3000)
            # Cargar todo el listado: desplazarse y pulsar "Ver más" mientras aparezcan beneficios nuevos
            vistos = -1
            for _ in range(40):
                links = pg.eval_on_selector_all(
                    "a[href*='/personas/beneficios/']", "els => els.map(e => e.href.split('#')[0].split('?')[0])")
                if len(set(links)) == vistos:
                    break
                vistos = len(set(links))
                boton = pg.get_by_role("button", name=re.compile(r"(ver|cargar|mostrar) m[aá]s", re.I))
                if boton.count():
                    boton.first.click()
                pg.mouse.wheel(0, 6000)
                pg.wait_for_timeout(1500)
            urls = sorted({u for u in links if re.search(r"/personas/beneficios/[a-z0-9\-]+/?$", u)
                           and not u.rstrip("/").endswith("/beneficios")})[:MAX_BENEFICIOS]
            print(f"BICE: {len(urls)} beneficios en el listado")
            descuentos = []
            for i, u in enumerate(urls, 1):
                try:
                    d = _leer_beneficio(pg, u)
                    if d and (not d["vigencia_hasta"] or d["vigencia_hasta"] >= date.today().isoformat()):
                        descuentos.append(d)
                except Exception as e:  # noqa: BLE001 — un beneficio con problemas no detiene el resto
                    print(f"  [omitido] {u}: {e}")
                time.sleep(0.5)
            print(f"BICE: {len(descuentos)} descuentos fuera de restaurantes")
        finally:
            b.close()
    if not descuentos:
        print("BICE: no se encontraron descuentos; se mantiene el archivo anterior.")
        return 1
    SALIDA.write_text(json.dumps({"generado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                  "descuentos": descuentos}, ensure_ascii=False, indent=1), "utf-8")
    print(f"Guardado en {SALIDA.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

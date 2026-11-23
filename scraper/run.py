"""Ejecuta todos los scrapers y escribe data/descuentos.json.

Uso:
    python -m scraper.run              # todos los bancos
    python -m scraper.run bci tenpo    # solo algunos
    python -m scraper.run --excluir santander,bancoestado
    python -m scraper.run bci --salida /tmp/prueba.json   # prueba sin tocar los datos publicados

Si un banco falla o no devuelve nada, se conservan sus descuentos de la ejecución
anterior y se marca su estado como "error" para que la web lo indique.
"""
from __future__ import annotations

import importlib
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

from scraper.common import es_solo_cuotas

ROOT = Path(__file__).resolve().parent.parent
SALIDA = ROOT / "data" / "descuentos.json"
WEB_DATA = ROOT / "web" / "data" / "descuentos.json"

BANCOS = ["bancochile", "santander", "bci", "bancoestado", "scotiabank", "itau",
          "falabella", "ripley", "cencosud", "security", "tenpo", "mach"]


def main(argv: list[str]) -> int:
    excluir: set[str] = set()
    if "--excluir" in argv:
        i = argv.index("--excluir")
        excluir = {x.strip() for x in argv[i + 1].split(",") if x.strip()}
        argv = argv[:i] + argv[i + 2:]
    salidas = [SALIDA, WEB_DATA]
    if "--salida" in argv:
        i = argv.index("--salida")
        salidas = [Path(argv[i + 1]).resolve()]
        argv = argv[:i] + argv[i + 2:]
    seleccion = [b for b in (argv or BANCOS) if b not in excluir]
    previo = json.loads(SALIDA.read_text("utf-8")) if SALIDA.exists() else {"bancos": {}, "descuentos": []}
    ahora = datetime.now(timezone.utc).isoformat(timespec="seconds")

    bancos = previo.get("bancos", {})
    descuentos = [d for d in previo.get("descuentos", []) if d["banco"] not in seleccion]

    for mod_name in seleccion:
        mod = importlib.import_module(f"scraper.bancos.{mod_name}")
        info = dict(mod.BANCO)
        bid = info["id"]
        try:
            items = mod.scrape()
            # Cuotas sin interés no son descuentos (criterio común a todos los bancos)
            items = [d for d in items if not es_solo_cuotas(d["titulo"])]
            if not items:
                raise RuntimeError("no se encontraron descuentos")
            vistos, unicos = set(), []
            for d in items:
                if d["id"] not in vistos:
                    vistos.add(d["id"])
                    unicos.append(d)
            descuentos.extend(unicos)
            info.update(estado="ok", cantidad=len(unicos), actualizado=ahora, error=None)
            print(f"[ok]    {bid}: {len(unicos)} descuentos")
        except Exception as e:  # noqa: BLE001 — un banco nunca debe botar a los demás
            viejos = [d for d in previo.get("descuentos", []) if d["banco"] == bid]
            descuentos.extend(viejos)
            antes = bancos.get(bid, {})
            info.update(estado="error", cantidad=len(viejos), actualizado=antes.get("actualizado"),
                        error=f"{type(e).__name__}: {e}"[:300])
            print(f"[error] {bid}: {e}")
            traceback.print_exc()
        bancos[bid] = info

    out = {"generado": ahora, "bancos": bancos, "descuentos": descuentos}
    txt = json.dumps(out, ensure_ascii=False, indent=1)
    for p in salidas:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(txt, "utf-8")
    if salidas[0] == SALIDA:
        geo_web = WEB_DATA.parent / "regiones.json"
        geo_web.write_text((ROOT / "scraper" / "regiones.json").read_text("utf-8"), "utf-8")
    con_ubic = sum(1 for d in descuentos if d.get("regiones"))
    print(f"Total: {len(descuentos)} descuentos ({con_ubic} con región) -> {salidas[0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

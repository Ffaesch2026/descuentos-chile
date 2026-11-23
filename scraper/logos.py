"""Descarga el ícono oficial de cada institución desde su sitio web a web/logos/.

Uso: python -m scraper.logos
Genera web/logos/index.json = {"<id>": "<archivo>"}; la web usa un monograma
de color para las instituciones sin logo.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from scraper.common import sesion

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "web" / "logos"
HOMES = {
    "bancochile": "https://portales.bancochile.cl/personas",
    "santander": "https://banco.santander.cl/personas",
    "bci": "https://www.bci.cl/personas",
    "bancoestado": "https://www.bancoestado.cl/",
    "scotiabank": "https://www.scotiabankchile.cl/",
    "itau": "https://www.itau.cl/",
    "falabella": "https://www.bancofalabella.cl/",
    "ripley": "https://www.bancoripley.cl/",
    "cencosud": "https://www.tarjetacencosud.cl/",
    "security": "https://www.bancosecurity.cl/",
    "tenpo": "https://www.tenpo.cl/",
    "mach": "https://www.machbank.cl/",
}
EXT = {"image/png": "png", "image/svg+xml": "svg", "image/jpeg": "jpg", "image/webp": "webp",
       "image/x-icon": "ico", "image/vnd.microsoft.icon": "ico"}


def candidatos(html: str, base: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for rel in ("apple-touch-icon", "apple-touch-icon-precomposed", "icon", "shortcut icon"):
        links = [l for l in soup.find_all("link", href=True) if rel in " ".join(l.get("rel", [])).lower()]
        links.sort(key=lambda l: -max([int(x) for x in re.findall(r"\d+", l.get("sizes", "0"))] or [0]))
        out += [urljoin(base, l["href"]) for l in links]
    out.append(urljoin(base, "/favicon.ico"))
    return out


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    s = sesion()
    index = {}
    for bid, home in HOMES.items():
        try:
            r = s.get(home, timeout=30)
            for url in candidatos(r.text, r.url):
                img = s.get(url, timeout=30)
                ctype = img.headers.get("content-type", "").split(";")[0].strip()
                if img.ok and ctype in EXT and len(img.content) > 200:
                    name = f"{bid}.{EXT[ctype]}"
                    (DEST / name).write_bytes(img.content)
                    index[bid] = name
                    print(f"[ok]    {bid}: {url}")
                    break
            else:
                print(f"[sin logo] {bid}")
        except Exception as e:  # noqa: BLE001
            print(f"[error] {bid}: {e}")
    (DEST / "index.json").write_text(json.dumps(index, indent=1), "utf-8")


if __name__ == "__main__":
    main()

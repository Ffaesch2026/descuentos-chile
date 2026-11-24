"""Publica en Instagram lo que corresponde hoy según instagram/calendario.json.

Por cada publicación: genera el carrusel, convierte las imágenes a JPEG, las sube al
repositorio (carpeta publicaciones/) para que tengan una URL pública, publica el carrusel
y lo anota en instagram/publicados.json para no repetirlo.

Uso:
    python -m instagram.programar                         # lo que toca hoy (solo genera, no publica)
    python -m instagram.programar --publicar              # lo que toca hoy, y publica
    python -m instagram.programar --rubro restaurantes --region RM --publicar   # una publicación puntual
    python -m instagram.programar --rubro restaurantes --region RM --publicar --forzar  # aunque ya se haya publicado este mes
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from PIL import Image

from instagram.publicar import ErrorInstagram, publicar_carrusel

ROOT = Path(__file__).resolve().parent.parent
CALENDARIO = ROOT / "instagram" / "calendario.json"
PUBLICADOS = ROOT / "instagram" / "publicados.json"
CARPETA_PUBLICA = ROOT / "publicaciones"
REPO_RAW = "https://raw.githubusercontent.com/Ffaesch2026/descuentos-chile"
CHILE = ZoneInfo("America/Santiago")


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], check=True, capture_output=True, text=True).stdout.strip()


def subir(rutas: list[Path], mensaje: str) -> str:
    """Hace commit y push de los archivos; devuelve el SHA del commit."""
    git("add", *[str(r) for r in rutas])
    if subprocess.run(["git", "-C", str(ROOT), "diff", "--cached", "--quiet"]).returncode != 0:
        git("commit", "-m", mensaje)
    for intento in range(3):
        try:
            git("pull", "--rebase", "-q", "origin", "main")
            git("push", "-q", "origin", "HEAD:main")
            break
        except subprocess.CalledProcessError as e:
            if intento == 2:
                raise RuntimeError(f"No se pudo subir al repositorio: {e.stderr}")
            time.sleep(5)
    return git("rev-parse", "HEAD")


def esperar_urls(urls: list[str]) -> None:
    for u in urls:
        for _ in range(12):
            if requests.head(u, timeout=20).status_code == 200:
                break
            time.sleep(5)
        else:
            raise RuntimeError(f"La imagen no está disponible en {u}")


def generar(rubro: str, region: str, salida: Path, por_tarjeta: bool = True) -> list[Path]:
    args = [sys.executable, "-m", "instagram.generar", "--rubro", rubro, "--region", region, "--salida", str(salida)]
    if por_tarjeta:
        args.append("--por-tarjeta")
    subprocess.run(args, check=True, cwd=ROOT)
    return sorted(salida.glob("*.png"))


def a_jpeg(pngs: list[Path], destino: Path) -> list[Path]:
    destino.mkdir(parents=True, exist_ok=True)
    for viejo in destino.glob("*.jpg"):
        viejo.unlink()
    out = []
    for p in pngs:
        j = destino / (p.stem + ".jpg")
        Image.open(p).convert("RGB").save(j, "JPEG", quality=92, optimize=True)
        out.append(j)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rubro")
    ap.add_argument("--region")
    ap.add_argument("--publicar", action="store_true", help="publicar en Instagram (si no, solo genera las imágenes)")
    ap.add_argument("--forzar", action="store_true", help="publicar aunque ya se haya publicado este mes")
    ap.add_argument("--hoy", help="fecha a simular, AAAA-MM-DD")
    a = ap.parse_args()

    hoy = datetime.strptime(a.hoy, "%Y-%m-%d") if a.hoy else datetime.now(CHILE)
    import os
    if a.publicar and not os.environ.get("IG_TOKEN", "").strip():
        # Aún no se conecta la cuenta de Instagram: se generan las imágenes para subirlas a mano
        print("Sin IG_TOKEN: se generan las imágenes y el texto para publicarlos a mano (no se publica).")
        a.publicar = False
    if a.rubro or a.region:
        if not (a.rubro and a.region):
            print("Indica --rubro y --region juntos.")
            return 2
        tareas = [{"rubro": a.rubro, "region": a.region}]
    else:
        cal = json.loads(CALENDARIO.read_text("utf-8"))["publicaciones"]
        tareas = [p for p in cal if p.get("activo") and int(p["dia"]) == hoy.day]
    if not tareas:
        print(f"Nada que publicar el {hoy:%d-%m-%Y}.")
        return 0

    publicados = json.loads(PUBLICADOS.read_text("utf-8")) if PUBLICADOS.exists() else {}
    fallas = 0
    for t in tareas:
        clave = f"{hoy:%Y-%m}-{t['rubro']}-{t['region']}"
        if clave in publicados and not a.forzar:
            print(f"[omitido] {clave}: ya publicado ({publicados[clave].get('permalink')})")
            continue
        try:
            print(f"[generando] {clave}")
            tmp = ROOT / "instagram" / "salida" / clave
            pngs = generar(t["rubro"], t["region"], tmp, t.get("por_tarjeta", True))
            texto = (tmp / "texto.txt").read_text("utf-8")
            if not a.publicar:
                print(f"[listo para subir a mano] {len(pngs)} imágenes y texto.txt en {tmp}")
                continue
            jpgs = a_jpeg(pngs, CARPETA_PUBLICA / clave)
            sha = subir(jpgs, f"Imágenes para Instagram: {clave}")
            urls = [f"{REPO_RAW}/{sha}/{j.relative_to(ROOT).as_posix()}" for j in jpgs]
            esperar_urls(urls)
            print(f"[publicando] {clave}: {len(urls)} imágenes")
            res = publicar_carrusel(urls, texto)
            publicados[clave] = {"fecha": datetime.now(CHILE).isoformat(timespec="minutes"), **res}
            PUBLICADOS.write_text(json.dumps(publicados, ensure_ascii=False, indent=1), "utf-8")
            subir([PUBLICADOS], f"Publicado en Instagram: {clave}")
            print(f"[ok] {clave}: {res.get('permalink')}")
        except (ErrorInstagram, RuntimeError, subprocess.CalledProcessError) as e:
            fallas += 1
            print(f"[error] {clave}: {e}")
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())

"""Publica un carrusel en Instagram con la API oficial (Instagram API con inicio de sesión de Instagram).

Necesita la variable de entorno IG_TOKEN: token de acceso de larga duración de la cuenta
(permisos instagram_business_basic e instagram_business_content_publish).

Instagram descarga cada imagen desde una URL pública, así que las imágenes deben estar
publicadas antes (ver instagram/programar.py, que las sube al repositorio).

Uso directo:
    python -m instagram.publicar --urls URL1 URL2 ... --texto texto.txt
    python -m instagram.publicar --cuenta            # muestra la cuenta del token (prueba)
    python -m instagram.publicar --renovar-token     # imprime un token renovado (60 días más)
"""
from __future__ import annotations

import argparse
import os
import sys
import time

import requests

API = os.environ.get("IG_API", "https://graph.instagram.com")
TIMEOUT = 60


class ErrorInstagram(RuntimeError):
    pass


def _token() -> str:
    t = os.environ.get("IG_TOKEN", "").strip()
    if not t:
        raise ErrorInstagram("Falta IG_TOKEN (token de acceso de Instagram).")
    return t


def _req(metodo: str, ruta: str, **params) -> dict:
    params["access_token"] = _token()
    r = requests.request(metodo, f"{API}/{ruta.lstrip('/')}",
                         params=params if metodo == "GET" else None,
                         data=params if metodo != "GET" else None, timeout=TIMEOUT)
    try:
        j = r.json()
    except ValueError:
        raise ErrorInstagram(f"Respuesta inesperada de Instagram ({r.status_code}): {r.text[:200]}")
    if r.status_code >= 400 or "error" in j:
        err = j.get("error", {})
        raise ErrorInstagram(f"Instagram rechazó {ruta}: {err.get('message') or j} (código {err.get('code')})")
    return j


def cuenta() -> dict:
    return _req("GET", "me", fields="user_id,username,account_type")


def renovar_token() -> str:
    """Devuelve un token con 60 días más de vigencia (el actual debe tener al menos 24 h)."""
    r = requests.get(f"{API}/refresh_access_token",
                     params={"grant_type": "ig_refresh_token", "access_token": _token()}, timeout=TIMEOUT)
    j = r.json()
    if "access_token" not in j:
        raise ErrorInstagram(f"No se pudo renovar el token: {j}")
    return j["access_token"]


def _esperar(contenedor: str, intentos: int = 30) -> None:
    for _ in range(intentos):
        estado = _req("GET", contenedor, fields="status_code,status").get("status_code")
        if estado == "FINISHED":
            return
        if estado in ("ERROR", "EXPIRED"):
            raise ErrorInstagram(f"Instagram no pudo procesar {contenedor}: {estado}")
        time.sleep(5)
    raise ErrorInstagram(f"Instagram tardó demasiado en procesar {contenedor}")


def publicar_carrusel(urls: list[str], texto: str) -> dict:
    """Crea un contenedor por imagen, luego el carrusel, y lo publica. Devuelve {id, permalink}."""
    if not 2 <= len(urls) <= 10:
        raise ErrorInstagram(f"Un carrusel necesita entre 2 y 10 imágenes (hay {len(urls)}).")
    uid = cuenta()["user_id"]
    hijos = []
    for u in urls:
        c = _req("POST", f"{uid}/media", image_url=u, is_carousel_item="true")["id"]
        hijos.append(c)
    for c in hijos:
        _esperar(c)
    carrusel = _req("POST", f"{uid}/media", media_type="CAROUSEL", children=",".join(hijos), caption=texto)["id"]
    _esperar(carrusel)
    pub = _req("POST", f"{uid}/media_publish", creation_id=carrusel)["id"]
    info = _req("GET", pub, fields="permalink")
    return {"id": pub, "permalink": info.get("permalink")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--urls", nargs="*")
    ap.add_argument("--texto")
    ap.add_argument("--cuenta", action="store_true")
    ap.add_argument("--renovar-token", action="store_true")
    a = ap.parse_args()
    try:
        if a.cuenta:
            c = cuenta()
            print(f"Cuenta: @{c.get('username')} ({c.get('account_type')}), id {c.get('user_id')}")
        elif a.renovar_token:
            print(renovar_token())
        else:
            texto = open(a.texto, encoding="utf-8").read() if a.texto else ""
            print(publicar_carrusel(a.urls or [], texto))
    except ErrorInstagram as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

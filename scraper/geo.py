"""Reconoce regiones y comunas de Chile en textos de ubicación (direcciones, listas de locales).

Usar solo con textos que SON ubicaciones (ej. "Av. Apoquindo 3000, Las Condes" o
"Región de Valparaíso"), no con descripciones libres: nombres como "Victoria",
"Independencia" o "Primavera" también son palabras comunes.
"""
from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

_DATA = Path(__file__).with_name("regiones.json")

# Nombre de cada región tal como suele escribirse después de "Región de/del/de la".
# Solo se reconocen con la palabra "región" (o su número romano) delante, porque muchas
# calles se llaman igual que una región (Av. Libertador Bernardo O'Higgins, calle Tarapacá...).
_NOMBRE_REGION = {
    "AP": ["arica y parinacota", "arica"], "TA": ["tarapaca"], "AN": ["antofagasta"], "AT": ["atacama"],
    "CO": ["coquimbo"], "VS": ["valparaiso"], "RM": ["metropolitana", "metropolitana de santiago", "santiago"],
    "LI": ["libertador", "o'higgins", "ohiggins", "o higgins", "libertador general bernardo o'higgins", "libertador bernardo o'higgins"],
    "ML": ["maule"], "NB": ["nuble"], "BI": ["biobio", "bio bio", "bio-bio"], "AR": ["la araucania", "araucania"],
    "LR": ["los rios"], "LL": ["los lagos"], "AI": ["aysen", "aisen", "aysen del general carlos ibanez del campo"],
    "MA": ["magallanes", "magallanes y la antartica chilena", "magallanes y antartica chilena"],
}
_ROMANO = {"AP": "xv", "TA": "i", "AN": "ii", "AT": "iii", "CO": "iv", "VS": "v", "LI": "vi", "ML": "vii",
           "NB": "xvi", "BI": "viii", "AR": "ix", "LR": "xiv", "LL": "x", "AI": "xi", "MA": "xii"}
# Comunas que casi siempre aparecen como nombre de calle (Av. Libertador Bernardo O'Higgins)
_COMUNAS_IGNORADAS = {"O’Higgins", "O'Higgins"}
# Formas sin la palabra "región" que no se confunden con calles
_SUELTOS = {"RM": ["region metropolitana", "rm", "r.m."]}


def _norm(s: str) -> str:
    s = "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn")
    s = s.lower().replace("’", "'")
    return re.sub(r"\s+", " ", s)


@lru_cache(maxsize=1)
def _tablas():
    regiones = json.loads(_DATA.read_text("utf-8"))["regiones"]
    comunas = []  # (regex, nombre, region_id) — nombres largos primero ("San Pedro de la Paz" antes que "San Pedro")
    for r in regiones:
        for c in r["comunas"]:
            if c in _COMUNAS_IGNORADAS:
                continue
            comunas.append((c, r["id"]))
    comunas.sort(key=lambda x: -len(x[0]))
    comunas_re = [(re.compile(r"(?<![a-z])" + re.escape(_norm(c)) + r"(?![a-z])"), c, rid) for c, rid in comunas]
    regiones_re = []
    for rid, nombres in _NOMBRE_REGION.items():
        alt = "|".join(re.escape(x) for x in sorted(nombres, key=len, reverse=True))
        regiones_re.append((re.compile(r"(?<![a-z])region (?:de |del |de la )?(?:" + alt + r")(?![a-z])"), rid))
    for rid, rom in _ROMANO.items():
        regiones_re.append((re.compile(r"(?<![a-z])(?:" + rom + r" region|region " + rom + r")(?![a-z])"), rid))
    for rid, xs in _SUELTOS.items():
        for x in xs:
            regiones_re.append((re.compile(r"(?<![a-z.])" + re.escape(x) + r"(?![a-z])"), rid))
    return regiones, comunas_re, regiones_re


def regiones() -> list[dict]:
    return _tablas()[0]


def ubicar(textos: list[str] | None) -> tuple[list[str], list[str]]:
    """Devuelve (ids de región, nombres de comuna) mencionados en los textos de ubicación."""
    _, comunas_re, regiones_re = _tablas()
    regs: set[str] = set()
    coms: set[str] = set()
    for t in textos or []:
        n = _norm(t)
        if not n:
            continue
        resto = n
        # Primero las regiones, y se quitan del texto para que "Región de Valparaíso"
        # no se cuente también como la comuna de Valparaíso
        for rx, rid in regiones_re:
            if rx.search(resto):
                regs.add(rid)
                resto = rx.sub(" ", resto)
        for rx, nombre, rid in comunas_re:
            if rx.search(resto):
                coms.add(nombre)
                regs.add(rid)
                resto = rx.sub(" ", resto)  # evita que "San Pedro" vuelva a coincidir dentro de "San Pedro de la Paz"
    orden = [r["id"] for r in regiones()]
    return sorted(regs, key=orden.index), sorted(coms)


def region_por_nombre(nombre: str) -> str | None:
    """Id de región a partir de un campo estructurado que solo contiene el nombre
    ("Valparaíso", "Región Metropolitana", "VIII", "Biobío")."""
    n = _norm(nombre).strip(" .")
    n = re.sub(r"^(?:region )?(?:de |del |de la )?", "", n)
    for rid, nombres in _NOMBRE_REGION.items():
        if n in nombres or n == _ROMANO.get(rid):
            return rid
    if n in ("rm", "r.m", "metropolitana", "santiago"):
        return "RM"
    return None

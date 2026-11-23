"""Scotiabank Chile — "Beneficios Scotia" (scotiarewards.cl/scclubfront).

scotiabankchile.cl/beneficios redirige a https://www.scotiarewards.cl/scclubfront. Las
páginas de categoría traen los datos incrustados en el HTML (no hace falta navegador):
  * "mundos/descuentos", "mundos/scotiabankweekends", rutas temáticas: llamadas JS
    `descuentos.push(new Descuento(id, nombre, imagen, codigoTarjeta, titulo, subtitulo,
    dias, descripcion, acceder, condiciones, direcciones, tyc, generaCanje, tags))`.
  * "platosycomida/rutagourmet": arreglos JSON `const sitiosSantiago = [...]` y
    `const sitiosRegiones = [...]` con los restaurantes de la Ruta Gourmet.
"""
from __future__ import annotations

import html as htmlmod
import json
import re
import time
from datetime import date, timedelta

from scraper import common, geo

BASE = "https://www.scotiarewards.cl/scclubfront"
BANCO = {"id": "scotiabank", "nombre": "Scotiabank", "sitio": BASE + "/categoria/mundos/descuentos"}

# Páginas con objetos Descuento (en orden; los repetidos se descartan por id).
PAGINAS_DESCUENTOS = [
    "mundos/descuentos",
    "mundos/scotiabankweekends",
    "platosycomida/rutadevinas",
    "platosycomida/Rutadulce",
    "platosycomida/rutajoven",
    "platosycomida/Rutarapida",
    "platosycomida/rutahogar",
    "platosycomida/rutainternacional",
    "mundos/viajes",
]
PAGINAS_SITIOS = ["platosycomida/rutagourmet", "platosycomida/rutainternacional"]

_FOCO_VISA = ["Visa Signature", "Visa Infinite Air", "Visa Infinite Wealth Management",
              "Visa Singular by Scotiabank Signature", "Visa ScotiaSingular",
              "Visa Singular by Scotiabank Infinite"]
# Cómo reconocer cada tarjeta en el texto normalizado de las condiciones.
_CLAVES = {
    "Visa Signature": r"(?<!singular by scotiabank )\bsignature",
    "Visa Infinite Air": r"infinite air",
    "Visa Infinite Wealth Management": r"wealth management",
    "Visa Singular by Scotiabank Signature": r"singular by scotiabank signature",
    "Visa ScotiaSingular": r"scotiasingular",
    "Visa Singular by Scotiabank Infinite": r"singular by scotiabank infinite",
}
# Códigos de tarjeta del sitio (ver `filtrosTarjetas` en el JS de la página).
_CODIGOS = {
    "todas": ["Tarjetas de Crédito Scotiabank", "Tarjeta de Débito Scotiabank"],
    "credito": ["Tarjetas de Crédito Scotiabank"],
    "creditovisa": ["Tarjetas de Crédito Visa Scotiabank"],
    "foco": _FOCO_VISA + ["Mastercard Black"],
    "focovisa": _FOCO_VISA,
}

# Tags del sitio -> rubro
_TAG_RUBRO = {
    "transporte": "viajes", "viajes": "viajes", "salud y belleza": "farmacias",
    "alimentos y bebidas": "restaurantes", "entretencion": "entretencion", "ninos": "entretencion",
    "hogar": "vestuario", "mascotas": "vestuario", "deportes y wellness": "farmacias",
    "vino, comida y mas": "restaurantes", "supermercado": "supermercados", "regalos": "vestuario",
    "e-commerce": "vestuario",
}
_PAGINA_RUBRO = {"rutadevinas": "restaurantes", "Rutadulce": "restaurantes",
                 "Rutarapida": "restaurantes", "rutainternacional": "restaurantes",
                 "rutagourmet": "restaurantes", "rutahogar": "vestuario", "viajes": "viajes"}

_MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre"]
_MES = "(" + "|".join(_MESES) + ")"


def _norm(s: str) -> str:
    return common.sin_tildes(common.limpiar(s)).lower()


def _texto(h: str | None) -> str:
    """HTML (con entidades) -> texto plano."""
    t = re.sub(r"<\s*(br|/p|/li)\s*/?>", ". ", h or "", flags=re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = htmlmod.unescape(t).replace("\xa0", " ")
    t = re.sub(r"\s*\|\s*", " ", t)
    t = re.sub(r"(\.\s*){2,}", ". ", t)
    return common.limpiar(t)


def _vigencia(texto: str) -> tuple[str | None, str | None]:
    t = _norm(texto)
    m = re.search(
        r"(\d{1,2})\s*(?:de\s+)?" + _MES + r"?\s*(?:de\s+|del\s+)?(\d{4})?\s*(?:al|hasta(?:\s+el)?|y\s+el)\s+"
        r"(\d{1,2})\s*(?:de\s+)?" + _MES + r"\s*(?:de\s+|del\s+)?(\d{4})", t)
    if m:
        d1, mes1, a1, d2, mes2, a2 = m.groups()
        i1, i2 = _MESES.index(mes1 or mes2) + 1, _MESES.index(mes2) + 1
        a1 = a1 or (str(int(a2) - 1) if i1 > i2 else a2)
        return f"{a1}-{i1:02d}-{int(d1):02d}", f"{a2}-{i2:02d}-{int(d2):02d}"
    m = re.search(r"(?:todos los \w+ |durante el mes )?de\s+" + _MES + r"\s+(?:de|del)\s+(\d{4})", t)
    if m and not re.search(r"hasta\s+el\s+\d", t):
        mes, anio = _MESES.index(m.group(1)) + 1, int(m.group(2))
        fin = (date(anio + (mes == 12), mes % 12 + 1, 1) - timedelta(days=1)).day
        return f"{anio}-{mes:02d}-01", f"{anio}-{mes:02d}-{fin:02d}"
    m = re.search(r"hasta\s+el\s+(\d{1,2})\s*(?:de\s+)?" + _MES + r"\s*(?:de\s+|del\s+)?(\d{4})", t)
    if m:
        return None, f"{m.group(3)}-{_MESES.index(m.group(2)) + 1:02d}-{int(m.group(1)):02d}"
    return None, None


def _tope(texto: str) -> str | None:
    m = re.search(r"(tope[^.$]{0,60}(?:\$|USD|US\$)\s?[\d.]+(?:\s+(?:por|al|mensual|diario)[^.]{0,50})?)", texto, re.I)
    return common.limpiar(m.group(1)).rstrip(".") if m else None


def _modalidad(texto: str) -> str | None:
    t = _norm(texto)
    m = []
    if re.search(r"presencial|en caja|tienda fisica|tiendas fisicas|en el local|en local|restaurante|en sucursal", t):
        m.append("Presencial")
    if re.search(r"online|sitio web|www\.|\.cl\b|\.com\b|codigo de descuento|cupon|e-commerce", t):
        m.append("Online")
    if re.search(r"\bapp\b|aplicacion", t):
        m.append("App")
    return m[0] if len(m) == 1 else None


def _tarjetas_texto(texto: str) -> list[str]:
    """Tarjetas mencionadas en la frase 'Pagando con tus Tarjetas ...' (sin la de exclusiones)."""
    t = texto.split("Se excluyen")[0]
    m = re.search(r"(?:pagando|pagar|pago)\s+(?:el total del consumo\s+)?con\s+(?:tus?\s+)?(Tarjetas?[^.]{0,250})", t, re.I)
    frase = m.group(1) if m else t
    n = _norm(frase)
    out = []
    if "credito" in n:
        if "visa" in n and any(k in n for k in ["signature", "infinite", "singular", "wealth"]):
            for nombre in _FOCO_VISA:
                clave = _CLAVES[nombre]
                if re.search(clave, n):
                    out.append(nombre)
            if "black" in n:
                out.append("Mastercard Black")
            if not out:
                out.append("Tarjetas de Crédito Visa Scotiabank")
        elif "visa" in n and "mastercard" not in n:
            out.append("Tarjetas de Crédito Visa Scotiabank")
        else:
            out.append("Tarjetas de Crédito Scotiabank")
    if "debito" in n:
        out.append("Tarjeta de Débito Scotiabank")
    return out


def _args_js(bloque: str) -> list | None:
    """Convierte la lista de argumentos de `new Descuento(...)` a una lista Python."""
    bloque = re.sub(r",\s*tags_\d+\s*$", ", null", bloque.strip())
    try:
        return json.loads("[" + bloque + "]")
    except ValueError:
        return None


def _descuentos_js(h: str) -> list[dict]:
    out = []
    for m in re.finditer(r"descuentos\.push\(new Descuento\((.*?)\)\);", h, re.S):
        a = _args_js(m.group(1))
        if not a or len(a) < 13:
            continue
        # tags definidos justo antes: new Tag(id, "Nombre", "icono") en tags_<id>
        tags = re.findall(r'var tag_%s_\d+ = new Tag\(\s*\d+,\s*"([^"]*)"' % a[0], h)
        out.append({
            "id": a[0], "codigo_interno": a[1], "imagen": a[2], "codigo": a[3], "titulo": a[4],
            "subtitulo": a[5], "dias": a[6], "descripcion": a[7], "acceder": a[8],
            "condiciones": a[9], "direcciones": a[10], "tyc": a[11],
            "tags": [json.loads(f'"{t}"') for t in tags],
        })
    return out


def _sitios_js(h: str) -> list[dict]:
    out = []
    for m in re.finditer(r"\n\s*const (sitios\w+) = (\[.*?\]);(?=\s*\n)", h):
        if m.group(1) == "sitiosTotales":
            continue
        try:
            out.extend(json.loads(m.group(2)))
        except ValueError:
            pass
    return out


# Números de región chilenos (campo id_region de la Ruta Gourmet) -> id
_REGION_NUM = {1: "TA", 2: "AN", 3: "AT", 4: "CO", 5: "VS", 6: "LI", 7: "ML", 8: "BI", 9: "AR",
               10: "LL", 11: "AI", 12: "MA", 13: "RM", 14: "LR", 15: "AP", 16: "NB"}


def _lineas_direccion(h: str | None) -> list[str]:
    """Campo `direcciones` (HTML) -> líneas que son direcciones. Se quitan URLs y las
    líneas que describen cobertura nacional o excepciones ("todos los locales del país")."""
    out = []
    for l in re.split(r"<\s*/?\s*(?:br|p|li)\b[^>]*>|\|", h or "", flags=re.I):
        l = htmlmod.unescape(re.sub(r"<[^>]+>", " ", l)).replace("\xa0", " ")
        l = re.sub(r"\S*(?:https?://|www\.|@)\S*|\S+\.(?:cl|com)\S*", " ", l)
        l = common.limpiar(l).strip(" -.•")
        if l and not re.search(r"pais|salvo|excepto|todo chile|todos los locales|aplica en", _norm(l)):
            out.append(l)
    return out


def _ubic_sitio(direccion: str | None) -> list[str]:
    """Dirección(es) de la Ruta Gourmet ("Calle 123, Comuna| Otra 45, Comuna") -> comunas.
    Solo el último tramo tras una coma: muchas calles se llaman como comunas
    ("Padre Luis de Valdivia 327, Santiago", "Camino a San Miguel 4943, Talca")."""
    out = []
    for d in (direccion or "").split("|"):
        partes = [x for x in d.split(",") if x.strip(" .")]
        if len(partes) > 1:
            out.append(partes[-1])
    return out


def _es_descuento(sub: str) -> bool:
    n = _norm(sub)
    return "%" in n or "dcto" in n or "descuento" in n or "devolucion" in n


def _imagen(src: str | None) -> str | None:
    if not src:
        return None
    if src.startswith("http"):
        return src
    if src.startswith("/scclubfront"):
        return "https://www.scotiarewards.cl" + src
    return BASE + src


def _rubro(comercio: str, tags: list[str], pagina: str) -> str | None:
    g = common.adivinar_rubro(comercio)
    if g != "otros":
        return g
    for t in tags:
        r = _TAG_RUBRO.get(_norm(t))
        if r:
            return r
    return _PAGINA_RUBRO.get(pagina.split("/")[-1])


_EXTRANJERO = re.compile(r"(?<![a-z])(lima|buenos aires|montevideo|punta del este|mendoza|cusco|arequipa|miraflores|peru|argentina|uruguay)(?![a-z])")


def scrape() -> list[dict]:
    s = common.sesion()
    out: list[dict] = []
    ids: set = set()
    errores = []
    for pagina in PAGINAS_DESCUENTOS + [p for p in PAGINAS_SITIOS if p not in PAGINAS_DESCUENTOS]:
        url = f"{BASE}/categoria/{pagina}"
        try:
            r = s.get(url, timeout=common.TIMEOUT)
            r.raise_for_status()
        except Exception as e:  # noqa: BLE001
            errores.append(f"{pagina}: {e}")
            continue
        h = r.text
        for d in _descuentos_js(h):
            if d["id"] in ids or not _es_descuento(d["subtitulo"]):
                continue
            ids.add(d["id"])
            desc = _texto(d["descripcion"])
            acceder = _texto(d["acceder"])
            cond = _texto(d["condiciones"])
            tyc = _texto(d["tyc"])
            dirs = _texto(d["direcciones"])
            dias_txt = _texto(d["dias"])
            comercio = _texto(d["titulo"])
            sub = _texto(d["subtitulo"])
            tarjetas = _CODIGOS.get(_norm(d["codigo"])) or _tarjetas_texto(" ".join([tyc, cond, desc, acceder]))
            desde, hasta = _vigencia(" ".join([cond, tyc, desc]))
            dias = common.extraer_dias(dias_txt)
            out.append(common.nuevo_descuento(
                banco=BANCO["id"],
                comercio=comercio,
                titulo=f"{sub} en {comercio} — {dias_txt}",
                descripcion=" ".join(x for x in [desc, acceder, cond, ("Dirección: " + dirs) if dirs else ""] if x),
                pct=common.extraer_pct(sub),
                rubro=_rubro(comercio, d["tags"], pagina),
                dias=dias,
                tarjetas=tarjetas,
                tope=_tope(" ".join([cond, tyc])),
                modalidad=_modalidad(" ".join([acceder, cond, dirs])),
                vigencia_desde=desde,
                vigencia_hasta=hasta,
                url=url,
                imagen=_imagen(d["imagen"]),
                ubicaciones=_lineas_direccion(d["direcciones"]),
            ))
        for x in _sitios_js(h):
            key = ("sitio", x.get("id_sitio") or x.get("nombre"))
            if key in ids:
                continue
            ids.add(key)
            texto = _texto(x.get("descripcion"))
            emision = re.search(r"emitidas? en ([^.]{0,40})", texto)
            if emision and "chile" not in _norm(emision.group(1)):
                continue  # beneficio para tarjetas emitidas en otros países
            oferta = common.limpiar(x.get("telefono"))  # el sitio guarda el descuento en "telefono"
            cuando = common.limpiar(x.get("especialidad"))
            nombre = common.limpiar(x.get("nombre"))
            desde, hasta = _vigencia(texto)
            out.append(common.nuevo_descuento(
                banco=BANCO["id"],
                comercio=nombre,
                titulo=f"{oferta} en {nombre} — {cuando}",
                descripcion=" ".join(x for x in [f"Dirección: {common.limpiar(x.get('direccion'))}.", texto] if x),
                pct=common.extraer_pct(oferta),
                rubro="restaurantes",
                dias=common.extraer_dias(cuando) or common.extraer_dias(texto.split("Promoción")[0]),
                tarjetas=_tarjetas_texto(texto),
                tope=_tope(texto),
                modalidad="Presencial" if "presencial" in _norm(texto) else None,
                vigencia_desde=desde,
                vigencia_hasta=hasta,
                url=url,
                imagen=_imagen(x.get("imagen")),
                ubicaciones=_ubic_sitio(x.get("direccion")),
                # id_region es el número de región chileno solo en la Ruta Gourmet
                # (en la ruta internacional identifica otra cosa: Lima y Las Condes comparten 1).
                regiones=[_REGION_NUM[x["id_region"]]] if pagina.endswith("rutagourmet")
                and x.get("id_region") in _REGION_NUM else None,
            ))
        time.sleep(0.5)
    if not out:
        raise RuntimeError("Scotiabank: no se encontraron descuentos. " + "; ".join(errores))
    # Restaurantes en el extranjero (Lima, Buenos Aires, Montevideo…): no son descuentos en Chile
    def _extranjero(o: dict) -> bool:
        m = re.search(r"Dirección: (.*)", o["descripcion"])
        return not o["regiones"] and bool(m) and bool(_EXTRANJERO.search(_norm(m.group(1)[:300])))
    out = [o for o in out if not _extranjero(o)]
    return out

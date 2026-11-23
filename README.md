# Mapa de Descuentos Chile

Página web que reúne en un solo panel los descuentos del mes con tarjetas de **crédito, débito y prepago** de los bancos e instituciones de Chile:

Banco de Chile · Santander · BCI · BancoEstado · Scotiabank · Itaú · Banco Falabella · Banco Ripley · Tarjeta Cencosud · Banco Security · Tenpo · MACH

## Qué hace la web

- **Vista por institución**: cada banco con su logo, sus descuentos ordenados de mayor a menor %.
- **Vista semana**: bancos × días, para ver qué conviene cada día.
- **Zoom** en 5 niveles (botones −/+, Ctrl + rueda del mouse o teclas +/−), desde un mapa solo con porcentajes hasta el detalle completo.
- **Filtros combinables** (todos de selección múltiple): día de la semana, rubro, rango de % de descuento, tipo de tarjeta (crédito / débito / prepago), tarjetas específicas por banco y buscador por comercio.
- Las tarjetas elegidas y el nivel de zoom se recuerdan en el navegador.
- Al hacer clic en un descuento se ve el detalle y el enlace a la página oficial del banco.

## Cómo se obtienen los datos

`scraper/` contiene un módulo por institución (`scraper/bancos/<banco>.py`) que lee los beneficios publicados en el sitio oficial. Cuando el sitio tiene una API interna se usa esa; si el sitio exige un navegador real, se usa Playwright. Todos normalizan al mismo formato con `scraper/common.py`.

```bash
pip install -r requirements.txt
python -m playwright install chromium
python -m scraper.run            # todos los bancos
python -m scraper.run tenpo bci  # solo algunos
python -m scraper.logos          # descarga los íconos de cada banco
```

Si un banco falla, se conservan sus datos de la ejecución anterior y la web avisa cuál no se pudo actualizar.

Resultado: `data/descuentos.json` (copiado en `web/data/` para la web). Cada descuento tiene: banco, comercio, título, descripción, `pct`, `rubro`, `dias` (0 = lunes … 6 = domingo), `tarjetas`, `tipos`, tope, modalidad, vigencia y `url` de la fuente.

### Criterios

- Se incluyen descuentos en comercios (porcentaje, 2x1, montos fijos). Se excluyen cuotas sin interés, tasas de crédito, sorteos, seguros y canjes de puntos.
- No se inventan datos: si el banco no indica días, tope o vigencia, el campo queda vacío y la web muestra "ver condiciones".
- El rubro se toma del banco cuando lo publica; si no, se deduce por palabras clave.

## Ver la web en tu computador

```bash
cd web && python -m http.server 8000
```

y abrir http://localhost:8000

## Actualización y publicación automática

`.github/workflows/actualizar.yml` corre los lunes, los jueves y el día 1 de cada mes (también se puede lanzar a mano en **Actions → Actualizar descuentos → Run workflow**). Lee los bancos y guarda los datos nuevos en el repositorio.

La web se publica en **Vercel**: `vercel.json` le indica que es un sitio estático y que publique la carpeta `web/`. Cada commit en `main` (incluidos los de la actualización automática) genera una nueva publicación.

### Santander y BancoEstado (desde un computador con Windows)

Estos dos bancos bloquean a los servidores de GitHub, así que la actualización automática de GitHub los omite y se leen desde un computador personal:

1. Instalar [Python](https://www.python.org/downloads/) (marcar *Add python.exe to PATH*) y [Git for Windows](https://git-scm.com/download/win).
2. Clonar el repositorio: `git clone https://github.com/Ffaesch2026/descuentos-chile.git`
3. En esa carpeta, ejecutar una vez: `powershell -ExecutionPolicy Bypass -File scripts\instalar-tarea.ps1`

Eso instala lo necesario, programa una tarea de Windows (lunes y jueves 9:00 y el día 1 de cada mes; si el computador está apagado, corre al encenderlo) y hace una primera ejecución. El registro queda en `scripts\actualizar-local.log`. No edites archivos en esa copia del repositorio: el script la deja igual a GitHub antes de cada ejecución.

## Agregar o arreglar un banco

1. Crear o editar `scraper/bancos/<id>.py` con `BANCO = {...}` y `def scrape() -> list[dict]` que devuelva descuentos creados con `common.nuevo_descuento(...)`.
2. Agregar el id a `BANCOS` en `scraper/run.py` y a la lista `BANKS` de `web/app.js` (nombre, monograma y color).
3. Probar con `python -m scraper.run <id>`.

Este proyecto no está afiliado a ningún banco. Los datos provienen de los sitios públicos de cada institución; revisa siempre las condiciones oficiales.

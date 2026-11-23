"use strict";
const DAYS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];
const MONTHS = ["Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"];
const CATS = {
  restaurantes: ["Restaurantes", "--r-food"],
  supermercados: ["Supermercados", "--r-super"],
  combustible: ["Combustible", "--r-fuel"],
  farmacias: ["Salud y farmacias", "--r-pharma"],
  viajes: ["Viajes y transporte", "--r-travel"],
  entretencion: ["Entretención", "--r-fun"],
  vestuario: ["Vestuario y hogar", "--r-retail"],
  delivery: ["Delivery", "--r-deli"],
  otros: ["Otros", "--r-other"],
};
const PCTS = [["Hasta 15%", 1, 15], ["16–25%", 16, 25], ["26–40%", 26, 40], ["41–50%", 41, 50], ["Más de 50%", 51, 100], ["Sin % (2x1, cuotas…)", null, null]];
const TYPES = { credito: "Crédito", debito: "Débito", prepago: "Prepago" };
// Orden de presentación, monograma y color de respaldo cuando no hay logo
const BANKS = [
  ["bancochile", "Banco de Chile", "BCh", "#1b3f8b"],
  ["santander", "Santander", "S", "#c8102e"],
  ["bci", "BCI", "bci", "#2f2f2f"],
  ["bancoestado", "BancoEstado", "BE", "#e05a00"],
  ["scotiabank", "Scotiabank", "Sc", "#b01d2b"],
  ["itau", "Itaú", "it", "#ec6608"],
  ["falabella", "Banco Falabella", "CMR", "#3a8f2a"],
  ["ripley", "Banco Ripley", "R", "#5b2a86"],
  ["cencosud", "Tarjeta Cencosud", "Cn", "#0068b3"],
  ["security", "Banco Security", "Se", "#6d1f6b"],
  ["tenpo", "Tenpo", "T", "#00a88a"],
  ["mach", "MACH", "M", "#6c2bd9"],
].map(([id, name, mono, c]) => ({ id, name, mono, c }));
let LOGOS = {}; // id -> archivo, desde logos/index.json

const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const key = (b, c) => b + "|" + c;
const todayIdx = (new Date().getDay() + 6) % 7;

let DATA = [], META = {};
const st = { days: new Set(), cats: new Set(), pcts: new Set(), types: new Set(), cards: new Set(), q: "", view: "inst", z: 3, collapsed: new Set() };
try { const z = +localStorage.getItem("dz"); if (z >= 1 && z <= 5) st.z = z; } catch (e) {}
try { JSON.parse(localStorage.getItem("cards") || "[]").forEach((k) => st.cards.add(k)); } catch (e) {}
const saveCards = () => { try { localStorage.setItem("cards", JSON.stringify([...st.cards])); } catch (e) {} };

function bank(id) { return BANKS.find((b) => b.id === id) || { id, name: META.bancos?.[id]?.nombre || id, mono: id.slice(0, 2), c: "#555" }; }
function logo(b, sm) {
  if (LOGOS[b.id]) return `<span class="logo hasimg${sm ? " sm" : ""}"><img src="logos/${esc(LOGOS[b.id])}" alt="" loading="lazy"></span>`;
  return `<span class="logo${sm ? " sm" : ""}" style="--bc:${b.c}">${esc(b.mono)}</span>`;
}
const catVar = (d) => `var(${(CATS[d.rubro] || CATS.otros)[1]})`;
const money = (t) => t || "Sin información";

function cardsByBank() {
  const m = new Map();
  for (const d of DATA) {
    if (!m.has(d.banco)) m.set(d.banco, new Set());
    d.tarjetas.forEach((t) => m.get(d.banco).add(t));
  }
  return m;
}

function chips() {
  $("#dayChips").innerHTML = DAYS.map((d, i) => `<button class="chip${i === todayIdx ? " today" : ""}" data-day="${i}" aria-pressed="${st.days.has(i)}">${d}${i === todayIdx ? " · hoy" : ""}</button>`).join("");
  const usedCats = new Set(DATA.map((d) => d.rubro));
  $("#catChips").innerHTML = Object.entries(CATS).filter(([k]) => usedCats.has(k)).map(([k, [n, v]]) => `<button class="chip" data-cat="${k}" aria-pressed="${st.cats.has(k)}" style="--c:var(${v})"><span class="dot"></span>${n}</button>`).join("");
  $("#pctChips").innerHTML = PCTS.map(([n, lo, hi], i) => {
    const c = DATA.filter((d) => inPct(d, i)).length;
    return c ? `<button class="chip" data-pct="${i}" aria-pressed="${st.pcts.has(i)}">${n} <span class="meta">(${c})</span></button>` : "";
  }).join("");
  $("#typeChips").innerHTML = Object.entries(TYPES).map(([k, n]) => `<button class="chip" data-type="${k}" aria-pressed="${st.types.has(k)}">${n}</button>`).join("");
}
function inPct(d, i) { const [, lo, hi] = PCTS[i]; return lo === null ? d.pct == null : d.pct != null && d.pct >= lo && d.pct <= hi; }

function cardPop() {
  const m = cardsByBank();
  $("#cardPop").innerHTML = BANKS.filter((b) => m.has(b.id) && m.get(b.id).size).map((b) => {
    const cards = [...m.get(b.id)].sort();
    const all = cards.every((c) => st.cards.has(key(b.id, c)));
    return `<div class="bank"><div class="bankhead">${logo(b, true)}${esc(b.name)}<button data-all="${b.id}">${all ? "Quitar" : "Todas"}</button></div>` +
      cards.map((c) => `<label><input type="checkbox" data-card="${esc(key(b.id, c))}" ${st.cards.has(key(b.id, c)) ? "checked" : ""}>${esc(c)}</label>`).join("") + `</div>`;
  }).join("") || `<p class="meta">Aún no hay tarjetas cargadas.</p>`;
  $("#cardCount").textContent = st.cards.size || "Todas";
  $("#selChips").innerHTML = [...st.cards].map((k) => { const [b, c] = k.split("|"); return `<button class="selchip" data-rm="${esc(k)}" aria-label="Quitar ${esc(bank(b).name + " " + c)}">${esc(bank(b).name)} · ${esc(c)}</button>`; }).join("");
}

function filtered() {
  const q = st.q.trim().toLowerCase();
  return DATA.filter((d) => (!st.days.size || d.dias.some((x) => st.days.has(x)))
    && (!st.cats.size || st.cats.has(d.rubro))
    && (!st.pcts.size || [...st.pcts].some((i) => inPct(d, i)))
    && (!st.types.size || d.tipos.some((t) => st.types.has(t)))
    && (!st.cards.size || d.tarjetas.some((c) => st.cards.has(key(d.banco, c))))
    && (!q || (d.comercio + " " + d.titulo).toLowerCase().includes(q)));
}

const daysHtml = (d) => d.dias.length
  ? `<div class="days">${DAYS.map((x, i) => `<i class="${d.dias.includes(i) ? "on" : ""}" title="${x}">${x[0]}</i>`).join("")}</div>`
  : `<div class="meta">Días: ver condiciones</div>`;
const pctHtml = (d) => d.pct != null ? `<span class="pct">${d.pct}%</span>` : `<span class="pct nopct">Beneficio</span>`;

function tile(d) {
  return `<button class="tile" data-id="${esc(d.id)}" style="--rc:${catVar(d)}" title="${esc(d.comercio)}${d.pct != null ? " · " + d.pct + "%" : ""}">
  ${pctHtml(d)}<span class="merchant">${esc(d.comercio)}</span>${daysHtml(d)}
  <span class="meta">${(CATS[d.rubro] || CATS.otros)[0]}${d.tope ? " · tope " + esc(d.tope) : ""}</span>
  <span class="cardtags">${d.tarjetas.slice(0, 6).map((c) => `<span>${esc(c)}</span>`).join("")}</span></button>`;
}
const byPct = (a, b) => (b.pct ?? -1) - (a.pct ?? -1);

function render() {
  const list = filtered();
  $("#sCount").textContent = list.length;
  $("#sBanks").textContent = new Set(list.map((d) => d.banco)).size;
  const p = list.map((d) => d.pct).filter((x) => x != null);
  $("#sMax").textContent = (p.length ? Math.max(...p) : 0) + "%";
  const v = $("#view");
  v.dataset.zl = st.z;
  document.documentElement.style.setProperty("--z", [0, 1.3, 2.2, 3, 3.8, 4.8][st.z]);
  $("#zLabel").textContent = ["", "Mapa", "Compacto", "Normal", "Amplio", "Detalle"][st.z];
  $("#zoomR").value = st.z;
  if (!list.length) { v.innerHTML = `<div class="empty">No hay descuentos con estos filtros. Prueba quitando un día, un rubro o un rango de %.</div>`; return; }
  const ids = [...new Set([...BANKS.map((b) => b.id), ...list.map((d) => d.banco)])];
  if (st.view === "inst") {
    v.innerHTML = ids.map((id) => {
      const items = list.filter((d) => d.banco === id).sort(byPct);
      if (!items.length) return "";
      const b = bank(id), col = st.collapsed.has(id), m = META.bancos?.[id];
      const err = m?.estado === "error" ? `<span class="badge" title="${esc(m.error || "")}">datos de la actualización anterior</span>` : "";
      const top = items.find((d) => d.pct != null);
      return `<section class="group" data-collapsed="${col}"><button class="ghead" data-toggle="${id}" aria-expanded="${!col}">
      ${logo(b)}<span class="gname">${esc(b.name)} ${err}<small>${[...new Set(items.flatMap((d) => d.tipos))].map((t) => TYPES[t]).join(" · ")}</small></span>
      <span class="gmeta"><span><b>${items.length}</b> desc.</span>${top ? `<span class="hidesm">hasta <b>${top.pct}%</b></span>` : ""}<span class="caret">▼</span></span></button>
      <div class="tiles">${items.map(tile).join("")}</div></section>`;
    }).join("");
  } else {
    const cap = [0, 2, 3, 4, 6, 999][st.z];
    v.innerHTML = `<div class="matrixwrap"><table class="matrix"><thead><tr><th>Institución</th>${DAYS.map((d, i) => `<th class="${i === todayIdx ? "today" : ""}">${d}${i === todayIdx ? " · hoy" : ""}</th>`).join("")}</tr></thead><tbody>` +
      ids.map((id) => {
        const items = list.filter((d) => d.banco === id);
        if (!items.length) return "";
        const b = bank(id);
        return `<tr><th><div class="bcell">${logo(b, true)}${esc(b.name)}</div></th>` + DAYS.map((_, i) => {
          const day = items.filter((d) => d.dias.includes(i)).sort(byPct);
          return `<td>${day.slice(0, cap).map((d) => `<button class="mpill" data-id="${esc(d.id)}" style="--rc:${catVar(d)}"><b>${d.pct != null ? d.pct + "%" : "★"}</b><span>${esc(d.comercio)}</span></button>`).join("")}${day.length > cap ? `<div class="more">+${day.length - cap} más</div>` : ""}</td>`;
        }).join("") + `</tr>`;
      }).join("") + `</tbody></table></div><p class="meta">Los descuentos sin días específicos no aparecen en esta vista.</p>`;
  }
}

function fmtDate(s) { if (!s) return null; const [y, m, d] = s.split("-"); return `${+d} de ${MONTHS[+m - 1].toLowerCase()} ${y}`; }
function openDetail(id) {
  const d = DATA.find((x) => x.id === id); if (!d) return;
  const b = bank(d.banco), dr = $("#drawer");
  dr.style.setProperty("--rc", catVar(d));
  const vig = d.vigencia_desde || d.vigencia_hasta ? `${fmtDate(d.vigencia_desde) || "…"} al ${fmtDate(d.vigencia_hasta) || "…"}` : "Ver condiciones";
  dr.innerHTML = `<button class="close" id="closeD">Cerrar</button>
  <div style="display:flex;gap:10px;align-items:center">${logo(b)}<strong>${esc(b.name)}</strong></div>
  <div class="big">${d.pct != null ? d.pct + "%" : "Beneficio"}</div><h2>${esc(d.comercio)}</h2>
  ${d.titulo && d.titulo !== d.comercio ? `<p><strong>${esc(d.titulo)}</strong></p>` : ""}${daysHtml(d)}
  ${d.descripcion ? `<p class="desc">${esc(d.descripcion)}</p>` : ""}
  <dl><dt>Rubro</dt><dd>${(CATS[d.rubro] || CATS.otros)[0]}</dd>
  <dt>Tarjetas</dt><dd>${d.tarjetas.length ? d.tarjetas.map(esc).join(", ") : "Ver condiciones"}</dd>
  <dt>Tipo</dt><dd>${d.tipos.map((t) => TYPES[t]).join(", ")}</dd>
  <dt>Tope</dt><dd>${esc(money(d.tope))}</dd>
  <dt>Modalidad</dt><dd>${esc(d.modalidad || "Sin información")}</dd>
  <dt>Vigencia</dt><dd>${esc(vig)}</dd>
  ${d.url ? `<dt>Fuente</dt><dd><a href="${esc(d.url)}" target="_blank" rel="noopener">Ver en el sitio de ${esc(b.name)}</a></dd>` : ""}</dl>
  <p class="desc">Revisa siempre las condiciones en el sitio oficial antes de usar el descuento.</p>`;
  dr.hidden = false; $("#scrim").hidden = false; $("#closeD").focus();
}
function closeDetail() { $("#drawer").hidden = true; $("#scrim").hidden = true; }
function setZ(z) { st.z = Math.max(1, Math.min(5, z)); try { localStorage.setItem("dz", st.z); } catch (e) {} render(); }
function toggle(set, v) { set.has(v) ? set.delete(v) : set.add(v); }

document.addEventListener("click", (e) => {
  const pop = $("#cardPop");
  if (!pop.hidden && !e.target.closest(".cardpick")) { pop.hidden = true; $("#cardBtn").setAttribute("aria-expanded", "false"); }
  const t = e.target.closest("button,input"); if (!t) return;
  const ds = t.dataset;
  if (ds.day) { toggle(st.days, +ds.day); chips(); render(); }
  else if (ds.cat) { toggle(st.cats, ds.cat); chips(); render(); }
  else if (ds.pct) { toggle(st.pcts, +ds.pct); chips(); render(); }
  else if (ds.type) { toggle(st.types, ds.type); chips(); render(); }
  else if (t.id === "cardBtn") { pop.hidden = !pop.hidden; t.setAttribute("aria-expanded", !pop.hidden); }
  else if (ds.card) { t.checked ? st.cards.add(ds.card) : st.cards.delete(ds.card); saveCards(); cardPop(); render(); }
  else if (ds.all) {
    const cards = [...(cardsByBank().get(ds.all) || [])];
    const all = cards.every((c) => st.cards.has(key(ds.all, c)));
    cards.forEach((c) => all ? st.cards.delete(key(ds.all, c)) : st.cards.add(key(ds.all, c)));
    saveCards(); cardPop(); render();
  }
  else if (ds.rm) { st.cards.delete(ds.rm); saveCards(); cardPop(); render(); }
  else if (ds.toggle) { toggle(st.collapsed, ds.toggle); render(); }
  else if (ds.id) openDetail(ds.id);
  else if (t.id === "closeD") closeDetail();
  else if (t.id === "clearAll") { ["days", "cats", "pcts", "types", "cards"].forEach((k) => st[k].clear()); st.q = ""; $("#q").value = ""; saveCards(); chips(); cardPop(); render(); }
  else if (t.id === "vInst" || t.id === "vWeek") {
    st.view = t.id === "vInst" ? "inst" : "week";
    $("#vInst").setAttribute("aria-pressed", st.view === "inst"); $("#vWeek").setAttribute("aria-pressed", st.view === "week"); render();
  }
  else if (t.id === "zIn") setZ(st.z + 1);
  else if (t.id === "zOut") setZ(st.z - 1);
});
$("#scrim").addEventListener("click", closeDetail);
$("#zoomR").addEventListener("input", (e) => setZ(+e.target.value));
$("#q").addEventListener("input", (e) => { st.q = e.target.value; render(); });
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeDetail();
  if (e.target.matches("input")) return;
  if (e.key === "+" || e.key === "=") setZ(st.z + 1);
  if (e.key === "-") setZ(st.z - 1);
});
$("#view").addEventListener("wheel", (e) => { if (e.ctrlKey) { e.preventDefault(); setZ(st.z + (e.deltaY < 0 ? 1 : -1)); } }, { passive: false });

async function load() {
  try {
    const [data, logos] = await Promise.all([
      fetch("data/descuentos.json", { cache: "no-cache" }).then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); }),
      fetch("logos/index.json").then((r) => (r.ok ? r.json() : {})).catch(() => ({})),
    ]);
    LOGOS = logos || {};
    META = data; DATA = data.descuentos || [];
    const g = new Date(data.generado);
    $("#month").textContent = `${MONTHS[g.getMonth()]} ${g.getFullYear()}`;
    const errs = Object.values(data.bancos || {}).filter((b) => b.estado === "error").map((b) => b.nombre);
    if (errs.length) { $("#noticeText").textContent = `No se pudo actualizar: ${errs.join(", ")}. Se muestran sus datos de la actualización anterior, si existen.`; $("#notice").hidden = false; }
    $("#foot").innerHTML = `<span>Actualizado el ${g.toLocaleString("es-CL", { dateStyle: "long", timeStyle: "short" })}. Datos tomados de los sitios públicos de cada institución.</span><span>Este sitio no está afiliado a ningún banco. Revisa siempre las condiciones en el sitio oficial.</span>`;
    // Descarta tarjetas guardadas que ya no existen
    const valid = new Set(DATA.flatMap((d) => d.tarjetas.map((c) => key(d.banco, c))));
    [...st.cards].forEach((k) => { if (!valid.has(k)) st.cards.delete(k); });
    chips(); cardPop(); render();
  } catch (e) {
    $("#view").innerHTML = `<div class="empty">No se pudieron cargar los descuentos (${esc(e.message)}). Recarga la página en unos minutos.</div>`;
  }
}
load();

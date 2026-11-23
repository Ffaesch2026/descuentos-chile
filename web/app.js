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
  ["bice", "Banco BICE", "BICE", "#0a2d6e"],
].map(([id, name, mono, c]) => ({ id, name, mono, c }));
let LOGOS = {}; // id -> archivo, desde logos/index.json

const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const key = (b, c) => b + "|" + c;
const todayIdx = (new Date().getDay() + 6) % 7;

let DATA = [], META = {}, REGIONES = [];
const st = { days: new Set(), cats: new Set(), pcts: new Set(), types: new Set(), cards: new Set(), banks: new Set(), regs: new Set(), coms: new Set(), incNac: true, comQ: "", q: "", view: "inst", z: 3, collapsed: new Set() };
try { const z = +localStorage.getItem("dz"); if (z >= 1 && z <= 5) st.z = z; } catch (e) {}
// Celular: rubro y región son obligatorios y se recuerdan; la vista por defecto es la tabla tipo afiche
const MQ = window.matchMedia("(max-width: 760px)");
let mobile = MQ.matches;
const lsGet = (k, d) => { try { return localStorage.getItem(k) || d; } catch (e) { return d; } };
const lsSet = (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} };
st.mcat = lsGet("mcat", "restaurantes");
st.mreg = lsGet("mreg", "RM");
st.expanded = new Set();
if (mobile) st.view = "tabla";
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
  const used = new Set(DATA.map((d) => d.banco));
  $("#bankChips").innerHTML = BANKS.filter((b) => used.has(b.id)).map((b) => `<button class="chip bankchip" data-bank="${b.id}" aria-pressed="${st.banks.has(b.id)}">${logo(b, true)}${esc(b.name)}</button>`).join("");
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

const regName = (id) => (REGIONES.find((r) => r.id === id) || { nombre: id }).nombre;
const regOfCom = (c) => (REGIONES.find((r) => r.comunas.includes(c)) || {}).id;
function geoPop() {
  const nReg = {}, nCom = {};
  DATA.forEach((d) => { (d.regiones || []).forEach((r) => (nReg[r] = (nReg[r] || 0) + 1)); (d.comunas || []).forEach((c) => (nCom[c] = (nCom[c] || 0) + 1)); });
  $("#regPop").innerHTML = REGIONES.map((r) => `<label><input type="checkbox" data-reg="${r.id}" ${st.regs.has(r.id) ? "checked" : ""}>${esc(r.nombre)} <span class="meta">(${nReg[r.id] || 0})</span></label>`).join("");
  const q = st.comQ.trim().toLowerCase();
  $("#comList").innerHTML = REGIONES.filter((r) => st.regs.has(r.id)).map((r) => {
    const cs = r.comunas.filter((c) => !q || c.toLowerCase().includes(q));
    if (!cs.length) return "";
    return `<div class="bank"><div class="bankhead">${esc(r.nombre)}</div>` + cs.map((c) => `<label><input type="checkbox" data-com="${esc(c)}" ${st.coms.has(c) ? "checked" : ""}>${esc(c)} <span class="meta">${nCom[c] ? "(" + nCom[c] + ")" : ""}</span></label>`).join("") + `</div>`;
  }).join("") || `<p class="meta">Sin comunas que coincidan.</p>`;
  $("#regCount").textContent = st.regs.size || "Todas";
  $("#comCount").textContent = st.coms.size || "Todas";
  const cb = $("#comBtn"); cb.disabled = !st.regs.size; cb.title = st.regs.size ? "" : "Elige primero una región";
  $("#nacWrap").hidden = !st.regs.size;
  $("#geoChips").innerHTML = [...st.regs].map((r) => `<button class="selchip" data-rmreg="${r}" aria-label="Quitar ${esc(regName(r))}">${esc(regName(r))}</button>`).join("") +
    [...st.coms].map((c) => `<button class="selchip" data-rmcom="${esc(c)}" aria-label="Quitar ${esc(c)}">${esc(c)}</button>`).join("");
}
// Un descuento sin ubicación es válido en todo Chile u online.
// Por cada región elegida: si se eligieron comunas de esa región, el descuento debe estar en alguna
// de ellas (o valer para toda la región, sin comuna específica); si no, basta con la región.
function inGeo(d) {
  if (!st.regs.size) return true;
  const regs = d.regiones || [], coms = d.comunas || [];
  if (!regs.length) return st.incNac;
  return regs.some((r) => {
    if (!st.regs.has(r)) return false;
    const elegidas = [...st.coms].filter((c) => regOfCom(c) === r);
    if (!elegidas.length) return true;
    const enRegion = coms.filter((c) => regOfCom(c) === r);
    return !enRegion.length || enRegion.some((c) => st.coms.has(c));
  });
}

function filtered() {
  const q = st.q.trim().toLowerCase();
  return DATA.filter((d) => (!st.days.size || d.dias.some((x) => st.days.has(x)))
    && (!st.cats.size || st.cats.has(d.rubro))
    && (!st.pcts.size || [...st.pcts].some((i) => inPct(d, i)))
    && (!st.types.size || d.tipos.some((t) => st.types.has(t)))
    && (!st.banks.size || st.banks.has(d.banco))
    && inGeo(d)
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
  <span class="meta">${(CATS[d.rubro] || CATS.otros)[0]}${d.tope ? " · " + esc(/^tope/i.test(d.tope) ? d.tope : "tope " + d.tope) : ""}</span>
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
  mDaySync();
  $("#sheetApply").textContent = list.length === 1 ? "Ver 1 descuento" : `Ver ${list.length} descuentos`;
  const nf = (st.days.size > 1 ? st.days.size : 0) + st.pcts.size + st.types.size + st.banks.size + st.coms.size + st.cards.size + (st.q.trim() ? 1 : 0) + (st.incNac ? 0 : 1);
  $("#fCount").textContent = nf; $("#fCount").hidden = !nf;
  ["vInst", "vWeek", "vTab"].forEach((id) => $("#" + id).setAttribute("aria-pressed", st.view === { vInst: "inst", vWeek: "week", vTab: "tabla" }[id]));
  if (!list.length) { v.innerHTML = `<div class="empty">No hay descuentos con estos filtros. Prueba quitando un día, un rubro o un rango de %.</div>`; return; }
  if (st.view === "tabla") { renderTabla(list); return; }
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
  <dt>Ubicación</dt><dd>${(d.comunas || []).length ? esc(d.comunas.join(", ")) + (d.comunas.length ? " (" + esc([...new Set(d.regiones)].map(regName).join(", ")) + ")" : "") : (d.regiones || []).length ? esc(d.regiones.map(regName).join(", ")) : "Todo Chile u online"}</dd>
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
  const inPick = e.target.closest(".cardpick");
  document.querySelectorAll(".pop").forEach((p) => {
    if (!p.hidden && (!inPick || !inPick.contains(p))) { p.hidden = true; p.previousElementSibling.setAttribute("aria-expanded", "false"); }
  });
  const t = e.target.closest("button,input"); if (!t) return;
  const ds = t.dataset;
  if (ds.day) { toggle(st.days, +ds.day); chips(); render(); }
  else if (ds.cat) { toggle(st.cats, ds.cat); chips(); render(); }
  else if (ds.pct) { toggle(st.pcts, +ds.pct); chips(); render(); }
  else if (ds.type) { toggle(st.types, ds.type); chips(); render(); }
  else if (ds.pop) { const p = $("#" + ds.pop); p.hidden = !p.hidden; t.setAttribute("aria-expanded", !p.hidden); if (!p.hidden && ds.pop === "comPop") $("#comQ").focus(); }
  else if (ds.bank) { toggle(st.banks, ds.bank); chips(); render(); }
  else if (ds.reg) {
    t.checked ? st.regs.add(ds.reg) : st.regs.delete(ds.reg);
    if (!t.checked) [...st.coms].forEach((c) => { if (regOfCom(c) === ds.reg) st.coms.delete(c); });
    geoPop(); render();
  }
  else if (ds.com) { t.checked ? st.coms.add(ds.com) : st.coms.delete(ds.com); geoPop(); render(); }
  else if (ds.rmreg) { st.regs.delete(ds.rmreg); [...st.coms].forEach((c) => { if (regOfCom(c) === ds.rmreg) st.coms.delete(c); }); geoPop(); render(); }
  else if (ds.rmcom) { st.coms.delete(ds.rmcom); geoPop(); render(); }
  else if (t.id === "incNac") { st.incNac = t.checked; render(); }
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
  else if (t.id === "fBtn" || t.id === "sheetClose" || t.id === "sheetApply") { setSheet(t.id === "fBtn" && !document.body.classList.contains("sheet-open")); }
  else if (ds.mday !== undefined) {
    st.days.clear(); if (ds.mday !== "") st.days.add(+ds.mday);
    st.expanded.clear(); chips(); render();
  }
  else if (ds.more) { toggle(st.expanded, ds.more); render(); }
  else if (t.id === "clearAll2") { $("#clearAll").click(); }
  else if (t.id === "clearAll") { ["days", "cats", "pcts", "types", "cards", "banks", "regs", "coms"].forEach((k) => st[k].clear()); st.q = ""; $("#q").value = ""; st.incNac = true; $("#incNac").checked = true; saveCards(); if (mobile) applyMobile(); chips(); cardPop(); geoPop(); render(); }
  else if (t.id === "vInst" || t.id === "vWeek" || t.id === "vTab") {
    st.view = { vInst: "inst", vWeek: "week", vTab: "tabla" }[t.id];
    $("#vInst").setAttribute("aria-pressed", st.view === "inst"); $("#vWeek").setAttribute("aria-pressed", st.view === "week"); render();
  }
  else if (t.id === "zIn") setZ(st.z + 1);
  else if (t.id === "zOut") setZ(st.z - 1);
});
$("#scrim").addEventListener("click", closeDetail);
$("#zoomR").addEventListener("input", (e) => setZ(+e.target.value));
$("#q").addEventListener("input", (e) => { st.q = e.target.value; render(); });
$("#comQ").addEventListener("input", (e) => { st.comQ = e.target.value; geoPop(); });
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") { closeDetail(); setSheet(false); }
  if (e.target.matches("input")) return;
  if (e.key === "+" || e.key === "=") setZ(st.z + 1);
  if (e.key === "-") setZ(st.z - 1);
});
$("#view").addEventListener("wheel", (e) => { if (e.ctrlKey) { e.preventDefault(); setZ(st.z + (e.deltaY < 0 ? 1 : -1)); } }, { passive: false });

// ---------- Celular ----------
const DSHORT = ["LUN", "MAR", "MIÉ", "JUE", "VIE", "SÁB", "DOM"];
function fmtDias(dias) {
  if (!dias.length) return "VER COND.";
  if (dias.length === 7) return "TODOS";
  const ds = [...dias].sort((a, b) => a - b);
  const contiguo = ds.every((x, i) => i === 0 || x === ds[i - 1] + 1);
  if (contiguo && ds.length >= 3) return `${DSHORT[ds[0]]}–${DSHORT[ds[ds.length - 1]]}`;
  return ds.map((x) => DSHORT[x]).join(" · ");
}
const PER_BANK = 12;
function renderTabla(list) {
  const ids = [...new Set([...BANKS.map((b) => b.id), ...list.map((d) => d.banco)])];
  const firstDay = (d) => (d.dias.length ? Math.min(...d.dias) : 9);
  const groups = ids.map((id) => {
    const all = list.filter((d) => d.banco === id);
    if (!all.length) return "";
    const b = bank(id);
    const shown = (st.expanded.has(id) ? all : [...all].sort(byPct).slice(0, PER_BANK))
      .sort((a, c) => firstDay(a) - firstDay(c) || (c.pct ?? -1) - (a.pct ?? -1));
    const tipos = [...new Set(all.flatMap((d) => d.tipos))].map((t) => ({ credito: "Créd.", debito: "Déb.", prepago: "Prep." }[t])).join(" / ");
    const topes = [...new Set(all.map((d) => d.tope).filter(Boolean))];
    const tope = topes.length === 1 && all.every((d) => d.tope) ? `<span class="ptope">${esc(topes[0])}</span>` : "";
    const rest = all.length - shown.length;
    return `<section class="pgroup" style="--bc:${b.c}">
      <div class="pbank">${logo(b, true)}<b>${esc(b.name)}</b><span>*${tipos}</span>${tope}</div>
      <div class="prows">${shown.map((d) => `<button class="prow" data-id="${esc(d.id)}"><span class="pday">${fmtDias(d.dias)}</span><span class="pcom">${esc(d.comercio)}</span><span class="ppct">${d.pct != null ? d.pct + "%" : "★"}</span></button>`).join("")}
      ${rest > 0 ? `<button class="pmore" data-more="${id}">Ver ${rest} más de ${esc(b.name)} ▾</button>` : st.expanded.has(id) && all.length > PER_BANK ? `<button class="pmore" data-more="${id}">Ver menos ▴</button>` : ""}</div>
    </section>`;
  }).join("");
  const cat = (CATS[st.mcat] || CATS.otros)[0], reg = regName(st.mreg);
  $("#view").innerHTML = `<div class="posterwrap"><div class="poster" id="poster">
    <div class="phead"><b>${esc(cat)} · ${esc(reg)}</b><span>${esc($("#month").textContent)} · ${list.length} descuentos${st.incNac ? " (incluye válidos en todo Chile)" : ""}</span></div>
    <div class="pcols">${groups}</div>
    <p class="pnote">Toca una fila para ver condiciones. Pellizca la pantalla para ampliar.</p></div></div>`;
  fitPoster();
}
function fitPoster() {
  const p = $("#poster"); if (!p) return;
  const w = p.parentElement.getBoundingClientRect().width;
  p.style.zoom = Math.min(1, w / 720);
}
window.addEventListener("resize", () => { if (st.view === "tabla") fitPoster(); });

// Día (opcional) en la barra del celular: "Todos" o un día; en el panel se pueden marcar varios
function mDaySync() {
  const box = $("#mDays"); if (!box) return;
  const one = st.days.size === 1 ? [...st.days][0] : null;
  box.innerHTML = `<button class="mday" data-mday="" aria-pressed="${!st.days.size}">Todos</button>` +
    DAYS.map((d, i) => `<button class="mday${i === todayIdx ? " today" : ""}" data-mday="${i}" aria-pressed="${one === i || (st.days.size > 1 && st.days.has(i))}">${i === todayIdx ? "Hoy" : d}</button>`).join("");
}

function setSheet(open) {
  document.body.classList.toggle("sheet-open", open);
  $("#fBtn").setAttribute("aria-expanded", open);
  $("#scrim").hidden = !open && $("#drawer").hidden;
}
function mobileSelects() {
  const used = new Set(DATA.map((d) => d.rubro));
  $("#mCat").innerHTML = Object.entries(CATS).filter(([k]) => used.has(k)).map(([k, [n]]) => `<option value="${k}" ${k === st.mcat ? "selected" : ""}>${n}</option>`).join("");
  $("#mReg").innerHTML = REGIONES.map((r) => `<option value="${r.id}" ${r.id === st.mreg ? "selected" : ""}>${esc(r.nombre)}</option>`).join("");
}
function applyMobile() {
  document.body.classList.toggle("is-mobile", mobile);
  if (!mobile) return;
  st.cats = new Set([st.mcat]);
  st.regs = new Set([st.mreg]);
  [...st.coms].forEach((c) => { if (regOfCom(c) !== st.mreg) st.coms.delete(c); });
  st.expanded.clear();
}
$("#mCat").addEventListener("change", (e) => { st.mcat = e.target.value; lsSet("mcat", st.mcat); applyMobile(); chips(); geoPop(); render(); window.scrollTo(0, 0); });
$("#mReg").addEventListener("change", (e) => { st.mreg = e.target.value; lsSet("mreg", st.mreg); applyMobile(); geoPop(); render(); window.scrollTo(0, 0); });
MQ.addEventListener("change", (e) => {
  mobile = e.matches;
  if (mobile) { if (st.view !== "week") st.view = "tabla"; } else { setSheet(false); if (st.view === "tabla") st.view = "inst"; }
  applyMobile(); chips(); geoPop(); render();
});
$("#scrim").addEventListener("click", () => setSheet(false));

async function load() {
  try {
    const [data, logos, geo] = await Promise.all([
      fetch("data/descuentos.json", { cache: "no-cache" }).then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); }),
      fetch("logos/index.json").then((r) => (r.ok ? r.json() : {})).catch(() => ({})),
      fetch("data/regiones.json").then((r) => (r.ok ? r.json() : { regiones: [] })).catch(() => ({ regiones: [] })),
    ]);
    REGIONES = geo.regiones || [];
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
    if (!Object.keys(CATS).includes(st.mcat) || !DATA.some((d) => d.rubro === st.mcat)) st.mcat = "restaurantes";
    if (!REGIONES.some((r) => r.id === st.mreg)) st.mreg = "RM";
    mobileSelects(); applyMobile();
    chips(); cardPop(); geoPop(); render();
  } catch (e) {
    $("#view").innerHTML = `<div class="empty">No se pudieron cargar los descuentos (${esc(e.message)}). Recarga la página en unos minutos.</div>`;
  }
}
load();

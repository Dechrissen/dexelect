// Dexelect web UI — (vanilla JS)
// Renders every config lever generically from the shape of the config dict the
// server returns, and mutates an in-memory `state.config` that is flattened back
// into value-only overrides at generate time.

"use strict";

const state = {
  game: null,
  config: {},        // full config dict from the server (with {value, options} objects)
  spheres: [],       // [{num, new_species, contents:[{name,type}]}] for the Spheres tab
  sphereModeMap: {}, // sphere mode -> list of active sphere nums
  hasParty: false,   // a party is currently rendered (gates HM/stats visibility)
  exportText: null,  // pre-rendered export .txt from the generate response
  exportFilename: null,
};

// Text colors matching the desktop GUI (ui/gui/app.py C_COVERED / C_DIM).
const COLOR_COVERED = "#006400";
const COLOR_DIM = "#999999";

const $ = (id) => document.getElementById(id);

// Status line above the tabs. A non-breaking space keeps the line's height
// reserved when there's no message, so appearing text never shifts the layout.
function setStatus(msg) {
  $("status").textContent = msg || " ";
}

// ---- tabs ------------------------------------------------------------------

// Show one panel at a time by toggling the native `hidden` attribute on each
// <section id="tab-...">
function showTab(name) {
  document.querySelectorAll("#tabs button").forEach((b) => {
    b.disabled = b.dataset.tab === name;  // mark the active tab (can't click it)
  });
  document.querySelectorAll("section[id^='tab-']").forEach((s) => {
    s.hidden = s.id !== "tab-" + name;
  });
}

// ---- helpers ---------------------------------------------------------------

function isValueOptions(v) {
  return v && typeof v === "object" && !Array.isArray(v) && "value" in v && "options" in v;
}

function isBoolMap(v) {
  return v && typeof v === "object" && !Array.isArray(v) && !isValueOptions(v);
}

// Coerce a free-text field: an all-digits string becomes an int (e.g. bst_max),
// otherwise the string is kept (e.g. 'none').
function coerceText(s) {
  const t = s.trim();
  return /^-?\d+$/.test(t) ? parseInt(t, 10) : t;
}

// Flatten state.config into the value-only overrides the server expects.
function toOverrides(config) {
  const out = {};
  for (const [k, v] of Object.entries(config)) {
    out[k] = isValueOptions(v) ? v.value : v;
  }
  return out;
}

// ---- config form rendering -------------------------------------------------

function renderConfig(config) {
  state.config = config;
  const root = $("config");
  root.innerHTML = "";

  for (const [key, v] of Object.entries(config)) {
    const wrap = document.createElement("div");
    const label = document.createElement("strong");
    label.textContent = key + ": ";
    wrap.appendChild(label);
    wrap.appendChild(buildControl(key, v));
    root.appendChild(wrap);
  }
}

function buildControl(key, v) {
  // boolean -> checkbox
  if (typeof v === "boolean") {
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = v;
    cb.onchange = () => { state.config[key] = cb.checked; };
    return cb;
  }

  // number -> number input
  if (typeof v === "number") {
    const inp = document.createElement("input");
    inp.type = "number";
    inp.value = v;
    inp.onchange = () => { state.config[key] = parseInt(inp.value, 10); };
    return inp;
  }

  // array (e.g. species_blacklist) -> comma-separated text
  if (Array.isArray(v)) {
    const inp = document.createElement("input");
    inp.type = "text";
    inp.size = 40;
    inp.value = v.join(", ");
    inp.onchange = () => {
      state.config[key] = inp.value.split(",").map((s) => s.trim()).filter(Boolean);
    };
    return inp;
  }

  // {value, options}
  if (isValueOptions(v)) {
    if (Array.isArray(v.value)) {
      // multi-select -> a checkbox per option
      const span = document.createElement("span");
      v.options.forEach((opt) => {
        const cb = document.createElement("input");
        cb.type = "checkbox";
        cb.checked = v.value.includes(opt);
        cb.onchange = () => {
          const set = new Set(state.config[key].value);
          if (cb.checked) set.add(opt); else set.delete(opt);
          // preserve option order
          state.config[key].value = v.options.filter((o) => set.has(o));
        };
        const lab = document.createElement("label");
        lab.appendChild(cb);
        lab.appendChild(document.createTextNode(" " + opt + " "));
        span.appendChild(lab);
      });
      return span;
    }
    // scalar -> dropdown
    const sel = document.createElement("select");
    v.options.forEach((opt) => {
      const o = document.createElement("option");
      o.value = opt;
      o.textContent = opt;
      if (opt === v.value) o.selected = true;
      sel.appendChild(o);
    });
    sel.onchange = () => { state.config[key].value = sel.value; };
    return sel;
  }

  // bool map (e.g. allowed_acquisition_methods) -> a checkbox per sub-key
  if (isBoolMap(v)) {
    const span = document.createElement("span");
    for (const [subk, subv] of Object.entries(v)) {
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.checked = !!subv;
      cb.onchange = () => { state.config[key][subk] = cb.checked; };
      const lab = document.createElement("label");
      lab.appendChild(cb);
      lab.appendChild(document.createTextNode(" " + subk + " "));
      span.appendChild(lab);
    }
    return span;
  }

  // string scalar (e.g. bst 'none') -> text with numeric coercion
  const inp = document.createElement("input");
  inp.type = "text";
  inp.value = v;
  inp.onchange = () => { state.config[key] = coerceText(inp.value); };
  return inp;
}

// ---- game / preset loading -------------------------------------------------

function fillSelect(sel, values, selected) {
  sel.innerHTML = "";
  values.forEach((val) => {
    const o = document.createElement("option");
    // preset entries are [id, label] pairs; everything else is a plain string
    if (Array.isArray(val)) { o.value = val[0]; o.textContent = val[1]; }
    else { o.value = val; o.textContent = val; }
    if (o.value === selected) o.selected = true;
    sel.appendChild(o);
  });
}

async function loadGame(game) {
  state.game = game;
  const data = await fetch(`/api/game/${encodeURIComponent(game)}`).then((r) => r.json());

  fillSelect($("generation_mode"), data.generation_modes, data.defaults.generation_mode);

  const suggested = data.suggested_sphere_mode;
  fillSelect($("sphere_mode"), data.sphere_modes, suggested);
  // annotate the suggested mode
  Array.from($("sphere_mode").options).forEach((o) => {
    if (o.value === suggested) o.textContent += " (suggested)";
  });

  state.spheres = data.spheres;
  state.sphereModeMap = data.sphere_mode_map;
  renderSphereMap();

  $("party_size").value = data.defaults.party_size;
  fillSelect($("preset"), data.presets, "default");
  renderConfig(data.config);
}

// ---- spheres tab -------------------------------------------------------------

// Render the sphere map for the currently selected sphere mode; spheres the
// mode doesn't enable are greyed out (matching the desktop GUI).
function renderSphereMap() {
  const root = $("sphere_map");
  root.innerHTML = "";
  const active = new Set(state.sphereModeMap[$("sphere_mode").value] || []);

  state.spheres.forEach((s) => {
    const on = active.has(s.num);
    const div = document.createElement("div");
    if (!on) div.style.color = COLOR_DIM;

    const hdr = document.createElement("strong");
    hdr.textContent =
      `Sphere ${s.num} (new species: ${s.new_species}) – ${on ? "Enabled" : "Disabled"}`;
    div.appendChild(hdr);

    const ul = document.createElement("ul");
    s.contents.forEach((e) => {
      const li = document.createElement("li");
      li.textContent = e.type === "map"
        ? e.name
        : `${e.name} [${e.type === "item" ? "item" : "unlock"}]`;
      ul.appendChild(li);
    });
    div.appendChild(ul);
    root.appendChild(div);
  });
}

async function loadPreset(preset) {
  const data = await fetch(
    `/api/game/${encodeURIComponent(state.game)}/preset/${encodeURIComponent(preset)}`
  ).then((r) => r.json());
  renderConfig(data.config);
}

// ---- generate + render party ----------------------------------------------

async function generate() {
  setStatus("Generating…");
  $("result").innerHTML = "";
  state.hasParty = false;
  state.exportText = null;
  state.exportFilename = null;
  $("export").disabled = true;  // greyed out until a party is on screen again
  applyDisplayToggles();  // hide the stale HM coverage / stats strips

  const body = {
    game: state.game,
    generation_mode: $("generation_mode").value,
    sphere_mode: $("sphere_mode").value,
    party_size: parseInt($("party_size").value, 10),
    config: toOverrides(state.config),
  };

  let data;
  try {
    data = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then((r) => r.json());
  } catch (e) {
    setStatus("Request failed: " + e);
    return;
  }

  if (data.error) {
    setStatus(data.error);
    return;
  }

  setStatus("");
  renderParty(data);
  state.exportText = data.export_text || null;
  state.exportFilename = data.export_filename || null;
  $("export").disabled = !state.exportText;
  showTab("party");  // jump to the result once it's ready
}

// Download the pre-rendered export text as a .txt file. Purely client-side:
// the string arrived with the generate response, so clicking issues no request.
function exportParty() {
  if (!state.exportText) return;
  const blob = new Blob([state.exportText], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = state.exportFilename || "dexelect_generated_party.txt";
  document.body.appendChild(a);  // Firefox needs the anchor in the DOM to click
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function renderParty(data) {
  const root = $("result");
  root.innerHTML = "";

  data.party.forEach((m, i) => {
    const div = document.createElement("div");

    const img = document.createElement("img");
    img.src = m.sprite_url;
    img.alt = m.name;
    img.width = 96;
    img.height = 96;
    div.appendChild(img);

    const name = document.createElement("span");
    name.textContent = ` ${i + 1}. ${m.name} [${m.types.join("/")}]`;
    div.appendChild(name);

    if (m.acquisition) {
      const a = m.acquisition;
      const acq = document.createElement("div");
      acq.dataset.acq = "1";  // targeted by the Acquisition Details display toggle
      acq.textContent =
        `    acquire as ${a.earliest_form} via ${a.method} at ${a.location} (Sphere ${a.sphere})`;
      div.appendChild(acq);
    }

    root.appendChild(div);
  });

  renderHmCoverage(data.hm_coverage);

  const s = data.stats;
  const dist = s.party_distribution
    ? Object.entries(s.party_distribution).map(([k, v]) => `S${k}: ${v}`).join("  ")
    : "—";
  // dl/dt/dd pattern matching the Help tab's Terminology section: bold label
  // lines with natively indented values, no CSS. #stats must stay a <div>:
  // these are block elements.
  const rows = [
    ["Lean", s.lean],
    ["Spread", s.spread],
    ["Pattern", s.pattern],
    ["Distribution", dist],
  ];
  $("stats").innerHTML =
    "<h3>Balance Stats</h3><blockquote><dl>" +
    rows.map(([label, value]) => `<dt><strong>${label}</strong></dt><dd>${value}</dd>`).join("") +
    "</dl></blockquote>";

  state.hasParty = true;
  applyDisplayToggles();
}

// HM coverage strip: every HM the game's config knows about, with the ones the
// party can learn in green and the rest greyed out (matching the GUI).
function renderHmCoverage(hm) {
  const root = $("hm_coverage");
  root.innerHTML = "";
  if (!hm) return;

  const hdr = document.createElement("h3");
  hdr.textContent = "HM Coverage";
  root.appendChild(hdr);

  const covered = new Set(hm.covered);
  hm.hms.forEach((name) => {
    const span = document.createElement("span");
    // Covered HMs get a tight "✓" prefix, matching the CLI's ✓SURF format.
    span.textContent = " " + (covered.has(name) ? "✓" + name : name) + " ";
    span.style.color = covered.has(name) ? COLOR_COVERED : COLOR_DIM;
    root.appendChild(span);
  });
}

// Apply the Setup tab's Display toggles to the Party tab's elements. Works via
// each element's own `hidden` attribute, so the state sticks even while the
// Party tab itself is hidden and is correct when the user switches back.
function applyDisplayToggles() {
  $("party_header").hidden = !state.hasParty;  // no "Party" header over an empty tab
  document.querySelectorAll("[data-acq]").forEach((d) => {
    d.hidden = !$("show_acq").checked;
  });
  $("hm_coverage").hidden = !state.hasParty || !$("show_hm").checked;
  $("stats").hidden = !state.hasParty || !$("show_balance").checked;
}

// ---- wiring ----------------------------------------------------------------

async function init() {
  // A fresh page never has a party, so the export button must start disabled
  // even when the browser (Firefox on F5) restores its pre-reload state.
  $("export").disabled = true;

  const { games } = await fetch("/api/games").then((r) => r.json());
  fillSelect($("game"), games, games[0]);

  document.querySelectorAll("#tabs button").forEach((b) => {
    b.onclick = () => showTab(b.dataset.tab);
  });
  showTab("party");

  $("game").onchange = () => loadGame($("game").value);
  $("sphere_mode").onchange = renderSphereMap;
  ["show_acq", "show_hm", "show_balance"].forEach((id) => {
    $(id).onchange = applyDisplayToggles;
  });
  $("preset").onchange = () => loadPreset($("preset").value);
  $("restore_defaults").onclick = () => {
    $("preset").value = "default";
    loadPreset("default");
  };
  $("generate").onclick = generate;
  $("export").onclick = exportParty;

  await loadGame(games[0]);
}

init();

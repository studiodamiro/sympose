/*
 * Sympose Dashboard scaffold — minimal runtime wiring.
 *
 * This only touches the endpoints that actually exist today:
 *   GET /health         → version, active personas, default persona
 *   GET /api/personas   → persona roster (fallback source)
 *
 * Everything else in the shell (chat stream, vault tree, nebula graph) is a
 * static placeholder until the corresponding routes are added to
 * sympose/server.py and the Vite + React + TS app replaces this file.
 */

const $ = (sel, root = document) => root.querySelector(sel);

function setField(name, value) {
  const el = document.querySelector(`[data-field="${name}"]`);
  if (el) el.textContent = value;
}

function setHealthTag(status, text) {
  const tag = $("#health-tag");
  if (!tag) return;
  tag.dataset.status = status;
  tag.textContent = text;
}

async function loadRuntime() {
  try {
    const res = await fetch("/health", { headers: { Accept: "application/json" } });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    setHealthTag("ok", `healthy · v${data.version ?? "?"}`);
    setField("version", data.version ?? "—");
    setField("default_persona", data.default_persona ?? "—");

    const personas = Array.isArray(data.active_personas) ? data.active_personas : [];
    setField("personas", personas.length ? personas.join(", ") : "none");
  } catch (err) {
    setHealthTag("error", "gateway unreachable");
    setField("version", "—");
    setField("default_persona", "—");
    setField("personas", "—");
    console.error("[sympose] /health failed:", err);
  }
}

// Composer is intentionally inert until the chat endpoints land.
$("#composer")?.addEventListener("submit", (e) => e.preventDefault());

loadRuntime();

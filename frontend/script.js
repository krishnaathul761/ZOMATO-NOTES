/* ============================================================
   ZOMATO NOTES — script.js  (all phases integrated)
   No onclick/onsubmit HTML attributes. No alert/confirm/prompt.
   ============================================================ */

// ── Config ─────────────────────────────────────────────────
const API_BASE    = "https://zomato-notes.onrender.com";
const X_TOKEN     = "zomato-dev-token";
const CACHE_KEY   = "zomato_notes_cache";
const MY_OWNER_ID = 1;

// ── State ───────────────────────────────────────────────────
let allNotes        = [];
let activeTag       = null;
let showMyNotesOnly = false;
let searchTimer     = null;

// ── P3: Category tree ───────────────────────────────────────
const CATEGORY_TREE = {
  name: "All Tags",
  children: [
    { name: "Work",     children: [{ name: "Standups", children: [] }, { name: "Retros", children: [] }] },
    { name: "Personal", children: [{ name: "Health", children: [{ name: "Fitness", children: [] }] }, { name: "Recipes", children: [] }] },
    { name: "Travel",   children: [] },
  ],
};

// ============================================================
// DATA LAYER
// ============================================================
async function fetchNotes(tag = null) {
  const url = tag ? `${API_BASE}/notes?tag=${encodeURIComponent(tag)}` : `${API_BASE}/notes`;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 90000);
  try {
    const res = await fetch(url, { signal: controller.signal });
    clearTimeout(timeout);
    if (!res.ok) throw new Error(`GET /notes failed: ${res.status}`);
    const notes = await res.json();
    if (!tag) localStorage.setItem(CACHE_KEY, JSON.stringify(notes));
    return notes;
  } catch (err) {
    clearTimeout(timeout);
    if (err.name === "AbortError") throw new Error("Backend is waking up (cold start). Please wait 30 seconds and refresh.");
    throw err;
  }
}

async function createNote(title, content, tag, ownerId, severity) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 90000); // 90s for cold start
  try {
    const res = await fetch(`${API_BASE}/notes`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, content, tag, owner_id: ownerId, severity }),
      signal: controller.signal,
    });
    clearTimeout(timeout);
    if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || `POST /notes failed: ${res.status}`); }
    return res.json();
  } catch (err) {
    clearTimeout(timeout);
    if (err.name === "AbortError") throw new Error("Request timed out. Backend may be waking up — please try again in 30 seconds.");
    throw err;
  }
}

async function deleteNote(id) {
  const res = await fetch(`${API_BASE}/notes/${id}`, { method: "DELETE", headers: { "x-token": X_TOKEN } });
  if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || `DELETE failed: ${res.status}`); }
  return true;
}

async function updateNote(id, patch) {
  const res = await fetch(`${API_BASE}/notes/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || `PUT failed: ${res.status}`); }
  return res.json();
}

// ============================================================
// RENDERING
// ============================================================
function relativeTime(iso) {
  const d = Date.now() - new Date(iso).getTime();
  const m = Math.floor(d / 60000), h = Math.floor(d / 3600000), dy = Math.floor(d / 86400000);
  if (m < 1) return "just now";
  if (m < 60) return `${m} min ago`;
  if (h < 24) return `${h} hr ago`;
  return `${dy}d ago`;
}

function createNoteCard(note) {
  const card = document.createElement("div");
  card.className = "note-card";
  card.dataset.id  = note.id;
  card.dataset.tag = (note.tag || "").toLowerCase();

  // P2: checkbox for bulk select
  const cb = document.createElement("input");
  cb.type = "checkbox"; cb.className = "note-select"; cb.dataset.id = note.id;
  card.appendChild(cb);

  // Delete btn
  const del = document.createElement("button");
  del.className = "delete-btn"; del.textContent = "✕"; del.title = "Delete";
  del.addEventListener("click", e => { e.stopPropagation(); handleDelete(note.id, card); });
  card.appendChild(del);

  // Title
  const titleEl = document.createElement("h3");
  titleEl.className = "note-title"; titleEl.textContent = note.title;
  card.appendChild(titleEl);

  // P2: severity badge
  if (note.severity) {
    const badge = document.createElement("span");
    badge.className = `severity-badge severity-${note.severity.toLowerCase()}`;
    badge.textContent = note.severity;
    card.appendChild(badge);
  }

  // P1: AI subtitle in list view
  if (note.ai_suggestion && note.ai_suggestion.summary) {
    const sub = document.createElement("p");
    sub.className = "note-subtitle"; sub.textContent = note.ai_suggestion.summary;
    card.appendChild(sub);
  }

  // Content
  const contentEl = document.createElement("p");
  contentEl.className = "note-content"; contentEl.textContent = note.content;
  card.appendChild(contentEl);

  // Meta
  const meta = document.createElement("div"); meta.className = "note-meta";
  const tagEl = document.createElement("span"); tagEl.className = "note-tag"; tagEl.textContent = note.tag || "untagged";
  const timeEl = document.createElement("span"); timeEl.className = "note-time"; timeEl.title = note.created_at; timeEl.textContent = relativeTime(note.created_at);
  const ownerEl = document.createElement("span"); ownerEl.className = "note-owner"; ownerEl.textContent = `owner #${note.owner_id}`;
  meta.appendChild(tagEl); meta.appendChild(timeEl); meta.appendChild(ownerEl);
  card.appendChild(meta);

  // P1: AI suggests panel
  if (note.ai_suggestion && note.ai_suggestion.tags) {
    card.appendChild(buildAiPanel(note));
  }

  // P2: tag confirm box (for merge warning)
  const confirmDiv = document.createElement("div");
  confirmDiv.className = "tag-confirm-box hidden"; confirmDiv.id = `tag-confirm-${note.id}`;
  card.appendChild(confirmDiv);

  // P2: similar notes on card click
  card.addEventListener("click", e => {
    const skip = ["delete-btn","note-select","btn-apply-tag","btn-use-existing","btn-use-suggested"];
    if (skip.some(cls => e.target.classList.contains(cls))) return;
    if (!isNaN(parseInt(note.id))) openSimilarPanel(note);
  });

  return card;
}

function buildAiPanel(note) {
  const panel = document.createElement("div");
  panel.className = "ai-panel"; panel.id = `ai-panel-${note.id}`;
  const lbl = document.createElement("p"); lbl.className = "ai-label"; lbl.textContent = "AI Suggests:";
  const tags = document.createElement("span"); tags.className = "ai-tags"; tags.textContent = note.ai_suggestion.tags.join(", ");
  const sum  = document.createElement("p"); sum.className = "ai-summary"; sum.textContent = note.ai_suggestion.summary;
  const btn  = document.createElement("button"); btn.className = "btn-apply-tag";
  btn.textContent = `Apply "${note.ai_suggestion.tags[0]}" as tag`;
  btn.addEventListener("click", () => handleApplyAiTag(note.id, note.ai_suggestion.tags[0], panel));
  panel.appendChild(lbl); panel.appendChild(tags); panel.appendChild(sum); panel.appendChild(btn);
  return panel;
}

function renderNotes(notes) {
  const list = document.getElementById("notes-list");
  list.innerHTML = "";
  notes.forEach(n => list.appendChild(createNoteCard(n)));
  document.getElementById("notes-count").textContent = `${notes.length} note${notes.length !== 1 ? "s" : ""}`;
}

// ============================================================
// TAG CHIPS + FILTERS
// ============================================================
function buildTagChips(notes) {
  const c = document.getElementById("tag-filters"); c.innerHTML = "";
  const tags = ["all", ...new Set(notes.map(n => n.tag).filter(Boolean))];
  tags.forEach(tag => {
    const chip = document.createElement("button");
    chip.className = "tag-chip"; chip.textContent = tag === "all" ? "All" : tag; chip.dataset.tag = tag;
    chip.addEventListener("click", () => handleTagFilter(tag, chip));
    c.appendChild(chip);
  });
  const a = c.querySelector('[data-tag="all"]'); if (a) a.classList.add("active");
}

function handleTagFilter(tag, chipEl) {
  document.querySelectorAll("#tag-filters .tag-chip").forEach(c => c.classList.remove("active"));
  chipEl.classList.add("active");
  activeTag = tag === "all" ? null : tag;
  applyFilters();
}

function applyFilters() {
  const q = document.getElementById("search-input").value.trim().toLowerCase();
  let r = showMyNotesOnly ? allNotes.filter(n => n.owner_id === MY_OWNER_ID) : allNotes;
  if (activeTag) r = r.filter(n => n.tag === activeTag);
  if (q) r = r.filter(n => n.title.toLowerCase().includes(q) || (n.tag && n.tag.toLowerCase().includes(q)));
  renderNotes(r);
}

// ============================================================
// DEBOUNCED SEARCH
// ============================================================
document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("search-input").addEventListener("input", e => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      console.log(`[${new Date().toISOString()}] search fired: "${e.target.value.trim()}"`);
      applyFilters();
    }, 400);
  });
});

// ============================================================
// ADD NOTE — optimistic UI + severity
// ============================================================
document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("add-note-form").addEventListener("submit", handleAddNote);
});

async function handleAddNote(e) {
  e.preventDefault();
  const title    = document.getElementById("input-title").value.trim();
  const content  = document.getElementById("input-content").value.trim();
  const tag      = document.getElementById("input-tag").value.trim() || null;
  const ownerId  = parseInt(document.getElementById("input-owner").value, 10);
  const severity = document.getElementById("input-severity").value || null;
  const errorEl  = document.getElementById("form-error");

  if (!title || !content) { errorEl.textContent = "Title and content are required."; errorEl.classList.remove("hidden"); return; }
  errorEl.classList.add("hidden");

  const opt = { id: `temp-${Date.now()}`, title, content, tag, severity, owner_id: ownerId, created_at: new Date().toISOString(), ai_suggestion: null };
  const card = createNoteCard(opt);
  card.classList.add("optimistic");
  document.getElementById("notes-list").prepend(card);

  try {
    const created = await createNote(title, content, tag, ownerId, severity);
    card.replaceWith(createNoteCard(created));
    document.getElementById("add-note-form").reset();
    allNotes = await fetchNotes();
    buildTagChips(allNotes);
  } catch (err) {
    card.remove();
    errorEl.textContent = `Failed to save: ${err.message}`;
    errorEl.classList.remove("hidden");
  }
}

// ============================================================
// DELETE
// ============================================================
async function handleDelete(id, cardEl) {
  try {
    await deleteNote(id);
    cardEl.remove();
    allNotes = allNotes.filter(n => n.id !== id);
    buildTagChips(allNotes);
    document.getElementById("notes-count").textContent = `${allNotes.length} note${allNotes.length !== 1 ? "s" : ""}`;
  } catch (err) {
    const m = document.createElement("p"); m.className = "error-msg"; m.textContent = `Delete failed: ${err.message}`;
    cardEl.appendChild(m); setTimeout(() => m.remove(), 4000);
  }
}

// ============================================================
// MY NOTES / ALL NOTES TOGGLE
// ============================================================
document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("btn-all-notes").addEventListener("click", () => {
    showMyNotesOnly = false;
    document.getElementById("btn-all-notes").classList.add("active");
    document.getElementById("btn-my-notes").classList.remove("active");
    applyFilters();
  });
  document.getElementById("btn-my-notes").addEventListener("click", () => {
    showMyNotesOnly = true;
    document.getElementById("btn-my-notes").classList.add("active");
    document.getElementById("btn-all-notes").classList.remove("active");
    applyFilters();
  });
});

// ============================================================
// EXPORT TO MARKDOWN
// ============================================================
document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("btn-export").addEventListener("click", () => {
    const ids = new Set([...document.querySelectorAll(".note-card[data-id]")].map(c => parseInt(c.dataset.id)).filter(x => !isNaN(x)));
    exportMarkdown(allNotes.filter(n => ids.has(n.id)));
  });
});

function exportMarkdown(notes) {
  if (!notes.length) return;
  const md = `# Zomato Notes Export\n\n` + notes.map(n =>
    `## ${n.title}\n**Tag:** ${n.tag || "untagged"} | **Owner:** #${n.owner_id} | **Created:** ${n.created_at}\n\n${n.content}\n\n---`
  ).join("\n");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([md], { type: "text/markdown" }));
  a.download = `zomato-notes-${new Date().toISOString().slice(0,10)}.md`;
  a.click();
}

// ============================================================
// P3 CATEGORY TREE — single recursive function
// ============================================================
function renderTree(node) {
  const li = document.createElement("li");
  const lbl = document.createElement("span"); lbl.className = "tree-label"; lbl.textContent = node.name;
  li.appendChild(lbl);
  if (node.children && node.children.length) {
    const ul = document.createElement("ul"); ul.className = "tree-children";
    node.children.forEach(child => ul.appendChild(renderTree(child)));
    li.appendChild(ul);
    lbl.addEventListener("click", () => ul.classList.toggle("hidden"));
  }
  return li;
}

// ============================================================
// LOADING / ERROR HELPERS
// ============================================================
function showLoading(v) { document.getElementById("loading-msg").classList.toggle("hidden", !v); }
function showError(msg) { const el = document.getElementById("error-msg"); el.textContent = msg; el.classList.remove("hidden"); }

// ============================================================
// INIT
// ============================================================
async function init() {
  showLoading(true);
  document.getElementById("error-msg").classList.add("hidden");
  try {
    allNotes = await fetchNotes();
    buildTagChips(allNotes);
    renderNotes(allNotes);
    document.getElementById("offline-banner").classList.add("hidden");
  } catch (err) {
    const cached = localStorage.getItem(CACHE_KEY);
    if (cached) {
      allNotes = JSON.parse(cached);
      buildTagChips(allNotes);
      renderNotes(allNotes);
      document.getElementById("offline-banner").classList.remove("hidden");
    } else {
      showError(`Could not load notes: ${err.message}`);
    }
  } finally {
    showLoading(false);
  }
  const treeRoot = document.createElement("ul");
  treeRoot.appendChild(renderTree(CATEGORY_TREE));
  document.getElementById("category-tree").appendChild(treeRoot);
}

document.addEventListener("DOMContentLoaded", init);

// ============================================================
// PHASE 3 — RANKING ENGINE
// ============================================================
async function fetchRankedNotes(keyword) {
  const res = await fetch(`${API_BASE}/notes/search?keyword=${encodeURIComponent(keyword)}`);
  if (!res.ok) throw new Error(`Search failed: ${res.status}`);
  return res.json();
}
async function fetchNotesByDate() {
  const res = await fetch(`${API_BASE}/notes/search?sort_by=date`);
  if (!res.ok) throw new Error(`Date sort failed: ${res.status}`);
  return res.json();
}
async function fetchLookup(title, algo) {
  const res = await fetch(`${API_BASE}/notes/lookup?title=${encodeURIComponent(title)}&algo=${algo}`);
  if (!res.ok) throw new Error(`Lookup failed: ${res.status}`);
  return res.json();
}
async function fetchQuickFind(tag) {
  const res = await fetch(`${API_BASE}/notes/quick-find?tag=${encodeURIComponent(tag)}`);
  if (!res.ok) throw new Error(`Quick find failed: ${res.status}`);
  return res.json();
}

function renderRankedResults(notes, labelFn) {
  const c = document.getElementById("ranked-results"); c.innerHTML = "";
  if (!notes || !notes.length) { c.textContent = "No results."; return; }
  notes.forEach(n => {
    const card = document.createElement("div"); card.className = "ranked-note-card";
    const score = document.createElement("span"); score.className = "ranked-score"; score.textContent = labelFn ? labelFn(n) : "";
    const title = document.createElement("strong"); title.textContent = n.title;
    const content = document.createElement("p"); content.textContent = n.content;
    const meta = document.createElement("small"); meta.textContent = `tag: ${n.tag || "untagged"} | owner #${n.owner_id}`; meta.style.color = "var(--text-muted)";
    card.appendChild(score); card.appendChild(title); card.appendChild(content); card.appendChild(meta);
    c.appendChild(card);
  });
}

function renderLookupResult(data, containerId) {
  const div = document.getElementById(containerId); div.innerHTML = "";
  if (!data.found) { div.textContent = data.message; div.style.color = "var(--text-muted)"; return; }
  const card = createNoteCard(data.note); card.classList.add("highlight"); div.appendChild(card);
}

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("btn-sort-relevance").addEventListener("click", async () => {
    const kw = document.getElementById("keyword-input").value.trim(); if (!kw) return;
    document.getElementById("btn-sort-relevance").classList.add("active");
    document.getElementById("btn-sort-date").classList.remove("active");
    try { renderRankedResults(await fetchRankedNotes(kw), n => `score: ${n.score}`); }
    catch (err) { document.getElementById("ranked-results").textContent = `Error: ${err.message}`; }
  });

  document.getElementById("btn-sort-date").addEventListener("click", async () => {
    document.getElementById("btn-sort-date").classList.add("active");
    document.getElementById("btn-sort-relevance").classList.remove("active");
    try { renderRankedResults(await fetchNotesByDate(), n => new Date(n.created_at).toLocaleDateString()); }
    catch (err) { document.getElementById("ranked-results").textContent = `Error: ${err.message}`; }
  });

  document.getElementById("btn-lookup-iterative").addEventListener("click", async () => {
    const t = document.getElementById("lookup-input").value.trim(); if (!t) return;
    try { renderLookupResult(await fetchLookup(t, "iterative"), "lookup-result"); }
    catch (err) { document.getElementById("lookup-result").textContent = `Error: ${err.message}`; }
  });

  document.getElementById("btn-lookup-recursive").addEventListener("click", async () => {
    const t = document.getElementById("lookup-input").value.trim(); if (!t) return;
    try { renderLookupResult(await fetchLookup(t, "recursive"), "lookup-result"); }
    catch (err) { document.getElementById("lookup-result").textContent = `Error: ${err.message}`; }
  });

  // Quick tag jump buttons
  const qc = document.getElementById("quick-tag-jump-ranking");
  ["work","health","recipes","travel","random","kb-demo","ai-demo"].forEach(tag => {
    const btn = document.createElement("button"); btn.className = "tag-chip"; btn.textContent = tag;
    btn.addEventListener("click", async () => {
      const rd = document.getElementById("quick-find-result-ranking");
      try {
        const data = await fetchQuickFind(tag); rd.innerHTML = "";
        if (data.found) { const card = createNoteCard(data.note); card.classList.add("highlight"); rd.appendChild(card); card.scrollIntoView({ behavior: "smooth", block: "nearest" }); }
        else { rd.textContent = data.message; rd.style.color = "var(--text-muted)"; }
      } catch (err) { rd.textContent = `Error: ${err.message}`; }
    });
    qc.appendChild(btn);
  });
});

// ============================================================
// PHASE 4 — SMART SEARCH (AI)
// ============================================================
async function fetchSmartSearch(query) {
  const res = await fetch(`${API_BASE}/notes/smart-search?q=${encodeURIComponent(query)}`);
  if (!res.ok) throw new Error(`Smart search failed: ${res.status}`);
  return res.json();
}

function renderSmartResults(results) {
  const c = document.getElementById("smart-search-results"); c.innerHTML = "";
  if (!results || !results.length) { c.textContent = "No results found."; c.style.color = "var(--text-muted)"; return; }
  results.forEach(n => {
    const card = document.createElement("div"); card.className = "smart-result-card";
    const badge = document.createElement("span"); badge.className = "similarity-badge"; badge.textContent = `${(n.similarity * 100).toFixed(1)}% match`;
    const title = document.createElement("strong"); title.textContent = n.title;
    const content = document.createElement("p"); content.textContent = n.content;
    const meta = document.createElement("small"); meta.textContent = `tag: ${n.tag || "untagged"} | owner #${n.owner_id}`; meta.style.color = "var(--text-muted)";
    card.appendChild(badge); card.appendChild(title); card.appendChild(content); card.appendChild(meta);
    c.appendChild(card);
  });
}

document.addEventListener("DOMContentLoaded", () => {
  const runSmartSearch = async () => {
    const q = document.getElementById("smart-search-input").value.trim(); if (!q) return;
    const c = document.getElementById("smart-search-results"); c.textContent = "Searching…"; c.style.color = "var(--text-muted)";
    try { renderSmartResults(await fetchSmartSearch(q)); }
    catch (err) { c.textContent = `Error: ${err.message}`; c.style.color = "var(--red)"; }
  };
  document.getElementById("btn-smart-search").addEventListener("click", runSmartSearch);
  document.getElementById("smart-search-input").addEventListener("keydown", e => { if (e.key === "Enter") runSmartSearch(); });
});

// ============================================================
// PHASE 4 — AI TAG APPLICATION + P2 MERGE WARNING
// ============================================================
function findSimilarTag(suggested, existing) {
  const s = suggested.toLowerCase().trim();
  for (const t of existing) {
    const e = t.toLowerCase().trim();
    if (e === s) return t;
    if (e.includes(s) || s.includes(e)) return t;
  }
  return null;
}

async function handleApplyAiTag(noteId, suggestedTag, panelEl) {
  const existing = [...new Set(allNotes.map(n => n.tag).filter(Boolean))];
  const similar  = findSimilarTag(suggestedTag, existing);

  if (similar && similar.toLowerCase() !== suggestedTag.toLowerCase()) {
    const confirmDiv = document.getElementById(`tag-confirm-${noteId}`);
    if (!confirmDiv) { await _doApplyTag(noteId, suggestedTag, panelEl, null); return; }
    confirmDiv.innerHTML = ""; confirmDiv.classList.remove("hidden");
    const msg = document.createElement("span"); msg.textContent = `Did you mean `;
    const bold = document.createElement("strong"); bold.textContent = similar;
    const q = document.createTextNode("? ");
    const useExisting = document.createElement("button"); useExisting.className = "btn-use-existing"; useExisting.textContent = `Use "${similar}"`;
    const useSuggested = document.createElement("button"); useSuggested.className = "btn-use-suggested"; useSuggested.textContent = `Use "${suggestedTag}"`;
    useExisting.addEventListener("click", () => _doApplyTag(noteId, similar, panelEl, confirmDiv));
    useSuggested.addEventListener("click", () => _doApplyTag(noteId, suggestedTag, panelEl, confirmDiv));
    confirmDiv.appendChild(msg); confirmDiv.appendChild(bold); confirmDiv.appendChild(q); confirmDiv.appendChild(useExisting); confirmDiv.appendChild(useSuggested);
  } else {
    await _doApplyTag(noteId, suggestedTag, panelEl, null);
  }
}

async function _doApplyTag(noteId, tag, panelEl, confirmDiv) {
  try {
    await updateNote(noteId, { tag });
    allNotes = await fetchNotes(); buildTagChips(allNotes); renderNotes(allNotes);
    if (panelEl)    panelEl.classList.add("hidden");
    if (confirmDiv) confirmDiv.classList.add("hidden");
  } catch (err) {
    const m = document.createElement("p"); m.className = "error-msg"; m.textContent = `Could not apply tag: ${err.message}`;
    if (panelEl) panelEl.appendChild(m);
  }
}

// ============================================================
// PHASE 5 P2 — BULK TAG UPDATE
// ============================================================
document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("notes-list").addEventListener("change", e => {
    if (!e.target.classList.contains("note-select")) return;
    const checked = document.querySelectorAll(".note-select:checked");
    document.getElementById("selected-count").textContent = `${checked.length} selected`;
    document.getElementById("bulk-toolbar").classList.toggle("hidden", checked.length === 0);
  });

  document.getElementById("btn-bulk-apply").addEventListener("click", async () => {
    const tag = document.getElementById("bulk-tag-input").value.trim();
    const checked = [...document.querySelectorAll(".note-select:checked")];
    if (!tag || !checked.length) return;
    await Promise.allSettled(checked.map(cb => updateNote(parseInt(cb.dataset.id), { tag })));
    allNotes = await fetchNotes(); buildTagChips(allNotes); renderNotes(allNotes);
    document.getElementById("bulk-toolbar").classList.add("hidden");
    document.getElementById("bulk-tag-input").value = "";
  });

  document.getElementById("btn-bulk-cancel").addEventListener("click", () => {
    document.querySelectorAll(".note-select:checked").forEach(cb => { cb.checked = false; });
    document.getElementById("bulk-toolbar").classList.add("hidden");
  });
});

// ============================================================
// PHASE 5 P2 — SIMILAR NOTES SIDEBAR
// ============================================================
document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("close-similar").addEventListener("click", () => {
    document.getElementById("similar-notes-panel").classList.add("hidden");
  });
});

async function fetchSimilarNotes(content) {
  return fetchSmartSearch(content);
}

async function openSimilarPanel(note) {
  const panel = document.getElementById("similar-notes-panel");
  const list  = document.getElementById("similar-notes-list");
  list.innerHTML = "<p style='color:var(--text-muted)'>Loading similar notes...</p>";
  panel.classList.remove("hidden");
  try {
    const results = (await fetchSimilarNotes(note.content)).filter(r => r.id !== note.id);
    list.innerHTML = "";
    if (!results.length) { list.textContent = "No similar notes found."; return; }
    results.forEach(r => {
      const item = document.createElement("div"); item.className = "similar-note-item";
      const t = document.createElement("strong"); t.textContent = r.title;
      const s = document.createElement("span"); s.className = "similarity-score";
      s.textContent = " " + (r.similarity * 100).toFixed(1) + "% match";
      const p = document.createElement("p"); p.textContent = r.content.slice(0, 120) + "...";
      item.appendChild(t); item.appendChild(s); item.appendChild(p);
      list.appendChild(item);
    });
  } catch (err) {
    list.textContent = "Could not load similar notes: " + err.message;
  }
}

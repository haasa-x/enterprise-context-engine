/* Context Engine — Admin Graph Viewer
 * Vanilla JS single-page app. Talks to the Context Engine REST API.
 *
 * Every request carries the `X-Tenant-Id` header. Because this runs in the
 * browser, the API base must be a HOST-reachable URL (default
 * http://localhost:8000) — NOT the docker-internal http://api:8000.
 */
"use strict";

/* ------------------------------------------------------------------ *
 * DOM handles
 * ------------------------------------------------------------------ */
const els = {
  apiBase: document.getElementById("apiBase"),
  tenantId: document.getElementById("tenantId"),
  customTenant: document.getElementById("customTenant"),
  userSelect: document.getElementById("userSelect"),
  eventWindow: document.getElementById("eventWindow"),
  loadUsersBtn: document.getElementById("loadUsersBtn"),
  refreshFeedBtn: document.getElementById("refreshFeedBtn"),
  banner: document.getElementById("banner"),
  profileText: document.getElementById("profileText"),
  profileMeta: document.getElementById("profileMeta"),
  profileHint: document.getElementById("profileHint"),
  patternList: document.getElementById("patternList"),
  patternHint: document.getElementById("patternHint"),
  graph: document.getElementById("graph"),
  graphStatus: document.getElementById("graphStatus"),
  graphLegend: document.getElementById("graphLegend"),
  fitGraphBtn: document.getElementById("fitGraphBtn"),
  timeline: document.getElementById("timeline"),
  timelineTip: document.getElementById("timelineTip"),
  eventFeed: document.getElementById("eventFeed"),
  feedHint: document.getElementById("feedHint"),
};

// How many days of history to request. Read live from the picker so switching
// it re-scopes every panel. Falls back to 90 if the control is absent.
function windowDays() {
  const v = els.eventWindow ? parseInt(els.eventWindow.value, 10) : 90;
  return Number.isFinite(v) ? v : 90;
}
// Server-side cap on events fetched per user (bounds the read + payload).
const EVENT_LIMIT = 300;
// Client-side cap on nodes drawn in the activity graph (bounds render cost).
const GRAPH_EVENT_CAP = 150;

let cy = null; // cytoscape instance

/* ------------------------------------------------------------------ *
 * API helpers
 * ------------------------------------------------------------------ */
function apiBase() {
  return els.apiBase.value.trim().replace(/\/+$/, "");
}
function tenant() {
  if (els.tenantId.value === "__other__") {
    return els.customTenant.value.trim();
  }
  return els.tenantId.value.trim();
}

async function apiGet(path) {
  // Static GitHub Pages demo: resolve requests to bundled JSON snapshots
  // (captured from a live engine) instead of hitting a running API.
  if (window.CE_DEMO_BASE) return demoGet(path);

  const base = apiBase();
  if (!base) throw new ApiError("Set an API base URL first.", 0);
  if (!tenant()) throw new ApiError("Set a Tenant ID first.", 0);

  let res;
  try {
    res = await fetch(base + path, {
      method: "GET",
      headers: { "X-Tenant-Id": tenant(), Accept: "application/json" },
    });
  } catch (networkErr) {
    throw new ApiError(
      "Could not reach the API at " + base +
        ". Is the engine running and is the base URL host-reachable (not http://api:8000)?",
      0
    );
  }

  let payload = null;
  try {
    payload = await res.json();
  } catch (_e) {
    payload = null;
  }

  if (!res.ok) {
    const detail = payload && (payload.detail || payload.error);
    throw new ApiError(detail || res.status + " " + res.statusText, res.status, payload);
  }
  return payload;
}

// Maps a native user id to its snapshot folder name (kept in sync with the
// fixture capture step). Non-alphanumeric runs collapse to underscores.
function demoSlug(id) {
  return id.replace(/[^a-zA-Z0-9]+/g, "_");
}

// Resolve an API path to a bundled snapshot file for the static demo.
async function demoGet(path) {
  const b = window.CE_DEMO_BASE.replace(/\/+$/, "");
  const t = tenant();
  let file = null;
  if (path === "/v1/admin/users") {
    file = b + "/" + t + "/users.json";
  } else {
    let m = path.match(/^\/v1\/admin\/users\/([^/]+)\/events/);
    if (m) {
      file = b + "/" + t + "/" + demoSlug(decodeURIComponent(m[1])) + "/events.json";
    } else if ((m = path.match(/^\/v1\/users\/([^/]+)\/profile/))) {
      file = b + "/" + t + "/" + demoSlug(decodeURIComponent(m[1])) + "/profile.json";
    }
  }
  if (!file) throw new ApiError("Unsupported demo request: " + path, 0);
  let res;
  try {
    res = await fetch(file, { headers: { Accept: "application/json" } });
  } catch (_e) {
    throw new ApiError("Demo data not reachable.", 0);
  }
  if (!res.ok) throw new ApiError("insufficient_data", res.status);
  return res.json();
}

class ApiError extends Error {
  constructor(message, status, body) {
    super(message);
    this.status = status;
    this.body = body || null;
  }
}

/* ------------------------------------------------------------------ *
 * Banner / status helpers
 * ------------------------------------------------------------------ */
function showBanner(message, kind) {
  els.banner.textContent = message;
  els.banner.className = "banner " + (kind || "info");
}
function hideBanner() {
  els.banner.className = "banner info hidden";
}

function esc(value) {
  return String(value == null ? "" : value).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[c]);
}

/* ------------------------------------------------------------------ *
 * User selector
 * ------------------------------------------------------------------ */
async function loadUsers() {
  hideBanner();
  els.userSelect.innerHTML = '<option value="">Loading users…</option>';
  els.loadUsersBtn.disabled = true;
  try {
    const data = await apiGet("/v1/admin/users");
    const users = (data && data.users) || [];
    if (users.length === 0) {
      els.userSelect.innerHTML = '<option value="">No users found for this tenant</option>';
      showBanner(
        "No users found for tenant \"" + tenant() +
          "\". Seed data first with samples/data/seed_events.py.",
        "info"
      );
      return;
    }
    els.userSelect.innerHTML =
      '<option value="">— select a user (' + users.length + ") —</option>" +
      users
        .slice()
        .sort()
        .map((u) => '<option value="' + esc(u) + '">' + esc(u) + "</option>")
        .join("");
    showBanner("Loaded " + users.length + " user(s) for tenant \"" + tenant() + "\".", "info");
  } catch (err) {
    els.userSelect.innerHTML = '<option value="">— load failed —</option>';
    showBanner(err.message, "error");
  } finally {
    els.loadUsersBtn.disabled = false;
  }
}

/* ------------------------------------------------------------------ *
 * Orchestration — load everything for one user
 * ------------------------------------------------------------------ */
async function selectUser(userId) {
  if (!userId) return;
  hideBanner();
  // These three panels are independent; run them concurrently.
  await Promise.all([loadUserGraphAndTimeline(userId), loadProfile(userId), loadFeed(userId)]);
}

async function loadUserGraphAndTimeline(userId) {
  els.graphStatus.textContent = "";
  setPlaceholder(els.timeline, "Loading events…");
  try {
    const data = await apiGet(
      "/v1/admin/users/" + encodeURIComponent(userId) +
        "/events?days=" + windowDays() + "&limit=" + EVENT_LIMIT
    );
    const events = (data && data.events) || [];
    renderGraph(userId, events);
    renderTimeline(events);
  } catch (err) {
    els.graphStatus.textContent = err.message;
    els.graphStatus.className = "mini-status graph-stat err";
    setPlaceholder(els.timeline, err.message, true);
  }
}

/* ------------------------------------------------------------------ *
 * Graph view — nodes: user / applications / business objects.
 * Edges: user -> object (PERFORMED), aggregated per (action, object) so
 * thickness scales with how many times the action was performed.
 * ------------------------------------------------------------------ */
function renderGraph(userId, allEvents) {
  // Events arrive most-recent-first; draw at most GRAPH_EVENT_CAP of them so a
  // busy user doesn't spawn hundreds of object nodes and stall the layout.
  const capped = allEvents.length > GRAPH_EVENT_CAP;
  const events = capped ? allEvents.slice(0, GRAPH_EVENT_CAP) : allEvents;

  const nodes = new Map();
  const edges = new Map();

  nodes.set("user:" + userId, {
    data: { id: "user:" + userId, label: userId, kind: "user" },
  });

  for (const ev of events) {
    const app = ev.applicationId || "unknown-app";
    const appId = "app:" + app;
    if (!nodes.has(appId)) {
      nodes.set(appId, { data: { id: appId, label: app, kind: "app" } });
    }

    const hasObject = ev.objectType != null && ev.objectId != null;
    const objKey = hasObject ? ev.objectType + ":" + ev.objectId : "(none)";
    const objNodeId = "obj:" + app + ":" + objKey;
    if (hasObject && !nodes.has(objNodeId)) {
      nodes.set(objNodeId, {
        data: { id: objNodeId, label: objKey, kind: "object", app: app },
      });
    }

    // Edge target: the business object when present, else the application.
    const targetId = hasObject ? objNodeId : appId;
    const action = ev.actionType || "action";
    const edgeKey = action + "->" + targetId;
    if (!edges.has(edgeKey)) {
      edges.set(edgeKey, {
        data: {
          id: "edge:" + edges.size,
          source: "user:" + userId,
          target: targetId,
          action: action,
          count: 0,
        },
      });
    }
    edges.get(edgeKey).data.count += 1;

    // Link the object to its owning application so the graph reads as a tree.
    if (hasObject) {
      const linkKey = "belongs:" + objNodeId;
      if (!edges.has(linkKey)) {
        edges.set(linkKey, {
          data: {
            id: "link:" + edges.size,
            source: appId,
            target: objNodeId,
            action: "",
            count: 0,
            structural: true,
          },
        });
      }
    }
  }

  // --- colour helpers: each application gets a stable colour from the palette,
  // and its objects/edges inherit a tint of it so clusters read at a glance.
  const APP_PALETTE = [
    "#6ea8fe", "#4dd8a6", "#ffb454", "#ff7b9c",
    "#b892ff", "#38c6e0", "#f6c744", "#7bd88f",
  ];
  function hexToRgb(hex) {
    const h = hex.replace("#", "");
    return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
  }
  function lighten(hex, t) {
    const [r, g, b] = hexToRgb(hex);
    const m = (c) => Math.round(c + (255 - c) * t);
    return `rgb(${m(r)}, ${m(g)}, ${m(b)})`;
  }
  function rgba(hex, a) {
    const [r, g, b] = hexToRgb(hex);
    return `rgba(${r}, ${g}, ${b}, ${a})`;
  }

  const appColor = new Map();
  let appIdx = 0;
  for (const n of nodes.values()) {
    if (n.data.kind === "app") {
      appColor.set(n.data.label, APP_PALETTE[appIdx++ % APP_PALETTE.length]);
    }
  }
  const colorForApp = (app) => appColor.get(app) || "#8a97b8";

  // Paint nodes.
  for (const n of nodes.values()) {
    if (n.data.kind === "user") n.data.color = "#93b4ff";
    else if (n.data.kind === "app") n.data.color = colorForApp(n.data.label);
    else if (n.data.kind === "object") n.data.color = lighten(colorForApp(n.data.app), 0.28);
  }

  // Compute max count for thickness scaling, then paint edges by app + frequency.
  let maxCount = 1;
  for (const e of edges.values()) {
    if (!e.data.structural && e.data.count > maxCount) maxCount = e.data.count;
  }
  for (const e of edges.values()) {
    const target = nodes.get(e.data.target);
    const app = target ? (target.data.app || target.data.label) : null;
    const base = colorForApp(app);
    if (e.data.structural) {
      e.data.color = rgba(base, 0.35);
    } else {
      const strength = e.data.count / maxCount; // 0..1
      e.data.label = e.data.action + " ×" + e.data.count;
      e.data.width = 2 + strength * 12; // 2–14 px
      e.data.color = rgba(base, 0.5 + strength * 0.45); // brighter = more frequent
    }
  }

  const elements = [...nodes.values(), ...edges.values()];

  if (cy) {
    cy.destroy();
    cy = null;
  }
  cy = cytoscape({
    container: els.graph,
    elements: elements,
    minZoom: 0.15,
    maxZoom: 3.5,
    wheelSensitivity: 0.25,
    style: [
      {
        selector: "node",
        style: {
          label: "data(label)",
          "font-size": 10,
          "font-weight": 600,
          color: "#eaf0ff",
          "text-valign": "bottom",
          "text-margin-y": 6,
          "text-wrap": "wrap",
          "text-max-width": 130,
          "text-outline-color": "#0b1020",
          "text-outline-width": 2.5,
          "background-color": "data(color)",
          "border-width": 2,
          "border-color": "rgba(255,255,255,0.75)",
          "border-opacity": 0.8,
          width: 26,
          height: 26,
          "underlay-color": "data(color)",
          "underlay-padding": 6,
          "underlay-opacity": 0.35,
          "underlay-shape": "ellipse",
          "transition-property": "opacity, border-color, underlay-opacity",
          "transition-duration": "140ms",
        },
      },
      {
        selector: 'node[kind="user"]',
        style: { width: 60, height: 60, "font-size": 14, "font-weight": 700, "border-width": 3, "underlay-padding": 11, "underlay-opacity": 0.5 },
      },
      { selector: 'node[kind="app"]', style: { width: 42, height: 42, "font-weight": 700, "underlay-padding": 8, "underlay-opacity": 0.42 } },
      { selector: 'node[kind="object"]', style: { shape: "round-rectangle", width: 22, height: 22, "underlay-shape": "round-rectangle", "underlay-opacity": 0.25 } },
      {
        selector: "edge",
        style: {
          width: "data(width)",
          "line-color": "data(color)",
          "target-arrow-color": "data(color)",
          "target-arrow-shape": "triangle",
          "arrow-scale": 0.9,
          "curve-style": "bezier",
          "line-cap": "round",
          "z-index": 1,
          label: "data(label)",
          "font-size": 8,
          "font-weight": 600,
          color: "#c7d2ec",
          "text-rotation": "autorotate",
          "text-background-color": "#111a30",
          "text-background-opacity": 0.9,
          "text-background-padding": 3,
          "text-background-shape": "round-rectangle",
          "transition-property": "opacity",
          "transition-duration": "140ms",
        },
      },
      {
        selector: "edge[?structural]",
        style: {
          width: 1.5,
          "line-color": "data(color)",
          "line-style": "dashed",
          "target-arrow-shape": "none",
          label: "",
          "z-index": 0,
        },
      },
      { selector: ".faded", style: { opacity: 0.1, "text-opacity": 0.06 } },
      { selector: ".highlight", style: { "border-color": "#ffffff", "border-opacity": 1, "underlay-opacity": 0.65 } },
    ],
    layout: {
      name: "cose",
      animate: true,
      animationDuration: 650,
      padding: 42,
      nodeRepulsion: 16000,
      idealEdgeLength: 115,
      edgeElasticity: 120,
      gravity: 0.55,
      componentSpacing: 130,
      nestingFactor: 0.9,
      randomize: false,
    },
  });

  cy.one("layoutstop", () => cy.fit(undefined, 45));

  // Hover a node to spotlight it and its immediate neighbourhood.
  cy.on("mouseover", "node", (e) => {
    const near = e.target.closedNeighborhood();
    cy.elements().addClass("faded");
    near.removeClass("faded");
    near.nodes().addClass("highlight");
  });
  cy.on("mouseout", "node", () => cy.elements().removeClass("faded highlight"));

  renderGraphLegend(appColor);

  const objCount = [...nodes.values()].filter((n) => n.data.kind === "object").length;
  const appCount = [...nodes.values()].filter((n) => n.data.kind === "app").length;
  els.graphStatus.className = "mini-status graph-stat";
  const shown =
    events.length + " events · " + appCount + " apps · " + objCount + " objects";
  els.graphStatus.textContent = capped
    ? shown + " · showing most recent " + GRAPH_EVENT_CAP + " of " + allEvents.length
    : shown;
}

/* Build the legend: node-type key plus a colour chip per application. */
function renderGraphLegend(appColor) {
  if (!els.graphLegend) return;
  const chip = (color, label, round) =>
    `<span class="legend-item"><span class="swatch${round ? " sq" : ""}" style="background:${color}"></span>${label}</span>`;
  const kinds =
    chip("#93b4ff", "User") +
    chip("#8a97b8", "Application") +
    chip("#c7cede", "Business object", true);
  let apps = "";
  for (const [app, color] of appColor) apps += chip(color, app);
  els.graphLegend.innerHTML =
    `<div class="legend-row">${kinds}</div>` +
    (apps ? `<div class="legend-row apps"><span class="legend-label">Apps</span>${apps}</div>` : "") +
    `<div class="legend-note">Thicker, brighter edge = more frequent action · hover a node to focus</div>`;
}

/* ------------------------------------------------------------------ *
 * Timeline view — bucket events per day, draw an SVG bar chart so
 * clustering (Monday leave approvals, month-end timesheets) is visible.
 * ------------------------------------------------------------------ */
function renderTimeline(events) {
  if (events.length === 0) {
    setPlaceholder(els.timeline, "No events in the last " + windowDays() + " days.");
    els.timelineTip.textContent = "";
    return;
  }

  const buckets = new Map(); // dayKey -> count
  let minTime = Infinity;
  let maxTime = -Infinity;
  for (const ev of events) {
    const t = new Date(ev.eventTimestamp);
    if (isNaN(t.getTime())) continue;
    const dayKey = t.toISOString().slice(0, 10);
    buckets.set(dayKey, (buckets.get(dayKey) || 0) + 1);
    minTime = Math.min(minTime, t.getTime());
    maxTime = Math.max(maxTime, t.getTime());
  }
  if (buckets.size === 0) {
    setPlaceholder(els.timeline, "Events had no parseable timestamps.");
    return;
  }

  // Build a continuous day axis so gaps (empty weekends) stay visible.
  const start = new Date(new Date(minTime).toISOString().slice(0, 10));
  const end = new Date(new Date(maxTime).toISOString().slice(0, 10));
  const days = [];
  for (let d = new Date(start); d <= end; d.setUTCDate(d.getUTCDate() + 1)) {
    const key = d.toISOString().slice(0, 10);
    days.push({ key: key, count: buckets.get(key) || 0, dow: d.getUTCDay() });
  }

  const maxCount = Math.max(...days.map((d) => d.count), 1);
  const barW = 7;
  const gap = 1;
  const chartH = 140;
  const padTop = 10;
  const padBottom = 26;
  const width = days.length * (barW + gap) + 40;
  const height = chartH + padTop + padBottom;

  let bars = "";
  let monthTicks = "";
  let lastMonth = "";
  days.forEach((d, i) => {
    const x = 30 + i * (barW + gap);
    const h = d.count === 0 ? 0 : Math.max(2, (d.count / maxCount) * chartH);
    const y = padTop + chartH - h;
    const weekend = d.dow === 0 || d.dow === 6;
    const fill = d.count === 0 ? "#eef1f7" : weekend ? "#9aa7c6" : "#3457d5";
    bars +=
      '<rect x="' + x + '" y="' + y + '" width="' + barW + '" height="' + h +
      '" rx="1.5" fill="' + fill + '"><title>' + esc(d.key) + ": " + d.count +
      " event(s)</title></rect>";
    const month = d.key.slice(0, 7);
    if (month !== lastMonth) {
      lastMonth = month;
      monthTicks +=
        '<line x1="' + x + '" y1="' + padTop + '" x2="' + x + '" y2="' + (padTop + chartH) +
        '" stroke="#e2e6ee" stroke-width="1"/>' +
        '<text x="' + (x + 2) + '" y="' + (height - 8) +
        '" font-size="10" fill="#67728a">' + esc(month) + "</text>";
    }
  });

  els.timeline.innerHTML =
    '<svg viewBox="0 0 ' + width + " " + height + '" width="' + width + '" height="' + height +
    '" xmlns="http://www.w3.org/2000/svg">' +
    '<text x="4" y="' + (padTop + 8) + '" font-size="9" fill="#67728a">' + maxCount + "</text>" +
    monthTicks +
    bars +
    "</svg>";

  els.timelineTip.innerHTML =
    "Blue = weekday, grey = weekend, empty = no activity. Busiest day: <strong>" +
    esc(days.reduce((a, b) => (b.count > a.count ? b : a)).key) +
    "</strong> (" + maxCount + " events).";
}

/* ------------------------------------------------------------------ *
 * Profile (NLQ) + pattern list — endpoint 3
 * ------------------------------------------------------------------ */
async function loadProfile(userId) {
  els.profileText.innerHTML = '<span class="placeholder"><span class="spinner"></span> Loading profile…</span>';
  els.profileMeta.hidden = true;
  els.profileHint.textContent = "";
  els.patternHint.textContent = "";
  els.patternList.innerHTML = '<div class="placeholder"><span class="spinner"></span> Loading patterns…</div>';

  let data;
  try {
    data = await apiGet("/v1/users/" + encodeURIComponent(userId) + "/profile");
  } catch (err) {
    if (err.status === 404) {
      els.profileText.innerHTML =
        '<span class="placeholder">Not enough activity yet to generate a profile for <strong>' +
        esc(userId) + "</strong>.</span>";
      els.patternList.innerHTML =
        '<div class="placeholder">No patterns yet — this user needs more recorded activity.</div>';
      els.profileHint.textContent = "insufficient data";
      return;
    }
    els.profileText.innerHTML = '<span class="placeholder">' + esc(err.message) + "</span>";
    els.patternList.innerHTML = '<div class="placeholder">Could not load patterns.</div>';
    return;
  }

  renderProfileText(data);
  renderPatterns(data);
}

function renderProfileText(data) {
  els.profileText.textContent = data.profile || "(empty profile)";
  const parts = [];
  parts.push("<span><strong>" + esc(data.totalEvents) + "</strong> events analysed</span>");
  if (data.generatedAt) {
    parts.push("<span>Generated " + esc(formatTimestamp(data.generatedAt)) + "</span>");
  } else {
    parts.push("<span>Generated on demand (not yet persisted)</span>");
  }
  if (data.version != null) parts.push("<span>Profile v" + esc(data.version) + "</span>");
  els.profileMeta.innerHTML = parts.join("");
  els.profileMeta.hidden = false;
}

function renderPatterns(data) {
  const cards = [];
  const byApp = data.byApplication || {};

  for (const app of Object.keys(byApp).sort()) {
    for (const p of byApp[app]) {
      const conf = Math.round((p.confidence || 0) * 100);
      const meta = [p.frequency, p.typicalTime ? "around " + p.typicalTime : null]
        .filter(Boolean)
        .join(" · ");
      cards.push(
        '<div class="pattern-card">' +
          '<div class="ptype">Recurring action · ' + esc(app) + "</div>" +
          '<div class="ptitle"><code>' + esc(p.actionType) + "</code></div>" +
          '<div class="pmeta">' + esc(meta) +
          (p.countInPeriod != null ? " · " + esc(p.countInPeriod) + " times in period" : "") +
          "</div>" +
          confBar(conf) +
        "</div>"
      );
    }
  }

  for (const s of data.crossAppSequences || []) {
    const conf = Math.round((s.confidence || 0) * 100);
    cards.push(
      '<div class="pattern-card">' +
        '<div class="ptype seq">Cross-app sequence</div>' +
        '<div class="ptitle"><code>' + esc(s.triggerAction) + "</code> in " + esc(s.triggerApp) +
        " → <code>" + esc(s.followAction) + "</code> in " + esc(s.followApp) + "</div>" +
        '<div class="pmeta">within ' + esc(s.typicalGap) + "</div>" +
        confBar(conf) +
      "</div>"
    );
  }

  const objs = data.activeObjects || [];
  els.patternHint.textContent =
    cards.length + " pattern(s)" + (objs.length ? " · " + objs.length + " active objects" : "");

  els.patternList.innerHTML = cards.length
    ? '<div class="pattern-grid">' + cards.join("") + "</div>"
    : '<div class="placeholder">No recurring patterns detected yet for this user.</div>';
}

function confBar(conf) {
  const color = conf >= 80 ? "var(--good)" : conf >= 50 ? "var(--warn)" : "var(--bad)";
  return (
    '<div class="confbar"><span style="width:' + conf + "%;background:" + color + '"></span></div>' +
    '<div class="conflabel"><span>confidence</span><span>' + conf + "%</span></div>"
  );
}

/* ------------------------------------------------------------------ *
 * Event feed — endpoint 2, newest first
 * ------------------------------------------------------------------ */
async function loadFeed(userId) {
  els.feedHint.textContent = "";
  els.eventFeed.innerHTML =
    '<div class="placeholder"><span class="spinner"></span> Loading events…</div>';
  try {
    const data = await apiGet(
      "/v1/admin/users/" + encodeURIComponent(userId) +
        "/events?days=" + windowDays() + "&limit=" + EVENT_LIMIT
    );
    const events = ((data && data.events) || [])
      .slice()
      .sort((a, b) => new Date(b.eventTimestamp) - new Date(a.eventTimestamp));
    renderFeed(events, data && data.truncated);
  } catch (err) {
    els.eventFeed.innerHTML = '<div class="placeholder">' + esc(err.message) + "</div>";
  }
}

function renderFeed(events, truncated) {
  if (events.length === 0) {
    els.eventFeed.innerHTML = '<div class="placeholder">No events for this user.</div>';
    els.feedHint.textContent = "";
    return;
  }
  els.feedHint.textContent =
    (truncated ? "most recent " : "") +
    events.length +
    " events (last " +
    windowDays() +
    " days)";

  const rows = events
    .map((ev) => {
      const obj =
        ev.objectType != null && ev.objectId != null
          ? esc(ev.objectType) + ":" + esc(ev.objectId)
          : "—";
      return (
        "<tr>" +
        '<td class="ts">' + esc(formatTimestamp(ev.eventTimestamp)) + "</td>" +
        '<td><span class="tag">' + esc(ev.applicationId) + "</span></td>" +
        "<td>" + esc(ev.actionType) +
        (ev.actionCategory ? ' <span class="obj">(' + esc(ev.actionCategory) + ")</span>" : "") +
        "</td>" +
        '<td class="obj">' + obj + "</td>" +
        "</tr>"
      );
    })
    .join("");

  els.eventFeed.innerHTML =
    '<table class="events"><thead><tr>' +
    "<th>Timestamp</th><th>App</th><th>Action</th><th>Object</th>" +
    "</tr></thead><tbody>" + rows + "</tbody></table>";
}

/* ------------------------------------------------------------------ *
 * Utilities
 * ------------------------------------------------------------------ */
function setPlaceholder(node, text, isError) {
  node.innerHTML = '<div class="placeholder"' + (isError ? ' style="color:var(--bad)"' : "") + ">" +
    esc(text) + "</div>";
}

function formatTimestamp(iso) {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return String(iso);
  return d.toLocaleString(undefined, {
    year: "numeric", month: "short", day: "2-digit",
    hour: "2-digit", minute: "2-digit",
  });
}

/* ------------------------------------------------------------------ *
 * Wiring
 * ------------------------------------------------------------------ */
els.loadUsersBtn.addEventListener("click", loadUsers);
els.userSelect.addEventListener("change", (e) => selectUser(e.target.value));
els.refreshFeedBtn.addEventListener("click", () => {
  const u = els.userSelect.value;
  if (u) loadFeed(u);
});
if (els.fitGraphBtn) {
  els.fitGraphBtn.addEventListener("click", () => {
    if (cy) cy.animate({ fit: { padding: 45 }, duration: 300 });
  });
}
els.apiBase.addEventListener("keydown", (e) => {
  if (e.key === "Enter") loadUsers();
});

// Picking a known shop loads it immediately; "Other…" reveals a text input.
els.tenantId.addEventListener("change", () => {
  const isOther = els.tenantId.value === "__other__";
  els.customTenant.hidden = !isOther;
  if (isOther) {
    els.customTenant.focus();
  } else {
    loadUsers();
  }
});

// Changing the history window re-scopes every panel for the current user.
// Absent in the static demo, so guard it.
if (els.eventWindow) {
  els.eventWindow.addEventListener("change", () => {
    if (els.userSelect.value) selectUser(els.userSelect.value);
  });
}

els.customTenant.addEventListener("keydown", (e) => {
  if (e.key === "Enter") loadUsers();
});
els.customTenant.addEventListener("blur", () => {
  if (els.customTenant.value.trim()) loadUsers();
});

// Attempt an initial user load with the defaults, honoring ?tenant= and ?user=
// deep links (shareable views; also drives headless screenshotting).
async function initFromUrl() {
  const params = new URLSearchParams(location.search);
  const t = params.get("tenant");
  if (t && els.tenantId && [...els.tenantId.options].some((o) => o.value === t)) {
    els.tenantId.value = t;
    if (els.customTenant) els.customTenant.hidden = els.tenantId.value !== "__other__";
  }
  await loadUsers();
  const u = params.get("user");
  if (u && [...els.userSelect.options].some((o) => o.value === u)) {
    els.userSelect.value = u;
    await selectUser(u);
  }
}
window.addEventListener("DOMContentLoaded", initFromUrl);

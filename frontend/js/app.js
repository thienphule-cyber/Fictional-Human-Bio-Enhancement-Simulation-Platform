/**
 * Router and shell for the Nebula dashboard.
 *
 * Pages are ES modules under js/ that export render(container). The shell builds
 * the navigation, shows the active page and surfaces server connectivity so a
 * stopped backend is obvious instead of silently producing empty panels.
 */

import { api } from "./api.js";
import { el, errorState, loadingState, toastError } from "./ui.js";

const ROUTES = [
  { id: "dashboard", label: "Dashboard", module: "./dashboard.js" },
  { id: "profiles", label: "Profiles", module: "./profiles.js" },
  { id: "gases", label: "Nebula Gas", module: "./gases.js" },
  { id: "compatibility", label: "Compatibility", module: "./compatibility.js" },
  { id: "devices", label: "Devices", module: "./devices.js" },
  { id: "simulation", label: "Simulation", module: "./simulation.js" },
  { id: "mutations", label: "Mutations", module: "./mutations.js" },
  { id: "analytics", label: "Analytics", module: "./analytics.js" },
];

const moduleCache = new Map();
let currentRoute = null;
let currentCleanup = null;

function routeFromHash() {
  const id = window.location.hash.replace(/^#\/?/, "").trim();
  return ROUTES.find((route) => route.id === id) ?? ROUTES[0];
}

async function loadRouteModule(route) {
  if (!moduleCache.has(route.id)) {
    moduleCache.set(route.id, await import(route.module));
  }
  return moduleCache.get(route.id);
}

function buildNav(activeId) {
  return el("nav", { class: "app-nav", "aria-label": "Primary" },
    ROUTES.map((route) =>
      el("a", {
        class: route.id === activeId ? "app-nav-link is-active" : "app-nav-link",
        href: `#/${route.id}`,
        text: route.label,
        "aria-current": route.id === activeId ? "page" : null,
      }),
    ),
  );
}

function buildStatusBar(meta) {
  if (!meta) {
    return el("div", { class: "status-bar status-bar-error" }, [
      el("span", { text: "Backend unreachable. Start it with: python -m backend.main" }),
    ]);
  }

  return el("div", { class: "status-bar" }, [
    el("span", { class: "status-dot", "aria-hidden": "true" }),
    el("span", { text: `${meta.app} v${meta.version}` }),
    el("span", { class: "status-sep", text: "·" }),
    el("span", { text: `${meta.host}:${meta.port}` }),
    el("span", { class: "status-sep", text: "·" }),
    el("span", { text: meta.debug ? "debug" : "release" }),
  ]);
}

async function mount() {
  const shell = document.getElementById("app");
  if (!shell) {
    console.error("Nebula: #app container is missing from index.html");
    return;
  }

  const route = routeFromHash();
  currentRoute = route.id;

  document.title = `${route.label} · Nebula`;

  const content = el("main", { class: "app-main", id: "app-content" });
  const nav = buildNav(route.id);

  let meta = null;
  try {
    meta = await api.meta();
  } catch (error) {
    if (error?.status === 0) {
      toastError(error);
    }
  }

  shell.replaceChildren(
    el("header", { class: "app-header" }, [
      el("div", { class: "app-brand" }, [
        el("span", { class: "app-brand-mark", "aria-hidden": "true", text: "◈" }),
        el("span", { class: "app-brand-name", text: "NEBULA" }),
        el("span", { class: "app-brand-tag", text: "Bio-Enhancement Simulation" }),
      ]),
      nav,
      buildStatusBar(meta),
    ]),
    content,
    el("footer", { class: "app-footer" }, [
      el("p", { text: "Fictional simulation model for demonstration only. Not medical, chemical, or physical guidance." }),
    ]),
  );

  content.replaceChildren(loadingState("Opening page…"));

  try {
    const module = await loadRouteModule(route);
    if (typeof module.render !== "function") {
      throw new Error(`Page module ${route.module} does not export render(container)`);
    }
    await module.render(content);
    if (typeof module.cleanup === "function") {
      currentCleanup = module.cleanup;
    }
  } catch (error) {
    if (error instanceof TypeError && String(error.message).includes("Failed to fetch dynamically imported module")) {
      content.replaceChildren(errorState(
        `Could not load ${route.module}. Check that the file exists under frontend/js/.`,
      ));
    } else {
      toastError(error);
      content.replaceChildren(errorState(error.message ?? "Page failed to load."));
    }
  }
}

function navigate() {
  if (currentRoute === routeFromHash().id) return;
  if (typeof currentCleanup === "function") {
    try { currentCleanup(); } catch { /* Cleanup must never block navigation. */ }
    currentCleanup = null;
  }
  mount();
}

export function start() {
  window.addEventListener("hashchange", navigate);

  if (!window.location.hash) {
    window.location.replace(`${window.location.pathname}#/dashboard`);
  }

  mount();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", start, { once: true });
} else {
  start();
}

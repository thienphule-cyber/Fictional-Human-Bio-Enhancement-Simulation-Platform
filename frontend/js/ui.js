/**
 * Small DOM, formatting and feedback helpers shared by every page.
 *
 * No framework: pages build real nodes, so nothing is parsed from HTML strings
 * and user-supplied text never becomes markup.
 */

const TOAST_HOST_ID = "nebula-toast-host";

export function qs(selector, scope = document) {
  return scope.querySelector(selector);
}

export function qsa(selector, scope = document) {
  return Array.from(scope.querySelectorAll(selector));
}

/**
 * Create an element.
 * `attrs.text` sets textContent, `attrs.html` is never used on purpose.
 */
export function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);

  for (const [key, value] of Object.entries(attrs)) {
    if (value === undefined || value === null || value === false) continue;

    if (key === "text") {
      node.textContent = String(value);
    } else if (key === "class") {
      node.className = value;
    } else if (key === "dataset") {
      Object.assign(node.dataset, value);
    } else if (key === "style" && typeof value === "object") {
      Object.assign(node.style, value);
    } else if (key.startsWith("on") && typeof value === "function") {
      node.addEventListener(key.slice(2).toLowerCase(), value);
    } else if (key === "value") {
      node.value = value;
    } else if (key === "checked" || key === "disabled" || key === "selected") {
      node[key] = Boolean(value);
    } else {
      node.setAttribute(key, String(value));
    }
  }

  for (const child of [].concat(children)) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }

  return node;
}

export function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
  return node;
}

export function replaceChildren(node, children) {
  clear(node);
  for (const child of [].concat(children)) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

/* -------------------------------------------------------------------------- */
/* Formatting                                                                  */
/* -------------------------------------------------------------------------- */

const NUMBER_FORMAT = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });
const COMPACT_FORMAT = new Intl.NumberFormat("en-US", { notation: "compact" });

export function formatNumber(value, digits = 2) {
  if (value === null || value === undefined || value === "") return "—";
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "—";
  if (digits === 0) return new Intl.NumberFormat("en-US").format(numeric);
  return numeric.toFixed(digits).replace(/\.?0+$/, "") || "0";
}

export function formatFixed(value, digits = 2) {
  if (value === null || value === undefined || value === "") return "—";
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "—";
  return numeric.toFixed(digits);
}

export function formatPercent(value, digits = 1) {
  if (value === null || value === undefined || value === "") return "—";
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "—";
  return `${numeric.toFixed(digits)}%`;
}

export function formatDelta(value, digits = 2) {
  if (value === null || value === undefined) return "—";
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "—";
  const sign = numeric > 0 ? "+" : "";
  return `${sign}${numeric.toFixed(digits)}`;
}

export function formatDateTime(value) {
  if (!value) return "—";
  // SQLite CURRENT_TIMESTAMP is UTC without a timezone marker.
  const iso = String(value).includes("T") ? value : `${String(value).replace(" ", "T")}Z`;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatCount(value) {
  if (value === null || value === undefined) return "—";
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "—";
  return COMPACT_FORMAT.format(numeric);
}

export function titleCase(value) {
  if (!value) return "";
  return String(value)
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

/* -------------------------------------------------------------------------- */
/* Small display pieces                                                        */
/* -------------------------------------------------------------------------- */

export function badge(text, tone = "neutral") {
  return el("span", { class: `badge badge-${tone}`, text });
}

export function parameterBar(value, color = "#38bdf8") {
  const numeric = Math.min(100, Math.max(0, Number(value) || 0));
  return el("div", { class: "meter", role: "img", "aria-label": `${formatNumber(numeric)} of 100` }, [
    el("div", {
      class: "meter-fill",
      style: { width: `${numeric}%`, background: color },
    }),
    el("span", { class: "meter-value", text: formatNumber(numeric) }),
  ]);
}

export function statCard(label, value, hint = null) {
  return el("article", { class: "stat-card" }, [
    el("p", { class: "stat-label", text: label }),
    el("p", { class: "stat-value", text: value }),
    hint ? el("p", { class: "stat-hint", text: hint }) : null,
  ]);
}

export function emptyState(message, actionLabel = null, onAction = null) {
  return el("div", { class: "empty-state" }, [
    el("p", { text: message }),
    actionLabel && onAction
      ? el("button", { class: "btn", type: "button", text: actionLabel, onClick: onAction })
      : null,
  ]);
}

export function loadingState(message = "Loading simulation data…") {
  return el("div", { class: "loading-state" }, [
    el("span", { class: "spinner", "aria-hidden": "true" }),
    el("span", { text: message }),
  ]);
}

export function errorState(message, onRetry = null) {
  return el("div", { class: "error-state", role: "alert" }, [
    el("p", { text: message }),
    onRetry
      ? el("button", { class: "btn", type: "button", text: "Retry", onClick: onRetry })
      : null,
  ]);
}

/**
 * Build a table from column descriptors.
 * columns: [{ label, render(row) }]
 */
export function dataTable(columns, rows, { empty = "No records yet." } = {}) {
  if (!rows || rows.length === 0) return emptyState(empty);

  return el("div", { class: "table-wrap" }, [
    el("table", { class: "data-table" }, [
      el("thead", {}, [
        el("tr", {}, columns.map((column) => el("th", { scope: "col", text: column.label }))),
      ]),
      el("tbody", {}, rows.map((row) =>
        el("tr", {}, columns.map((column) =>
          el("td", { dataset: { label: column.label } }, [column.render(row)]),
        )),
      )),
    ]),
  ]);
}

/* -------------------------------------------------------------------------- */
/* Forms                                                                       */
/* -------------------------------------------------------------------------- */

export function field(label, control, hint = null) {
  const id = control.id || `field-${Math.random().toString(36).slice(2, 9)}`;
  control.id = id;

  return el("label", { class: "field", for: id }, [
    el("span", { class: "field-label", text: label }),
    control,
    hint ? el("span", { class: "field-hint", text: hint }) : null,
  ]);
}

export function select(options, { value = "", name = "" } = {}) {
  return el(
    "select",
    { name },
    options.map((option) => {
      const optionValue = typeof option === "string" ? option : option.value;
      const label = typeof option === "string" ? titleCase(option) : option.label;
      const node = el("option", { value: optionValue, text: label });
      if (String(optionValue) === String(value)) node.selected = true;
      return node;
    }),
  );
}

export function numberInput({ value = 0, min = 0, max = 100, step = 1, name = "" } = {}) {
  return el("input", { type: "number", value, min, max, step, name });
}

export function textInput({ value = "", placeholder = "", name = "", maxLength = null } = {}) {
  const attrs = { type: "text", value, placeholder, name };
  if (maxLength) attrs.maxlength = maxLength;
  return el("input", attrs);
}

export function formValues(form) {
  const result = {};
  for (const [key, value] of new FormData(form).entries()) {
    result[key] = typeof value === "string" ? value.trim() : value;
  }
  return result;
}

export function setBusy(button, busy, busyLabel = "Working…") {
  if (!button) return;
  if (busy) {
    button.dataset.label = button.textContent;
    button.textContent = busyLabel;
    button.disabled = true;
  } else {
    button.textContent = button.dataset.label ?? button.textContent;
    button.disabled = false;
    delete button.dataset.label;
  }
}

/* -------------------------------------------------------------------------- */
/* Toasts                                                                      */
/* -------------------------------------------------------------------------- */

function toastHost() {
  let host = document.getElementById(TOAST_HOST_ID);
  if (!host) {
    host = el("div", { id: TOAST_HOST_ID, class: "toast-host", role: "status", "aria-live": "polite" });
    document.body.append(host);
  }
  return host;
}

export function toast(message, tone = "info", timeout = 4200) {
  const node = el("div", { class: `toast toast-${tone}`, text: message });
  toastHost().append(node);

  const remove = () => {
    node.classList.add("toast-leaving");
    window.setTimeout(() => node.remove(), 220);
  };

  node.addEventListener("click", remove);
  window.setTimeout(remove, timeout);
  return node;
}

export function toastError(error) {
  const message = error?.message ?? String(error);
  toast(message, "error", 7000);
}

/**
 * Chart.js wrappers.
 *
 * Chart.js is loaded from a CDN in index.html as a global, so every helper here
 * checks for it and degrades to a plain message instead of throwing.
 */

import { PARAMETERS, RISK_STATUSES, riskColor } from "./constants.js";
import { el, emptyState } from "./ui.js";

const registry = new WeakMap();

function chartLib() {
  return window.Chart ?? null;
}

export function isChartAvailable() {
  return chartLib() !== null;
}

const BASE_OPTIONS = {
  responsive: true,
  maintainAspectRatio: false,
  interaction: { mode: "index", intersect: false },
  plugins: {
    legend: {
      labels: { color: "#cbd5e1", boxWidth: 12, usePointStyle: true },
    },
    tooltip: {
      backgroundColor: "rgba(15, 23, 42, 0.94)",
      borderColor: "rgba(148, 163, 184, 0.35)",
      borderWidth: 1,
      padding: 10,
    },
  },
  scales: {
    x: {
      ticks: { color: "#94a3b8" },
      grid: { color: "rgba(148, 163, 184, 0.12)" },
    },
    y: {
      ticks: { color: "#94a3b8" },
      grid: { color: "rgba(148, 163, 184, 0.12)" },
    },
  },
};

function mergeOptions(overrides = {}) {
  return {
    ...BASE_OPTIONS,
    ...overrides,
    plugins: { ...BASE_OPTIONS.plugins, ...(overrides.plugins ?? {}) },
    scales: overrides.scales === undefined
      ? BASE_OPTIONS.scales
      : { ...BASE_OPTIONS.scales, ...overrides.scales },
  };
}

function canvasHost(canvas, height) {
  const host = el("div", { class: "chart-host", style: { height: `${height}px` } });
  host.append(canvas);
  return host;
}

function makeCanvas() {
  return el("canvas", { role: "img" });
}

function teardown(canvas) {
  const existing = registry.get(canvas);
  if (existing) {
    existing.destroy();
    registry.delete(canvas);
  }
}

export function destroyChart(canvas) {
  if (canvas) teardown(canvas);
}

/**
 * Line chart of the eight biological parameters across simulation ticks.
 * trends is the payload of /api/analytics/sessions/{id}/trends.
 */
export function parametersLineChart(trends, { height = 320, only = null } = {}) {
  const Chart = chartLib();
  if (!Chart) return emptyState("Chart.js failed to load, so this graph is unavailable.");

  const canvas = makeCanvas();
  const keys = only ?? PARAMETERS.map((parameter) => parameter.key);

  const chart = new Chart(canvas, {
    type: "line",
    data: {
      labels: trends.labels.map((tick) => `Tick ${tick}`),
      datasets: PARAMETERS.filter((parameter) => keys.includes(parameter.key)).map(
        (parameter) => ({
          label: parameter.short,
          data: trends.datasets[parameter.key] ?? [],
          borderColor: parameter.color,
          backgroundColor: `${parameter.color}22`,
          borderWidth: 2,
          pointRadius: 0,
          pointHoverRadius: 4,
          tension: 0.3,
          fill: false,
        }),
      ),
    },
    options: mergeOptions({
      scales: {
        y: {
          min: 0,
          max: 100,
          ticks: { color: "#94a3b8" },
          grid: { color: "rgba(148, 163, 184, 0.12)" },
        },
      },
    }),
  });

  registry.set(canvas, chart);
  return canvasHost(canvas, height);
}

/**
 * Risk level trend across hazard assessments, coloured per level.
 */
export function riskLineChart(assessments, { height = 240 } = {}) {
  const Chart = chartLib();
  if (!Chart) return emptyState("Chart.js failed to load, so this graph is unavailable.");
  if (!assessments || assessments.length === 0) {
    return emptyState("No hazard assessments recorded for this session yet.");
  }

  const canvas = makeCanvas();
  const chart = new Chart(canvas, {
    type: "line",
    data: {
      labels: assessments.map((item) => `Tick ${item.tick}`),
      datasets: [
        {
          label: "Risk Level",
          data: assessments.map((item) => item.risk_level),
          borderColor: "#f97316",
          backgroundColor: "rgba(249, 115, 22, 0.18)",
          borderWidth: 2,
          pointRadius: 3,
          stepped: true,
          fill: true,
        },
      ],
    },
    options: mergeOptions({
      plugins: { legend: { display: false } },
      scales: {
        y: {
          min: 0,
          max: 5,
          ticks: {
            color: "#94a3b8",
            stepSize: 1,
            callback: (value) => RISK_STATUSES[value] ?? value,
          },
          grid: { color: "rgba(148, 163, 184, 0.12)" },
        },
      },
    }),
  });

  registry.set(canvas, chart);
  return canvasHost(canvas, height);
}

/**
 * Bar chart comparing one value across sessions (used on the Analytics page).
 * points: [{ label, value }]
 */
export function comparisonBarChart(points, { label = "Value", height = 300, color = "#38bdf8" } = {}) {
  const Chart = chartLib();
  if (!Chart) return emptyState("Chart.js failed to load, so this graph is unavailable.");
  if (!points || points.length === 0) return emptyState("Nothing to compare yet.");

  const canvas = makeCanvas();
  const chart = new Chart(canvas, {
    type: "bar",
    data: {
      labels: points.map((point) => point.label),
      datasets: [
        {
          label,
          data: points.map((point) => point.value),
          backgroundColor: points.map((point) => point.color ?? color),
          borderRadius: 6,
          borderSkipped: false,
        },
      ],
    },
    options: mergeOptions({ plugins: { legend: { display: false } } }),
  });

  registry.set(canvas, chart);
  return canvasHost(canvas, height);
}

/**
 * Doughnut chart of grouped counts, e.g. sessions by status.
 * entries: [[label, count], ...]
 */
export function distributionChart(entries, { height = 260, colors = null } = {}) {
  const Chart = chartLib();
  if (!Chart) return emptyState("Chart.js failed to load, so this graph is unavailable.");
  if (!entries || entries.length === 0) return emptyState("No data recorded yet.");

  const canvas = makeCanvas();
  const chart = new Chart(canvas, {
    type: "doughnut",
    data: {
      labels: entries.map(([label]) => label),
      datasets: [
        {
          data: entries.map(([, count]) => count),
          backgroundColor: entries.map(([label], index) =>
            colors?.[index] ?? riskColor(index) ?? "#38bdf8",
          ),
          borderColor: "rgba(15, 23, 42, 0.9)",
          borderWidth: 2,
        },
      ],
    },
    options: mergeOptions({
      cutout: "58%",
      scales: {},
      plugins: { legend: { position: "bottom", labels: { color: "#cbd5e1", usePointStyle: true } } },
    }),
  });

  registry.set(canvas, chart);
  return canvasHost(canvas, height);
}

/**
 * Horizontal breakdown of the eight parameters for one snapshot.
 */
export function parameterRadarChart(parameters, { height = 300 } = {}) {
  const Chart = chartLib();
  if (!Chart) return emptyState("Chart.js failed to load, so this graph is unavailable.");
  if (!parameters) return emptyState("No biological snapshot available.");

  const canvas = makeCanvas();
  const chart = new Chart(canvas, {
    type: "radar",
    data: {
      labels: PARAMETERS.map((parameter) => parameter.short),
      datasets: [
        {
          label: "Current profile",
          data: PARAMETERS.map((parameter) => Number(parameters[parameter.key] ?? 0)),
          borderColor: "#38bdf8",
          backgroundColor: "rgba(56, 189, 248, 0.22)",
          borderWidth: 2,
          pointRadius: 3,
        },
      ],
    },
    options: mergeOptions({
      scales: {
        r: {
          min: 0,
          max: 100,
          angleLines: { color: "rgba(148, 163, 184, 0.18)" },
          grid: { color: "rgba(148, 163, 184, 0.18)" },
          pointLabels: { color: "#cbd5e1" },
          ticks: { display: false },
        },
      },
    }),
  });

  registry.set(canvas, chart);
  return canvasHost(canvas, height);
}

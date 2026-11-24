import { api } from "./api.js";
import { PARAMETERS, RISK_STATUSES, riskColor, classColor } from "./constants.js";
import {
  badge, dataTable, el, emptyState, errorState, formatDateTime, formatNumber,
  loadingState, parameterBar, qs, statCard, toastError,
} from "./ui.js";
import { distributionChart } from "./charts.js";

export async function render(container) {
  container.replaceChildren(loadingState("Loading dashboard…"));

  try {
    const [stats, activity] = await Promise.all([
      api.analytics.statistics(),
      api.analytics.recent(8),
    ]);

    const counts = stats.counts ?? {};
    const cards = el("section", { class: "stats-grid" }, [
      statCard("Human Profiles", counts.profiles ?? 0),
      statCard("Nebula Gases", counts.gases ?? 0),
      statCard("Control Devices", counts.devices ?? 0),
      statCard("Simulation Sessions", counts.sessions ?? 0),
      statCard("Enhancement Ticks", counts.metric_rows ?? 0),
      statCard("Hazard Assessments", counts.hazard_assessments ?? 0),
    ]);

    const statusEntries = Object.entries(stats.sessions_by_status ?? {});
    const classEntries = Object.entries(stats.profiles_by_physical_class ?? {})
      .sort(([a], [b]) => Number(a) - Number(b))
      .map(([key, value]) => [`Class ${key}`, value]);

    const sessionsTable = dataTable(
      [
        { label: "Session", render: (row) => row.session_code },
        { label: "Subject", render: (row) => row.subject_code },
        { label: "Gas", render: (row) => row.gas_code },
        { label: "Hazard", render: (row) => badge(`Level ${row.hazard_level}`, `risk-${row.hazard_level}`) },
        { label: "Status", render: (row) => badge(row.status, row.status.toLowerCase().replaceAll(" ", "-")) },
        { label: "Ticks", render: (row) => row.current_tick },
        { label: "Created", render: (row) => formatDateTime(row.created_at) },
      ],
      activity,
      { empty: "No sessions yet. Create a profile, gas, device, and simulation to get started." },
    );

    container.replaceChildren(
      el("div", { class: "page-stack" }, [
        el("section", { class: "page-heading" }, [
          el("div", {}, [
            el("p", { class: "eyebrow", text: "SYSTEM OVERVIEW" }),
            el("h1", { text: "Nebula Dashboard" }),
            el("p", { class: "muted", text: "A live overview of fictional simulation records and system activity." }),
          ]),
          el("button", { class: "btn btn-secondary", type: "button", text: "Refresh", onClick: () => render(container) }),
        ]),
        cards,
        el("section", { class: "dashboard-grid" }, [
          el("article", { class: "panel" }, [
            el("div", { class: "panel-heading" }, [
              el("h2", { text: "Sessions by Status" }),
              el("span", { class: "muted", text: `${Object.values(stats.sessions_by_status ?? {}).reduce((a, b) => a + b, 0)} total` }),
            ]),
            statusEntries.length ? distributionChart(statusEntries, { height: 270 }) : emptyState("No session data yet."),
          ]),
          el("article", { class: "panel" }, [
            el("div", { class: "panel-heading" }, [
              el("h2", { text: "Profiles by Physical Class" }),
              el("span", { class: "muted", text: `${Object.values(stats.profiles_by_physical_class ?? {}).reduce((a, b) => a + b, 0)} total` }),
            ]),
            classEntries.length
              ? distributionChart(classEntries, { height: 270, colors: classEntries.map((_, index) => classColor(index)) })
              : emptyState("No profile data yet."),
          ]),
        ]),
        el("section", { class: "panel" }, [
          el("div", { class: "panel-heading" }, [
            el("h2", { text: "Recent Sessions" }),
            el("span", { class: "muted", text: "Most recently created" }),
          ]),
          sessionsTable,
        ]),
        el("section", { class: "panel" }, [
          el("div", { class: "panel-heading" }, [
            el("h2", { text: "Biological Parameter Reference" }),
            el("span", { class: "muted", text: "Fictional 0–100 model scale" }),
          ]),
          el("div", { class: "parameter-grid" }, PARAMETERS.map((parameter) =>
            el("div", { class: "parameter-row" }, [
              el("span", { text: parameter.label }),
              parameterBar(50, parameter.color),
            ]),
          )),
        ]),
      ]),
    );
  } catch (error) {
    toastError(error);
    container.replaceChildren(errorState(error.message, () => render(container)));
  }
}

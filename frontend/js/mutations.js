import { api } from "./api.js";
import { MUTATION_LEVELS, RISK_STATUSES } from "./constants.js";
import {
  badge, dataTable, el, emptyState, errorState, formatDateTime, formatNumber,
  loadingState, statCard, toastError,
} from "./ui.js";

export async function render(container) {
  container.replaceChildren(loadingState("Loading mutation records…"));
  try {
    const [mutations, hazardHistory] = await Promise.all([
      api.analytics.mutationHistory(null, 100),
      api.analytics.hazardHistory(null, 100),
    ]);

    const peakLevel = mutations.reduce((peak, row) => Math.max(peak, row.mutation_level), 0);
    const byType = {};
    for (const row of mutations) {
      if (!row.mutation_type || row.mutation_type === "None") continue;
      byType[row.mutation_type] = (byType[row.mutation_type] ?? 0) + 1;
    }

    container.replaceChildren(
      el("div", { class: "page-stack" }, [
        el("section", { class: "page-heading" }, [
          el("div", {}, [
            el("p", { class: "eyebrow", text: "MUTATION LOG" }),
            el("h1", { text: "Mutations & Hazard" }),
            el("p", { class: "muted", text: "Fictional transformation records. Levels are model labels, not medical findings." }),
          ]),
          el("button", { class: "btn btn-secondary", type: "button", text: "Refresh", onClick: () => render(container) }),
        ]),
        el("section", { class: "stats-grid" }, [
          statCard("Mutation Records", mutations.length),
          statCard("Peak Level", `${peakLevel} · ${MUTATION_LEVELS[peakLevel] ?? ""}`),
          statCard("Distinct Types", Object.keys(byType).length),
          statCard("Hazard Assessments", hazardHistory.length),
        ]),
        el("section", { class: "panel" }, [
          el("h2", { text: "Recent Mutations" }),
          dataTable([
            { label: "Session", render: (row) => row.session_code },
            { label: "Tick", render: (row) => row.tick },
            { label: "Type", render: (row) => row.mutation_type },
            { label: "Level", render: (row) => badge(`${row.mutation_level} · ${row.mutation_level_name}`, `risk-${row.mutation_level}`) },
            { label: "Risk", render: (row) => formatNumber(row.mutation_risk) },
            { label: "Stability", render: (row) => formatNumber(row.mutation_stability) },
            { label: "Recorded", render: (row) => formatDateTime(row.recorded_at) },
          ], mutations, { empty: "No mutation records yet. Mutations appear only when a tick produces level 1 or higher." }),
        ]),
        el("section", { class: "panel" }, [
          el("h2", { text: "Recent Hazard Assessments" }),
          dataTable([
            { label: "Session", render: (row) => row.session_code },
            { label: "Tick", render: (row) => row.tick },
            { label: "Risk", render: (row) => badge(`L${row.risk_level} · ${row.risk_status}`, `risk-${row.risk_level}`) },
            { label: "Stability", render: (row) => row.stability_status },
            { label: "Shutdown", render: (row) => row.shutdown_triggered ? badge("Recommended", "danger") : badge("No", "success") },
            { label: "Assessed", render: (row) => formatDateTime(row.assessed_at) },
          ], hazardHistory, { empty: "No hazard assessments yet. Run an assessment from the Simulation page." }),
        ]),
      ]),
    );
  } catch (error) {
    toastError(error);
    container.replaceChildren(errorState(error.message, () => render(container)));
  }
}

import { api } from "./api.js";
import { PARAMETERS, MUTATION_LEVELS, RISK_STATUSES } from "./constants.js";
import {
  badge, dataTable, el, emptyState, errorState, field, formatDateTime,
  formatDelta, formatFixed, formatNumber, loadingState, select, statCard,
  toast, toastError,
} from "./ui.js";
import { comparisonBarChart, distributionChart, parametersLineChart, riskLineChart } from "./charts.js";

async function renderOverview(host) {
  host.replaceChildren(loadingState("Loading platform statistics…"));
  try {
    const [stats, activity] = await Promise.all([
      api.analytics.statistics(),
      api.analytics.recent(10),
    ]);

    const counts = stats.counts ?? {};
    const riskEntries = Object.entries(stats.assessments_by_risk_level ?? {})
      .sort(([a], [b]) => Number(a) - Number(b))
      .map(([level, total]) => [`L${level} ${RISK_STATUSES[Number(level)] ?? ""}`.trim(), total]);

    host.replaceChildren(
      el("div", { class: "page-stack" }, [
        el("section", { class: "stats-grid" }, [
          statCard("Profiles", counts.profiles ?? 0),
          statCard("Gases", counts.gases ?? 0),
          statCard("Devices", counts.devices ?? 0),
          statCard("Sessions", counts.sessions ?? 0),
          statCard("Compatibility Records", counts.compatibility_records ?? 0),
          statCard("Enhancement Rows", counts.enhancement_records ?? 0),
          statCard("Mutation Rows", counts.mutation_records ?? 0),
          statCard("Metric Rows", counts.metric_rows ?? 0),
        ]),
        el("section", { class: "dashboard-grid" }, [
          el("article", { class: "panel" }, [
            el("h2", { text: "Assessments by Risk Level" }),
            riskEntries.length ? distributionChart(riskEntries, { height: 280 }) : emptyState("No hazard assessments yet."),
          ]),
          el("article", { class: "panel" }, [
            el("h2", { text: "Sessions by Status" }),
            Object.entries(stats.sessions_by_status ?? {}).length
              ? distributionChart(Object.entries(stats.sessions_by_status ?? {}), { height: 280 })
              : emptyState("No sessions yet."),
          ]),
        ]),
        el("section", { class: "panel" }, [
          el("h2", { text: "Recent Activity" }),
          dataTable([
            { label: "Session", render: (row) => row.session_code },
            { label: "Subject", render: (row) => row.subject_code },
            { label: "Status", render: (row) => badge(row.status, row.status.toLowerCase().replaceAll(" ", "-")) },
            { label: "Ticks", render: (row) => row.current_tick },
            { label: "Created", render: (row) => formatDateTime(row.created_at) },
          ], activity, { empty: "No activity recorded yet." }),
        ]),
      ]),
    );
  } catch (error) {
    toastError(error);
    host.replaceChildren(errorState(error.message, () => renderOverview(host)));
  }
}

async function renderTrends(host, sessions) {
  if (!sessions.length) {
    host.replaceChildren(emptyState("Create a simulation session before exploring trends."));
    return;
  }

  const selector = el("select", { name: "session_id" }, sessions.map((session) =>
    el("option", { value: session.id, text: `${session.session_code} · ${session.status}` }),
  ));
  const chartHost = el("div", { class: "page-stack" });
  const deltaHost = el("div", { class: "page-stack" });

  const load = async () => {
    chartHost.replaceChildren(loadingState("Loading trend data…"));
    try {
      const sessionId = Number(selector.value);
      const trends = await api.analytics.trends(sessionId);
      const deltas = await api.analytics.deltas(sessionId);

      if (!trends.ticks) {
        chartHost.replaceChildren(emptyState("This session has no recorded ticks yet. Run a step in the Simulation page."));
        deltaHost.replaceChildren();
        return;
      }

      chartHost.replaceChildren(
        el("section", { class: "panel" }, [
          el("div", { class: "panel-heading" }, [
            el("h2", { text: "Biological Parameter Trends" }),
            badge(`${trends.ticks} ticks`),
          ]),
          parametersLineChart(trends, { height: 360 }),
        ]),
      );

      deltaHost.replaceChildren(
        el("section", { class: "panel" }, [
          el("h2", { text: "Change Across Session" }),
          dataTable([
            { label: "Parameter", render: (row) => row.label },
            { label: "First", render: (row) => formatNumber(row.first) },
            { label: "Last", render: (row) => formatNumber(row.last) },
            { label: "Delta", render: (row) => badge(formatDelta(row.delta), row.delta >= 0 ? "success" : "danger") },
          ], PARAMETERS.map((parameter) => ({
            label: parameter.label,
            first: deltas.first?.[parameter.key],
            last: deltas.last?.[parameter.key],
            delta: deltas.delta?.[parameter.key] ?? 0,
          }))),
        ]),
      );
    } catch (error) {
      toastError(error);
      chartHost.replaceChildren(errorState(error.message, load));
    }
  };

  selector.addEventListener("change", load);
  host.replaceChildren(
    el("div", { class: "page-stack" }, [
      el("section", { class: "panel" }, [field("Session", selector)]),
      chartHost,
      deltaHost,
    ]),
  );
  await load();
}

async function renderCompare(host, sessions) {
  if (sessions.length < 2) {
    host.replaceChildren(emptyState("At least two simulation sessions are required to compare."));
    return;
  }

  const checkboxes = sessions.map((session) =>
    el("label", { class: "checkbox-row" }, [
      el("input", { type: "checkbox", value: session.id, name: "session_ids" }),
      el("span", { text: `${session.session_code} · ${session.status} · ${session.profile?.subject_code ?? ""}` }),
    ]),
  );

  const resultHost = el("div", { class: "page-stack" });
  const form = el("form", { class: "compare-form" }, [
    el("div", { class: "checkbox-grid" }, checkboxes),
    el("button", { class: "btn btn-primary", type: "submit", text: "Compare Selected Sessions" }),
  ]);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const selected = checkboxes
      .map((row) => row.querySelector("input"))
      .filter((input) => input.checked)
      .map((input) => Number(input.value));

    if (selected.length < 2) {
      toast("Select at least two sessions.", "warning");
      return;
    }
    if (selected.length > 10) {
      toast("Select at most ten sessions.", "warning");
      return;
    }

    resultHost.replaceChildren(loadingState("Comparing sessions…"));
    try {
      const comparison = await api.analytics.compare(selected);
      resultHost.replaceChildren(
        el("section", { class: "panel" }, [
          el("div", { class: "panel-heading" }, [
            el("h2", { text: "Comparison" }),
            badge(`${comparison.count} sessions`),
          ]),
          comparisonBarChart(
            comparison.sessions.map((item) => ({ label: item.session_code, value: item.ticks })),
            { label: "Ticks", height: 280 },
          ),
          dataTable([
            { label: "Session", render: (row) => row.session_code },
            { label: "Status", render: (row) => row.status },
            { label: "Subject", render: (row) => row.subject_code ?? "—" },
            { label: "Gas", render: (row) => `${row.gas_code ?? "—"} (L${row.gas_hazard_level ?? "—"})` },
            { label: "Ticks", render: (row) => row.ticks },
            { label: "Peak Mutation", render: (row) => MUTATION_LEVELS[row.peak_mutation_level] ?? row.peak_mutation_level },
            { label: "Peak Risk", render: (row) => row.peak_risk_level === null ? "—" : `L${row.peak_risk_level}` },
            { label: "Final Status", render: (row) => row.final_biological_status ?? "—" },
            { label: "Δ Muscle", render: (row) => formatDelta(row.delta?.muscle_density ?? 0) },
            { label: "Δ Stability", render: (row) => formatDelta(row.delta?.cellular_stability ?? 0) },
          ], comparison.sessions),
          el("p", { class: "muted", text:
            `Average ticks ${formatFixed(comparison.average_ticks)} · ` +
            `Highest risk: ${comparison.highest_risk ? comparison.highest_risk.session_id : "—"} · ` +
            `Highest mutation: ${comparison.highest_mutation ? comparison.highest_mutation.session_id : "—"}` }),
        ]),
      );
    } catch (error) {
      toastError(error);
      resultHost.replaceChildren(errorState(error.message));
    }
  });

  host.replaceChildren(form, resultHost);
}

async function renderReports(host, profiles, sessions) {
  const reportHost = el("div", { class: "page-stack" });

  const sessionSelector = el("select", { name: "session_id" }, sessions.map((session) =>
    el("option", { value: session.id, text: session.session_code }),
  ));
  const profileSelector = el("select", { name: "profile_id" }, profiles.map((profile) =>
    el("option", { value: profile.id, text: `${profile.subject_code} — ${profile.full_name}` }),
  ));

  const loadSession = async () => {
    if (!sessionSelector.value) return;
    reportHost.replaceChildren(loadingState("Building session report…"));
    try {
      const report = await api.analytics.sessionReport(Number(sessionSelector.value));
      const session = report.session;
      reportHost.replaceChildren(
        el("div", { class: "page-stack" }, [
          el("section", { class: "panel" }, [
            el("div", { class: "panel-heading" }, [el("h2", { text: `Session report · ${session.session_code}` }), badge(session.status)]),
            el("p", { class: "muted", text: `${session.subject_code ?? "Subject"} · Class ${session.physical_class ?? "—"} · ${session.ticks} ticks` }),
            el("div", { class: "metric-grid" }, [
              ["Average Absorption", report.enhancement.average_absorption],
              ["Average Digestion", report.enhancement.average_digestion],
              ["Average Adaptation", report.enhancement.average_adaptation],
              ["Average Gain", report.enhancement.average_gain],
              ["Average Stability", report.enhancement.average_stability],
              ["Hazard Assessments", report.hazard_assessments],
            ].map(([label, value]) => el("div", { class: "metric" }, [
              el("span", { class: "metric-label", text: label }),
              el("span", { class: "metric-value", text: formatNumber(value) }),
            ]))),
          ]),
          el("section", { class: "panel" }, [
            el("h2", { text: "Mutations" }),
            dataTable([
              { label: "Type", render: (row) => row.mutation_type },
              { label: "Occurrences", render: (row) => row.occurrences },
              { label: "Peak Level", render: (row) => `${row.peak_level} · ${MUTATION_LEVELS[row.peak_level] ?? ""}` },
            ], report.mutations, { empty: "No mutations were recorded in this session." }),
          ]),
        ]),
      );
    } catch (error) {
      toastError(error);
      reportHost.replaceChildren(errorState(error.message, loadSession));
    }
  };

  const loadProfile = async () => {
    if (!profileSelector.value) return;
    reportHost.replaceChildren(loadingState("Building profile report…"));
    try {
      const report = await api.analytics.profileReport(Number(profileSelector.value));
      reportHost.replaceChildren(
        el("div", { class: "page-stack" }, [
          el("section", { class: "panel" }, [
            el("div", { class: "panel-heading" }, [el("h2", { text: `Profile report · ${report.profile.subject_code}` }), badge(`Class ${report.profile.physical_class}`, `class-${report.profile.physical_class}`)]),
            el("p", { class: "muted", text: `${report.profile.full_name} · ${report.session_count} sessions · ${report.compatibility.evaluations} compatibility evaluations` }),
            el("div", { class: "metric-grid" }, [
              ["Average Compatibility", report.compatibility.average_score],
              ["Average Mutation Risk", report.compatibility.average_mutation_risk],
              ["Average Enhancement Potential", report.compatibility.average_enhancement_potential],
            ].map(([label, value]) => el("div", { class: "metric" }, [
              el("span", { class: "metric-label", text: label }),
              el("span", { class: "metric-value", text: formatNumber(value) }),
            ]))),
          ]),
          el("section", { class: "panel" }, [
            el("h2", { text: "Sessions" }),
            dataTable([
              { label: "Session", render: (row) => row.session_code },
              { label: "Status", render: (row) => row.status },
              { label: "Ticks", render: (row) => row.ticks },
              { label: "Peak Risk", render: (row) => row.peak_risk_level === null ? "—" : `L${row.peak_risk_level}` },
              { label: "Final Status", render: (row) => row.final_biological_status ?? "—" },
            ], report.sessions, { empty: "This profile has no sessions yet." }),
          ]),
        ]),
      );
    } catch (error) {
      toastError(error);
      reportHost.replaceChildren(errorState(error.message, loadProfile));
    }
  };

  sessionSelector.addEventListener("change", loadSession);
  profileSelector.addEventListener("change", loadProfile);

  host.replaceChildren(
    el("div", { class: "page-stack" }, [
      el("section", { class: "panel" }, [
        el("h2", { text: "Session Report" }),
        field("Session", sessionSelector),
      ]),
      el("section", { class: "panel" }, [
        el("h2", { text: "Profile Report" }),
        field("Profile", profileSelector),
      ]),
      reportHost,
    ]),
  );
}

export async function render(container) {
  container.replaceChildren(loadingState("Loading analytics…"));

  let profiles = [];
  let sessions = [];
  try {
    [profiles, sessions] = await Promise.all([api.humans.list(), api.sessions.list(null, 100)]);
  } catch (error) {
    toastError(error);
    container.replaceChildren(errorState(error.message, () => render(container)));
    return;
  }

  const overview = el("div");
  const trends = el("div");
  const compare = el("div");
  const reports = el("div");

  const tabs = [
    { id: "overview", label: "Overview", host: overview },
    { id: "trends", label: "Trends", host: trends },
    { id: "compare", label: "Compare", host: compare },
    { id: "reports", label: "Reports", host: reports },
  ];

  const loaded = new Set();
  const panels = tabs.map((tab) => {
    const panel = el("section", { class: "tab-panel", dataset: { tab: tab.id } }, [tab.host]);
    return panel;
  });

  const tabBar = el("nav", { class: "tab-bar", role: "tablist" });
  const buttons = tabs.map((tab, index) => {
    const button = el("button", {
      class: index === 0 ? "tab-button is-active" : "tab-button",
      type: "button",
      role: "tab",
      text: tab.label,
      onClick: async () => {
        buttons.forEach((other) => other.classList.remove("is-active"));
        button.classList.add("is-active");
        panels.forEach((panel, panelIndex) => {
          panel.classList.toggle("is-active", panelIndex === index);
        });
        if (!loaded.has(tab.id)) {
          loaded.add(tab.id);
          if (tab.id === "overview") await renderOverview(overview);
          if (tab.id === "trends") await renderTrends(trends, sessions);
          if (tab.id === "compare") await renderCompare(compare, sessions);
          if (tab.id === "reports") await renderReports(reports, profiles, sessions);
        }
      },
    });
    tabBar.append(button);
    return button;
  });

  panels.forEach((panel, index) => panel.classList.toggle("is-active", index === 0));

  container.replaceChildren(
    el("div", { class: "page-stack" }, [
      el("section", { class: "page-heading" }, [
        el("div", {}, [
          el("p", { class: "eyebrow", text: "DATA & REPORTS" }),
          el("h1", { text: "Analytics" }),
          el("p", { class: "muted", text: "Every figure is computed from stored simulation records only." }),
        ]),
      ]),
      tabBar,
      ...panels,
    ]),
  );

  loaded.add("overview");
  await renderOverview(overview);
}

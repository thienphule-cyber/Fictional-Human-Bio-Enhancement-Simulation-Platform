import { api } from "./api.js";
import { PARAMETERS, FOCUS_OPTIONS, RISK_STATUSES, riskColor } from "./constants.js";
import {
  badge, dataTable, el, emptyState, errorState, field, formatDateTime,
  formatNumber, loadingState, numberInput, parameterBar, qs, select,
  toast, toastError,
} from "./ui.js";
import { parametersLineChart, riskLineChart } from "./charts.js";

function sessionStatusTone(status) {
  if (status === "Running") return "success";
  if (status === "Emergency Shutdown") return "danger";
  if (status === "Paused") return "warning";
  return "neutral";
}

function renderResult(result) {
  const stageItems = Object.entries(result.stages ?? {}).map(([key, value]) =>
    el("div", { class: "metric" }, [
      el("span", { class: "metric-label", text: key.replaceAll("_", " ") }),
      el("span", { class: "metric-value", text: formatNumber(value) }),
    ]),
  );

  return el("div", { class: "result-block" }, [
    el("div", { class: "panel-heading" }, [
      el("h3", { text: `Tick ${result.tick} result` }),
      badge(result.biological_status, result.biological_status.toLowerCase()),
    ]),
    el("div", { class: "metric-grid" }, stageItems),
    el("p", { class: "muted", text: `Class ${result.physical_class} · Risk level ${result.risk_level} · Compatibility ${formatNumber(result.compatibility?.score)}` }),
    result.mutation?.occurred
      ? el("p", { class: "notice notice-warning", text: `Mutation: ${result.mutation.mutation_type} · ${result.mutation.mutation_level_name} · risk ${formatNumber(result.mutation.mutation_risk)}` })
      : el("p", { class: "notice notice-success", text: "No mutation detected in this simulated tick." }),
  ]);
}

async function renderSessionWorkspace(host, session) {
  host.replaceChildren(loadingState("Loading session metrics…"));
  try {
    const [metrics, summary, mutationSummary] = await Promise.all([
      api.sessions.metrics(session.id),
      api.sessions.summary(session.id),
      api.sessions.mutationSummary(session.id),
    ]);
    const trendResponse = await api.analytics.trends(session.id);
    const status = session.status;
    const refresh = () => renderSessionWorkspace(host, session);

    const controls = el("div", { class: "button-row" });
    if (["Created", "Paused", "Stopped"].includes(status)) {
      controls.append(el("button", { class: "btn btn-primary", type: "button", text: status === "Paused" ? "Resume" : "Start", onClick: async () => {
        try { await api.sessions.start(session.id); toast("Session is running.", "success"); await refresh(); }
        catch (error) { toastError(error); }
      }}));
    }
    if (status === "Running") {
      controls.append(
        el("button", { class: "btn btn-secondary", type: "button", text: "Pause", onClick: async () => {
          try { await api.sessions.pause(session.id); toast("Session paused.", "info"); await refresh(); }
          catch (error) { toastError(error); }
        }}),
        el("button", { class: "btn btn-danger", type: "button", text: "Stop", onClick: async () => {
          try { await api.sessions.stop(session.id); toast("Session stopped.", "warning"); await refresh(); }
          catch (error) { toastError(error); }
        }}),
      );
    }
    if (["Running", "Stopped"].includes(status)) {
      controls.append(el("button", { class: "btn btn-secondary", type: "button", text: "Complete", onClick: async () => {
        try { await api.sessions.complete(session.id); toast("Session completed.", "success"); await refresh(); }
        catch (error) { toastError(error); }
      }}));
    }
    if (["Running", "Paused", "Created"].includes(status)) {
      controls.append(el("button", { class: "btn btn-danger", type: "button", text: "Emergency Shutdown", onClick: async () => {
        if (!window.confirm("Set this fictional simulation session to Emergency Shutdown?")) return;
        try { await api.sessions.shutdown(session.id); toast("Session shut down.", "warning"); await refresh(); }
        catch (error) { toastError(error); }
      }}));
    }

    const stepForm = el("form", { class: "inline-form" }, [
      field("Intensity", numberInput({ name: "intensity", value: 50, min: 0, max: 100, step: 1 })),
      field("Focus", select(FOCUS_OPTIONS, { name: "focus", value: "muscle" })),
      el("button", { class: "btn btn-primary", type: "submit", text: "Run One Tick", disabled: status !== "Running" }),
    ]);
    const resultHost = el("div", { class: "step-result" });

    stepForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = stepForm.querySelector("button[type=submit]");
      button.disabled = true;
      try {
        const values = Object.fromEntries(new FormData(stepForm).entries());
        const result = await api.sessions.step(session.id, {
          intensity: Number(values.intensity),
          focus: values.focus,
        });
        resultHost.replaceChildren(renderResult(result));
        toast(`Tick ${result.tick} completed.`, "success");
        await renderSessionWorkspace(host, await api.sessions.get(session.id));
      } catch (error) {
        toastError(error);
      } finally {
        button.disabled = false;
      }
    });

    const latestMetric = metrics.at(-1);
    const parameterPanel = latestMetric
      ? el("div", { class: "parameter-grid" }, PARAMETERS.map((parameter) =>
          el("div", { class: "parameter-row" }, [
            el("span", { text: parameter.label }),
            parameterBar(latestMetric[parameter.key], parameter.color),
          ]),
        ))
      : emptyState("Run a tick to create the first metric snapshot.");

    let assessments = [];
    try { assessments = await api.hazard.history(session.id); } catch { /* The session may not have hazard records yet. */ }

    const assessButton = el("button", { class: "btn btn-secondary", type: "button", text: "Assess Hazard", onClick: async () => {
      try {
        const result = await api.hazard.assess(session.id, true);
        toast(`Hazard: ${result.risk_status} (level ${result.risk_level}).`, result.shutdown_recommended ? "warning" : "success");
        await renderSessionWorkspace(host, await api.sessions.get(session.id));
      } catch (error) { toastError(error); }
    }});

    host.replaceChildren(
      el("div", { class: "page-stack" }, [
        el("section", { class: "panel session-banner" }, [
          el("div", { class: "panel-heading" }, [
            el("div", {}, [el("p", { class: "eyebrow", text: session.session_code }), el("h2", { text: session.profile?.full_name ?? `Profile ${session.profile_id}` }), el("p", { class: "muted", text: `${session.gas?.gas_name ?? "Gas"} · ${session.gas?.hazard_name ?? "Hazard unknown"}` })]),
            badge(status, sessionStatusTone(status)),
          ]),
          el("p", { class: "muted", text: `Tick ${session.current_tick} · Class ${session.profile?.physical_class ?? "—"} · Created ${formatDateTime(session.created_at)}` }),
          controls,
        ]),
        el("section", { class: "panel" }, [
          el("div", { class: "panel-heading" }, [el("h2", { text: "Simulation Controls" }), el("span", { class: "muted", text: "Fictional software simulation only" })]),
          stepForm,
          resultHost,
        ]),
        el("section", { class: "stats-grid" }, [
          el("article", { class: "stat-card" }, [el("p", { class: "stat-label", text: "Recorded Ticks" }), el("p", { class: "stat-value", text: summary.ticks })]),
          el("article", { class: "stat-card" }, [el("p", { class: "stat-label", text: "Peak Risk" }), el("p", { class: "stat-value", text: summary.peak_risk_level ?? "—" })]),
          el("article", { class: "stat-card" }, [el("p", { class: "stat-label", text: "Mutation Records" }), el("p", { class: "stat-value", text: mutationSummary.records })]),
        ]),
        el("section", { class: "panel" }, [
          el("div", { class: "panel-heading" }, [el("h2", { text: "Parameter Trends" }), badge(`${trendResponse.ticks} ticks`)]),
          trendResponse.ticks ? parametersLineChart(trendResponse) : emptyState("No trend data recorded yet."),
        ]),
        el("section", { class: "panel" }, [
          el("div", { class: "panel-heading" }, [el("h2", { text: "Current Parameters" }), latestMetric ? badge(latestMetric.biological_status, latestMetric.biological_status.toLowerCase()) : null]),
          parameterPanel,
        ]),
        el("section", { class: "panel" }, [
          el("div", { class: "panel-heading" }, [el("h2", { text: "Hazard Monitor" }), assessButton]),
          assessments.length ? riskLineChart(assessments) : emptyState("No hazard assessments yet. Use Assess Hazard to record one."),
          assessments.length ? dataTable([
            { label: "Tick", render: (row) => row.tick },
            { label: "Risk", render: (row) => badge(`L${row.risk_level} · ${row.risk_status}`, `risk-${row.risk_level}`) },
            { label: "Stability", render: (row) => row.stability_status },
            { label: "Shutdown", render: (row) => row.shutdown_triggered ? badge("Recommended", "danger") : badge("No", "success") },
          ], assessments.slice(-8).reverse()) : null,
        ]),
      ]),
    );
  } catch (error) {
    toastError(error);
    host.replaceChildren(errorState(error.message, () => renderSessionWorkspace(host, session)));
  }
}

export async function render(container) {
  container.replaceChildren(loadingState("Loading simulation workspace…"));
  try {
    const [profiles, gases, devices, sessions] = await Promise.all([
      api.humans.list(), api.gases.list(), api.devices.list(), api.sessions.list(null, 100),
    ]);

    const workspace = el("section", { class: "simulation-workspace" }, [emptyState("Select or create a session to open the simulation workspace.")]);

    const sessionSelect = el("select", { name: "session_id" }, [
      el("option", { value: "", text: "Select a session…" }),
      ...sessions.map((session) => el("option", {
        value: session.id,
        text: `${session.session_code} · ${session.status} · ${session.profile?.subject_code ?? "Subject"}`,
      })),
    ]);
    sessionSelect.addEventListener("change", async () => {
      if (!sessionSelect.value) return;
      try { await renderSessionWorkspace(workspace, await api.sessions.get(Number(sessionSelect.value))); }
      catch (error) { toastError(error); }
    });

    const createForm = el("form", { class: "inline-form" });
    const profileSelect = el("select", { name: "profile_id" }, profiles.map((profile) =>
      el("option", { value: profile.id, text: `${profile.subject_code} — ${profile.full_name}` }),
    ));
    const gasSelect = el("select", { name: "gas_id" }, gases.map((gas) =>
      el("option", { value: gas.id, text: `${gas.gas_id} · Level ${gas.hazard_level}` }),
    ));
    const deviceSelect = el("select", { name: "device_id" }, devices.map((device) =>
      el("option", { value: device.id, text: `${device.device_code} — ${device.device_type}` }),
    ));
    const createButton = el("button", { class: "btn btn-primary", type: "submit", text: "Create Session", disabled: !profiles.length || !gases.length || !devices.length });
    createForm.append(field("Profile", profileSelect), field("Gas", gasSelect), field("Device", deviceSelect), createButton);
    createForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      createButton.disabled = true;
      try {
        const session = await api.sessions.create({
          profile_id: Number(profileSelect.value),
          gas_id: Number(gasSelect.value),
          device_id: Number(deviceSelect.value),
        });
        toast("Simulation session created.", "success");
        await renderSessionWorkspace(workspace, session);
        await render(container);
      } catch (error) {
        toastError(error);
      } finally {
        createButton.disabled = false;
      }
    });

    container.replaceChildren(
      el("div", { class: "page-stack" }, [
        el("section", { class: "page-heading" }, [
          el("div", {}, [el("p", { class: "eyebrow", text: "SIMULATION ENGINE" }), el("h1", { text: "Simulation" }), el("p", { class: "muted", text: "Create and control fictional simulation sessions. Outputs are software-only model results." })]),
          el("button", { class: "btn btn-secondary", type: "button", text: "Refresh", onClick: () => render(container) }),
        ]),
        el("section", { class: "panel" }, [el("h2", { text: "Create Session" }), createForm]),
        el("section", { class: "panel" }, [el("h2", { text: "Open Existing Session" }), field("Session", sessionSelect)]),
        workspace,
      ]),
    );

    if (sessions.length) {
      sessionSelect.value = String(sessions[0].id);
      await renderSessionWorkspace(workspace, sessions[0]);
    }
  } catch (error) {
    toastError(error);
    container.replaceChildren(errorState(error.message, () => render(container)));
  }
}

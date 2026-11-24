import { api } from "./api.js";
import { DEVICE_TYPES } from "./constants.js";
import {
  badge, dataTable, el, emptyState, errorState, field, formatNumber,
  loadingState, numberInput, select, textInput, toast, toastError,
} from "./ui.js";

function createDeviceForm(onCreated) {
  const form = el("form", { class: "form-grid" }, [
    field("Device Code", textInput({ name: "device_code", placeholder: "DEV-BM01", maxLength: 32 })),
    field("Device Name", textInput({ name: "device_name", placeholder: "Bio-Monitor Mk-I", maxLength: 120 })),
    field("Device Type", select(DEVICE_TYPES, { name: "device_type", value: DEVICE_TYPES[0] })),
  ]);
  const submit = el("button", { class: "btn btn-primary", type: "submit", text: "Register Device" });
  form.append(submit);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    submit.disabled = true;
    try {
      const data = Object.fromEntries(new FormData(form).entries());
      await api.devices.create(data);
      toast("Control device registered.", "success");
      form.reset();
      await onCreated();
    } catch (error) {
      toastError(error);
    } finally {
      submit.disabled = false;
    }
  });
  return form;
}

function deviceCard(device, onChanged) {
  const config = device.configuration;
  const statusTone = device.operational ? "success" : "danger";
  const controls = el("div", { class: "button-row" });

  const commandButtons = {
    "Bio-Monitor": ["start", "pause", "stop", "emergency_shutdown"],
    "Nebula Regulator": ["start", "pause", "stop", "stabilize"],
    Stabilizer: ["stabilize", "reset"],
  }[device.device_type] ?? [];

  for (const command of commandButtons) {
    const button = el("button", {
      class: command === "emergency_shutdown" ? "btn btn-danger btn-small" : "btn btn-secondary btn-small",
      type: "button",
      text: command.replaceAll("_", " "),
      onClick: async () => {
        button.disabled = true;
        try {
          const result = await api.devices.sendCommand(device.id, command);
          toast(result.message, command === "emergency_shutdown" ? "warning" : "success");
          await onChanged();
        } catch (error) {
          toastError(error);
        } finally {
          button.disabled = false;
        }
      },
    });
    controls.append(button);
  }

  const configForm = el("form", { class: "form-grid compact-form" });
  for (const [key, label] of [
    ["device_integrity", "Integrity"],
    ["monitoring_accuracy", "Monitoring Accuracy"],
    ["control_efficiency", "Control Efficiency"],
    ["stability_support", "Stability Support"],
  ]) {
    configForm.append(field(label, numberInput({ name: key, value: config[key], min: 0, max: 100, step: 0.1 })));
  }
  const saveButton = el("button", { class: "btn btn-small btn-primary", type: "submit", text: "Save Configuration" });
  configForm.append(saveButton);
  configForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    saveButton.disabled = true;
    try {
      const data = Object.fromEntries(new FormData(configForm).entries());
      await api.devices.updateConfiguration(device.id, Object.fromEntries(
        Object.entries(data).map(([key, value]) => [key, Number(value)]),
      ));
      toast("Device configuration updated.", "success");
      await onChanged();
    } catch (error) {
      toastError(error);
    } finally {
      saveButton.disabled = false;
    }
  });

  return el("article", { class: "panel device-card" }, [
    el("div", { class: "panel-heading" }, [
      el("div", {}, [
        el("p", { class: "eyebrow", text: device.device_code }),
        el("h2", { text: device.device_name }),
        el("p", { class: "muted", text: device.device_type }),
      ]),
      badge(device.operational ? "Operational" : "Offline / Shutdown", statusTone),
    ]),
    el("div", { class: "metric-grid" }, [
      ["Integrity", config.device_integrity],
      ["Monitoring", config.monitoring_accuracy],
      ["Control", config.control_efficiency],
      ["Stability Support", config.stability_support],
    ].map(([label, value]) => el("div", { class: "metric" }, [
      el("span", { class: "metric-label", text: label }),
      el("span", { class: "metric-value", text: `${formatNumber(value)}%` }),
    ]))),
    el("details", { class: "form-details" }, [el("summary", { text: "Edit configuration" }), configForm]),
    el("div", { class: "device-commands" }, [el("p", { class: "field-label", text: "Commands" }), controls]),
  ]);
}

export async function render(container) {
  container.replaceChildren(loadingState("Loading control devices…"));
  try {
    const [devices, summary] = await Promise.all([api.devices.list(), api.devices.summary()]);
    const refresh = () => render(container);
    container.replaceChildren(
      el("div", { class: "page-stack" }, [
        el("section", { class: "page-heading" }, [
          el("div", {}, [
            el("p", { class: "eyebrow", text: "CONTROL LAYER" }),
            el("h1", { text: "Devices" }),
            el("p", { class: "muted", text: "Manage simulated controls. Commands change simulation state only; they do not operate real hardware." }),
          ]),
          el("button", { class: "btn btn-secondary", type: "button", text: "Refresh", onClick: refresh }),
        ]),
        el("section", { class: "stats-grid" }, [
          el("article", { class: "stat-card" }, [el("p", { class: "stat-label", text: "Total Devices" }), el("p", { class: "stat-value", text: summary.total })]),
          el("article", { class: "stat-card" }, [el("p", { class: "stat-label", text: "Operational" }), el("p", { class: "stat-value", text: summary.operational })]),
          el("article", { class: "stat-card" }, [el("p", { class: "stat-label", text: "Average Integrity" }), el("p", { class: "stat-value", text: summary.average_integrity === null ? "—" : `${formatNumber(summary.average_integrity)}%` })]),
        ]),
        el("section", { class: "panel" }, [el("h2", { text: "Register Device" }), createDeviceForm(refresh)]),
        devices.length
          ? el("section", { class: "device-grid" }, devices.map((device) => deviceCard(device, refresh)))
          : el("section", { class: "panel" }, [emptyState("No control devices registered yet.")]),
      ]),
    );
  } catch (error) {
    toastError(error);
    container.replaceChildren(errorState(error.message, () => render(container)));
  }
}

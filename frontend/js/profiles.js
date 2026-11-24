import { api } from "./api.js";
import { PARAMETERS, PHYSICAL_CLASSES, BIOLOGICAL_STATUSES, classColor } from "./constants.js";
import {
  badge, dataTable, el, emptyState, errorState, field, formatDateTime,
  formatNumber, loadingState, numberInput, parameterBar, qs, select,
  textInput, toast, toastError,
} from "./ui.js";
import { parameterRadarChart } from "./charts.js";

function profileForm(onCreated) {
  const form = el("form", { class: "form-grid" });
  form.append(
    field("Subject Code", textInput({ name: "subject_code", placeholder: "SUB-001", maxLength: 32 })),
    field("Full Name", textInput({ name: "full_name", placeholder: "Simulation subject", maxLength: 120 })),
    field("Physical Class", select(PHYSICAL_CLASSES.map((label, value) => ({ value, label: `Class ${value} — ${label}` })), { name: "physical_class", value: 0 })),
    field("Biological Status", select(BIOLOGICAL_STATUSES, { name: "biological_status", value: "Normal" })),
    field("Notes", el("textarea", { name: "notes", rows: 3, maxlength: "500", placeholder: "Optional notes" })),
  );

  const parameterDetails = el("details", { class: "form-details" }, [
    el("summary", { text: "Initial biological parameters (optional)" }),
    el("div", { class: "form-grid parameter-form" }, PARAMETERS.map((parameter) =>
      field(parameter.label, numberInput({ name: parameter.key, value: 50, min: 0, max: 100, step: 0.1 })),
    )),
  ]);
  form.append(parameterDetails);
  const submit = el("button", { class: "btn btn-primary", type: "submit", text: "Create Profile" });
  form.append(submit);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    submit.disabled = true;
    try {
      const data = Object.fromEntries(new FormData(form).entries());
      const initialParameters = {};
      for (const parameter of PARAMETERS) initialParameters[parameter.key] = Number(data[parameter.key] ?? 50);
      const payload = {
        subject_code: data.subject_code,
        full_name: data.full_name,
        physical_class: Number(data.physical_class),
        biological_status: data.biological_status,
        notes: data.notes || null,
        initial_parameters: initialParameters,
      };
      await api.humans.create(payload);
      toast("Profile created.", "success");
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

export async function render(container) {
  container.replaceChildren(loadingState("Loading profiles…"));
  try {
    const profiles = await api.humans.list();
    const form = profileForm(() => render(container));
    const rows = profiles.map((profile) => ({ ...profile }));

    const table = dataTable(
      [
        { label: "Subject Code", render: (row) => row.subject_code },
        { label: "Name", render: (row) => row.full_name },
        { label: "Class", render: (row) => badge(`Class ${row.physical_class} · ${row.physical_class_name}`, `class-${row.physical_class}`) },
        { label: "Status", render: (row) => badge(row.biological_status, row.biological_status.toLowerCase()) },
        { label: "Created", render: (row) => formatDateTime(row.created_at) },
        { label: "Details", render: (row) => el("button", { class: "btn btn-small btn-secondary", type: "button", text: "View", onClick: () => showProfileDetails(row.id) }) },
      ],
      rows,
      { empty: "No profiles yet. Use the form above to create a simulation profile." },
    );

    container.replaceChildren(
      el("div", { class: "page-stack" }, [
        el("section", { class: "page-heading" }, [
          el("div", {}, [el("p", { class: "eyebrow", text: "SUBJECT REGISTRY" }), el("h1", { text: "Human Profiles" }), el("p", { class: "muted", text: "Manage fictional subject records and biological parameter snapshots." })]),
          el("button", { class: "btn btn-secondary", type: "button", text: "Refresh", onClick: () => render(container) }),
        ]),
        el("section", { class: "panel" }, [el("h2", { text: "Create Profile" }), form]),
        el("section", { class: "panel" }, [
          el("div", { class: "panel-heading" }, [el("h2", { text: "Registered Profiles" }), badge(`${profiles.length} profiles`)]),
          table,
        ]),
      ]),
    );
  } catch (error) {
    toastError(error);
    container.replaceChildren(errorState(error.message, () => render(container)));
  }
}

async function showProfileDetails(profileId) {
  try {
    const [profile, parameters] = await Promise.all([
      api.humans.get(profileId),
      api.humans.latestParameters(profileId),
    ]);

    const modal = el("dialog", { class: "modal" });
    const close = () => modal.close();
    modal.append(
      el("div", { class: "modal-heading" }, [
        el("div", {}, [el("p", { class: "eyebrow", text: profile.subject_code }), el("h2", { text: profile.full_name })]),
        el("button", { class: "icon-button", type: "button", "aria-label": "Close", text: "×", onClick: close }),
      ]),
      el("div", { class: "profile-summary" }, [
        badge(`Class ${profile.physical_class} · ${profile.physical_class_name}`, `class-${profile.physical_class}`),
        badge(profile.biological_status, profile.biological_status.toLowerCase()),
        profile.notes ? el("p", { class: "muted", text: profile.notes }) : null,
      ]),
      parameterRadarChart(parameters, { height: 340 }),
      el("div", { class: "parameter-grid" }, PARAMETERS.map((parameter) =>
        el("div", { class: "parameter-row" }, [
          el("span", { text: parameter.label }),
          parameterBar(parameters[parameter.key], parameter.color),
        ]),
      )),
    );
    document.body.append(modal);
    modal.addEventListener("close", () => modal.remove(), { once: true });
    modal.showModal();
  } catch (error) {
    toastError(error);
  }
}

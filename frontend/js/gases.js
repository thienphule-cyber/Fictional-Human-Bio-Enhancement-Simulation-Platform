import { api } from "./api.js";
import { badge, dataTable, el, errorState, field, formatNumber, loadingState,
  numberInput, parameterBar, select, textInput, toast, toastError } from "./ui.js";

const HAZARD_NAMES = [
  "Inert", "Low Hazard", "Moderate Hazard",
  "High Hazard", "Extreme Hazard", "Critical Hazard",
];

function gasForm(onCreated) {
  const form = el("form", { class: "form-grid" });
  form.append(
    field("Gas Code", textInput({ name: "gas_id", placeholder: "NG-001", maxLength: 32 })),
    field("Gas Name", textInput({ name: "gas_name", placeholder: "Nebula Gas designation", maxLength: 120 })),
    field("Hazard Level", select(HAZARD_NAMES.map((label, value) => ({ value, label: `Level ${value} — ${label}` })), { name: "hazard_level", value: 1 })),
    field("Gas Purity", numberInput({ name: "gas_purity", value: 80, min: 0, max: 100, step: 0.1 })),
    field("Energy Potential", numberInput({ name: "energy_potential", value: 50, min: 0, max: 100, step: 0.1 })),
    field("Mutation Potential", numberInput({ name: "mutation_potential", value: 30, min: 0, max: 100, step: 0.1 })),
    field("Stability Index", numberInput({ name: "stability_index", value: 70, min: 0, max: 100, step: 0.1 })),
  );

  const submit = el("button", { class: "btn btn-primary", type: "submit", text: "Add Gas" });
  form.append(submit);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    submit.disabled = true;
    try {
      const data = Object.fromEntries(new FormData(form).entries());
      await api.gases.create({
        gas_id: data.gas_id,
        gas_name: data.gas_name,
        hazard_level: Number(data.hazard_level),
        gas_purity: Number(data.gas_purity),
        energy_potential: Number(data.energy_potential),
        mutation_potential: Number(data.mutation_potential),
        stability_index: Number(data.stability_index),
      });
      toast("Nebula Gas added to the catalogue.", "success");
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
  container.replaceChildren(loadingState("Loading gas catalogue…"));
  try {
    const gases = await api.gases.list();

    const table = dataTable(
      [
        { label: "Code", render: (row) => row.gas_id },
        { label: "Name", render: (row) => row.gas_name },
        { label: "Hazard", render: (row) => badge(`L${row.hazard_level} · ${row.hazard_name}`, `risk-${row.hazard_level}`) },
        { label: "Purity", render: (row) => parameterBar(row.gas_purity, "#38bdf8") },
        { label: "Energy", render: (row) => parameterBar(row.energy_potential, "#f97316") },
        { label: "Mutation", render: (row) => parameterBar(row.mutation_potential, "#c026d3") },
        { label: "Stability", render: (row) => parameterBar(row.stability_index, "#22c55e") },
      ],
      gases,
      { empty: "No Nebula Gas records yet. Add one with the form above." },
    );

    container.replaceChildren(
      el("div", { class: "page-stack" }, [
        el("section", { class: "page-heading" }, [
          el("div", {}, [
            el("p", { class: "eyebrow", text: "GAS CATALOGUE" }),
            el("h1", { text: "Nebula Gas" }),
            el("p", { class: "muted", text: "Fictional gas profiles used by the simulation model. All values are 0–100 model scales." }),
          ]),
          el("button", { class: "btn btn-secondary", type: "button", text: "Refresh", onClick: () => render(container) }),
        ]),
        el("section", { class: "panel" }, [el("h2", { text: "Register Gas" }), gasForm(() => render(container))]),
        el("section", { class: "panel" }, [
          el("div", { class: "panel-heading" }, [el("h2", { text: "Catalogue" }), badge(`${gases.length} records`)]),
          table,
        ]),
      ]),
    );
  } catch (error) {
    toastError(error);
    container.replaceChildren(errorState(error.message, () => render(container)));
  }
}

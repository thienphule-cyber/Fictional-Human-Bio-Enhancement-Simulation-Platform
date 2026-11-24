import { api } from "./api.js";
import { badge, dataTable, el, emptyState, errorState, field, formatDateTime,
  formatNumber, loadingState, select, toast, toastError } from "./ui.js";

export async function render(container) {
  container.replaceChildren(loadingState("Loading compatibility matrix…"));
  try {
    const [profiles, gases] = await Promise.all([api.humans.list(), api.gases.list()]);

    if (profiles.length === 0 || gases.length === 0) {
      container.replaceChildren(
        el("div", { class: "page-stack" }, [
          el("section", { class: "page-heading" }, [
            el("div", {}, [el("p", { class: "eyebrow", text: "COMPATIBILITY" }), el("h1", { text: "Compatibility Matrix" })]),
          ]),
          el("section", { class: "panel" }, [
            emptyState("You need at least one human profile and one Nebula Gas before evaluating compatibility."),
          ]),
        ]),
      );
      return;
    }

    const profileSelect = select(profiles.map((profile) => ({
      value: profile.id,
      label: `${profile.subject_code} — ${profile.full_name}`,
    })), { name: "profile_id" });

    const gasSelect = select(gases.map((gas) => ({
      value: gas.id,
      label: `${gas.gas_id} — L${gas.hazard_level} ${gas.hazard_name}`,
    })), { name: "gas_id" });

    const resultPanel = el("section", { class: "panel" }, [emptyState("Select a profile and a gas, then evaluate.")]);

    const form = el("form", { class: "inline-form" }, [
      field("Human Profile", profileSelect),
      field("Nebula Gas", gasSelect),
      el("div", { class: "form-actions" }, [
        el("button", { class: "btn btn-primary", type: "submit", text: "Evaluate" }),
      ]),
    ]);

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = form.querySelector("button[type=submit]");
      button.disabled = true;
      resultPanel.replaceChildren(loadingState("Evaluating compatibility…"));
      try {
        const result = await api.compatibility.evaluate(Number(profileSelect.value), Number(gasSelect.value));
        resultPanel.replaceChildren(renderResult(result));
        toast("Compatibility evaluated and stored.", "success");
      } catch (error) {
        toastError(error);
        resultPanel.replaceChildren(errorState(error.message));
      } finally {
        button.disabled = false;
      }
    });

    container.replaceChildren(
      el("div", { class: "page-stack" }, [
        el("section", { class: "page-heading" }, [
          el("div", {}, [
            el("p", { class: "eyebrow", text: "COMPATIBILITY" }),
            el("h1", { text: "Compatibility Matrix" }),
            el("p", { class: "muted", text: "Score one fictional profile against one Nebula Gas across digest, adaptation, and mutation indicators." }),
          ]),
        ]),
        el("section", { class: "panel" }, [el("h2", { text: "Evaluate" }), form]),
        resultPanel,
      ]),
    );
  } catch (error) {
    toastError(error);
    container.replaceChildren(errorState(error.message, () => render(container)));
  }
}

function renderResult(result) {
  const statusTone = result.result_status === "Compatible"
    ? "compatible"
    : result.result_status === "Partially Compatible" ? "partial" : "incompatible";

  const metrics = [
    ["Compatibility Score", result.compatibility_score],
    ["Digest Efficiency", result.digest_efficiency],
    ["Adaptation Stability", result.adaptation_stability],
    ["Mutation Risk", result.mutation_risk],
    ["Enhancement Potential", result.enhancement_potential],
  ];

  return el("div", { class: "page-stack" }, [
    el("div", { class: "panel-heading" }, [
      el("h2", { text: "Result" }),
      badge(result.result_status, statusTone),
    ]),
    el("div", { class: "metric-grid" }, metrics.map(([label, value]) =>
      el("div", { class: "metric" }, [
        el("span", { class: "metric-label", text: label }),
        el("span", { class: "metric-value", text: formatNumber(value) }),
      ]),
    )),
    el("p", { class: "muted", text:
      `Gas hazard level ${result.hazard_level} (${result.hazard_classification}); ` +
      `class ceiling ${result.class_hazard_ceiling}; ` +
      `${result.within_class_limit ? "within" : "beyond"} the class limit.` }),
  ]);
}

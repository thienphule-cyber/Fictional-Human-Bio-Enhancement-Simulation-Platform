/**
 * Shared vocabulary for the Nebula dashboard.
 *
 * Every label here mirrors a Python constant in backend/, so when a backend
 * list changes, this file is the single place the frontend needs to follow.
 */

export const PARAMETERS = [
  { key: "muscle_density", label: "Muscle Density", short: "Muscle", color: "#f43f5e" },
  { key: "bone_density", label: "Bone Density", short: "Bone", color: "#fb923c" },
  { key: "cardiovascular_capacity", label: "Cardiovascular Capacity", short: "Cardio", color: "#ef4444" },
  { key: "neural_activity", label: "Neural Activity", short: "Neural", color: "#a855f7" },
  { key: "cellular_stability", label: "Cellular Stability", short: "Stability", color: "#38bdf8" },
  { key: "metabolic_efficiency", label: "Metabolic Efficiency", short: "Metabolic", color: "#22c55e" },
  { key: "regeneration_index", label: "Regeneration Index", short: "Regen", color: "#14b8a6" },
  { key: "mutation_resistance", label: "Mutation Resistance", short: "Resistance", color: "#94a3b8" },
];

export const PARAMETER_KEYS = PARAMETERS.map((parameter) => parameter.key);

export const PARAMETER_LABELS = Object.fromEntries(
  PARAMETERS.map((parameter) => [parameter.key, parameter.label]),
);

export const FOCUS_OPTIONS = [
  { value: "muscle", label: "Muscle" },
  { value: "skeletal", label: "Skeletal" },
  { value: "cardiovascular", label: "Cardiovascular" },
  { value: "neural", label: "Neural" },
  { value: "metabolic", label: "Metabolic" },
  { value: "regenerative", label: "Regenerative" },
];

export const PHYSICAL_CLASSES = [
  "Normal",
  "Adapted",
  "Enhanced",
  "Advanced",
  "Superior",
  "Apex",
];

export const BIOLOGICAL_STATUSES = [
  "Normal",
  "Adaptation",
  "Enhanced",
  "Unstable",
  "Mutated",
  "Critical",
];

export const RISK_STATUSES = [
  "Safe Simulation State",
  "Low Risk",
  "Moderate Risk",
  "High Risk",
  "Critical Risk",
  "Biological Collapse",
];

export const MUTATION_LEVELS = [
  "Stable",
  "Latent",
  "Minor",
  "Manifest",
  "Severe",
  "Critical",
];

export const SESSION_STATUSES = [
  "Created",
  "Running",
  "Paused",
  "Stopped",
  "Completed",
  "Emergency Shutdown",
];

export const DEVICE_TYPES = ["Bio-Monitor", "Nebula Regulator", "Stabilizer"];

/** Mirrors the command permissions in backend/devices.py. */
export const DEVICE_COMMANDS = {
  "Bio-Monitor": ["start", "pause", "stop", "emergency_shutdown"],
  "Nebula Regulator": ["start", "pause", "stop", "stabilize"],
  Stabilizer: ["stabilize", "reset"],
};

export const RISK_COLORS = [
  "#22c55e",
  "#84cc16",
  "#eab308",
  "#f97316",
  "#ef4444",
  "#c026d3",
];

export const CLASS_COLORS = [
  "#64748b",
  "#38bdf8",
  "#22d3ee",
  "#a855f7",
  "#f97316",
  "#f43f5e",
];

export function riskColor(level) {
  const index = Number(level);
  if (!Number.isInteger(index) || index < 0 || index > 5) return "#64748b";
  return RISK_COLORS[index];
}

export function classColor(physicalClass) {
  const index = Number(physicalClass);
  if (!Number.isInteger(index) || index < 0 || index > 5) return "#64748b";
  return CLASS_COLORS[index];
}

export const PHYSICAL_PARAMETER_DEFAULTS = {
  muscle_density: 50,
  bone_density: 50,
  cardiovascular_capacity: 50,
  neural_activity: 50,
  cellular_stability: 50,
  metabolic_efficiency: 50,
  regeneration_index: 50,
  mutation_resistance: 50,
};

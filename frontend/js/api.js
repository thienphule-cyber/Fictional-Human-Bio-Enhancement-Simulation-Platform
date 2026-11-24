/**
 * API client for the Nebula backend.
 *
 * Every call is relative to the page origin, so the dashboard keeps working
 * whatever port the auto-scanning server in backend/main.py ended up using.
 */

const API_BASE = "/api";

export class ApiError extends Error {
  constructor(message, { status = 0, errorType = null } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.errorType = errorType;
  }
}

function buildUrl(path, params) {
  const url = new URL(`${API_BASE}${path}`, window.location.origin);
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value === undefined || value === null || value === "") continue;
    url.searchParams.set(key, String(value));
  }
  return url;
}

function readDetail(payload, fallback) {
  if (payload === null || payload === undefined) return fallback;
  if (typeof payload === "string" && payload.trim()) return payload;

  const detail = payload.detail;
  if (typeof detail === "string") return detail;

  // FastAPI validation errors arrive as a list of {loc, msg, type}.
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        const field = Array.isArray(item.loc)
          ? item.loc.filter((part) => part !== "body").join(".")
          : "";
        return field ? `${field}: ${item.msg}` : String(item.msg ?? item);
      })
      .join("; ");
  }

  return fallback;
}

async function request(path, { method = "GET", body, params, signal } = {}) {
  const init = {
    method,
    signal,
    headers: { Accept: "application/json" },
  };

  if (body !== undefined) {
    init.headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }

  let response;
  try {
    response = await fetch(buildUrl(path, params), init);
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new ApiError(
      "Cannot reach the Nebula server. Check that backend.main is still running.",
      { status: 0 },
    );
  }

  const contentType = response.headers.get("content-type") ?? "";
  let payload = null;

  if (response.status !== 204) {
    if (contentType.includes("application/json")) {
      payload = await response.json().catch(() => null);
    } else {
      payload = await response.text();
    }
  }

  if (!response.ok) {
    throw new ApiError(
      readDetail(payload, `Request failed with status ${response.status}`),
      { status: response.status, errorType: payload?.error_type ?? null },
    );
  }

  return payload;
}

export const api = {
  health: () => request("/health"),
  meta: () => request("/meta"),

  humans: {
    list: () => request("/humans"),
    get: (profileId) => request(`/humans/${profileId}`),
    create: (payload) => request("/humans", { method: "POST", body: payload }),
    update: (profileId, payload) =>
      request(`/humans/${profileId}`, { method: "PATCH", body: payload }),
    latestParameters: (profileId) => request(`/humans/${profileId}/parameters/latest`),
    addParameters: (profileId, payload) =>
      request(`/humans/${profileId}/parameters`, { method: "POST", body: payload }),
    compatibilityHistory: (profileId, limit = 50) =>
      request(`/humans/${profileId}/compatibility`, { params: { limit } }),
  },

  gases: {
    list: () => request("/gases"),
    get: (gasPrimaryKey) => request(`/gases/${gasPrimaryKey}`),
    create: (payload) => request("/gases", { method: "POST", body: payload }),
  },

  compatibility: {
    evaluate: (profileId, gasId, persist = true) =>
      request("/compatibility", {
        method: "POST",
        body: { profile_id: profileId, gas_id: gasId, persist },
      }),
  },

  devices: {
    list: () => request("/devices"),
    summary: () => request("/devices/summary"),
    get: (deviceId) => request(`/devices/${deviceId}`),
    create: (payload) => request("/devices", { method: "POST", body: payload }),
    updateConfiguration: (deviceId, payload) =>
      request(`/devices/${deviceId}/configuration`, { method: "PATCH", body: payload }),
    sendCommand: (deviceId, command) =>
      request(`/devices/${deviceId}/command`, { method: "POST", body: { command } }),
    status: (deviceId) => request(`/devices/${deviceId}/status`),
    effectiveControl: (deviceId) => request(`/devices/${deviceId}/effective-control`),
  },

  sessions: {
    list: (profileId = null, limit = 50) =>
      request("/sessions", { params: { profile_id: profileId, limit } }),
    get: (sessionId) => request(`/sessions/${sessionId}`),
    create: (payload) => request("/sessions", { method: "POST", body: payload }),
    start: (sessionId) => request(`/sessions/${sessionId}/start`, { method: "POST" }),
    pause: (sessionId) => request(`/sessions/${sessionId}/pause`, { method: "POST" }),
    stop: (sessionId) => request(`/sessions/${sessionId}/stop`, { method: "POST" }),
    complete: (sessionId) => request(`/sessions/${sessionId}/complete`, { method: "POST" }),
    shutdown: (sessionId) => request(`/sessions/${sessionId}/shutdown`, { method: "POST" }),
    step: (sessionId, payload = {}) =>
      request(`/sessions/${sessionId}/step`, { method: "POST", body: payload }),
    metrics: (sessionId, limit = 200) =>
      request(`/sessions/${sessionId}/metrics`, { params: { limit } }),
    enhancements: (sessionId, limit = 200) =>
      request(`/sessions/${sessionId}/enhancements`, { params: { limit } }),
    summary: (sessionId) => request(`/sessions/${sessionId}/summary`),
    mutations: (sessionId, limit = 200) =>
      request(`/sessions/${sessionId}/mutations`, { params: { limit } }),
    mutationSummary: (sessionId) => request(`/sessions/${sessionId}/mutations/summary`),
  },

  hazard: {
    assess: (sessionId, persist = true) =>
      request(`/sessions/${sessionId}/hazard/assess`, {
        method: "POST",
        params: { persist },
      }),
    history: (sessionId, limit = 100) =>
      request(`/sessions/${sessionId}/hazard`, { params: { limit } }),
    summary: (sessionId) => request(`/sessions/${sessionId}/hazard/summary`),
  },

  analytics: {
    trends: (sessionId, limit = 500) =>
      request(`/analytics/sessions/${sessionId}/trends`, { params: { limit } }),
    deltas: (sessionId) => request(`/analytics/sessions/${sessionId}/deltas`),
    enhancementHistory: (profileId = null, limit = 50) =>
      request("/analytics/enhancement-history", {
        params: { profile_id: profileId, limit },
      }),
    mutationHistory: (profileId = null, limit = 50) =>
      request("/analytics/mutation-history", {
        params: { profile_id: profileId, limit },
      }),
    hazardHistory: (profileId = null, limit = 50) =>
      request("/analytics/hazard-history", {
        params: { profile_id: profileId, limit },
      }),
    compare: (sessionIds) =>
      request("/analytics/compare", {
        method: "POST",
        body: { session_ids: sessionIds },
      }),
    sessionReport: (sessionId) =>
      request(`/analytics/sessions/${sessionId}/report`),
    profileReport: (profileId) =>
      request(`/analytics/profiles/${profileId}/report`),
    statistics: () => request("/analytics/statistics"),
    recent: (limit = 20) => request("/analytics/recent", { params: { limit } }),
  },
};

import { submissionRequest } from "@/services/application-contract.mjs";
import { getAuthProvider, getStoredLocalToken, resolveAccessToken } from "@/services/auth-token.mjs";
import { getSupabaseClient } from "@/services/supabase";

export const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1").replace(/\/$/, "");
const REQUEST_TIMEOUT_MS = 15000;

export class ApiError extends Error {
  constructor(message, status = 0, details = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.details = details;
  }
}

function messageFromPayload(payload, status) {
  const detail = payload?.error?.message ?? payload?.detail ?? payload?.message;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((item) => item.msg || item.message || "Invalid input").join(" · ");
  return `Request failed (${status})`;
}

export function unwrapResponse(payload) {
  return payload && typeof payload === "object" && Object.prototype.hasOwnProperty.call(payload, "data")
    ? payload.data
    : payload;
}

async function accessToken() {
  if (typeof window === "undefined") return null;
  const provider = getAuthProvider();
  if (provider === "local") {
    return resolveAccessToken(provider, { localToken: getStoredLocalToken() });
  }
  if (provider === "supabase") {
    const client = getSupabaseClient();
    if (!client) return null;
    const { data, error } = await client.auth.getSession();
    if (error) throw new ApiError(error.message);
    return resolveAccessToken(provider, { supabaseSession: data.session });
  }
  return null;
}

export async function request(path, options = {}) {
  const {
    method = "GET", body, headers = {}, authenticated = true, signal,
    timeout = REQUEST_TIMEOUT_MS, raw = false,
  } = options;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(new Error("Request timed out")), timeout);
  const abortFromCaller = () => controller.abort(signal.reason);
  if (signal) {
    if (signal.aborted) abortFromCaller();
    else signal.addEventListener("abort", abortFromCaller, { once: true });
  }
  const requestHeaders = new Headers(headers);
    const isFormData = typeof FormData !== "undefined" && body instanceof FormData;
    if (!isFormData && body !== undefined && !requestHeaders.has("Content-Type")) {
    requestHeaders.set("Content-Type", "application/json");
  }
  requestHeaders.set("Accept", "application/json");
  try {
    if (authenticated) {
      const token = await accessToken();
      if (token) requestHeaders.set("Authorization", `Bearer ${token}`);
    }
    const response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers: requestHeaders,
      body: body === undefined ? undefined : isFormData ? body : JSON.stringify(body),
      signal: controller.signal,
      cache: "no-store",
    });
    const text = await response.text();
    let payload = null;
    if (text) {
      try { payload = JSON.parse(text); }
      catch { payload = text; }
    }
    if (!response.ok) throw new ApiError(messageFromPayload(payload, response.status), response.status, payload);
    return raw ? payload : unwrapResponse(payload);
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (controller.signal.aborted) {
      const reason = controller.signal.reason?.message;
      throw new ApiError(reason === "Request timed out" ? "The request timed out. Please try again." : "The request was cancelled.");
    }
    if (error instanceof TypeError) throw new ApiError("Could not connect to AVSAR. Check that the backend is running and the API URL is correct.");
    throw new ApiError(error?.message || "An unexpected request error occurred.");
  } finally {
    clearTimeout(timeoutId);
    if (signal) signal.removeEventListener("abort", abortFromCaller);
  }
}

function query(params) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") search.set(key, String(value));
  });
  const result = search.toString();
  return result ? `?${result}` : "";
}

async function requestPage(path) {
  const payload = await request(path, { raw: true });
  if (payload && typeof payload === "object" && Object.prototype.hasOwnProperty.call(payload, "data")) {
    return { items: payload.data, meta: payload.meta || {} };
  }
  return { items: payload, meta: {} };
}

export const api = {
  authConfig: () => request("/auth/config", { authenticated: false }),
  currentUser: () => request("/auth/me"),
  logout: () => request("/auth/logout", { method: "POST" }),
  profile: () => request("/profile/me"),
  updateProfile: (values) => request("/profile/me", { method: "PUT", body: values }),
  opportunities: (filters = {}) => requestPage(`/opportunities${query(filters)}`),
  opportunity: (id) => request(`/opportunities/${encodeURIComponent(id)}`),
  recommendations: (filters = {}) => requestPage(`/recommendations${query(filters)}`),
  eligibility: (id) => request(`/eligibility/check/${encodeURIComponent(id)}`, { method: "POST" }),
  analyzeTrust: (id) => request("/verification/analyze", { method: "POST", body: { opportunity_id: id } }),
  trust: (id) => request(`/trust/verify/${encodeURIComponent(id)}`),
  applications: (filters = {}) => request(`/applications${query(filters)}`),
  application: (id) => request(`/applications/${encodeURIComponent(id)}`),
  createApplication: (opportunityId) => request("/applications", { method: "POST", body: { opportunity_id: opportunityId } }),
  updateApplication: (id, revision, status) => request(`/applications/${encodeURIComponent(id)}`, { method: "PATCH", body: { revision, status } }),
  updateApplicationMaterial: (id, revision, material) => request(`/applications/${encodeURIComponent(id)}`, { method: "PATCH", body: { revision, material } }),
  approveApplication: (id, revision) => request(`/applications/${encodeURIComponent(id)}/approve`, { method: "POST", body: { revision } }),
  submitApplication: (id, revision, key) => { const call = submissionRequest(id, revision, key); return request(call.path, call.options); },
  jobResult: (id) => request(`/jobs/${encodeURIComponent(id)}/result`),
  calendar: (filters = {}) => request(`/calendar/deadlines${query(filters)}`),
  notifications: (filters = {}) => request(`/notifications${query(filters)}`),
  uploadResume: (file) => {
    const body = new FormData();
    body.append("file", file);
    return request("/resume/upload", { method: "POST", body, timeout: 60000 });
  },
  job: (id) => request(`/jobs/${encodeURIComponent(id)}`),
  skillProgress: () => request("/skills/progress"),
  compareSkills: (opportunityId) => request("/skills/compare", { method: "POST", body: { opportunity_id: opportunityId } }),
  matchResume: (opportunityId, documentId) => request(`/resume/match/${encodeURIComponent(opportunityId)}`, { method: "POST", body: { document_id: documentId } }),
};

export async function localAuth(action, credentials) {
  const legacyBase = API_BASE_URL.replace(/\/api\/v1$/, "/api");
  const response = await fetch(`${legacyBase}/auth/${action}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(credentials),
    cache: "no-store",
  });
  const payload = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(messageFromPayload(payload, response.status), response.status, payload);
  return payload;
}

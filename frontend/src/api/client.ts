import type {
  Analytics, ApiErrorBody, Claim, Match, MatchRow, MyReports, Notification, PendingDeposit, PersonRow, RecoveryCase,
  Report, ReportCreated, ReportRow, StaffAction, StaffSummary, TokenResponse, User,
} from "./types";

const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "";
const API = `${BASE}/api/v1`;
const TOKEN_KEY = "findback.token";

export const tokenStore = {
  get: () => { try { return localStorage.getItem(TOKEN_KEY); } catch { return null; } },
  set: (t: string) => { try { localStorage.setItem(TOKEN_KEY, t); } catch { /* ignore */ } },
  clear: () => { try { localStorage.removeItem(TOKEN_KEY); } catch { /* ignore */ } },
};

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string,
              public details: { field: string; message: string }[] = []) { super(message); }
}

let onUnauthorized: (() => void) | null = null;
export const setUnauthorizedHandler = (fn: () => void) => { onUnauthorized = fn; };

async function raw(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  const token = tokenStore.get();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  let res: Response;
  try { res = await fetch(`${API}${path}`, { ...init, headers }); }
  catch { throw new ApiError(0, "network_error", "Cannot reach the server. Check your connection and try again."); }
  if (!res.ok) {
    let body: Partial<ApiErrorBody> = {};
    try { body = await res.json(); } catch { /* non-JSON error */ }
    const e = body.error;
    if (res.status === 401 && token) { tokenStore.clear(); onUnauthorized?.(); }
    throw new ApiError(res.status, e?.code ?? "http_error", e?.message ?? `Request failed (${res.status})`, e?.details);
  }
  return res;
}

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  return (await raw(path, init)).json() as Promise<T>;
}
const post = <T>(path: string, body?: unknown) =>
  json<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });
const patch = <T>(path: string, body: unknown) => json<T>(path, { method: "PATCH", body: JSON.stringify(body) });
const qs = (o: Record<string, string | number | boolean | undefined | null>) => {
  const p = Object.entries(o).filter(([, v]) => v !== undefined && v !== null && v !== "" && v !== "all")
    .map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`);
  return p.length ? `?${p.join("&")}` : "";
};

export const api = {
  register: (d: { name: string; email: string; password: string }) => post<TokenResponse>("/auth/register", d),
  login: (d: { email: string; password: string }) => post<TokenResponse>("/auth/login", d),
  me: () => json<User>("/auth/me"),

  createLost: (fd: FormData) => json<ReportCreated>("/reports/lost", { method: "POST", body: fd }),
  createFound: (fd: FormData) => json<ReportCreated>("/reports/found", { method: "POST", body: fd }),
  myReports: () => json<MyReports>("/reports/mine"),
  editReport: (kind: "lost" | "found", id: number, body: Record<string, unknown>) => patch<Report>(`/reports/${kind}/${id}`, body),
  resolveLost: (id: number) => post<{ ok: boolean }>(`/reports/lost/${id}/resolve`),
  reportImage: async (kind: "lost" | "found", id: number) => (await raw(`/reports/${kind}/${id}/image`)).blob(),

  matches: (includeDismissed = false) => json<Match[]>(`/matches${qs({ include_dismissed: includeDismissed || undefined })}`),
  matchImage: async (id: number, which: "lost" | "found") => (await raw(`/matches/${id}/images/${which}`)).blob(),
  claim: (id: number, proof?: string) => post<Claim>(`/matches/${id}/interest`, { proof: proof || null }),
  dismiss: (id: number) => post<Match>(`/matches/${id}/dismiss`),
  restore: (id: number) => post<Match>(`/matches/${id}/restore`),
  recoveryRequests: () => json<Claim[]>("/recovery-requests"),
  cancelClaim: (id: number) => post<Claim>(`/recovery-requests/${id}/cancel`),

  notifications: () => json<Notification[]>("/notifications"),
  markRead: (id: number) => post<{ ok: boolean }>(`/notifications/${id}/read`),
  readAll: () => post<{ ok: boolean }>("/notifications/read-all"),

  staff: {
    summary: () => json<StaffSummary>("/staff/summary"),
    analytics: () => json<Analytics>("/staff/analytics"),
    deposits: () => json<PendingDeposit[]>("/staff/found/pending-deposits"),
    confirmDeposit: (id: number) => post<{ ok: boolean }>(`/staff/found/${id}/confirm-deposit`),
    cases: (status?: string, q?: string) => json<RecoveryCase[]>(`/staff/recovery-requests${qs({ status, q })}`),
    caseAction: (id: number, action: "verify" | "reject" | "complete") => post<RecoveryCase>(`/staff/recovery-requests/${id}/${action}`),
    matches: (filter?: string, minScore?: number, q?: string) => json<MatchRow[]>(`/staff/matches${qs({ filter, min_score: minScore, q })}`),
    people: (q?: string) => json<PersonRow[]>(`/staff/people${qs({ q })}`),
    reports: (kind: "lost" | "found", status?: string, q?: string) => json<ReportRow[]>(`/staff/reports${qs({ kind, status, q })}`),
    log: (target?: string, q?: string) => json<StaffAction[]>(`/staff/log${qs({ target, q })}`),
    exportCsv: async (what: string) => (await raw(`/staff/export/${what}.csv`)).blob(),
  },
};

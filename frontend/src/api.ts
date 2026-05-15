const TOKEN_KEY = "wemo_admin_token";

export function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) ?? "";
}

export function setToken(value: string) {
  if (value.trim()) {
    localStorage.setItem(TOKEN_KEY, value.trim());
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
}

async function apiFetch(path: string, init?: RequestInit) {
  const headers = new Headers(init?.headers);
  const t = getToken();
  if (t) {
    headers.set("Authorization", `Bearer ${t}`);
  }
  const res = await fetch(path, { ...init, headers });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = await res.json();
      if (j?.detail) {
        detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
      }
    } catch {
      /* ignore */
    }
    if (res.status === 401) {
      detail =
        detail && detail.length > 5
          ? detail
          : "Unauthorized (401). Set “Admin token” to match WEMO_ADMIN_PASSWORD, then Save token.";
    }
    throw new Error(detail || `HTTP ${res.status}`);
  }
  if (res.status === 204) {
    return null;
  }
  const ct = res.headers.get("content-type");
  if (ct?.includes("application/json")) {
    return res.json();
  }
  return res.text();
}

export type Device = {
  id: number;
  name: string;
  ip: string;
  port: number | null;
  model: string | null;
  serial: string | null;
  udn: string;
  last_seen: string;
  last_state: number | null;
  last_state_at: string | null;
  online: boolean;
  last_error: string | null;
};

export type Schedule = {
  id: number;
  device_id: number;
  action: "on" | "off";
  time_of_day: string;
  days_of_week: number[];
  enabled: boolean;
  created_at: string;
  updated_at: string;
};

export type DiscoverResult = {
  devices: Device[];
  discovered_this_run: number;
  message: string | null;
};

export const api = {
  health: () => apiFetch("/api/health") as Promise<{ status: string }>,
  listDevices: () => apiFetch("/api/devices") as Promise<Device[]>,
  discover: () => apiFetch("/api/discover", { method: "POST" }) as Promise<DiscoverResult>,
  manualDevice: (ip: string, name?: string) =>
    apiFetch("/api/devices/manual", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ip, name: name || null }),
    }) as Promise<Device>,
  deviceStatus: (id: number) =>
    apiFetch(`/api/devices/${id}/status`) as Promise<{
      device_id: number;
      online: boolean;
      last_state: number | null;
      last_state_at: string | null;
      last_error: string | null;
    }>,
  deviceOn: (id: number) => apiFetch(`/api/devices/${id}/on`, { method: "POST" }),
  deviceOff: (id: number) => apiFetch(`/api/devices/${id}/off`, { method: "POST" }),
  listSchedules: () => apiFetch("/api/schedules") as Promise<Schedule[]>,
  createSchedule: (body: {
    device_id: number;
    action: "on" | "off";
    time_of_day: string;
    days_of_week: number[];
    enabled?: boolean;
  }) =>
    apiFetch("/api/schedules", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }) as Promise<Schedule>,
  updateSchedule: (
    id: number,
    body: Partial<{
      device_id: number;
      action: "on" | "off";
      time_of_day: string;
      days_of_week: number[];
      enabled: boolean;
    }>,
  ) =>
    apiFetch(`/api/schedules/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }) as Promise<Schedule>,
  deleteSchedule: (id: number) =>
    apiFetch(`/api/schedules/${id}`, { method: "DELETE" }) as Promise<{ ok: boolean }>,
};

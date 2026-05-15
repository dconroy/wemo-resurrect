import { useCallback, useEffect, useMemo, useState } from "react";
import type { CSSProperties } from "react";
import { api, Device, Schedule, getToken, setToken } from "./api";
import { logoUrl } from "./branding";

const DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function fmtDays(days: number[]) {
  return [...days]
    .sort((a, b) => a - b)
    .map((i) => DOW[i] ?? String(i))
    .join(", ");
}

function cardStyle(online: boolean): CSSProperties {
  return {
    border: `1px solid ${online ? "#2d4a35" : "#4a2d2d"}`,
    borderRadius: 10,
    padding: "0.85rem 1rem",
    background: "#1a1d26",
    minWidth: 240,
    flex: "1 1 280px",
  };
}

export default function App() {
  const [devices, setDevices] = useState<Device[]>([]);
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [tokenInput, setTokenInput] = useState(getToken());
  const [manualIp, setManualIp] = useState("");
  const [manualName, setManualName] = useState("");
  const [schedDeviceId, setSchedDeviceId] = useState<number | "">("");
  const [schedAction, setSchedAction] = useState<"on" | "off">("on");
  const [schedTime, setSchedTime] = useState("18:00");
  const [schedDays, setSchedDays] = useState<number[]>([0, 1, 2, 3, 4, 5, 6]);
  const [editingId, setEditingId] = useState<number | null>(null);

  const deviceName = useMemo(() => {
    const m = new Map<number, string>();
    for (const d of devices) {
      m.set(d.id, d.name);
    }
    return m;
  }, [devices]);

  const load = useCallback(async () => {
    setMsg(null);
    const [devs, sch] = await Promise.all([
      api.listDevices(),
      api.listSchedules(),
    ]);
    setDevices(devs);
    setSchedules(sch);
    setSchedDeviceId((cur) => {
      if (cur === "" && devs.length) {
        return devs[0].id;
      }
      return cur;
    });
  }, []);

  useEffect(() => {
    load().catch((e: Error) => setMsg(e.message));
  }, [load]);

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setMsg(null);
    setInfo(null);
    try {
      await fn();
    } catch (e) {
      setMsg((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const toggleDay = (d: number) => {
    setSchedDays((prev) =>
      prev.includes(d) ? prev.filter((x) => x !== d) : [...prev, d].sort((a, b) => a - b),
    );
  };

  const resetScheduleForm = () => {
    setEditingId(null);
    setSchedAction("on");
    setSchedTime("18:00");
    setSchedDays([0, 1, 2, 3, 4, 5, 6]);
  };

  const startEdit = (s: Schedule) => {
    setEditingId(s.id);
    setSchedDeviceId(s.device_id);
    setSchedAction(s.action);
    setSchedTime(s.time_of_day);
    setSchedDays([...s.days_of_week]);
  };

  return (
    <div style={{ maxWidth: 1100, margin: "0 auto" }}>
      <header
        style={{
          marginBottom: "1.25rem",
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          gap: "1rem 1.25rem",
        }}
      >
        <img
          src={logoUrl}
          alt="WeMo Resurrect"
          style={{
            maxWidth: 220,
            maxHeight: 100,
            width: "auto",
            height: "auto",
            objectFit: "contain",
            display: "block",
            borderRadius: 12,
            boxShadow: "0 4px 24px rgba(0,0,0,0.35)",
          }}
        />
        <div style={{ flex: "1 1 200px", minWidth: 0 }}>
          <h1 style={{ margin: "0 0 0.25rem", fontSize: "1.5rem" }}>WeMo Resurrect</h1>
          <p style={{ margin: 0, color: "#9aa3b2", fontSize: "0.95rem" }}>
            LAN-only dashboard for legacy Belkin WeMo plugs and switches. No cloud.
          </p>
        </div>
      </header>

      <section
        style={{
          marginBottom: "1.25rem",
          padding: "0.75rem 1rem",
          background: "#1a1d26",
          borderRadius: 8,
          border: "1px solid #2a3140",
        }}
      >
        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.75rem", alignItems: "end" }}>
          <div>
            <label style={{ display: "block", fontSize: "0.8rem", color: "#9aa3b2" }}>
              Admin token (optional)
            </label>
            <input
              type="password"
              autoComplete="off"
              value={tokenInput}
              onChange={(e) => setTokenInput(e.target.value)}
              placeholder="matches WEMO_ADMIN_PASSWORD"
              style={{
                width: 220,
                padding: "0.35rem 0.5rem",
                borderRadius: 6,
                border: "1px solid #3d4556",
                background: "#12141a",
                color: "#e8eaef",
              }}
            />
          </div>
          <button
            type="button"
            onClick={() => {
              setToken(tokenInput);
              setMsg(null);
              setInfo("Token saved in this browser.");
            }}
            style={btnSecondary}
          >
            Save token
          </button>
        </div>
        <p style={{ margin: "0.5rem 0 0", fontSize: "0.8rem", color: "#6b7380" }}>
          When `WEMO_ADMIN_PASSWORD` is set, **every** `/api/*` call except `GET /api/health` must send that value as a Bearer token (the UI has an “Admin token” field for this).
        </p>
      </section>

      <section
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: "0.75rem",
          marginBottom: "1.5rem",
          alignItems: "end",
        }}
      >
        <button
          type="button"
          disabled={busy}
          onClick={() =>
            run(async () => {
              const result = await api.discover();
              setDevices(result.devices);
              setInfo(
                result.discovered_this_run > 0
                  ? `Discovery finished: ${result.discovered_this_run} device(s) responded this scan.`
                  : result.message ||
                      "Discovery finished: no SSDP replies this scan.",
              );
              await load();
            })
          }
          style={btnPrimary}
        >
          Discover devices
        </button>
        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", alignItems: "end" }}>
          <div>
            <label style={{ display: "block", fontSize: "0.8rem", color: "#9aa3b2" }}>
              Add by IP
            </label>
            <input
              value={manualIp}
              onChange={(e) => setManualIp(e.target.value)}
              placeholder="192.168.1.50"
              style={inputStyle}
            />
          </div>
          <div>
            <label style={{ display: "block", fontSize: "0.8rem", color: "#9aa3b2" }}>
              Name (optional)
            </label>
            <input
              value={manualName}
              onChange={(e) => setManualName(e.target.value)}
              placeholder="Living room lamp"
              style={{ ...inputStyle, width: 180 }}
            />
          </div>
          <button
            type="button"
            disabled={busy || !manualIp.trim()}
            onClick={() =>
              run(async () => {
                const d = await api.manualDevice(
                  manualIp.trim(),
                  manualName.trim() || undefined,
                );
                setManualIp("");
                setManualName("");
                setDevices((prev) => {
                  const others = prev.filter((x) => x.id !== d.id);
                  return [...others, d].sort((a, b) => a.name.localeCompare(b.name));
                });
                setSchedDeviceId(d.id);
              })
            }
            style={btnPrimary}
          >
            Add device
          </button>
        </div>
      </section>

      {info && (
        <div
          style={{
            marginBottom: "1rem",
            padding: "0.55rem 0.85rem",
            background: "#1e2a3d",
            borderRadius: 6,
            color: "#c5d4f0",
            border: "1px solid #2a4060",
            fontSize: "0.92rem",
            lineHeight: 1.45,
          }}
        >
          {info}
        </div>
      )}

      {msg && (
        <div
          style={{
            marginBottom: "1rem",
            padding: "0.5rem 0.75rem",
            background: "#3a2424",
            borderRadius: 6,
            color: "#ffb4b4",
          }}
        >
          {msg}
        </div>
      )}

      <h2 style={{ fontSize: "1.1rem", margin: "0 0 0.75rem" }}>Devices</h2>
      {devices.length === 0 ? (
        <p style={{ color: "#9aa3b2" }}>No devices yet. Run discovery or add one by IP.</p>
      ) : (
        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.75rem" }}>
          {devices.map((d) => (
            <div key={d.id} style={cardStyle(d.online)}>
              <div style={{ fontWeight: 600, marginBottom: "0.25rem" }}>{d.name}</div>
              <div style={{ fontSize: "0.85rem", color: "#9aa3b2", marginBottom: "0.35rem" }}>
                {d.ip}
                {d.model ? ` · ${d.model}` : ""}
              </div>
              <div style={{ fontSize: "0.85rem", marginBottom: "0.5rem" }}>
                <span
                  style={{
                    padding: "0.1rem 0.4rem",
                    borderRadius: 4,
                    background: d.online ? "#1e3d2a" : "#3d1e1e",
                    color: d.online ? "#9dffb4" : "#ffb4b4",
                  }}
                >
                  {d.online ? "online" : "offline"}
                </span>
                {d.last_state !== null && d.last_state !== undefined && (
                  <span style={{ marginLeft: "0.5rem" }}>
                    Switch: <strong>{d.last_state ? "ON" : "OFF"}</strong>
                  </span>
                )}
              </div>
              {d.last_error && (
                <div
                  style={{
                    fontSize: "0.8rem",
                    color: "#ffb4b4",
                    marginBottom: "0.5rem",
                    wordBreak: "break-word",
                  }}
                >
                  {d.last_error}
                </div>
              )}
              <div style={{ display: "flex", flexWrap: "wrap", gap: "0.35rem" }}>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() =>
                    run(async () => {
                      const st = await api.deviceStatus(d.id);
                      setDevices((prev) =>
                        prev.map((x) =>
                          x.id === d.id
                            ? {
                                ...x,
                                online: st.online,
                                last_state: st.last_state,
                                last_state_at: st.last_state_at,
                                last_error: st.last_error,
                              }
                            : x,
                        ),
                      );
                    })
                  }
                  style={btnSecondary}
                >
                  Refresh
                </button>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() =>
                    run(async () => {
                      await api.deviceOn(d.id);
                      await load();
                    })
                  }
                  style={btnOn}
                >
                  On
                </button>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() =>
                    run(async () => {
                      await api.deviceOff(d.id);
                      await load();
                    })
                  }
                  style={btnOff}
                >
                  Off
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <h2 style={{ fontSize: "1.1rem", margin: "1.75rem 0 0.75rem" }}>Schedules</h2>
      <p style={{ color: "#9aa3b2", fontSize: "0.9rem", marginTop: 0 }}>
        Times use the server&apos;s local timezone. Weekdays: Mon = 0 through Sun = 6.
      </p>

      <div
        style={{
          marginBottom: "1rem",
          padding: "1rem",
          background: "#1a1d26",
          borderRadius: 8,
          border: "1px solid #2a3140",
        }}
      >
        <div style={{ fontWeight: 600, marginBottom: "0.75rem" }}>
          {editingId ? `Edit schedule #${editingId}` : "New schedule"}
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.75rem", alignItems: "end" }}>
          <div>
            <label style={labelStyle}>Device</label>
            <select
              value={schedDeviceId === "" ? "" : String(schedDeviceId)}
              onChange={(e) => setSchedDeviceId(Number(e.target.value))}
              style={inputStyle}
              disabled={!devices.length}
            >
              {devices.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label style={labelStyle}>Action</label>
            <select
              value={schedAction}
              onChange={(e) => setSchedAction(e.target.value as "on" | "off")}
              style={inputStyle}
            >
              <option value="on">Turn on</option>
              <option value="off">Turn off</option>
            </select>
          </div>
          <div>
            <label style={labelStyle}>Time (HH:MM)</label>
            <input
              value={schedTime}
              onChange={(e) => setSchedTime(e.target.value)}
              style={{ ...inputStyle, width: 90 }}
            />
          </div>
        </div>
        <div style={{ marginTop: "0.75rem" }}>
          <span style={{ ...labelStyle, display: "block", marginBottom: "0.35rem" }}>
            Days
          </span>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "0.35rem" }}>
            {DOW.map((label, idx) => (
              <label
                key={label}
                style={{
                  fontSize: "0.85rem",
                  padding: "0.2rem 0.45rem",
                  borderRadius: 4,
                  background: schedDays.includes(idx) ? "#2a3f6d" : "#2a3140",
                  cursor: "pointer",
                }}
              >
                <input
                  type="checkbox"
                  checked={schedDays.includes(idx)}
                  onChange={() => toggleDay(idx)}
                  style={{ marginRight: "0.25rem" }}
                />
                {label}
              </label>
            ))}
          </div>
        </div>
        <div style={{ marginTop: "0.85rem", display: "flex", gap: "0.5rem" }}>
          <button
            type="button"
            disabled={busy || schedDeviceId === "" || !schedDays.length}
            onClick={() =>
              run(async () => {
                if (schedDeviceId === "") {
                  return;
                }
                if (editingId) {
                  await api.updateSchedule(editingId, {
                    device_id: schedDeviceId,
                    action: schedAction,
                    time_of_day: schedTime,
                    days_of_week: schedDays,
                  });
                } else {
                  await api.createSchedule({
                    device_id: schedDeviceId,
                    action: schedAction,
                    time_of_day: schedTime,
                    days_of_week: schedDays,
                  });
                }
                resetScheduleForm();
                await load();
              })
            }
            style={btnPrimary}
          >
            {editingId ? "Save changes" : "Create schedule"}
          </button>
          {editingId && (
            <button type="button" onClick={() => resetScheduleForm()} style={btnSecondary}>
              Cancel edit
            </button>
          )}
        </div>
      </div>

      {schedules.length === 0 ? (
        <p style={{ color: "#9aa3b2" }}>No schedules yet.</p>
      ) : (
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.9rem" }}>
          <thead>
            <tr style={{ textAlign: "left", borderBottom: "1px solid #2a3140" }}>
              <th style={thStyle}>Device</th>
              <th style={thStyle}>Action</th>
              <th style={thStyle}>Time</th>
              <th style={thStyle}>Days</th>
              <th style={thStyle}>Enabled</th>
              <th style={thStyle} />
            </tr>
          </thead>
          <tbody>
            {schedules.map((s) => (
              <tr key={s.id} style={{ borderBottom: "1px solid #252a36" }}>
                <td style={tdStyle}>{deviceName.get(s.device_id) ?? `#${s.device_id}`}</td>
                <td style={tdStyle}>{s.action}</td>
                <td style={tdStyle}>{s.time_of_day}</td>
                <td style={tdStyle}>{fmtDays(s.days_of_week)}</td>
                <td style={tdStyle}>
                  <input
                    type="checkbox"
                    checked={s.enabled}
                    disabled={busy}
                    onChange={() =>
                      run(async () => {
                        await api.updateSchedule(s.id, { enabled: !s.enabled });
                        await load();
                      })
                    }
                  />
                </td>
                <td style={tdStyle}>
                  <button type="button" style={btnSmall} onClick={() => startEdit(s)}>
                    Edit
                  </button>{" "}
                  <button
                    type="button"
                    style={btnSmall}
                    onClick={() =>
                      run(async () => {
                        await api.deleteSchedule(s.id);
                        if (editingId === s.id) {
                          resetScheduleForm();
                        }
                        await load();
                      })
                    }
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

const thStyle: CSSProperties = { padding: "0.4rem 0.5rem", color: "#9aa3b2" };
const tdStyle: CSSProperties = { padding: "0.45rem 0.5rem", verticalAlign: "middle" };
const labelStyle: CSSProperties = {
  display: "block",
  fontSize: "0.8rem",
  color: "#9aa3b2",
  marginBottom: "0.2rem",
};
const inputStyle: CSSProperties = {
  padding: "0.35rem 0.5rem",
  borderRadius: 6,
  border: "1px solid #3d4556",
  background: "#12141a",
  color: "#e8eaef",
  minWidth: 140,
};

const btnPrimary: CSSProperties = {
  padding: "0.45rem 0.85rem",
  borderRadius: 6,
  border: "none",
  background: "#3d5afe",
  color: "#fff",
  fontWeight: 600,
};

const btnSecondary: CSSProperties = {
  padding: "0.45rem 0.85rem",
  borderRadius: 6,
  border: "1px solid #3d4556",
  background: "#252a36",
  color: "#e8eaef",
};

const btnOn: CSSProperties = {
  ...btnSecondary,
  background: "#1e3d2a",
  borderColor: "#2d5a40",
};

const btnOff: CSSProperties = {
  ...btnSecondary,
  background: "#3d1e1e",
  borderColor: "#5a2d2d",
};

const btnSmall: CSSProperties = {
  ...btnSecondary,
  padding: "0.25rem 0.5rem",
  fontSize: "0.8rem",
};

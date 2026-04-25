import { useState, useMemo } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell
} from "recharts";
import { useCompany } from "../components/CompanyContext";
import { useClaudeInsight } from "../hooks/useClaudeInsight";
import { formatCurrency, formatVolume } from "../utils/formatCurrency";

// ─── Mock data (mirrors production_plan output from Session 4 LP engine) ──────
const TODAY = "24 Apr 2025";

const mockPlan = [
  {
    sequence: 1,
    sku: "P1-SKU-12",
    display: "Product 1 — 12mm",
    brand: "P1",
    target_mt: 480,
    actual_mt: null,
    status: "IN_PROGRESS",
    start_time: "06:00",
    end_time: "09:00",
    billet_draw_mt: 504,
    urgency_score: 92,
    notes: "High demand — priority slot",
  },
  {
    sequence: 2,
    sku: "P1-SKU-10",
    display: "Product 1 — 10mm",
    brand: "P1",
    target_mt: 380,
    actual_mt: null,
    status: "QUEUED",
    start_time: "09:00",
    end_time: "11:30",
    billet_draw_mt: 399,
    urgency_score: 84,
    notes: "",
  },
  {
    sequence: 3,
    sku: "P1-SKU-16",
    display: "Product 1 — 16mm",
    brand: "P1",
    target_mt: 340,
    actual_mt: null,
    status: "QUEUED",
    start_time: "11:30",
    end_time: "13:30",
    billet_draw_mt: 357,
    urgency_score: 76,
    notes: "Changeover: +2 hrs added",
  },
  {
    sequence: 4,
    sku: "CHANGEOVER",
    display: "Changeover",
    brand: null,
    target_mt: null,
    actual_mt: null,
    status: "CHANGEOVER",
    start_time: "13:30",
    end_time: "15:30",
    billet_draw_mt: 0,
    urgency_score: null,
    notes: "SKU switch: 16mm → 8mm",
  },
  {
    sequence: 5,
    sku: "P1-SKU-8",
    display: "Product 1 — 8mm",
    brand: "P1",
    target_mt: 260,
    actual_mt: null,
    status: "QUEUED",
    start_time: "15:30",
    end_time: "17:00",
    billet_draw_mt: 273,
    urgency_score: 68,
    notes: "",
  },
  {
    sequence: 6,
    sku: "P2-SKU-12",
    display: "Product 2 — 12mm",
    brand: "P2",
    target_mt: 560,
    actual_mt: null,
    status: "QUEUED",
    start_time: "17:00",
    end_time: "20:30",
    billet_draw_mt: 588,
    urgency_score: 58,
    notes: "P2 allocation slot",
  },
  {
    sequence: 7,
    sku: "P2-SKU-10",
    display: "Product 2 — 10mm",
    brand: "P2",
    target_mt: 420,
    actual_mt: null,
    status: "QUEUED",
    start_time: "20:30",
    end_time: "23:00",
    billet_draw_mt: 441,
    urgency_score: 51,
    notes: "",
  },
  {
    sequence: 8,
    sku: "P2-SKU-16",
    display: "Product 2 — 16mm",
    brand: "P2",
    target_mt: 360,
    actual_mt: null,
    status: "QUEUED",
    start_time: "23:00",
    end_time: "02:00",
    billet_draw_mt: 378,
    urgency_score: 44,
    notes: "",
  },
];

const mockBilletStock = {
  p1_stock_mt: 2840,
  p2_stock_mt: 2210,
  p1_required_today: 1533,
  p2_required_today: 1407,
  p1_pipeline_mt: 0,
  p2_pipeline_mt: 200,
};

const mockMillSummary = {
  total_target_mt: 2800,
  changeover_hrs: 2,
  rolling_hrs: 14,
  scheduled_hrs: 16,
  mill_rate_mth: 18.8,
  capacity_utilisation_pct: 87.5,
};

const mockAlerts = [
  { level: "warn",  text: "P1 billet stock covers 1.85 days at current run rate — monitor closely." },
  { level: "info",  text: "Changeover at 13:30 adds 2 hrs of non-productive mill time today." },
  { level: "ok",    text: "P2 billet adequate — 200 MT pipeline inbound covers projected shortfall." },
];

// ─── Sub-components ───────────────────────────────────────────────────────────
function StatusBadge({ status }) {
  const map = {
    IN_PROGRESS: { label: "In Progress", bg: "#16a34a", text: "#dcfce7" },
    QUEUED:      { label: "Queued",      bg: "#0c447c", text: "#bfdbfe" },
    CHANGEOVER:  { label: "Changeover",  bg: "#7c3aed", text: "#ede9fe" },
    DONE:        { label: "Done",        bg: "#334155", text: "#cbd5e1" },
  };
  const s = map[status] || map.QUEUED;
  return (
    <span style={{
      background: s.bg, color: s.text, fontSize: 10,
      padding: "2px 7px", borderRadius: 4, fontWeight: 600, letterSpacing: "0.04em",
    }}>{s.label}</span>
  );
}

function AlertRow({ level, text }) {
  const map = { warn: { bg: "#f59e0b22", border: "#f59e0b", icon: "⚠", col: "#f59e0b" }, info: { bg: "#3b82f622", border: "#3b82f6", icon: "ℹ", col: "#60a5fa" }, ok: { bg: "#22c55e22", border: "#22c55e", icon: "✓", col: "#22c55e" } };
  const s = map[level] || map.info;
  return (
    <div style={{
      background: s.bg, border: `1px solid ${s.border}33`,
      borderLeft: `3px solid ${s.border}`,
      borderRadius: 6, padding: "8px 12px",
      display: "flex", gap: 8, alignItems: "flex-start", marginBottom: 8,
    }}>
      <span style={{ color: s.col, fontSize: 13, lineHeight: 1 }}>{s.icon}</span>
      <span style={{ fontSize: 12, color: "var(--text)", lineHeight: 1.5 }}>{text}</span>
    </div>
  );
}

function BilletGauge({ label, stock, required, pipeline, accent }) {
  const available = stock + pipeline;
  const days = +(available / (required || 1)).toFixed(1);
  const pct = Math.min((available / (required * 2)) * 100, 100);
  const ok = days >= 2;
  return (
    <div style={{ padding: "12px 0", borderBottom: "1px solid var(--border)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4, fontSize: 12 }}>
        <span style={{ color: "var(--muted)" }}>{label}</span>
        <span style={{ fontFamily: "'DM Mono', monospace", color: ok ? "#22c55e" : "#f59e0b" }}>
          {available.toLocaleString()} MT available
        </span>
      </div>
      <div style={{ height: 5, background: "var(--border)", borderRadius: 3, overflow: "hidden", marginBottom: 4 }}>
        <div style={{ height: "100%", width: `${pct}%`, background: ok ? "#22c55e" : "#f59e0b", borderRadius: 3 }} />
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "var(--muted)" }}>
        <span>Required today: {required.toLocaleString()} MT {pipeline > 0 ? `· Pipeline: +${pipeline} MT` : ""}</span>
        <span>{days} days cover</span>
      </div>
    </div>
  );
}

function InsightStrip({ insight, loading, refresh, accent }) {
  return (
    <div style={{
      background: "var(--surface)", border: "1px solid var(--border)",
      borderLeft: `4px solid ${accent}`,
      borderRadius: 8, padding: "12px 16px",
      display: "flex", alignItems: "flex-start", gap: 12, marginBottom: 24,
    }}>
      <div style={{ fontSize: 16 }}>⚡</div>
      <div style={{ flex: 1, fontSize: 13, color: "var(--text)", lineHeight: 1.5 }}>
        {loading ? <span style={{ color: "var(--muted)" }}>Generating supervisor briefing…</span> : insight}
      </div>
      <button onClick={refresh} style={{
        background: "none", border: "1px solid var(--border)", borderRadius: 6,
        padding: "4px 10px", fontSize: 11, color: "var(--muted)", cursor: "pointer",
      }}>↻</button>
    </div>
  );
}

// ─── Main Screen ──────────────────────────────────────────────────────────────
export default function DailyRollingPlan() {
  const { company } = useCompany();
  const accent  = company?.primary_colour  || "#e67e22";
  const accent2 = company?.secondary_colour || "#2c3e50";

  const [selectedSeq, setSelectedSeq] = useState(null);

  const productionSlots = mockPlan.filter(p => p.sku !== "CHANGEOVER");
  const totalTarget = productionSlots.reduce((s, p) => s + (p.target_mt || 0), 0);
  const totalBillet = productionSlots.reduce((s, p) => s + (p.billet_draw_mt || 0), 0);

  const chartData = productionSlots.map(p => ({
    name: p.display.replace("Product 1 — ", "P1-").replace("Product 2 — ", "P2-"),
    target_mt: p.target_mt,
    brand: p.brand,
    urgency: p.urgency_score,
  }));

  const promptData = useMemo(() => ({
    screen: "Daily Rolling Plan",
    date: TODAY,
    total_target_mt: totalTarget,
    total_billet_draw_mt: totalBillet,
    rolling_hrs: mockMillSummary.rolling_hrs,
    changeover_hrs: mockMillSummary.changeover_hrs,
    p1_billet_days: 1.85,
    p2_billet_days: 2.57,
    first_sku: "Product 1 — 12mm (in progress)",
    capacity_utilisation_pct: mockMillSummary.capacity_utilisation_pct,
    alert_count: mockAlerts.filter(a => a.level === "warn").length,
  }), []);

  const { insight, loading, refresh } = useClaudeInsight(
    `You are a steel mill production supervisor assistant. 
    Give a 2–3 sentence morning briefing for today's rolling plan: ${JSON.stringify(promptData)}. 
    Mention the most important alert, the day's target, and one thing the supervisor should watch. 
    Practical language, no jargon.`,
    [promptData]
  );

  const css = `
    :root { --surface: #1a1f2e; --border: rgba(255,255,255,0.08); --text: #f1f5f9; --muted: #64748b; }
    @media (prefers-color-scheme: light) {
      :root { --surface: #ffffff; --border: rgba(0,0,0,0.08); --text: #1e293b; --muted: #94a3b8; }
    }
    .plan-row { cursor: pointer; transition: background 0.15s; }
    .plan-row:hover { background: rgba(255,255,255,0.04) !important; }
  `;

  return (
    <>
      <style>{css}</style>
      <div style={{ padding: "0 0 40px" }}>

        {/* Date header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
          <div>
            <div style={{ fontSize: 11, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>Daily Rolling Plan</div>
            <div style={{ fontSize: 18, fontWeight: 600, color: "var(--text)", fontFamily: "'DM Mono', monospace" }}>{TODAY}</div>
          </div>
          <div style={{ display: "flex", gap: 20, fontSize: 12 }}>
            <div style={{ textAlign: "right" }}>
              <div style={{ color: "var(--muted)", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.05em" }}>Day Target</div>
              <div style={{ fontFamily: "'DM Mono', monospace", color: "var(--text)", fontSize: 18, fontWeight: 600 }}>{totalTarget.toLocaleString()} MT</div>
            </div>
            <div style={{ textAlign: "right" }}>
              <div style={{ color: "var(--muted)", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.05em" }}>Billet Draw</div>
              <div style={{ fontFamily: "'DM Mono', monospace", color: accent, fontSize: 18, fontWeight: 600 }}>{totalBillet.toLocaleString()} MT</div>
            </div>
            <div style={{ textAlign: "right" }}>
              <div style={{ color: "var(--muted)", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.05em" }}>Mill Util</div>
              <div style={{ fontFamily: "'DM Mono', monospace", color: "#22c55e", fontSize: 18, fontWeight: 600 }}>{mockMillSummary.capacity_utilisation_pct}%</div>
            </div>
          </div>
        </div>

        <InsightStrip insight={insight} loading={loading} refresh={refresh} accent={accent} />

        {/* Alerts */}
        <div style={{ marginBottom: 20 }}>
          {mockAlerts.map((a, i) => <AlertRow key={i} level={a.level} text={a.text} />)}
        </div>

        {/* Plan table + sidebar */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 280px", gap: 16, marginBottom: 16 }}>

          {/* Plan table */}
          <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, overflow: "hidden" }}>
            <div style={{ padding: "10px 14px", fontSize: 12, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.06em", borderBottom: "1px solid var(--border)" }}>
              Today's Rolling Sequence
            </div>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border)" }}>
                  {["#","SKU","Status","Time Window","Target MT","Billet Draw","Urgency"].map(h => (
                    <th key={h} style={{ padding: "7px 10px", textAlign: h === "#" || h === "SKU" || h === "Status" ? "left" : "right", color: "var(--muted)", fontWeight: 500, fontSize: 11 }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {mockPlan.map((row, i) => {
                  const isChangeover = row.sku === "CHANGEOVER";
                  const isSelected = selectedSeq === row.sequence;
                  return (
                    <tr
                      key={i}
                      className="plan-row"
                      onClick={() => !isChangeover && setSelectedSeq(isSelected ? null : row.sequence)}
                      style={{
                        borderBottom: "1px solid var(--border)",
                        background: isSelected ? `${accent}18` : isChangeover ? "rgba(124,58,237,0.07)" : "transparent",
                        opacity: isChangeover ? 0.7 : 1,
                      }}
                    >
                      <td style={{ padding: "8px 10px", color: "var(--muted)", fontFamily: "'DM Mono', monospace" }}>{isChangeover ? "—" : row.sequence}</td>
                      <td style={{ padding: "8px 10px", color: isChangeover ? "#a78bfa" : row.brand === "P1" ? accent : "var(--muted)", fontWeight: 500 }}>
                        {isChangeover ? `⇄ ${row.notes}` : row.display}
                      </td>
                      <td style={{ padding: "8px 10px" }}>{!isChangeover && <StatusBadge status={row.status} />}</td>
                      <td style={{ padding: "8px 10px", textAlign: "right", fontFamily: "'DM Mono', monospace", color: "var(--muted)", fontSize: 11 }}>{row.start_time}–{row.end_time}</td>
                      <td style={{ padding: "8px 10px", textAlign: "right", fontFamily: "'DM Mono', monospace", color: "var(--text)" }}>
                        {row.target_mt ? row.target_mt.toLocaleString() : "—"}
                      </td>
                      <td style={{ padding: "8px 10px", textAlign: "right", fontFamily: "'DM Mono', monospace", color: accent }}>
                        {row.billet_draw_mt > 0 ? row.billet_draw_mt.toLocaleString() : "—"}
                      </td>
                      <td style={{ padding: "8px 10px", textAlign: "right" }}>
                        {row.urgency_score != null && (
                          <span style={{
                            fontFamily: "'DM Mono', monospace", fontSize: 12,
                            color: row.urgency_score > 80 ? "#ef4444" : row.urgency_score > 65 ? "#f59e0b" : "#22c55e",
                            fontWeight: 600,
                          }}>{row.urgency_score}</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {selectedSeq && (() => {
              const row = mockPlan.find(p => p.sequence === selectedSeq);
              return row ? (
                <div style={{ padding: "10px 14px", background: `${accent}10`, borderTop: "1px solid var(--border)", fontSize: 12 }}>
                  <span style={{ color: "var(--muted)" }}>Notes: </span>
                  <span style={{ color: "var(--text)" }}>{row.notes || "No notes for this slot."}</span>
                </div>
              ) : null;
            })()}
          </div>

          {/* Billet & Mill sidebar */}
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {/* Billet stocks */}
            <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, padding: "14px 16px" }}>
              <div style={{ fontSize: 12, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4 }}>
                Billet Stock
              </div>
              <BilletGauge
                label="Product 1 Billet"
                stock={mockBilletStock.p1_stock_mt}
                required={mockBilletStock.p1_required_today}
                pipeline={mockBilletStock.p1_pipeline_mt}
                accent={accent}
              />
              <BilletGauge
                label="Product 2 Billet"
                stock={mockBilletStock.p2_stock_mt}
                required={mockBilletStock.p2_required_today}
                pipeline={mockBilletStock.p2_pipeline_mt}
                accent={accent2}
              />
            </div>

            {/* Mill runtime breakdown */}
            <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, padding: "14px 16px" }}>
              <div style={{ fontSize: 12, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 12 }}>
                Mill Runtime Today
              </div>
              {[
                { label: "Rolling hrs", val: mockMillSummary.rolling_hrs, of: 16, col: accent },
                { label: "Changeover hrs", val: mockMillSummary.changeover_hrs, of: 16, col: "#a78bfa" },
                { label: "Scheduled hrs", val: mockMillSummary.scheduled_hrs, of: 24, col: "#22c55e" },
              ].map((r, i) => (
                <div key={i} style={{ marginBottom: 10 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, marginBottom: 3 }}>
                    <span style={{ color: "var(--muted)" }}>{r.label}</span>
                    <span style={{ fontFamily: "'DM Mono', monospace", color: r.col }}>{r.val} hrs</span>
                  </div>
                  <div style={{ height: 5, background: "var(--border)", borderRadius: 3, overflow: "hidden" }}>
                    <div style={{ height: "100%", width: `${(r.val / r.of) * 100}%`, background: r.col, borderRadius: 3 }} />
                  </div>
                </div>
              ))}
              <div style={{ borderTop: "1px solid var(--border)", paddingTop: 10, marginTop: 4, display: "flex", justifyContent: "space-between", fontSize: 12 }}>
                <span style={{ color: "var(--muted)" }}>Capacity utilisation</span>
                <span style={{ fontFamily: "'DM Mono', monospace", color: "#22c55e", fontWeight: 600 }}>{mockMillSummary.capacity_utilisation_pct}%</span>
              </div>
            </div>
          </div>
        </div>

        {/* Target by SKU bar chart */}
        <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, padding: "16px 16px 8px" }}>
          <div style={{ fontSize: 12, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 14 }}>
            Today's Target MT by SKU
          </div>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={chartData} margin={{ top: 0, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
              <XAxis dataKey="name" tick={{ fontSize: 10, fill: "var(--muted)" }} />
              <YAxis tick={{ fontSize: 10, fill: "var(--muted)", fontFamily: "'DM Mono', monospace" }} />
              <Tooltip content={({ active, payload, label }) => {
                if (!active || !payload?.length) return null;
                return (
                  <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 6, padding: "8px 12px", fontSize: 12 }}>
                    <div style={{ fontWeight: 600, color: "var(--text)", marginBottom: 4 }}>{label}</div>
                    <div style={{ fontFamily: "'DM Mono', monospace", color: "var(--text)" }}>{payload[0].value} MT</div>
                    <div style={{ color: "var(--muted)", marginTop: 2 }}>Urgency: {payload[0]?.payload?.urgency}</div>
                  </div>
                );
              }} />
              <Bar dataKey="target_mt" name="Target MT" radius={[3, 3, 0, 0]}>
                {chartData.map((entry, i) => (
                  <Cell key={i} fill={entry.brand === "P1" ? accent : accent2} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

      </div>
    </>
  );
}

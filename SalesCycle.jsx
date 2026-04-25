import { useState, useMemo } from "react";
import {
  LineChart, Line, BarChart, Bar, AreaChart, Area, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine
} from "recharts";
import { useCompany } from "../components/CompanyContext";
import { useClaudeInsight } from "../hooks/useClaudeInsight";
import { formatCurrency, formatPerTon, formatVolume } from "../utils/formatCurrency";

// ─── Mock data ────────────────────────────────────────────────────────────────
const mockMonthlySales = [
  { month:"Nov", volume_mt:4650, revenue_inr:27900000, realisation_per_ton:6000, target_mt:4800 },
  { month:"Dec", volume_mt:4020, revenue_inr:24521000, realisation_per_ton:6100, target_mt:4500 },
  { month:"Jan", volume_mt:5010, revenue_inr:31062000, realisation_per_ton:6200, target_mt:5000 },
  { month:"Feb", volume_mt:4880, revenue_inr:30256000, realisation_per_ton:6200, target_mt:5000 },
  { month:"Mar", volume_mt:5290, revenue_inr:33416000, realisation_per_ton:6316, target_mt:5200 },
  { month:"Apr", volume_mt:5120, revenue_inr:32614000, realisation_per_ton:6370, target_mt:5200 },
];

// 12-month forecast (Apr already actuals, May–Mar forecast)
const mockForecast = [
  { month:"Apr", volume_mt:5120,  is_forecast:false },
  { month:"May", volume_mt:5350,  is_forecast:true },
  { month:"Jun", volume_mt:5480,  is_forecast:true },
  { month:"Jul", volume_mt:5210,  is_forecast:true },
  { month:"Aug", volume_mt:5090,  is_forecast:true },
  { month:"Sep", volume_mt:5320,  is_forecast:true },
  { month:"Oct", volume_mt:5580,  is_forecast:true },
  { month:"Nov", volume_mt:5720,  is_forecast:true },
  { month:"Dec", volume_mt:5150,  is_forecast:true },
  { month:"Jan", volume_mt:5890,  is_forecast:true },
  { month:"Feb", volume_mt:6020,  is_forecast:true },
  { month:"Mar", volume_mt:6180,  is_forecast:true },
];

const mockSKUSales = [
  { sku:"8mm",  p1:780,  p2:290, real_p1:6500, real_p2:6100 },
  { sku:"10mm", p1:1010, p2:400, real_p1:6450, real_p2:6050 },
  { sku:"12mm", p1:1260, p2:560, real_p1:6380, real_p2:5990 },
  { sku:"16mm", p1:920,  p2:360, real_p1:6340, real_p2:5950 },
  { sku:"20mm", p1:660,  p2:200, real_p1:6400, real_p2:6010 },
  { sku:"25mm", p1:370,  p2:80,  real_p1:6420, real_p2:6020 },
  { sku:"32mm", p1:95,   p2:0,   real_p1:6300, real_p2:0 },
];

const mockRegionMix = [
  { name:"Chennai", value:41, color:"#e67e22" },
  { name:"Coimbatore", value:19, color:"#2c3e50" },
  { name:"Madurai", value:14, color:"#3498db" },
  { name:"Salem", value:12, color:"#27ae60" },
  { name:"Others", value:14, color:"#7f8c8d" },
];

// ─── Sub-components ───────────────────────────────────────────────────────────
function KpiCard({ label, value, sub, delta, accent }) {
  const up = delta >= 0;
  return (
    <div style={{
      background: "var(--surface)", border: "1px solid var(--border)",
      borderRadius: 8, padding: "14px 16px", borderTop: `3px solid ${accent}`,
    }}>
      <div style={{ fontSize: 11, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 6 }}>{label}</div>
      <div style={{ fontSize: 22, fontFamily: "'DM Mono', monospace", fontWeight: 600, color: "var(--text)" }}>{value}</div>
      {sub && <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 2 }}>{sub}</div>}
      {delta !== undefined && (
        <div style={{ fontSize: 11, marginTop: 4, color: up ? "#22c55e" : "#ef4444" }}>
          {up ? "▲" : "▼"} {Math.abs(delta)}% vs prev month
        </div>
      )}
    </div>
  );
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: "var(--surface)", border: "1px solid var(--border)",
      borderRadius: 6, padding: "8px 12px", fontSize: 12,
    }}>
      <div style={{ fontWeight: 600, marginBottom: 4, color: "var(--text)" }}>{label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ color: p.color, fontFamily: "'DM Mono', monospace" }}>
          {p.name}: {typeof p.value === "number" ? p.value.toLocaleString() : p.value}
        </div>
      ))}
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
        {loading ? <span style={{ color: "var(--muted)" }}>Analysing sales data…</span> : insight}
      </div>
      <button onClick={refresh} style={{
        background: "none", border: "1px solid var(--border)", borderRadius: 6,
        padding: "4px 10px", fontSize: 11, color: "var(--muted)", cursor: "pointer",
      }}>↻</button>
    </div>
  );
}

// ─── Main Screen ──────────────────────────────────────────────────────────────
export default function SalesCycle() {
  const { company } = useCompany();
  const accent  = company?.primary_colour  || "#e67e22";
  const accent2 = company?.secondary_colour || "#2c3e50";

  const current = mockMonthlySales[mockMonthlySales.length - 1];
  const prev    = mockMonthlySales[mockMonthlySales.length - 2];

  const volumeDelta = +(((current.volume_mt - prev.volume_mt) / prev.volume_mt) * 100).toFixed(1);
  const revDelta    = +(((current.revenue_inr - prev.revenue_inr) / prev.revenue_inr) * 100).toFixed(1);
  const realDelta   = +(((current.realisation_per_ton - prev.realisation_per_ton) / prev.realisation_per_ton) * 100).toFixed(1);
  const vsTarget    = +(((current.volume_mt - current.target_mt) / current.target_mt) * 100).toFixed(1);

  const promptData = useMemo(() => ({
    screen: "Sales Cycle",
    current_month: "Apr",
    volume_mt: current.volume_mt,
    revenue_inr: current.revenue_inr,
    realisation_per_ton: current.realisation_per_ton,
    vs_target_pct: vsTarget,
    volume_delta_pct: volumeDelta,
    realisation_delta_pct: realDelta,
    top_region: "Chennai (41%)",
    sku_leader: "12mm (1,820 MT combined)",
  }), []);

  const { insight, loading, refresh } = useClaudeInsight(
    `You are a steel sales analyst for a Tamil Nadu TMT rebar manufacturer. 
    Analyse this sales data: ${JSON.stringify(promptData)}. 
    Give 2–3 sentences. Mention realisation trend vs target, top-selling SKU or region opportunity, and one specific action. 
    Use Lakhs/Crores for revenue. No jargon.`,
    [promptData]
  );

  const css = `
    :root { --surface: #1a1f2e; --border: rgba(255,255,255,0.08); --text: #f1f5f9; --muted: #64748b; }
    @media (prefers-color-scheme: light) {
      :root { --surface: #ffffff; --border: rgba(0,0,0,0.08); --text: #1e293b; --muted: #94a3b8; }
    }
  `;

  return (
    <>
      <style>{css}</style>
      <div style={{ padding: "0 0 40px" }}>

        <InsightStrip insight={insight} loading={loading} refresh={refresh} accent={accent} />

        {/* KPI Row */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 24 }}>
          <KpiCard
            label="Volume — Apr"
            value={`${current.volume_mt.toLocaleString()} MT`}
            sub={`Target: ${current.target_mt.toLocaleString()} MT`}
            delta={volumeDelta}
            accent={vsTarget >= 0 ? "#22c55e" : "#ef4444"}
          />
          <KpiCard
            label="Revenue — Apr"
            value={formatCurrency(current.revenue_inr)}
            delta={revDelta}
            accent={accent}
          />
          <KpiCard
            label="Realisation / Ton"
            value={`₹${current.realisation_per_ton.toLocaleString()}`}
            delta={realDelta}
            accent={accent}
          />
          <KpiCard
            label="vs Target"
            value={`${vsTarget > 0 ? "+" : ""}${vsTarget}%`}
            sub={vsTarget >= 0 ? "Above target" : "Below target"}
            accent={vsTarget >= 0 ? "#22c55e" : "#ef4444"}
          />
        </div>

        {/* Revenue trend + Volume vs Target */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }}>

          <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, padding: "16px 16px 8px" }}>
            <div style={{ fontSize: 12, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 14 }}>
              Revenue & Realisation — 6M
            </div>
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={mockMonthlySales} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="revFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={accent} stopOpacity={0.18} />
                    <stop offset="95%" stopColor={accent} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="month" tick={{ fontSize: 11, fill: "var(--muted)" }} />
                <YAxis yAxisId="left" tickFormatter={v => `${(v/1000000).toFixed(1)}M`} tick={{ fontSize: 10, fill: "var(--muted)", fontFamily: "'DM Mono', monospace" }} />
                <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 10, fill: "var(--muted)", fontFamily: "'DM Mono', monospace" }} />
                <Tooltip content={<CustomTooltip />} />
                <Area yAxisId="left" dataKey="revenue_inr" name="Revenue ₹" stroke={accent} fill="url(#revFill)" strokeWidth={2} dot={{ r: 3 }} />
                <Line yAxisId="right" dataKey="realisation_per_ton" name="₹/Ton" stroke="#f59e0b" strokeWidth={2} dot={{ r: 3 }} />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, padding: "16px 16px 8px" }}>
            <div style={{ fontSize: 12, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 14 }}>
              Volume vs Target — 6M (MT)
            </div>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={mockMonthlySales} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="month" tick={{ fontSize: 11, fill: "var(--muted)" }} />
                <YAxis tick={{ fontSize: 10, fill: "var(--muted)", fontFamily: "'DM Mono', monospace" }} />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="target_mt" name="Target MT" fill="var(--border)" radius={[3, 3, 0, 0]} />
                <Bar dataKey="volume_mt" name="Actual MT" fill={accent} radius={[3, 3, 0, 0]} opacity={0.9} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Forecast + Region mix + SKU realisation */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 220px", gap: 16, marginBottom: 16 }}>
          <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, padding: "16px 16px 8px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
              <div style={{ fontSize: 12, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
                12-Month Volume Forecast (MT)
              </div>
              <div style={{ display: "flex", gap: 12, fontSize: 11 }}>
                <span style={{ display: "flex", alignItems: "center", gap: 4, color: "var(--muted)" }}>
                  <span style={{ width: 10, height: 10, background: accent, display: "inline-block", borderRadius: 2 }} /> Actual
                </span>
                <span style={{ display: "flex", alignItems: "center", gap: 4, color: "var(--muted)" }}>
                  <span style={{ width: 10, height: 3, borderTop: "2px dashed #64748b", display: "inline-block" }} /> Forecast
                </span>
              </div>
            </div>
            <ResponsiveContainer width="100%" height={180}>
              <AreaChart data={mockForecast} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="forecastFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={accent} stopOpacity={0.12} />
                    <stop offset="95%" stopColor={accent} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="month" tick={{ fontSize: 10, fill: "var(--muted)" }} />
                <YAxis domain={[4500, 6500]} tick={{ fontSize: 10, fill: "var(--muted)", fontFamily: "'DM Mono', monospace" }} />
                <Tooltip content={<CustomTooltip />} />
                <Area
                  type="monotone" dataKey="volume_mt" name="Volume MT"
                  stroke={accent} fill="url(#forecastFill)" strokeWidth={2}
                  strokeDasharray="0"
                  dot={(props) => {
                    const { cx, cy, payload } = props;
                    return payload.is_forecast
                      ? <circle key={cx} cx={cx} cy={cy} r={3} fill="none" stroke={accent} strokeWidth={2} />
                      : <circle key={cx} cx={cx} cy={cy} r={3} fill={accent} />;
                  }}
                />
                <ReferenceLine x="Apr" stroke="var(--muted)" strokeDasharray="4 2" label={{ value: "Today", fontSize: 10, fill: "var(--muted)", position: "top" }} />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {/* Region Donut */}
          <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, padding: "16px" }}>
            <div style={{ fontSize: 12, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 14 }}>
              Region Mix — Apr
            </div>
            <div style={{ display: "flex", justifyContent: "center" }}>
              <PieChart width={160} height={140}>
                <Pie data={mockRegionMix} cx={80} cy={70} innerRadius={40} outerRadius={65} dataKey="value" stroke="none">
                  {mockRegionMix.map((entry, i) => <Cell key={i} fill={entry.color} />)}
                </Pie>
              </PieChart>
            </div>
            <div style={{ marginTop: 4 }}>
              {mockRegionMix.map((r, i) => (
                <div key={i} style={{ display: "flex", justifyContent: "space-between", fontSize: 11, padding: "2px 0", color: "var(--muted)" }}>
                  <span style={{ display: "flex", alignItems: "center", gap: 5 }}>
                    <span style={{ width: 8, height: 8, background: r.color, borderRadius: 2, display: "inline-block" }} />
                    {r.name}
                  </span>
                  <span style={{ fontFamily: "'DM Mono', monospace" }}>{r.value}%</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* SKU Table */}
        <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, overflow: "hidden" }}>
          <div style={{ padding: "12px 16px", fontSize: 12, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.06em", borderBottom: "1px solid var(--border)" }}>
            SKU Sales Breakdown — Apr
          </div>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                {["SKU","P1 Vol MT","P2 Vol MT","Total MT","P1 ₹/Ton","P2 ₹/Ton"].map(h => (
                  <th key={h} style={{ padding: "8px 14px", textAlign: h === "SKU" ? "left" : "right", color: "var(--muted)", fontWeight: 500, fontFamily: h === "SKU" ? "inherit" : "'DM Mono', monospace" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {mockSKUSales.map((row, i) => (
                <tr key={i} style={{ borderBottom: "1px solid var(--border)", background: i % 2 === 0 ? "transparent" : "rgba(255,255,255,0.02)" }}>
                  <td style={{ padding: "8px 14px", color: "var(--text)", fontWeight: 500 }}>{row.sku}</td>
                  <td style={{ padding: "8px 14px", textAlign: "right", fontFamily: "'DM Mono', monospace", color: "var(--text)" }}>{row.p1.toLocaleString()}</td>
                  <td style={{ padding: "8px 14px", textAlign: "right", fontFamily: "'DM Mono', monospace", color: "var(--muted)" }}>{row.p2.toLocaleString()}</td>
                  <td style={{ padding: "8px 14px", textAlign: "right", fontFamily: "'DM Mono', monospace", color: "var(--text)", fontWeight: 600 }}>{(row.p1 + row.p2).toLocaleString()}</td>
                  <td style={{ padding: "8px 14px", textAlign: "right", fontFamily: "'DM Mono', monospace", color: accent }}>₹{row.real_p1.toLocaleString()}</td>
                  <td style={{ padding: "8px 14px", textAlign: "right", fontFamily: "'DM Mono', monospace", color: "var(--muted)" }}>{row.real_p2 > 0 ? `₹${row.real_p2.toLocaleString()}` : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

      </div>
    </>
  );
}

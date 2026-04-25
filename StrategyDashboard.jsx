import { useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  AreaChart, Area, BarChart, Bar, Legend, ReferenceLine, ComposedChart
} from "recharts";
import { useCompany } from "../components/CompanyContext";
import { useClaudeInsight } from "../hooks/useClaudeInsight";
import { formatCurrency, formatVolume } from "../utils/formatCurrency";

// ─── Mock data — strategy layer (above forecast, never mixed with forecast data) ─

// 36 months: 24 actual + 12 forecast, with strategic targets overlaid
const MONTHS_HISTORY = [
  { month: "May-23",  actual: 1420, p1: 540,  p2: 880, target: 1400, ebitda: 7200000,  margin: 12.1 },
  { month: "Jun-23",  actual: 1480, p1: 590,  p2: 890, target: 1430, ebitda: 7800000,  margin: 12.5 },
  { month: "Jul-23",  actual: 1510, p1: 620,  p2: 890, target: 1450, ebitda: 8100000,  margin: 12.8 },
  { month: "Aug-23",  actual: 1490, p1: 640,  p2: 850, target: 1460, ebitda: 7900000,  margin: 12.6 },
  { month: "Sep-23",  actual: 1550, p1: 680,  p2: 870, target: 1480, ebitda: 8600000,  margin: 13.2 },
  { month: "Oct-23",  actual: 1600, p1: 720,  p2: 880, target: 1500, ebitda: 9200000,  margin: 13.7 },
  { month: "Nov-23",  actual: 1580, p1: 740,  p2: 840, target: 1520, ebitda: 8900000,  margin: 13.4 },
  { month: "Dec-23",  actual: 1620, p1: 780,  p2: 840, target: 1540, ebitda: 9500000,  margin: 13.9 },
  { month: "Jan-24",  actual: 1540, p1: 760,  p2: 780, target: 1500, ebitda: 8700000,  margin: 13.5 },
  { month: "Feb-24",  actual: 1590, p1: 810,  p2: 780, target: 1530, ebitda: 9100000,  margin: 13.6 },
  { month: "Mar-24",  actual: 1650, p1: 860,  p2: 790, target: 1560, ebitda: 9800000,  margin: 14.1 },
  { month: "Apr-24",  actual: 1680, p1: 900,  p2: 780, target: 1590, ebitda: 10100000, margin: 14.3 },
  { month: "May-24",  actual: 1700, p1: 930,  p2: 770, target: 1610, ebitda: 10400000, margin: 14.5 },
  { month: "Jun-24",  actual: 1720, p1: 960,  p2: 760, target: 1640, ebitda: 10700000, margin: 14.7 },
  { month: "Jul-24",  actual: 1740, p1: 1000, p2: 740, target: 1660, ebitda: 11000000, margin: 15.0 },
  { month: "Aug-24",  actual: 1780, p1: 1040, p2: 740, target: 1700, ebitda: 11400000, margin: 15.2 },
  { month: "Sep-24",  actual: 1800, p1: 1080, p2: 720, target: 1720, ebitda: 11800000, margin: 15.5 },
  { month: "Oct-24",  actual: 1830, p1: 1120, p2: 710, target: 1750, ebitda: 12100000, margin: 15.7 },
  { month: "Nov-24",  actual: 1810, p1: 1100, p2: 710, target: 1760, ebitda: 11900000, margin: 15.6 },
  { month: "Dec-24",  actual: 1860, p1: 1150, p2: 710, target: 1790, ebitda: 12500000, margin: 15.9 },
  { month: "Jan-25",  actual: 1820, p1: 1140, p2: 680, target: 1780, ebitda: 12200000, margin: 15.8 },
  { month: "Feb-25",  actual: 1840, p1: 1160, p2: 680, target: 1800, ebitda: 12400000, margin: 16.0 },
  { month: "Mar-25",  actual: 1870, p1: 1190, p2: 680, target: 1820, ebitda: 12700000, margin: 16.1 },
  { month: "Apr-25",  actual: 1850, p1: 1180, p2: 670, target: 1830, ebitda: 12500000, margin: 16.0 },
  // Forecast months
  { month: "May-25",  forecast: 1900, p1_fcst: 1230, p2_fcst: 670, target: 1860, ebitda_fcst: 13000000, margin_fcst: 16.4 },
  { month: "Jun-25",  forecast: 1940, p1_fcst: 1270, p2_fcst: 670, target: 1900, ebitda_fcst: 13400000, margin_fcst: 16.6 },
  { month: "Jul-25",  forecast: 1960, p1_fcst: 1300, p2_fcst: 660, target: 1940, ebitda_fcst: 13700000, margin_fcst: 16.8 },
  { month: "Aug-25",  forecast: 2000, p1_fcst: 1350, p2_fcst: 650, target: 1980, ebitda_fcst: 14100000, margin_fcst: 17.0 },
  { month: "Sep-25",  forecast: 2040, p1_fcst: 1390, p2_fcst: 650, target: 2020, ebitda_fcst: 14500000, margin_fcst: 17.2 },
  { month: "Oct-25",  forecast: 2060, p1_fcst: 1420, p2_fcst: 640, target: 2050, ebitda_fcst: 14800000, margin_fcst: 17.4 },
  { month: "Nov-25",  forecast: 2040, p1_fcst: 1410, p2_fcst: 630, target: 2060, ebitda_fcst: 14600000, margin_fcst: 17.3 },
  { month: "Dec-25",  forecast: 2100, p1_fcst: 1470, p2_fcst: 630, target: 2100, ebitda_fcst: 15200000, margin_fcst: 17.6 },
  { month: "Jan-26",  forecast: 2080, p1_fcst: 1460, p2_fcst: 620, target: 2120, ebitda_fcst: 15000000, margin_fcst: 17.5 },
  { month: "Feb-26",  forecast: 2110, p1_fcst: 1500, p2_fcst: 610, target: 2160, ebitda_fcst: 15300000, margin_fcst: 17.7 },
  { month: "Mar-26",  forecast: 2150, p1_fcst: 1550, p2_fcst: 600, target: 2200, ebitda_fcst: 15700000, margin_fcst: 18.0 },
  { month: "Apr-26",  forecast: 2180, p1_fcst: 1580, p2_fcst: 600, target: 2240, ebitda_fcst: 16000000, margin_fcst: 18.2 },
];

const STRATEGIC_TARGETS = {
  annual_revenue_target: 240000000,
  annual_ebitda_target: 42000000,
  p1_share_target_pct: 70,
  p2_rundown_target_pct: 30,
  ebitda_margin_target: 18,
  volume_target_monthly: 2200,
};

// ─── Sub-components ──────────────────────────────────────────────────────────

function TargetGauge({ label, current, target, unit, colour, invert }) {
  const pct = Math.min((current / target) * 100, 110);
  const isAhead = invert ? current <= target : current >= target;
  const statusColor = isAhead ? "#22c55e" : pct >= 85 ? "#f59e0b" : "#ef4444";
  const statusLabel = isAhead ? "On Track" : pct >= 85 ? "Near Target" : "Behind";
  return (
    <div style={{ background: "#fff", border: "1px solid #e8ecf0", borderRadius: 10, padding: "18px 20px" }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: "#8b95a1", textTransform: "uppercase", letterSpacing: 1, marginBottom: 10 }}>{label}</div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 10 }}>
        <div>
          <div style={{ fontSize: 22, fontWeight: 700, fontFamily: "'DM Mono', monospace", color: "#1a2332" }}>{current}{unit}</div>
          <div style={{ fontSize: 11, color: "#8b95a1" }}>Target: {target}{unit}</div>
        </div>
        <span style={{ background: statusColor + "20", color: statusColor, borderRadius: 5, padding: "3px 10px", fontSize: 11, fontWeight: 700 }}>{statusLabel}</span>
      </div>
      <div style={{ height: 8, background: "#f1f5f9", borderRadius: 4, overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${Math.min(pct, 100)}%`, background: statusColor, borderRadius: 4, transition: "width 0.8s ease" }} />
      </div>
      <div style={{ fontSize: 10, color: "#8b95a1", marginTop: 4 }}>{pct.toFixed(0)}% of target</div>
    </div>
  );
}

// ─── Main Screen ─────────────────────────────────────────────────────────────

export default function StrategyDashboard() {
  const { company } = useCompany();
  const primary = company.primary_colour || "#2563eb";
  const secondary = company.secondary_colour || "#7c3aed";
  const p1Label = company.brand_p1 || "Product 1";
  const p2Label = company.brand_p2 || "Product 2";

  // Current month stats (from last actual)
  const lastActual = MONTHS_HISTORY.filter(m => m.actual).slice(-1)[0];
  const currentP1Share = Math.round((lastActual.p1 / lastActual.actual) * 100);
  const currentP2Share = 100 - currentP1Share;
  const ytdEbitda = MONTHS_HISTORY.filter(m => m.actual && m.month.includes("25")).reduce((s, m) => s + m.ebitda, 0);
  const ytdVolume = MONTHS_HISTORY.filter(m => m.actual && m.month.includes("25")).reduce((s, m) => s + m.actual, 0);

  // Transition curve data: P1 share over time
  const transitionData = MONTHS_HISTORY.map(m => ({
    month: m.month,
    p1_share: m.actual ? Math.round((m.p1 / m.actual) * 100) : Math.round((m.p1_fcst / m.forecast) * 100),
    p2_share: m.actual ? Math.round((m.p2 / m.actual) * 100) : Math.round((m.p2_fcst / m.forecast) * 100),
    isForecast: !m.actual,
  }));

  const insightPrompt = `You are a senior strategy advisor for a TMT rebar steel manufacturer in Tamil Nadu reviewing a 3-year strategic plan.
Current month: ${p1Label} is ${currentP1Share}% of volume (strategic target: ${STRATEGIC_TARGETS.p1_share_target_pct}%). ${p2Label} is ${currentP2Share}% (target rundown to ${STRATEGIC_TARGETS.p2_rundown_target_pct}%).
YTD 2025 EBITDA: ${formatCurrency(ytdEbitda)}. Annual EBITDA target: ${formatCurrency(STRATEGIC_TARGETS.annual_ebitda_target)}.
Forecast shows volume reaching 2,180 MT/month by April 2026 vs strategic target of 2,200 MT.
In 2-3 sentences, give the most important strategic action to ensure ${p1Label} transition stays on track. Use Lakhs/Crores. One action only.`;

  const { insight, loading: insightLoading, refresh: refreshInsight } = useClaudeInsight(insightPrompt, [currentP1Share]);

  // Chart data: volume actual + forecast + target
  const volumeChartData = MONTHS_HISTORY.map((m, i) => ({
    month: m.month,
    Actual: m.actual || null,
    Forecast: m.forecast || null,
    Target: m.target,
    isForecast: !m.actual,
  }));

  // P1 / P2 split over time
  const brandSplitData = MONTHS_HISTORY.map(m => ({
    month: m.month,
    [p1Label]: m.actual ? m.p1 : m.p1_fcst,
    [p2Label]: m.actual ? m.p2 : m.p2_fcst,
  }));

  // EBITDA trend
  const ebitdaData = MONTHS_HISTORY.map(m => ({
    month: m.month,
    "EBITDA Margin": m.margin || m.margin_fcst,
    isForecast: !m.actual,
  }));

  return (
    <div style={{ padding: "28px 32px", background: "#f7f8fa", minHeight: "100vh", fontFamily: "'DM Sans', sans-serif" }}>
      {/* Header */}
      <div style={{ marginBottom: 28 }}>
        <div style={{ fontSize: 22, fontWeight: 700, color: "#1a2332", fontFamily: "'Syne', sans-serif" }}>Strategy Dashboard</div>
        <div style={{ fontSize: 13, color: "#8b95a1", marginTop: 4 }}>Forecast vs Strategic Target · 36-Month View · {p1Label} Growth · {p2Label} Transition</div>
        <div style={{ marginTop: 8, padding: "6px 12px", background: "#fffbeb", border: "1px solid #fcd34d", borderRadius: 6, display: "inline-block", fontSize: 11, color: "#92400e", fontWeight: 600 }}>
          ⚠ Strategic targets are management-set goals — they do not influence the forecast engine (pure historical data principle)
        </div>
      </div>

      {/* Strategic Target Gauges */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16, marginBottom: 24 }}>
        <TargetGauge label={`${p1Label} Share`} current={currentP1Share} target={STRATEGIC_TARGETS.p1_share_target_pct} unit="%" colour={primary} />
        <TargetGauge label={`${p2Label} Share`} current={currentP2Share} target={STRATEGIC_TARGETS.p2_rundown_target_pct} unit="%" colour={secondary} invert />
        <TargetGauge label="Monthly Volume" current={lastActual.actual} target={STRATEGIC_TARGETS.volume_target_monthly} unit=" MT" colour="#059669" />
        <TargetGauge label="EBITDA Margin" current={lastActual.margin} target={STRATEGIC_TARGETS.ebitda_margin_target} unit="%" colour="#f59e0b" />
      </div>

      {/* AI Insight */}
      <div style={{ background: "#fff", border: `1px solid ${primary}22`, borderLeft: `4px solid ${primary}`, borderRadius: 10, padding: "16px 20px", marginBottom: 24, display: "flex", gap: 14, alignItems: "flex-start" }}>
        <div style={{ fontSize: 18 }}>🤖</div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: primary, textTransform: "uppercase", letterSpacing: 1, marginBottom: 6 }}>AI Strategy Insight</div>
          {insightLoading
            ? <div style={{ fontSize: 13, color: "#8b95a1" }}>Analysing strategic position…</div>
            : <div style={{ fontSize: 13, color: "#374151", lineHeight: 1.6 }}>{insight}</div>
          }
        </div>
        <button onClick={refreshInsight} style={{ background: "none", border: `1px solid ${primary}44`, borderRadius: 6, padding: "4px 10px", fontSize: 11, color: primary, cursor: "pointer" }}>↻</button>
      </div>

      {/* Volume: Forecast vs Target (36M) */}
      <div style={{ background: "#fff", borderRadius: 10, border: "1px solid #e8ecf0", padding: "20px 24px", marginBottom: 20 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: "#374151" }}>Volume: Actual / Forecast vs Strategic Target (MT)</div>
          <div style={{ display: "flex", gap: 16, fontSize: 11 }}>
            <span style={{ display: "flex", alignItems: "center", gap: 5 }}><span style={{ width: 20, height: 2, background: primary, display: "inline-block" }} /> Actual</span>
            <span style={{ display: "flex", alignItems: "center", gap: 5 }}><span style={{ width: 20, height: 2, background: primary, display: "inline-block", opacity: 0.4 }} /> Forecast</span>
            <span style={{ display: "flex", alignItems: "center", gap: 5 }}><span style={{ width: 20, height: 2, background: "#ef4444", display: "inline-block", borderTop: "2px dashed #ef4444" }} /> Target</span>
          </div>
        </div>
        <div style={{ fontSize: 11, color: "#8b95a1", marginBottom: 16 }}>Dashed line = strategic target (management-set) | Solid line = pure statistical forecast</div>
        <ResponsiveContainer width="100%" height={230}>
          <ComposedChart data={volumeChartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
            <XAxis dataKey="month" tick={{ fontSize: 9, fill: "#8b95a1" }} interval={2} />
            <YAxis tick={{ fontSize: 11, fill: "#8b95a1" }} domain={[1300, 2400]} />
            <Tooltip contentStyle={{ fontSize: 11, borderRadius: 6 }} />
            <ReferenceLine x="Apr-25" stroke="#8b95a1" strokeDasharray="4 2" label={{ value: "Today", position: "top", fontSize: 10, fill: "#8b95a1" }} />
            <Area type="monotone" dataKey="Actual"   fill={`${primary}15`} stroke={primary}    strokeWidth={2} dot={false} />
            <Area type="monotone" dataKey="Forecast" fill={`${primary}08`} stroke={primary}    strokeWidth={1.5} strokeDasharray="5 3" dot={false} fillOpacity={0.5} />
            <Line  type="monotone" dataKey="Target"  stroke="#ef4444" strokeWidth={1.5} strokeDasharray="6 3" dot={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Bottom row: Brand transition + EBITDA margin */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, marginBottom: 20 }}>
        {/* P1 growth / P2 decline */}
        <div style={{ background: "#fff", borderRadius: 10, border: "1px solid #e8ecf0", padding: "20px 24px" }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: "#374151", marginBottom: 4 }}>{p1Label} Growth · {p2Label} Managed Decline</div>
          <div style={{ fontSize: 11, color: "#8b95a1", marginBottom: 16 }}>Monthly volume split (MT) — stacked</div>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={brandSplitData.filter((_, i) => i % 2 === 0)}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="month" tick={{ fontSize: 9, fill: "#8b95a1" }} />
              <YAxis tick={{ fontSize: 11, fill: "#8b95a1" }} />
              <Tooltip contentStyle={{ fontSize: 11, borderRadius: 6 }} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Area type="monotone" dataKey={p2Label} stackId="1" fill={`${secondary}40`} stroke={secondary} strokeWidth={1.5} />
              <Area type="monotone" dataKey={p1Label} stackId="1" fill={`${primary}60`} stroke={primary}    strokeWidth={1.5} />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* EBITDA margin trend */}
        <div style={{ background: "#fff", borderRadius: 10, border: "1px solid #e8ecf0", padding: "20px 24px" }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: "#374151", marginBottom: 4 }}>EBITDA Margin % — 36-Month Trend</div>
          <div style={{ fontSize: 11, color: "#8b95a1", marginBottom: 16 }}>Target: {STRATEGIC_TARGETS.ebitda_margin_target}% by end of FY26</div>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={ebitdaData.filter((_, i) => i % 2 === 0)}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="month" tick={{ fontSize: 9, fill: "#8b95a1" }} />
              <YAxis tick={{ fontSize: 11, fill: "#8b95a1" }} domain={[10, 20]} tickFormatter={v => `${v}%`} />
              <Tooltip formatter={v => `${v}%`} contentStyle={{ fontSize: 11, borderRadius: 6 }} />
              <ReferenceLine y={STRATEGIC_TARGETS.ebitda_margin_target} stroke="#ef4444" strokeDasharray="4 2" label={{ value: `Target ${STRATEGIC_TARGETS.ebitda_margin_target}%`, position: "right", fontSize: 10, fill: "#ef4444" }} />
              <Area type="monotone" dataKey="EBITDA Margin" fill="#f59e0b30" stroke="#f59e0b" strokeWidth={2} dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Strategic Milestones Table */}
      <div style={{ background: "#fff", borderRadius: 10, border: "1px solid #e8ecf0", padding: "20px 24px" }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: "#374151", marginBottom: 16 }}>Strategic Milestones</div>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
          <thead>
            <tr style={{ background: "#f7f8fa" }}>
              {["Milestone", "Target", "Current", "Status", "Expected By"].map(h => (
                <th key={h} style={{ padding: "9px 12px", textAlign: "left", color: "#8b95a1", fontWeight: 600, fontSize: 11, textTransform: "uppercase" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {[
              { milestone: `${p1Label} reaches 60% volume share`,     target: "60%",         current: `${currentP1Share}%`,  status: currentP1Share >= 60 ? "achieved" : "in-progress", by: "Jun 2025" },
              { milestone: `${p1Label} reaches 70% volume share`,     target: "70%",         current: `${currentP1Share}%`,  status: "in-progress",  by: "Dec 2025" },
              { milestone: `${p2Label} below 30% volume share`,       target: "<30%",        current: `${currentP2Share}%`,  status: currentP2Share <= 30 ? "achieved" : "in-progress",  by: "Mar 2026" },
              { milestone: "Monthly volume exceeds 2,000 MT",         target: "2,000 MT",    current: `${lastActual.actual} MT`, status: lastActual.actual >= 2000 ? "achieved" : "in-progress", by: "Sep 2025" },
              { milestone: "EBITDA Margin 18%",                       target: "18%",         current: `${lastActual.margin}%`, status: "in-progress",  by: "Apr 2026" },
              { milestone: "Annual EBITDA ₹4.2 Cr",                   target: "₹4.2 Cr",     current: formatCurrency(ytdEbitda) + " YTD", status: "in-progress", by: "Mar 2026" },
            ].map((row, i) => {
              const statusMap = {
                achieved:    { bg: "#f0fdf4", color: "#16a34a", label: "✓ Achieved" },
                "in-progress": { bg: "#eff6ff", color: "#2563eb", label: "→ In Progress" },
                "at-risk":   { bg: "#fef3c7", color: "#b45309", label: "⚠ At Risk" },
              };
              const s = statusMap[row.status];
              return (
                <tr key={i} style={{ borderTop: "1px solid #f1f5f9" }}>
                  <td style={{ padding: "10px 12px", color: "#374151" }}>{row.milestone}</td>
                  <td style={{ padding: "10px 12px", fontFamily: "'DM Mono', monospace", fontWeight: 600, color: "#1a2332" }}>{row.target}</td>
                  <td style={{ padding: "10px 12px", fontFamily: "'DM Mono', monospace", color: "#6b7280" }}>{row.current}</td>
                  <td style={{ padding: "10px 12px" }}>
                    <span style={{ background: s.bg, color: s.color, borderRadius: 5, padding: "3px 10px", fontSize: 11, fontWeight: 700 }}>{s.label}</span>
                  </td>
                  <td style={{ padding: "10px 12px", color: "#6b7280", fontSize: 12 }}>{row.by}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

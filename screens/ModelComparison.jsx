import { useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, ReferenceLine
} from "recharts";
import { useCompany } from "../components/CompanyContext";
import { useClaudeInsight } from "../hooks/useClaudeInsight";

// ─── Mock data — mirrors forecasting engine model registry ───────────────────

const MODELS = [
  { id: "sarima",        name: "SARIMA",           category: "Statistical", mape: 4.2,  status: "champion", weight: 0.38, trend: [4.8,4.5,4.3,4.2,4.2,4.1] },
  { id: "sarima_x",     name: "SARIMAX",           category: "Statistical", mape: 4.6,  status: "active",   weight: 0.18, trend: [5.1,4.9,4.7,4.6,4.6,4.5] },
  { id: "ets",          name: "ETS",               category: "Statistical", mape: 5.1,  status: "active",   weight: 0.10, trend: [5.8,5.5,5.3,5.2,5.1,5.0] },
  { id: "prophet",      name: "Prophet",           category: "ML",          mape: 4.9,  status: "active",   weight: 0.12, trend: [6.2,5.8,5.4,5.1,4.9,4.8] },
  { id: "xgb_lag",      name: "XGBoost + Lags",    category: "ML",          mape: 5.8,  status: "active",   weight: 0.08, trend: [7.1,6.5,6.0,5.9,5.8,5.7] },
  { id: "xgb_cal",      name: "XGBoost + Calendar",category: "ML",          mape: 6.1,  status: "active",   weight: 0.07, trend: [7.4,6.8,6.4,6.2,6.1,6.0] },
  { id: "lgbm",         name: "LightGBM",          category: "ML",          mape: 5.5,  status: "active",   weight: 0.07, trend: [6.8,6.2,5.8,5.5,5.5,5.4] },
  { id: "rnn_vanilla",  name: "RNN (Vanilla)",     category: "Deep",        mape: 7.2,  status: "watch",    weight: 0.00, trend: [8.5,8.1,7.8,7.4,7.2,7.1] },
  { id: "lstm",         name: "LSTM",              category: "Deep",        mape: 6.4,  status: "active",   weight: 0.00, trend: [8.2,7.5,7.0,6.7,6.4,6.3] },
  { id: "gru",          name: "GRU",               category: "Deep",        mape: 6.8,  status: "watch",    weight: 0.00, trend: [9.0,8.3,7.6,7.1,6.8,6.7] },
  { id: "tcn",          name: "TCN",               category: "Deep",        mape: 7.5,  status: "watch",    weight: 0.00, trend: [9.5,8.8,8.2,7.8,7.5,7.4] },
  { id: "ensemble",     name: "Ensemble",          category: "Ensemble",    mape: 3.8,  status: "deployed", weight: 1.00, trend: [4.5,4.2,4.0,3.9,3.8,3.7] },
];

const MONTHS = ["Nov", "Dec", "Jan", "Feb", "Mar", "Apr"];

const forecastComparison = [
  { month: "May",  actual: null, sarima: 1820, ensemble: 1840, prophet: 1870, ets: 1790 },
  { month: "Jun",  actual: null, sarima: 1910, ensemble: 1920, prophet: 1950, ets: 1880 },
  { month: "Jul",  actual: null, sarima: 1870, ensemble: 1885, prophet: 1900, ets: 1850 },
  { month: "Aug",  actual: null, sarima: 1950, ensemble: 1960, prophet: 1990, ets: 1920 },
  { month: "Sep",  actual: null, sarima: 2010, ensemble: 2030, prophet: 2060, ets: 1980 },
  { month: "Oct",  actual: null, sarima: 1990, ensemble: 2010, prophet: 2040, ets: 1960 },
  { month: "Nov",  actual: null, sarima: 2100, ensemble: 2110, prophet: 2140, ets: 2070 },
  { month: "Dec",  actual: null, sarima: 2050, ensemble: 2060, prophet: 2090, ets: 2020 },
];

const CATEGORY_COLORS = {
  Statistical: "#2563eb",
  ML: "#7c3aed",
  Deep: "#dc2626",
  Ensemble: "#059669",
};

// ─── Sub-components ──────────────────────────────────────────────────────────

function StatusBadge({ status }) {
  const map = {
    champion: { bg: "#fef9c3", color: "#92400e", label: "🏆 Champion" },
    deployed: { bg: "#dcfce7", color: "#166534", label: "⚡ Deployed" },
    active:   { bg: "#eff6ff", color: "#1d4ed8", label: "✓ Active" },
    watch:    { bg: "#fef3c7", color: "#b45309", label: "⚠ Watch" },
  };
  const s = map[status] || map.active;
  return (
    <span style={{ background: s.bg, color: s.color, borderRadius: 5, padding: "2px 8px", fontSize: 10, fontWeight: 700 }}>{s.label}</span>
  );
}

function MapeSparkline({ values }) {
  const max = Math.max(...values);
  const min = Math.min(...values);
  const range = max - min || 1;
  const w = 60, h = 24;
  const pts = values.map((v, i) => {
    const x = (i / (values.length - 1)) * w;
    const y = h - ((v - min) / range) * h;
    return `${x},${y}`;
  }).join(" ");
  return (
    <svg width={w} height={h} style={{ display: "block" }}>
      <polyline points={pts} fill="none" stroke="#2563eb" strokeWidth={1.5} />
      <circle cx={w} cy={h - ((values[values.length-1] - min) / range) * h} r={2.5} fill="#2563eb" />
    </svg>
  );
}

function WeightBar({ weight, colour }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <div style={{ flex: 1, height: 6, background: "#e8ecf0", borderRadius: 3, overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${weight * 100}%`, background: colour, borderRadius: 3 }} />
      </div>
      <span style={{ fontSize: 11, fontFamily: "'DM Mono', monospace", color: "#374151", minWidth: 32, textAlign: "right" }}>{(weight * 100).toFixed(0)}%</span>
    </div>
  );
}

// ─── Main Screen ─────────────────────────────────────────────────────────────

export default function ModelComparison() {
  const { company } = useCompany();
    
  const primary = company?.primary_colour || "#2563eb";
  const [activeCategory, setActiveCategory] = useState("All");
  const [sortBy, setSortBy] = useState("mape");

  const categories = ["All", "Statistical", "ML", "Deep", "Ensemble"];

  const filtered = MODELS
    .filter(m => activeCategory === "All" || m.category === activeCategory)
    .sort((a, b) => sortBy === "mape" ? a.mape - b.mape : b.weight - a.weight);

  const champion = MODELS.find(m => m.status === "champion");
  const deployed = MODELS.find(m => m.status === "deployed");
  const avgMape = (MODELS.reduce((s, m) => s + m.mape, 0) / MODELS.length).toFixed(1);

  const insightPrompt = `You are a data science lead reviewing 12 forecasting models for a TMT rebar steel manufacturer in Tamil Nadu.
The ensemble model has MAPE ${deployed?.mape}%, outperforming the individual champion SARIMA at MAPE ${champion?.mape}%.
The ensemble currently uses 7 active models (Statistical + ML). Deep learning models (RNN, LSTM, GRU, TCN) are on watch — MAPE range 6.4–7.5%.
In 2-3 sentences, give a clear recommendation on model governance action. One action only. No statistical jargon.`;

  const { insight, loading: insightLoading, refresh: refreshInsight } = useClaudeInsight(insightPrompt, []);

  const lineColors = ["#2563eb", "#059669", "#7c3aed", "#f59e0b", "#dc2626"];
  const lineKeys = ["ensemble", "sarima", "prophet", "ets"];

  return (
    <div style={{ padding: "28px 32px", background: "#f7f8fa", minHeight: "100vh", fontFamily: "'DM Sans', sans-serif" }}>
      {/* Header */}
      <div style={{ marginBottom: 28 }}>
        <div style={{ fontSize: 22, fontWeight: 700, color: "#1a2332", fontFamily: "'Syne', sans-serif" }}>Model Comparison</div>
        <div style={{ fontSize: 13, color: "#8b95a1", marginTop: 4 }}>12-model ensemble · Last evaluated: April 2025 · Next re-evaluation: July 2025</div>
      </div>

      {/* Summary KPIs */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16, marginBottom: 24 }}>
        {[
          { label: "Deployed Model", value: "Ensemble", sub: `${deployed?.mape}% MAPE`, accent: "#059669" },
          { label: "Champion Individual", value: "SARIMA", sub: `${champion?.mape}% MAPE`, accent: primary },
          { label: "Active Models", value: "7 / 12", sub: "5 on watch/inactive", accent: "#f59e0b" },
          { label: "Avg Model MAPE", value: `${avgMape}%`, sub: "Across all 12 models", accent: "#8b5cf6" },
        ].map(k => (
          <div key={k.label} style={{ background: "#fff", border: "1px solid #e8ecf0", borderLeft: `4px solid ${k.accent}`, borderRadius: 10, padding: "18px 22px" }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: "#8b95a1", textTransform: "uppercase", letterSpacing: 1, marginBottom: 6 }}>{k.label}</div>
            <div style={{ fontSize: 22, fontWeight: 700, color: "#1a2332", fontFamily: "'DM Mono', monospace" }}>{k.value}</div>
            <div style={{ fontSize: 12, color: "#8b95a1", marginTop: 4 }}>{k.sub}</div>
          </div>
        ))}
      </div>

      {/* AI Insight */}
      <div style={{ background: "#fff", border: `1px solid ${primary}22`, borderLeft: `4px solid ${primary}`, borderRadius: 10, padding: "16px 20px", marginBottom: 24, display: "flex", gap: 14, alignItems: "flex-start" }}>
        <div style={{ fontSize: 18 }}>🤖</div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: primary, textTransform: "uppercase", letterSpacing: 1, marginBottom: 6 }}>AI Model Governance Insight</div>
          {insightLoading
            ? <div style={{ fontSize: 13, color: "#8b95a1" }}>Analysing model performance…</div>
            : <div style={{ fontSize: 13, color: "#374151", lineHeight: 1.6 }}>{insight}</div>
          }
        </div>
        <button onClick={refreshInsight} style={{ background: "none", border: `1px solid ${primary}44`, borderRadius: 6, padding: "4px 10px", fontSize: 11, color: primary, cursor: "pointer" }}>↻</button>
      </div>

      {/* Forecast chart */}
      <div style={{ background: "#fff", borderRadius: 10, border: "1px solid #e8ecf0", padding: "20px 24px", marginBottom: 20 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: "#374151", marginBottom: 16 }}>12-Month Forecast Comparison (MT)</div>
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={forecastComparison}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
            <XAxis dataKey="month" tick={{ fontSize: 11, fill: "#8b95a1" }} />
            <YAxis tick={{ fontSize: 11, fill: "#8b95a1" }} domain={[1700, 2200]} />
            <Tooltip contentStyle={{ fontSize: 12, borderRadius: 6 }} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Line type="monotone" dataKey="ensemble" name="Ensemble" stroke="#059669" strokeWidth={2.5} dot={false} />
            <Line type="monotone" dataKey="sarima"   name="SARIMA"   stroke="#2563eb" strokeWidth={1.5} strokeDasharray="4 2" dot={false} />
            <Line type="monotone" dataKey="prophet"  name="Prophet"  stroke="#7c3aed" strokeWidth={1.5} strokeDasharray="4 2" dot={false} />
            <Line type="monotone" dataKey="ets"      name="ETS"      stroke="#f59e0b" strokeWidth={1.5} strokeDasharray="4 2" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Model table */}
      <div style={{ background: "#fff", borderRadius: 10, border: "1px solid #e8ecf0", padding: "20px 24px" }}>
        {/* Filter + Sort bar */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: "#374151" }}>All Models</div>
          <div style={{ display: "flex", gap: 8 }}>
            {categories.map(c => (
              <button key={c} onClick={() => setActiveCategory(c)} style={{
                padding: "5px 12px", borderRadius: 6, fontSize: 11, fontWeight: 600, cursor: "pointer",
                background: activeCategory === c ? primary : "#f1f5f9",
                color: activeCategory === c ? "#fff" : "#6b7280",
                border: "none"
              }}>{c}</button>
            ))}
            <button onClick={() => setSortBy(sortBy === "mape" ? "weight" : "mape")} style={{
              padding: "5px 12px", borderRadius: 6, fontSize: 11, fontWeight: 600, cursor: "pointer",
              background: "#f1f5f9", color: "#6b7280", border: "1px solid #e8ecf0"
            }}>Sort: {sortBy === "mape" ? "MAPE ↑" : "Weight ↓"}</button>
          </div>
        </div>

        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
          <thead>
            <tr style={{ background: "#f7f8fa" }}>
              {["Model", "Category", "Status", "Current MAPE", "MAPE Trend (6M)", "Ensemble Weight", ""].map(h => (
                <th key={h} style={{ padding: "9px 12px", textAlign: "left", color: "#8b95a1", fontWeight: 600, fontSize: 11, textTransform: "uppercase", letterSpacing: 0.5 }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map(m => {
              const catColor = CATEGORY_COLORS[m.category] || primary;
              const mapeColor = m.mape <= 4.5 ? "#059669" : m.mape <= 6 ? "#f59e0b" : "#ef4444";
              return (
                <tr key={m.id} style={{
                  borderTop: "1px solid #f1f5f9",
                  background: m.status === "deployed" ? "#f0fdf4" : m.status === "champion" ? "#fffbeb" : "transparent"
                }}>
                  <td style={{ padding: "10px 12px", fontWeight: 700, color: "#1a2332" }}>
                    {m.status === "deployed" && <span style={{ marginRight: 6 }}>⚡</span>}
                    {m.status === "champion" && <span style={{ marginRight: 6 }}>🏆</span>}
                    {m.name}
                  </td>
                  <td style={{ padding: "10px 12px" }}>
                    <span style={{ background: `${catColor}15`, color: catColor, borderRadius: 4, padding: "2px 8px", fontSize: 11, fontWeight: 600 }}>{m.category}</span>
                  </td>
                  <td style={{ padding: "10px 12px" }}><StatusBadge status={m.status} /></td>
                  <td style={{ padding: "10px 12px", fontFamily: "'DM Mono', monospace", fontWeight: 700, color: mapeColor }}>
                    {m.mape.toFixed(1)}%
                  </td>
                  <td style={{ padding: "10px 12px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <MapeSparkline values={m.trend} />
                      <span style={{ fontSize: 10, color: "#8b95a1" }}>{MONTHS[0]}→{MONTHS[MONTHS.length-1]}</span>
                    </div>
                  </td>
                  <td style={{ padding: "10px 12px", width: 160 }}>
                    <WeightBar weight={m.weight} colour={catColor} />
                  </td>
                  <td style={{ padding: "10px 12px" }}>
                    {m.status === "watch" && (
                      <span style={{ fontSize: 10, color: "#b45309", background: "#fef3c7", padding: "2px 6px", borderRadius: 4 }}>Needs more data</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

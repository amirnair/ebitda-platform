import { useState, useEffect, useCallback } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  WaterfallChart, Cell
} from "recharts";
import { useCompany } from "../components/CompanyContext";
import { useClaudeInsight } from "../hooks/useClaudeInsight";
import { formatCurrency, formatVolume, formatMargin } from "../utils/formatCurrency";

// ─── Base scenario (mirrors EBITDA engine current month) ─────────────────────
const BASE = {
  volume_mt: 1850,
  realisation_per_ton: 52500,
  power_units_per_hr: 850,
  power_rate: 7.2,
  runtime_hrs: 480,
  fuel_rate_per_hr: 1200,
  fixed_overheads: 2800000,
  rolling_factor: 1.05,
  scrap_cost_per_ton: 38000,
};

function calcEbitda(p) {
  const revenue = p.volume_mt * p.realisation_per_ton;
  const billet_mt = p.volume_mt * p.rolling_factor;
  const rm_cost = billet_mt * p.scrap_cost_per_ton;
  const power_cost = p.power_units_per_hr * p.power_rate * p.runtime_hrs;
  const fuel_cost = p.fuel_rate_per_hr * p.runtime_hrs;
  const production_cost = power_cost + fuel_cost;
  const overheads = p.fixed_overheads;
  const ebitda = revenue - rm_cost - production_cost - overheads;
  const margin = (ebitda / revenue) * 100;
  return { revenue, rm_cost, production_cost, overheads, ebitda, margin };
}

// ─── Slider component ────────────────────────────────────────────────────────
function SimSlider({ label, value, min, max, step, unit, format, onChange, accent, delta }) {
  const pct = ((value - min) / (max - min)) * 100;
  const deltaStr = delta !== 0 ? (delta > 0 ? `+${delta > 1000 ? formatCurrency(delta) : delta}` : (delta > -1000 ? delta : formatCurrency(delta))) : "—";
  return (
    <div style={{ marginBottom: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8, alignItems: "center" }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: "#374151" }}>{label}</span>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          {delta !== 0 && (
            <span style={{ fontSize: 11, fontFamily: "'DM Mono', monospace", color: delta > 0 ? "#22c55e" : "#ef4444", fontWeight: 600 }}>
              {delta > 0 ? "▲" : "▼"} {Math.abs(delta)}
            </span>
          )}
          <span style={{ fontSize: 15, fontWeight: 700, fontFamily: "'DM Mono', monospace", color: "#1a2332" }}>{format ? format(value) : value}{unit}</span>
        </div>
      </div>
      <input
        type="range"
        min={min} max={max} step={step} value={value}
        onChange={e => onChange(Number(e.target.value))}
        style={{ width: "100%", accentColor: accent, cursor: "pointer", height: 4 }}
      />
      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 4 }}>
        <span style={{ fontSize: 10, color: "#8b95a1" }}>{min}{unit}</span>
        <span style={{ fontSize: 10, color: "#8b95a1" }}>{max}{unit}</span>
      </div>
    </div>
  );
}

function EbitdaBridge({ base, sim }) {
  const items = [
    { name: "Base EBITDA",       value: base.ebitda,                 type: "start" },
    { name: "Volume Δ",          value: sim.revenue - base.revenue - (sim.rm_cost - base.rm_cost), type: "delta" },
    { name: "Realisation Δ",     value: (sim.realisation_per_ton - base.realisation_per_ton) * (sim.volume_mt || BASE.volume_mt), type: "delta" },
    { name: "Power Cost Δ",      value: -(sim.production_cost - base.production_cost), type: "delta" },
    { name: "Simulated EBITDA",  value: sim.ebitda,                  type: "end" },
  ];

  const maxVal = Math.max(...items.map(i => Math.abs(i.value)));
  return (
    <div>
      {items.map((item, i) => {
        const barWidth = Math.abs(item.value) / maxVal * 100;
        const isPositive = item.value >= 0;
        const isStart = item.type === "start";
        const isEnd = item.type === "end";
        const colour = isStart || isEnd ? "#2563eb" : isPositive ? "#22c55e" : "#ef4444";
        return (
          <div key={i} style={{ marginBottom: 10 }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
              <span style={{ fontSize: 12, color: "#374151" }}>{item.name}</span>
              <span style={{ fontSize: 12, fontFamily: "'DM Mono', monospace", fontWeight: 600, color: colour }}>
                {item.type === "delta" && (isPositive ? "+" : "")}{formatCurrency(item.value)}
              </span>
            </div>
            <div style={{ height: 8, background: "#f1f5f9", borderRadius: 4, overflow: "hidden" }}>
              <div style={{ height: "100%", width: `${barWidth}%`, background: colour, borderRadius: 4, marginLeft: isPositive || isStart || isEnd ? 0 : `${100 - barWidth}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ─── Main Screen ─────────────────────────────────────────────────────────────

export default function EbitdaSimulator() {
  const { company } = useCompany();
  const primary = company.primary_colour || "#2563eb";
  const secondary = company.secondary_colour || "#7c3aed";

  const [volume, setVolume]           = useState(BASE.volume_mt);
  const [realisation, setRealisation] = useState(BASE.realisation_per_ton);
  const [powerRate, setPowerRate]     = useState(BASE.power_rate);
  const [scrapCost, setScrapCost]     = useState(BASE.scrap_cost_per_ton);
  const [runtimeHrs, setRuntimeHrs]   = useState(BASE.runtime_hrs);
  const [overheads, setOverheads]     = useState(BASE.fixed_overheads);
  const [savedScenarios, setSavedScenarios] = useState([]);

  const baseResult = calcEbitda(BASE);
  const simParams  = { ...BASE, volume_mt: volume, realisation_per_ton: realisation, power_rate: powerRate, scrap_cost_per_ton: scrapCost, runtime_hrs: runtimeHrs, fixed_overheads: overheads };
  const simResult  = calcEbitda(simParams);

  const ebitdaDelta = simResult.ebitda - baseResult.ebitda;
  const marginDelta = simResult.margin - baseResult.margin;

  const handleReset = () => {
    setVolume(BASE.volume_mt);
    setRealisation(BASE.realisation_per_ton);
    setPowerRate(BASE.power_rate);
    setScrapCost(BASE.scrap_cost_per_ton);
    setRuntimeHrs(BASE.runtime_hrs);
    setOverheads(BASE.fixed_overheads);
  };

  const handleSave = () => {
    const label = `Scenario ${savedScenarios.length + 1}`;
    setSavedScenarios(prev => [...prev.slice(-2), { label, ebitda: simResult.ebitda, margin: simResult.margin.toFixed(1), volume, realisation, powerRate }]);
  };

  const insightPrompt = `You are a steel manufacturer CFO running an EBITDA scenario analysis.
Base EBITDA: ${formatCurrency(baseResult.ebitda)} (Margin: ${baseResult.margin.toFixed(1)}%).
Simulated EBITDA: ${formatCurrency(simResult.ebitda)} (Margin: ${simResult.margin.toFixed(1)}%).
Changes applied: Volume ${volume} MT (base: ${BASE.volume_mt}), Realisation ₹${realisation}/ton (base: ₹${BASE.realisation_per_ton}), Power ₹${powerRate}/unit (base: ₹${BASE.power_rate}), Scrap ₹${scrapCost}/ton (base: ₹${BASE.scrap_cost_per_ton}).
In 2-3 sentences, state the key EBITDA driver in this scenario and one specific action to capture or protect the EBITDA improvement. Use Lakhs/Crores. No jargon.`;

  const { insight, loading: insightLoading, refresh: refreshInsight } = useClaudeInsight(insightPrompt, [volume, realisation, powerRate, scrapCost, runtimeHrs]);

  const comparisonData = [
    { name: "Revenue",          base: baseResult.revenue,          sim: simResult.revenue },
    { name: "RM Cost",          base: -baseResult.rm_cost,          sim: -simResult.rm_cost },
    { name: "Production Cost",  base: -baseResult.production_cost,  sim: -simResult.production_cost },
    { name: "Overheads",        base: -baseResult.overheads,        sim: -simResult.overheads },
    { name: "EBITDA",           base: baseResult.ebitda,            sim: simResult.ebitda },
  ];

  return (
    <div style={{ padding: "28px 32px", background: "#f7f8fa", minHeight: "100vh", fontFamily: "'DM Sans', sans-serif" }}>
      {/* Header */}
      <div style={{ marginBottom: 28, display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <div style={{ fontSize: 22, fontWeight: 700, color: "#1a2332", fontFamily: "'Syne', sans-serif" }}>EBITDA Simulator</div>
          <div style={{ fontSize: 13, color: "#8b95a1", marginTop: 4 }}>What-if analysis · Adjust levers and see instant EBITDA impact</div>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <button onClick={handleSave} style={{ padding: "8px 18px", background: primary, color: "#fff", border: "none", borderRadius: 8, fontSize: 13, fontWeight: 600, cursor: "pointer" }}>Save Scenario</button>
          <button onClick={handleReset} style={{ padding: "8px 18px", background: "#fff", color: "#374151", border: "1px solid #e8ecf0", borderRadius: 8, fontSize: 13, fontWeight: 600, cursor: "pointer" }}>Reset</button>
        </div>
      </div>

      {/* EBITDA Impact Banner */}
      <div style={{
        background: ebitdaDelta >= 0 ? "linear-gradient(135deg, #f0fdf4, #dcfce7)" : "linear-gradient(135deg, #fef2f2, #fee2e2)",
        border: `1px solid ${ebitdaDelta >= 0 ? "#bbf7d0" : "#fecaca"}`,
        borderRadius: 12, padding: "20px 28px", marginBottom: 24,
        display: "flex", justifyContent: "space-around", alignItems: "center"
      }}>
        {[
          { label: "Simulated EBITDA", value: formatCurrency(simResult.ebitda), base: formatCurrency(baseResult.ebitda) },
          { label: "EBITDA Δ", value: `${ebitdaDelta >= 0 ? "+" : ""}${formatCurrency(ebitdaDelta)}`, highlight: true },
          { label: "EBITDA Margin", value: `${simResult.margin.toFixed(1)}%`, base: `Base: ${baseResult.margin.toFixed(1)}%` },
          { label: "Margin Δ", value: `${marginDelta >= 0 ? "+" : ""}${marginDelta.toFixed(1)} pp`, highlight: true },
        ].map(k => (
          <div key={k.label} style={{ textAlign: "center" }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: "#6b7280", textTransform: "uppercase", letterSpacing: 1, marginBottom: 6 }}>{k.label}</div>
            <div style={{ fontSize: k.highlight ? 28 : 24, fontWeight: 800, fontFamily: "'DM Mono', monospace", color: k.highlight ? (ebitdaDelta >= 0 ? "#16a34a" : "#dc2626") : "#1a2332" }}>{k.value}</div>
            {k.base && <div style={{ fontSize: 11, color: "#9ca3af", marginTop: 3 }}>{k.base}</div>}
          </div>
        ))}
      </div>

      {/* Main layout: sliders + chart */}
      <div style={{ display: "grid", gridTemplateColumns: "400px 1fr", gap: 20, marginBottom: 20 }}>
        {/* Sliders */}
        <div style={{ background: "#fff", borderRadius: 10, border: "1px solid #e8ecf0", padding: "24px" }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: "#374151", marginBottom: 20 }}>Scenario Levers</div>

          <SimSlider
            label="Sales Volume (MT)"
            value={volume} min={1000} max={2500} step={50}
            unit=" MT"
            delta={volume - BASE.volume_mt}
            onChange={setVolume} accent={primary}
          />
          <SimSlider
            label="Realisation / Ton (₹)"
            value={realisation} min={44000} max={62000} step={500}
            unit="" format={v => `₹${(v/1000).toFixed(1)}K`}
            delta={realisation - BASE.realisation_per_ton}
            onChange={setRealisation} accent={primary}
          />
          <SimSlider
            label="Scrap/Billet Cost / Ton (₹)"
            value={scrapCost} min={30000} max={50000} step={500}
            unit="" format={v => `₹${(v/1000).toFixed(1)}K`}
            delta={scrapCost - BASE.scrap_cost_per_ton}
            onChange={setScrapCost} accent="#dc2626"
          />
          <SimSlider
            label="Power Rate (₹/unit)"
            value={powerRate} min={5.0} max={10.0} step={0.1}
            unit="" format={v => `₹${v.toFixed(1)}`}
            delta={Math.round((powerRate - BASE.power_rate) * 10) / 10}
            onChange={setPowerRate} accent="#f59e0b"
          />
          <SimSlider
            label="Mill Runtime (hrs/month)"
            value={runtimeHrs} min={300} max={600} step={10}
            unit=" hrs"
            delta={runtimeHrs - BASE.runtime_hrs}
            onChange={setRuntimeHrs} accent={secondary}
          />
          <SimSlider
            label="Fixed Overheads (₹)"
            value={overheads} min={1500000} max={5000000} step={100000}
            unit="" format={v => formatCurrency(v)}
            delta={overheads - BASE.fixed_overheads}
            onChange={setOverheads} accent="#6b7280"
          />
        </div>

        {/* Right panel */}
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          {/* P&L comparison */}
          <div style={{ background: "#fff", borderRadius: 10, border: "1px solid #e8ecf0", padding: "20px 24px", flex: 1 }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: "#374151", marginBottom: 16 }}>P&L Comparison: Base vs Simulated</div>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={comparisonData} barGap={4}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="name" tick={{ fontSize: 10, fill: "#8b95a1" }} />
                <YAxis tick={{ fontSize: 10, fill: "#8b95a1" }} tickFormatter={v => formatCurrency(v)} />
                <Tooltip formatter={v => formatCurrency(v)} contentStyle={{ fontSize: 11, borderRadius: 6 }} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar dataKey="base" name="Base" fill="#94a3b8" radius={[4,4,0,0]} barSize={18} />
                <Bar dataKey="sim"  name="Simulated" fill={primary} radius={[4,4,0,0]} barSize={18} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Breakdown table */}
          <div style={{ background: "#fff", borderRadius: 10, border: "1px solid #e8ecf0", padding: "20px 24px" }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: "#374151", marginBottom: 12 }}>Detailed P&L Breakdown</div>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
              <thead>
                <tr style={{ background: "#f7f8fa" }}>
                  {["Line Item", "Base", "Simulated", "Δ Change"].map(h => (
                    <th key={h} style={{ padding: "8px 12px", textAlign: h === "Line Item" ? "left" : "right", color: "#8b95a1", fontWeight: 600, fontSize: 11, textTransform: "uppercase" }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[
                  { label: "Revenue",          base: baseResult.revenue,          sim: simResult.revenue,          sign: 1 },
                  { label: "Raw Material Cost", base: baseResult.rm_cost,          sim: simResult.rm_cost,          sign: -1 },
                  { label: "Production Cost",  base: baseResult.production_cost,  sim: simResult.production_cost,  sign: -1 },
                  { label: "Fixed Overheads",  base: baseResult.overheads,        sim: simResult.overheads,        sign: -1 },
                  { label: "EBITDA",           base: baseResult.ebitda,           sim: simResult.ebitda,           sign: 1, bold: true },
                  { label: "EBITDA Margin %",  base: `${baseResult.margin.toFixed(1)}%`, sim: `${simResult.margin.toFixed(1)}%`, sign: 1, isStr: true, bold: true },
                ].map(row => {
                  const delta = row.isStr ? null : (row.sim - row.base) * row.sign;
                  const deltaStr = row.isStr ? `${(simResult.margin - baseResult.margin).toFixed(1)} pp` : (delta >= 0 ? "+" : "") + formatCurrency(delta);
                  const deltaColor = row.isStr
                    ? (simResult.margin > baseResult.margin ? "#22c55e" : simResult.margin < baseResult.margin ? "#ef4444" : "#8b95a1")
                    : (delta > 0 ? "#22c55e" : delta < 0 ? "#ef4444" : "#8b95a1");
                  return (
                    <tr key={row.label} style={{ borderTop: "1px solid #f1f5f9", background: row.bold ? "#f7f8fa" : "transparent" }}>
                      <td style={{ padding: "9px 12px", color: "#374151", fontWeight: row.bold ? 700 : 400 }}>{row.label}</td>
                      <td style={{ padding: "9px 12px", textAlign: "right", fontFamily: "'DM Mono', monospace", color: "#6b7280" }}>{row.isStr ? row.base : formatCurrency(row.base)}</td>
                      <td style={{ padding: "9px 12px", textAlign: "right", fontFamily: "'DM Mono', monospace", color: "#1a2332", fontWeight: row.bold ? 700 : 400 }}>{row.isStr ? row.sim : formatCurrency(row.sim)}</td>
                      <td style={{ padding: "9px 12px", textAlign: "right", fontFamily: "'DM Mono', monospace", fontWeight: 600, color: deltaColor }}>{row.isStr ? deltaStr : deltaStr}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* AI Insight */}
      <div style={{ background: "#fff", border: `1px solid ${primary}22`, borderLeft: `4px solid ${primary}`, borderRadius: 10, padding: "16px 20px", marginBottom: 24, display: "flex", gap: 14, alignItems: "flex-start" }}>
        <div style={{ fontSize: 18 }}>🤖</div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: primary, textTransform: "uppercase", letterSpacing: 1, marginBottom: 6 }}>AI Scenario Analysis</div>
          {insightLoading
            ? <div style={{ fontSize: 13, color: "#8b95a1" }}>Analysing scenario…</div>
            : <div style={{ fontSize: 13, color: "#374151", lineHeight: 1.6 }}>{insight}</div>
          }
        </div>
        <button onClick={refreshInsight} style={{ background: "none", border: `1px solid ${primary}44`, borderRadius: 6, padding: "4px 10px", fontSize: 11, color: primary, cursor: "pointer" }}>↻</button>
      </div>

      {/* Saved Scenarios */}
      {savedScenarios.length > 0 && (
        <div style={{ background: "#fff", borderRadius: 10, border: "1px solid #e8ecf0", padding: "20px 24px" }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: "#374151", marginBottom: 12 }}>Saved Scenarios</div>
          <div style={{ display: "flex", gap: 16 }}>
            {savedScenarios.map((s, i) => (
              <div key={i} style={{ flex: 1, background: "#f7f8fa", borderRadius: 8, padding: "14px 16px", border: "1px solid #e8ecf0" }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: "#374151", marginBottom: 8 }}>{s.label}</div>
                <div style={{ fontSize: 11, color: "#6b7280" }}>EBITDA: <strong style={{ color: "#1a2332", fontFamily: "'DM Mono', monospace" }}>{formatCurrency(s.ebitda)}</strong></div>
                <div style={{ fontSize: 11, color: "#6b7280" }}>Margin: <strong style={{ color: "#1a2332", fontFamily: "'DM Mono', monospace" }}>{s.margin}%</strong></div>
                <div style={{ fontSize: 11, color: "#6b7280" }}>Vol: {s.volume} MT · Real: ₹{(s.realisation/1000).toFixed(1)}K</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

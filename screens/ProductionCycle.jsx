import { useState, useEffect, useMemo } from "react";
import {
  LineChart, Line, BarChart, Bar, AreaChart, Area,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
  ReferenceLine
} from "recharts";
import { useCompany } from "../components/CompanyContext";
import { useClaudeInsight } from "../hooks/useClaudeInsight";
import { formatCurrency, formatPerTon, formatVolume, formatMargin } from "../utils/formatCurrency";
import { supabase } from "../lib/supabaseClient";

// ─── Mock data ────────────────────────────────────────────────────────────────
const MONTHS = ["Nov","Dec","Jan","Feb","Mar","Apr"];

const mockMonthlyProduction = [
  { month:"Nov", output_mt:4820, power_cost_per_ton:1840, downtime_pct:6.2, wastage_pct:1.8, runtime_hrs:302 },
  { month:"Dec", output_mt:4210, power_cost_per_ton:1920, downtime_pct:8.1, wastage_pct:2.1, runtime_hrs:264 },
  { month:"Jan", output_mt:5120, power_cost_per_ton:1780, downtime_pct:4.8, wastage_pct:1.6, runtime_hrs:320 },
  { month:"Feb", output_mt:4960, power_cost_per_ton:1810, downtime_pct:5.3, wastage_pct:1.7, runtime_hrs:310 },
  { month:"Mar", output_mt:5380, power_cost_per_ton:1750, downtime_pct:3.9, wastage_pct:1.5, runtime_hrs:336 },
  { month:"Apr", output_mt:5240, power_cost_per_ton:1770, downtime_pct:4.2, wastage_pct:1.6, runtime_hrs:328 },
];

const BENCHMARKS = {
  power_cost_per_ton: 1800,
  downtime_pct: 5.0,
  wastage_pct: 1.8,
  efficiency_pct: 88,
};

const mockSKUOutput = [
  { sku:"8mm",  p1:820,  p2:310 },
  { sku:"10mm", p1:1040, p2:420 },
  { sku:"12mm", p1:1280, p2:580 },
  { sku:"16mm", p1:940,  p2:380 },
  { sku:"20mm", p1:680,  p2:210 },
  { sku:"25mm", p1:380,  p2:90 },
  { sku:"32mm", p1:100,  p2:0 },
];

// ─── Sub-components ───────────────────────────────────────────────────────────
function KpiCard({ label, value, delta, deltaLabel, accent, mono = true }) {
  const up = delta >= 0;
  return (
    <div style={{
      background: "var(--surface)",
      border: "1px solid var(--border)",
      borderRadius: 8,
      padding: "14px 16px",
      borderTop: `3px solid ${accent}`,
    }}>
      <div style={{ fontSize: 11, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 6 }}>{label}</div>
      <div style={{ fontSize: 22, fontFamily: mono ? "'DM Mono', monospace" : "inherit", fontWeight: 600, color: "var(--text)" }}>{value}</div>
      {delta !== undefined && (
        <div style={{ fontSize: 11, marginTop: 4, color: up ? "#22c55e" : "#ef4444" }}>
          {up ? "▲" : "▼"} {Math.abs(delta)}% {deltaLabel}
        </div>
      )}
    </div>
  );
}

function BenchmarkBar({ label, value, benchmark, unit, goodDir = "low" }) {
  const isGood = goodDir === "low" ? value <= benchmark : value >= benchmark;
  const pct = Math.min((value / (benchmark * 1.5)) * 100, 100);
  const bPct = (benchmark / (benchmark * 1.5)) * 100;
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 4 }}>
        <span style={{ color: "var(--muted)" }}>{label}</span>
        <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 12 }}>
          <span style={{ color: isGood ? "#22c55e" : "#ef4444", fontWeight: 600 }}>{value}{unit}</span>
          <span style={{ color: "var(--muted)" }}> / {benchmark}{unit} bmark</span>
        </span>
      </div>
      <div style={{ position: "relative", height: 6, background: "var(--border)", borderRadius: 3, overflow: "visible" }}>
        <div style={{
          height: "100%", width: `${pct}%`, borderRadius: 3,
          background: isGood ? "#22c55e" : "#ef4444",
          transition: "width 0.6s ease",
        }} />
        <div style={{
          position: "absolute", top: -3, left: `${bPct}%`,
          width: 2, height: 12, background: "var(--muted)", borderRadius: 1,
        }} />
      </div>
    </div>
  );
}

// ─── Custom Tooltip ───────────────────────────────────────────────────────────
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

// ─── AI Insight strip ─────────────────────────────────────────────────────────
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
        {loading ? <span style={{ color: "var(--muted)" }}>Analysing production data…</span> : insight}
      </div>
      <button onClick={refresh} style={{
        background: "none", border: "1px solid var(--border)", borderRadius: 6,
        padding: "4px 10px", fontSize: 11, color: "var(--muted)", cursor: "pointer",
      }}>↻</button>
    </div>
  );
}

// ─── Main Screen ──────────────────────────────────────────────────────────────
export default function ProductionCycle() {
  const { company } = useCompany();
  const accent = company?.primary_colour || "#e67e22";
  const accent2 = company?.secondary_colour || "#2c3e50";

  const [liveData, setLiveData] = useState([]);
    const [loading, setLoading] = useState(true);
    const [dbError, setDbError] = useState(null);
    useEffect(() => {
          if (!company?.id) return;
          async function load() {
                  setLoading(true); setDbError(null);
                  const { data, error: err } = await supabase
                    .from("production_data").select("*")
                    .eq("company_id", company.id)
                    .order("year", { ascending: true }).order("month", { ascending: true });
                  if (err) { setDbError(err.message); setLoading(false); return; }
                  setLiveData(data || []);
                  setLoading(false);
          }
          load();
    }, [company?.id]);
    if (loading) return <div className="p-8 text-gray-400">Loading production data...</div>;
    if (dbError) return <div className="p-8 text-red-400">Error: {dbError}</div>;
    const monthlyData = liveData.length > 0 ? liveData : mockMonthlyProduction;
    const current = monthlyData[monthlyData.length - 1];
    const prev    = monthlyData[monthlyData.length - 2];

  const outputDelta   = +(((current.output_mt - prev.output_mt) / prev.output_mt) * 100).toFixed(1);
  const powerDelta    = +(((current.power_cost_per_ton - prev.power_cost_per_ton) / prev.power_cost_per_ton) * 100).toFixed(1);
  const downtimeDelta = +(((current.downtime_pct - prev.downtime_pct) / prev.downtime_pct) * 100).toFixed(1);

  const efficiencyPct = +((current.runtime_hrs / (current.runtime_hrs / (1 - current.downtime_pct / 100))) * 100).toFixed(1);

  const promptData = useMemo(() => ({
    screen: "Production Cycle",
    current_month: "Apr",
    output_mt: current.output_mt,
    power_cost_per_ton: current.power_cost_per_ton,
    power_benchmark: BENCHMARKS.power_cost_per_ton,
    downtime_pct: current.downtime_pct,
    downtime_benchmark: BENCHMARKS.downtime_pct,
    wastage_pct: current.wastage_pct,
    wastage_benchmark: BENCHMARKS.wastage_pct,
    output_delta_pct: outputDelta,
    power_delta_pct: powerDelta,
  }), []);

  const { insight, loading, refresh } = useClaudeInsight(
    `You are a steel mill production analyst. Analyse this production data and give 2–3 sentences of actionable insight. 
    Data: ${JSON.stringify(promptData)}. 
    Focus on the most important lever: power cost vs benchmark, downtime trend, or output trend. 
    Mention specific numbers. One clear action the production manager should take. No jargon.`,
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
            label="Mill Output — Apr"
            value={`${current.output_mt.toLocaleString()} MT`}
            delta={outputDelta}
            deltaLabel="vs Mar"
            accent={accent}
          />
          <KpiCard
            label="Power Cost / Ton"
            value={`₹${current.power_cost_per_ton.toLocaleString()}`}
            delta={-powerDelta}
            deltaLabel="vs Mar"
            accent={current.power_cost_per_ton > BENCHMARKS.power_cost_per_ton ? "#ef4444" : "#22c55e"}
          />
          <KpiCard
            label="Downtime %"
            value={`${current.downtime_pct}%`}
            delta={-downtimeDelta}
            deltaLabel="vs Mar"
            accent={current.downtime_pct > BENCHMARKS.downtime_pct ? "#ef4444" : "#22c55e"}
          />
          <KpiCard
            label="Wastage %"
            value={`${current.wastage_pct}%`}
            delta={0}
            accent={current.wastage_pct > BENCHMARKS.wastage_pct ? "#ef4444" : "#22c55e"}
          />
        </div>

        {/* Two-column: Output trend + Benchmark panel */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 320px", gap: 16, marginBottom: 16 }}>

          {/* Mill Output + Power Cost trend */}
          <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, padding: "16px 16px 8px" }}>
            <div style={{ fontSize: 12, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 14 }}>
              Mill Output (MT) & Power Cost / Ton — 6 Months
            </div>
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={monthlyData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="outputFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={accent} stopOpacity={0.18} />
                    <stop offset="95%" stopColor={accent} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="month" tick={{ fontSize: 11, fill: "var(--muted)" }} />
                <YAxis yAxisId="left" tick={{ fontSize: 11, fill: "var(--muted)", fontFamily: "'DM Mono', monospace" }} />
                <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11, fill: "var(--muted)", fontFamily: "'DM Mono', monospace" }} />
                <Tooltip content={<CustomTooltip />} />
                <Area yAxisId="left" type="monotone" dataKey="output_mt" name="Output MT" stroke={accent} fill="url(#outputFill)" strokeWidth={2} dot={{ r: 3 }} />
                <Line yAxisId="right" type="monotone" dataKey="power_cost_per_ton" name="₹/Ton" stroke="#f59e0b" strokeWidth={2} dot={{ r: 3 }} strokeDasharray="4 2" />
              </AreaChart>
            </ResponsiveContainer>
            <div style={{ display: "flex", gap: 16, marginTop: 8, paddingLeft: 4 }}>
              <span style={{ fontSize: 11, display: "flex", alignItems: "center", gap: 4, color: "var(--muted)" }}>
                <span style={{ width: 10, height: 3, background: accent, display: "inline-block", borderRadius: 2 }} /> Output MT
              </span>
              <span style={{ fontSize: 11, display: "flex", alignItems: "center", gap: 4, color: "var(--muted)" }}>
                <span style={{ width: 10, height: 3, background: "#f59e0b", display: "inline-block", borderRadius: 2, borderTop: "2px dashed #f59e0b" }} /> ₹/Ton (power)
              </span>
            </div>
          </div>

          {/* Benchmark panel */}
          <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, padding: "16px" }}>
            <div style={{ fontSize: 12, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 16 }}>
              vs Benchmark
            </div>
            <BenchmarkBar label="Power Cost / Ton (₹)" value={current.power_cost_per_ton} benchmark={BENCHMARKS.power_cost_per_ton} unit="" goodDir="low" />
            <BenchmarkBar label="Downtime %" value={current.downtime_pct} benchmark={BENCHMARKS.downtime_pct} unit="%" goodDir="low" />
            <BenchmarkBar label="Wastage %" value={current.wastage_pct} benchmark={BENCHMARKS.wastage_pct} unit="%" goodDir="low" />
            <div style={{ borderTop: "1px solid var(--border)", paddingTop: 14, marginTop: 4 }}>
              <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 6 }}>RUNTIME — APR</div>
              <div style={{ fontFamily: "'DM Mono', monospace", fontSize: 20, color: "var(--text)" }}>
                {current.runtime_hrs} <span style={{ fontSize: 12, color: "var(--muted)" }}>hrs</span>
              </div>
              <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 2 }}>
                Std: 16 hrs/day × {Math.round(current.runtime_hrs / 16)} days scheduled
              </div>
            </div>
          </div>
        </div>

        {/* SKU output stacked bar + downtime sparkline */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>

          {/* SKU Output by brand */}
          <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, padding: "16px 16px 8px" }}>
            <div style={{ fontSize: 12, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 14 }}>
              Output by SKU — Apr (MT)
            </div>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={mockSKUOutput} layout="vertical" margin={{ top: 0, right: 8, left: 20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 10, fill: "var(--muted)", fontFamily: "'DM Mono', monospace" }} />
                <YAxis type="category" dataKey="sku" tick={{ fontSize: 11, fill: "var(--muted)" }} width={32} />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="p1" name="Product 1" stackId="a" fill={accent} radius={[0, 0, 0, 0]} />
                <Bar dataKey="p2" name="Product 2" stackId="a" fill={accent2} radius={[0, 3, 3, 0]} />
              </BarChart>
            </ResponsiveContainer>
            <div style={{ display: "flex", gap: 16, marginTop: 8, paddingLeft: 4 }}>
              <span style={{ fontSize: 11, display: "flex", alignItems: "center", gap: 4, color: "var(--muted)" }}>
                <span style={{ width: 10, height: 10, background: accent, display: "inline-block", borderRadius: 2 }} /> Product 1
              </span>
              <span style={{ fontSize: 11, display: "flex", alignItems: "center", gap: 4, color: "var(--muted)" }}>
                <span style={{ width: 10, height: 10, background: accent2, display: "inline-block", borderRadius: 2 }} /> Product 2
              </span>
            </div>
          </div>

          {/* Downtime & Wastage trend */}
          <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, padding: "16px 16px 8px" }}>
            <div style={{ fontSize: 12, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 14 }}>
              Downtime % & Wastage % — 6M Trend
            </div>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={monthlyData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="month" tick={{ fontSize: 11, fill: "var(--muted)" }} />
                <YAxis tick={{ fontSize: 11, fill: "var(--muted)", fontFamily: "'DM Mono', monospace" }} />
                <Tooltip content={<CustomTooltip />} />
                <ReferenceLine y={BENCHMARKS.downtime_pct} stroke="#ef4444" strokeDasharray="4 2" label={{ value: "DT bmark", fontSize: 10, fill: "#ef4444", position: "insideTopRight" }} />
                <ReferenceLine y={BENCHMARKS.wastage_pct} stroke="#f59e0b" strokeDasharray="4 2" label={{ value: "WS bmark", fontSize: 10, fill: "#f59e0b", position: "insideBottomRight" }} />
                <Line type="monotone" dataKey="downtime_pct" name="Downtime %" stroke="#ef4444" strokeWidth={2} dot={{ r: 3 }} />
                <Line type="monotone" dataKey="wastage_pct" name="Wastage %" stroke="#f59e0b" strokeWidth={2} dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

      </div>
    </>
  );
}

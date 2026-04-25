/**
 * EbitdaCommandCentre.jsx — Fixed with null-safe company references
 */
import { useState, useMemo } from "react";
import {
  LineChart, Line, AreaChart, Area,
  PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer,
} from "recharts";
import { useCompany } from "../components/CompanyContext";
import { useClaudeInsight } from "../hooks/useClaudeInsight";
import {
  formatCurrency, formatPerTon, formatVolume,
  formatMargin, formatDelta,
} from "../utils/formatCurrency";

function useSyntheticEbitda(period) {
  return useMemo(() => {
    const months12 = ["May","Jun","Jul","Aug","Sep","Oct","Nov","Dec","Jan","Feb","Mar","Apr"];
    const actuals12 = [28.1,30.4,27.8,31.2,29.5,33.8,35.1,32.6,36.4,34.2,34.5,38.4];
    const forecast12 = [40.1,41.8,43.2,44.5,46.0,47.8,49.2,50.1,51.4,52.8,54.0];
    const fcMonths12 = ["May","Jun","Jul","Aug","Sep","Oct","Nov","Dec","Jan","Feb","Mar"];
    if (period === "3M") return { trendData: [{ month: "Feb", actual: 34.2 },{ month: "Mar", actual: 34.5 },{ month: "Apr", actual: 38.4 }], forecastData: [] };
    if (period === "36M") {
      const labels = ["Apr'22","Jul'22","Oct'22","Jan'23","Apr'23","Jul'23","Oct'23","Jan'24","Apr'24","Jul'24","Oct'24","Jan'25","Apr'25"];
      const vals = [18.2,19.5,21.3,23.8,22.4,24.1,26.8,28.0,29.5,31.2,33.8,34.5,38.4];
      return { trendData: labels.map((m, i) => ({ month: m, actual: vals[i] })), forecastData: [] };
    }
    return {
      trendData: months12.map((m, i) => ({ month: m, actual: actuals12[i] })),
      forecastData: fcMonths12.map((m, i) => ({ month: m, forecast: forecast12[i] })),
    };
  }, [period]);
}

function KpiCard({ label, value, deltaText, deltaDir, sub }) {
  const colours = { up: "#1D9E75", down: "#D85A30", flat: "#888780" };
  return (
    <div style={{ background: "var(--color-background-secondary)", borderRadius: "var(--border-radius-md)", padding: "14px 16px" }}>
      <p style={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.07em", textTransform: "uppercase", color: "var(--color-text-tertiary)", margin: "0 0 6px" }}>{label}</p>
      <p style={{ fontFamily: "'DM Mono', monospace", fontSize: 22, fontWeight: 500, color: "var(--color-text-primary)", margin: "0 0 5px", lineHeight: 1.2 }}>{value}</p>
      <p style={{ fontSize: 12, color: "var(--color-text-secondary)", margin: 0, display: "flex", alignItems: "center", gap: 5 }}>
        {deltaText && <span style={{ fontWeight: 600, color: colours[deltaDir] ?? colours.flat }}>{deltaText}</span>}
        {sub}
      </p>
    </div>
  );
}

function CycleGauge({ name, pct, colour, stub }) {
  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 5 }}>
        <span style={{ fontSize: 13, fontWeight: 500, color: "var(--color-text-primary)" }}>{name}</span>
        <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 12, color: "var(--color-text-secondary)" }}>{stub ? "— Phase 3" : `${pct}%`}</span>
      </div>
      <div style={{ height: 6, background: "var(--color-background-secondary)", borderRadius: 4, overflow: "hidden" }}>
        <div style={{ height: "100%", borderRadius: 4, width: stub ? 0 : `${pct}%`, background: colour, transition: "width 0.9s cubic-bezier(.23,1,.32,1)" }} />
      </div>
    </div>
  );
}

function InsightPanel({ kpis, companyName, brand1Name, brand2Name, secondaryColour, secondaryColourLight }) {
  const prompt = useMemo(() => {
    if (!kpis) return null;
    return `Monthly EBITDA report for ${companyName} — ${new Date().toLocaleDateString("en-IN", { month: "long", year: "numeric" })}:
EBITDA: ${kpis.ebitda} (${kpis.ebitdaDelta} vs last month)
Margin: ${kpis.margin}, Revenue: ${kpis.revenue}, Volume: ${kpis.volume}
Top SKU: 25mm ${brand1Name} at ₹56,800/T, 9.8% margin
Lowest: 10mm ${brand2Name} at ₹51,200/T, 4.7% margin
${brand1Name} revenue share: 68%
Alert: 16mm ${brand1Name} stock at 1.4 days — below 2-day buffer.
Generate a 2–3 sentence analyst insight for the business owner.`;
  }, [kpis, companyName, brand1Name, brand2Name]);

  const { insight, loading, error, refresh } = useClaudeInsight(prompt, [prompt], { max_tokens: 200 });
  const sc = secondaryColour ?? '#6366f1';
  const scl = secondaryColourLight ?? '#eef2ff';

  return (
    <div style={{ background: scl, borderLeft: `3px solid ${sc}`, borderRadius: "0 var(--border-radius-md) var(--border-radius-md) 0", padding: "12px 16px", marginBottom: 14, display: "flex", alignItems: "flex-start", gap: 10 }}>
      <div style={{ width: 18, height: 18, borderRadius: "50%", background: sc, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, marginTop: 1 }}>
        <svg width="10" height="10" viewBox="0 0 10 10" fill="none"><path d="M5 1v4M5 7.5v1" stroke="#fff" strokeWidth="1.5" strokeLinecap="round"/></svg>
      </div>
      <div style={{ flex: 1 }}>
        <p style={{ fontSize: 11, fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase", color: sc, margin: "0 0 4px" }}>
          AI Insight · {new Date().toLocaleDateString("en-IN", { month: "long", year: "numeric" })}
        </p>
        {loading && <p style={{ fontSize: 13, color: "var(--color-text-secondary)", margin: 0 }}>Analysing monthly data…</p>}
        {error && <p style={{ fontSize: 13, color: "#D85A30", margin: 0 }}>{error} — <button onClick={refresh} style={{ background: "none", border: "none", color: "#D85A30", cursor: "pointer", fontSize: 13, textDecoration: "underline", padding: 0 }}>retry</button></p>}
        {insight && !loading && <p style={{ fontSize: 13, lineHeight: 1.6, color: "var(--color-text-primary)", margin: 0 }}>{insight}</p>}
      </div>
    </div>
  );
}

function TrendTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: "var(--color-background-primary)", border: "0.5px solid var(--color-border-secondary)", borderRadius: "var(--border-radius-md)", padding: "8px 12px", fontSize: 12 }}>
      <p style={{ color: "var(--color-text-secondary)", margin: "0 0 4px" }}>{label}</p>
      {payload.map(p => (
        <p key={p.dataKey} style={{ margin: "2px 0", fontWeight: 500, color: p.dataKey === "forecast" ? "#1D9E75" : "#185FA5", fontFamily: "'DM Mono', monospace" }}>
          {p.dataKey === "forecast" ? "Forecast" : "Actual"}: ₹{p.value?.toFixed(1)} L
        </p>
      ))}
    </div>
  );
}

function MixTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: "var(--color-background-primary)", border: "0.5px solid var(--color-border-secondary)", borderRadius: "var(--border-radius-md)", padding: "8px 12px", fontSize: 12 }}>
      <p style={{ margin: 0, fontWeight: 500 }}>{payload[0].name}: {payload[0].value}%</p>
    </div>
  );
}

function LegendItem({ colour, label, solid, dashed }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 11, color: "var(--color-text-secondary)" }}>
      <div style={{ width: 14, height: 2, background: solid ? colour : "transparent", borderTop: dashed ? `2px dashed ${colour}` : "none", borderRadius: 2 }} />
      {label}
    </div>
  );
}

export default function EbitdaCommandCentre() {
  const { company } = useCompany();
  const [period, setPeriod] = useState("12M");
  const { trendData, forecastData } = useSyntheticEbitda(period);

  // Null-safe fallbacks
  const primary   = company?.primary_colour ?? '#f59e0b';
  const secondary = company?.secondary_colour ?? '#6366f1';
  const companyName  = company?.company_name ?? company?.name ?? 'AC Industries';
  const brand1Name   = company?.brand_1?.name ?? 'Product 1';
  const brand2Name   = company?.brand_2?.name ?? 'Product 2';
  const brand1Role   = company?.brand_1?.role ?? 'Growth Brand';
  const brand1ColourLight = company?.brand_1?.colour_light ?? '#fef3c7';
  const brand1Colour      = company?.brand_1?.colour ?? primary;
  const brand2ColourLight = company?.brand_2?.colour_light ?? '#ede9fe';
  const brand2Colour      = company?.brand_2?.colour ?? secondary;

  const kpis = {
    ebitda:      formatCurrency(3_840_000),
    ebitdaDelta: formatDelta(0.112).text,
    margin:      formatMargin(0.083),
    marginDelta: formatDelta(0.006, "pp").text,
    revenue:     formatCurrency(46_200_000),
    revDelta:    formatDelta(0.078).text,
    volume:      formatVolume(1847),
    volDelta:    "▼ 2.1% vs target",
  };

  const skuData = [
    { sku: "25mm", brand: "P1", real: 56800, margin: 0.098, top: true },
    { sku: "20mm", brand: "P1", real: 55600, margin: 0.092, top: true },
    { sku: "32mm", brand: "P1", real: 55200, margin: 0.090, top: true },
    { sku: "8mm",  brand: "P2", real: 51800, margin: 0.051, top: false },
    { sku: "10mm", brand: "P2", real: 51200, margin: 0.047, top: false },
  ];

  const mixData = [
    { name: brand1Name, value: 68 },
    { name: brand2Name, value: 32 },
  ];

  return (
    <div style={{ fontFamily: "'Syne', var(--font-sans), sans-serif" }}>
      {/* Period selector */}
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 16 }}>
        <div style={{ display: "flex", gap: 2, background: "var(--color-background-secondary)", borderRadius: "var(--border-radius-md)", padding: 2 }}>
          {["3M","12M","36M"].map(p => (
            <button key={p} onClick={() => setPeriod(p)} style={{ fontFamily: "'Syne', sans-serif", fontSize: 11, fontWeight: 500, padding: "5px 14px", borderRadius: 6, border: "none", cursor: "pointer", background: period === p ? "var(--color-background-primary)" : "transparent", color: period === p ? "var(--color-text-primary)" : "var(--color-text-secondary)", boxShadow: period === p ? "0 0 0 0.5px var(--color-border-secondary)" : "none", transition: "all 0.12s" }}>{p}</button>
          ))}
        </div>
      </div>

      {/* KPI row */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0,1fr))", gap: 10, marginBottom: 14 }}>
        <KpiCard label="EBITDA — MTD" value={kpis.ebitda} deltaText={kpis.ebitdaDelta} deltaDir="up" sub="vs last month" />
        <KpiCard label="EBITDA Margin" value={kpis.margin} deltaText={kpis.marginDelta} deltaDir="up" sub="vs last month" />
        <KpiCard label="Revenue — MTD" value={kpis.revenue} deltaText={kpis.revDelta} deltaDir="up" sub="vs last month" />
        <KpiCard label="Volume Dispatched" value={kpis.volume} deltaText="▼ 2.1%" deltaDir="down" sub="vs target" />
      </div>

      {/* Trend + Gauges */}
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 12, marginBottom: 12 }}>
        <div style={{ background: "var(--color-background-primary)", border: "0.5px solid var(--color-border-tertiary)", borderRadius: "var(--border-radius-lg)", padding: "16px 20px" }}>
          <p style={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--color-text-secondary)", margin: "0 0 14px" }}>
            {period === "36M" ? "36-month EBITDA trend" : period === "3M" ? "Last 3 months" : "12-month trend + 12-month forecast"}
          </p>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={trendData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="actualGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={primary} stopOpacity={0.12}/>
                  <stop offset="95%" stopColor={primary} stopOpacity={0}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border-tertiary)" vertical={false}/>
              <XAxis dataKey="month" tick={{ fontSize: 10, fill: "#888780" }} axisLine={false} tickLine={false}/>
              <YAxis tick={{ fontSize: 10, fill: "#888780" }} tickFormatter={v => `₹${v}L`} axisLine={false} tickLine={false}/>
              <Tooltip content={<TrendTooltip />}/>
              <Area dataKey="actual" name="Actual" stroke={primary} strokeWidth={2} fill="url(#actualGrad)" dot={{ r: 3, fill: primary, strokeWidth: 0 }} activeDot={{ r: 5 }} connectNulls={false}/>
            </AreaChart>
          </ResponsiveContainer>
          {period === "12M" && forecastData.length > 0 && (
            <ResponsiveContainer width="100%" height={80}>
              <LineChart data={[{ month: "Apr", forecast: 38.4 }, ...forecastData]} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
                <XAxis dataKey="month" tick={{ fontSize: 10, fill: "#888780" }} axisLine={false} tickLine={false}/>
                <YAxis tick={{ fontSize: 10, fill: "#888780" }} tickFormatter={v => `₹${v}L`} axisLine={false} tickLine={false}/>
                <Tooltip content={<TrendTooltip />}/>
                <Line dataKey="forecast" name="Forecast" stroke={secondary} strokeWidth={1.5} strokeDasharray="5 4" dot={{ r: 2, fill: secondary, strokeWidth: 0 }} activeDot={{ r: 4 }}/>
              </LineChart>
            </ResponsiveContainer>
          )}
          <div style={{ display: "flex", gap: 16, marginTop: 8 }}>
            <LegendItem colour={primary} label="Actual EBITDA" solid />
            {period === "12M" && <LegendItem colour={secondary} label="12-month forecast" dashed />}
          </div>
        </div>

        <div style={{ background: "var(--color-background-primary)", border: "0.5px solid var(--color-border-tertiary)", borderRadius: "var(--border-radius-lg)", padding: "16px 20px" }}>
          <p style={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--color-text-secondary)", margin: "0 0 18px" }}>3-Cycle Health</p>
          <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
            <CycleGauge name="Revenue Lifecycle" pct={92} colour={primary} />
            <CycleGauge name="Production Cycle" pct={79} colour={secondary} />
            <CycleGauge name="Raw Material" pct={0} colour="#888780" stub />
          </div>
          <div style={{ marginTop: 24, paddingTop: 14, borderTop: "0.5px solid var(--color-border-tertiary)" }}>
            <p style={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.07em", textTransform: "uppercase", color: "var(--color-text-tertiary)", margin: "0 0 8px" }}>Score guide</p>
            {[{ range: "90–100%", label: "On plan", colour: "#1D9E75" },{ range: "70–89%", label: "Monitor", colour: "#BA7517" },{ range: "< 70%", label: "Action", colour: "#D85A30" }].map(r => (
              <div key={r.range} style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "var(--color-text-secondary)", marginBottom: 4 }}>
                <span>{r.range}</span>
                <span style={{ color: r.colour, fontWeight: 600 }}>{r.label}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* AI Insight */}
      <InsightPanel kpis={kpis} companyName={companyName} brand1Name={brand1Name} brand2Name={brand2Name} secondaryColour={secondary} secondaryColourLight={company?.secondary_colour_light ?? '#eef2ff'} />

      {/* SKU margins + Mix donut */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <div style={{ background: "var(--color-background-primary)", border: "0.5px solid var(--color-border-tertiary)", borderRadius: "var(--border-radius-lg)", padding: "16px 20px" }}>
          <p style={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--color-text-secondary)", margin: "0 0 12px" }}>SKU Margins — top & bottom performers</p>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                {["SKU","Brand","Realisation","Margin"].map(h => (
                  <th key={h} style={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase", color: "var(--color-text-tertiary)", textAlign: h === "Realisation" || h === "Margin" ? "right" : "left", padding: "0 0 8px", borderBottom: "0.5px solid var(--color-border-tertiary)" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {skuData.map((s, i) => {
                const isBreak = i === 3;
                const brandColour = s.brand === "P1" ? brand1Colour : brand2Colour;
                const brandColourLight = s.brand === "P1" ? brand1ColourLight : brand2ColourLight;
                return (
                  <>
                    {isBreak && (
                      <tr key="break">
                        <td colSpan={4} style={{ fontSize: 10, letterSpacing: "0.06em", textTransform: "uppercase", color: "var(--color-text-tertiary)", padding: "8px 0 4px", borderBottom: "0.5px solid var(--color-border-tertiary)" }}>Bottom performers</td>
                      </tr>
                    )}
                    <tr key={s.sku + s.brand}>
                      <td style={{ fontSize: 13, padding: "7px 0", borderBottom: "0.5px solid var(--color-border-tertiary)", color: "var(--color-text-primary)" }}>{s.sku}</td>
                      <td style={{ padding: "7px 0", borderBottom: "0.5px solid var(--color-border-tertiary)" }}>
                        <span style={{ display: "inline-block", padding: "2px 7px", borderRadius: 20, fontSize: 10, fontWeight: 600, background: brandColourLight, color: brandColour }}>{s.brand}</span>
                      </td>
                      <td style={{ fontFamily: "'DM Mono', monospace", fontSize: 12, textAlign: "right", padding: "7px 0", borderBottom: "0.5px solid var(--color-border-tertiary)", color: "var(--color-text-primary)" }}>{formatPerTon(s.real)}</td>
                      <td style={{ fontFamily: "'DM Mono', monospace", fontSize: 12, textAlign: "right", padding: "7px 0", borderBottom: "0.5px solid var(--color-border-tertiary)", fontWeight: 600, color: s.top ? "#1D9E75" : "#D85A30" }}>{formatMargin(s.margin)}</td>
                    </tr>
                  </>
                );
              })}
            </tbody>
          </table>
        </div>

        <div style={{ background: "var(--color-background-primary)", border: "0.5px solid var(--color-border-tertiary)", borderRadius: "var(--border-radius-lg)", padding: "16px 20px" }}>
          <p style={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--color-text-secondary)", margin: "0 0 4px" }}>Revenue mix — {brand1Name} vs {brand2Name}</p>
          <ResponsiveContainer width="100%" height={180}>
            <PieChart>
              <Pie data={mixData} cx="50%" cy="50%" innerRadius={54} outerRadius={76} paddingAngle={3} dataKey="value" startAngle={90} endAngle={-270}>
                <Cell fill={primary} />
                <Cell fill={brand2Colour} />
              </Pie>
              <Tooltip content={<MixTooltip />} />
            </PieChart>
          </ResponsiveContainer>
          <div style={{ display: "flex", justifyContent: "center", gap: 20, marginTop: 4 }}>
            {mixData.map((m, i) => (
              <div key={m.name} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: "var(--color-text-secondary)" }}>
                <span style={{ width: 10, height: 10, borderRadius: 2, flexShrink: 0, background: i === 0 ? primary : brand2Colour }} />
                {m.name} — {m.value}%
              </div>
            ))}
          </div>
          <div style={{ marginTop: 16, paddingTop: 12, borderTop: "0.5px solid var(--color-border-tertiary)", fontSize: 12, color: "var(--color-text-secondary)", lineHeight: 1.5 }}>
            <span style={{ fontWeight: 600, color: "var(--color-text-primary)" }}>{brand1Name}</span>{" "}
            is the {brand1Role.toLowerCase()}. Target mix shift: 70:30 by Q2.
          </div>
        </div>
      </div>
    </div>
  );
}

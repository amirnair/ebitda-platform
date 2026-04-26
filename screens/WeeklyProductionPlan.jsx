import { useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  LineChart, Line, Legend, ReferenceLine
} from "recharts";
import { useCompany } from "../components/CompanyContext";
import { useClaudeInsight } from "../hooks/useClaudeInsight";
import { formatVolume, formatCurrency } from "../utils/formatCurrency";

// ─── Mock data — mirrors LP engine / production_plan output ───────────────────
const WEEK_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

const weeklyPlan = [
  { day: "Mon", date: "28 Apr", p1_mt: 120, p2_mt: 80, target_mt: 200, capacity_pct: 82, billet_draw_p1: 126, billet_draw_p2: 84, skus: ["P1-SKU-16", "P1-SKU-12", "P2-SKU-16"] },
  { day: "Tue", date: "29 Apr", p1_mt: 130, p2_mt: 70, target_mt: 200, capacity_pct: 88, billet_draw_p1: 137, billet_draw_p2: 74, skus: ["P1-SKU-20", "P1-SKU-25", "P2-SKU-12"] },
  { day: "Wed", date: "30 Apr", p1_mt: 140, p2_mt: 60, target_mt: 200, capacity_pct: 91, billet_draw_p1: 147, billet_draw_p2: 63, skus: ["P1-SKU-16", "P1-SKU-32", "P2-SKU-10"] },
  { day: "Thu", date: "01 May", p1_mt: 125, p2_mt: 75, target_mt: 200, capacity_pct: 85, billet_draw_p1: 131, billet_draw_p2: 79, skus: ["P1-SKU-12", "P1-SKU-16", "P2-SKU-16"] },
  { day: "Fri", date: "02 May", p1_mt: 110, p2_mt: 90, target_mt: 200, capacity_pct: 79, billet_draw_p1: 116, billet_draw_p2: 95, skus: ["P2-SKU-20", "P2-SKU-25", "P1-SKU-10"] },
  { day: "Sat", date: "03 May", p1_mt: 135, p2_mt: 65, target_mt: 200, capacity_pct: 87, billet_draw_p1: 142, billet_draw_p2: 68, skus: ["P1-SKU-8", "P1-SKU-16", "P2-SKU-8"] },
  { day: "Sun", date: "04 May", p1_mt: 90,  p2_mt: 50, target_mt: 150, capacity_pct: 72, billet_draw_p1: 95,  billet_draw_p2: 53, skus: ["P1-SKU-16", "P2-SKU-16"] },
];

const skuBreakdown = [
  { sku: "P1-SKU-8",  brand: "P1", qty_mt: 45,  days: [1,0,0,0,0,1,0] },
  { sku: "P1-SKU-10", brand: "P1", qty_mt: 38,  days: [0,0,0,0,1,0,0] },
  { sku: "P1-SKU-12", brand: "P1", qty_mt: 125, days: [1,0,0,1,0,0,0] },
  { sku: "P1-SKU-16", brand: "P1", qty_mt: 290, days: [1,0,1,1,0,1,1] },
  { sku: "P1-SKU-20", brand: "P1", qty_mt: 95,  days: [0,1,0,0,0,0,0] },
  { sku: "P1-SKU-25", brand: "P1", qty_mt: 72,  days: [0,1,0,0,0,0,0] },
  { sku: "P1-SKU-32", brand: "P1", qty_mt: 54,  days: [0,0,1,0,0,0,0] },
  { sku: "P2-SKU-8",  brand: "P2", qty_mt: 28,  days: [0,0,0,0,0,1,0] },
  { sku: "P2-SKU-10", brand: "P2", qty_mt: 35,  days: [0,0,1,0,0,0,0] },
  { sku: "P2-SKU-12", brand: "P2", qty_mt: 48,  days: [0,1,0,0,0,0,0] },
  { sku: "P2-SKU-16", brand: "P2", qty_mt: 180, days: [1,0,0,1,0,0,1] },
  { sku: "P2-SKU-20", brand: "P2", qty_mt: 65,  days: [0,0,0,0,1,0,0] },
  { sku: "P2-SKU-25", brand: "P2", qty_mt: 45,  days: [0,0,0,0,1,0,0] },
];

const billetProcurement = {
  p1_opening: 485,
  p2_opening: 312,
  p1_draw_total: 894,
  p2_draw_total: 516,
  p1_safety_stock: 150,
  p2_safety_stock: 100,
  p1_recommend_order: 559,
  p2_recommend_order: 304,
  p1_closing_projected: 150,
  p2_closing_projected: 100,
};

// ─── Sub-components ──────────────────────────────────────────────────────────

function KpiCard({ label, value, sub, accent }) {
  return (
    <div style={{
      background: "#fff",
      border: "1px solid #e8ecf0",
      borderRadius: 10,
      padding: "18px 22px",
      borderLeft: `4px solid ${accent}`,
    }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: "#8b95a1", textTransform: "uppercase", letterSpacing: 1, marginBottom: 6 }}>{label}</div>
      <div style={{ fontSize: 24, fontWeight: 700, color: "#1a2332", fontFamily: "'DM Mono', monospace" }}>{value}</div>
      {sub && <div style={{ fontSize: 12, color: "#8b95a1", marginTop: 4 }}>{sub}</div>}
    </div>
  );
}

function CapacityBar({ pct, primary }) {
  const colour = pct >= 90 ? "#ef4444" : pct >= 75 ? primary : "#22c55e";
  return (
    <div style={{ position: "relative", height: 8, background: "#e8ecf0", borderRadius: 4, overflow: "hidden" }}>
      <div style={{ position: "absolute", left: 0, top: 0, height: "100%", width: `${pct}%`, background: colour, borderRadius: 4, transition: "width 0.6s ease" }} />
    </div>
  );
}

function DayDot({ active }) {
  return (
    <div style={{
      width: 10, height: 10, borderRadius: "50%",
      background: active ? "#22c55e" : "#e8ecf0",
      border: active ? "2px solid #16a34a" : "2px solid #d1d5db",
    }} />
  );
}

// ─── Main Screen ─────────────────────────────────────────────────────────────

export default function WeeklyProductionPlan() {
  const { company } = useCompany();  if (!company) return null;
  const primary = company.primary_colour || "#2563eb";
  const secondary = company.secondary_colour || "#7c3aed";
  const p1Label = company.brand_p1 || "Product 1";
  const p2Label = company.brand_p2 || "Product 2";

  const [selectedDay, setSelectedDay] = useState(null);

  const totalP1 = weeklyPlan.reduce((s, d) => s + d.p1_mt, 0);
  const totalP2 = weeklyPlan.reduce((s, d) => s + d.p2_mt, 0);
  const totalMT = totalP1 + totalP2;
  const avgCap = Math.round(weeklyPlan.reduce((s, d) => s + d.capacity_pct, 0) / weeklyPlan.length);

  const insightPrompt = `You are a steel mill production manager reviewing the week-ahead rolling plan for a TMT rebar mill in Tamil Nadu. 
Week total: ${totalMT} MT planned (${p1Label}: ${totalP1} MT, ${p2Label}: ${totalP2} MT). Average capacity utilisation: ${avgCap}%. 
Billet procurement recommendation: ${p1Label} ${billetProcurement.p1_recommend_order} MT, ${p2Label} ${billetProcurement.p2_recommend_order} MT.
In 2-3 sentences, highlight the most important production management action for this week, noting any capacity or billet risk. Use Lakhs/Crores for any cost figures. One clear action. No jargon.`;

  const { insight, loading: insightLoading, refresh: refreshInsight } = useClaudeInsight(insightPrompt, [totalMT]);

  const chartData = weeklyPlan.map(d => ({
    name: d.day,
    [p1Label]: d.p1_mt,
    [p2Label]: d.p2_mt,
    Target: d.target_mt,
    Capacity: d.capacity_pct,
  }));

  return (
    <div style={{ padding: "28px 32px", background: "#f7f8fa", minHeight: "100vh", fontFamily: "'DM Sans', sans-serif" }}>
      {/* Header */}
      <div style={{ marginBottom: 28 }}>
        <div style={{ fontSize: 22, fontWeight: 700, color: "#1a2332", fontFamily: "'Syne', sans-serif" }}>Weekly Production Plan</div>
        <div style={{ fontSize: 13, color: "#8b95a1", marginTop: 4 }}>Week of 28 Apr – 04 May 2025 · Auto-generated from LP optimiser</div>
      </div>

      {/* KPI Row */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16, marginBottom: 24 }}>
        <KpiCard label="Week Total MT" value={formatVolume(totalMT)} sub="Planned production" accent={primary} />
        <KpiCard label={`${p1Label} MT`} value={formatVolume(totalP1)} sub={`${Math.round(totalP1/totalMT*100)}% of week`} accent={primary} />
        <KpiCard label={`${p2Label} MT`} value={formatVolume(totalP2)} sub={`${Math.round(totalP2/totalMT*100)}% of week`} accent={secondary} />
        <KpiCard label="Avg Capacity" value={`${avgCap}%`} sub="Mill utilisation" accent={avgCap >= 85 ? "#22c55e" : "#f59e0b"} />
      </div>

      {/* AI Insight */}
      <div style={{
        background: "#fff", border: `1px solid ${primary}22`, borderLeft: `4px solid ${primary}`,
        borderRadius: 10, padding: "16px 20px", marginBottom: 24, display: "flex", gap: 14, alignItems: "flex-start"
      }}>
        <div style={{ fontSize: 18 }}>🤖</div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: primary, textTransform: "uppercase", letterSpacing: 1, marginBottom: 6 }}>AI Weekly Insight</div>
          {insightLoading
            ? <div style={{ fontSize: 13, color: "#8b95a1" }}>Analysing week-ahead plan…</div>
            : <div style={{ fontSize: 13, color: "#374151", lineHeight: 1.6 }}>{insight}</div>
          }
        </div>
        <button onClick={refreshInsight} style={{ background: "none", border: `1px solid ${primary}44`, borderRadius: 6, padding: "4px 10px", fontSize: 11, color: primary, cursor: "pointer" }}>↻</button>
      </div>

      {/* Charts row */}
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 20, marginBottom: 20 }}>
        {/* Stacked bar */}
        <div style={{ background: "#fff", borderRadius: 10, border: "1px solid #e8ecf0", padding: "20px 24px" }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: "#374151", marginBottom: 16 }}>Daily Production by Brand (MT)</div>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={chartData} barSize={28}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#8b95a1" }} />
              <YAxis tick={{ fontSize: 11, fill: "#8b95a1" }} />
              <Tooltip contentStyle={{ fontSize: 12, borderRadius: 6 }} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Bar dataKey={p1Label} stackId="a" fill={primary} radius={[0,0,0,0]} />
              <Bar dataKey={p2Label} stackId="a" fill={secondary} radius={[4,4,0,0]} />
              <ReferenceLine y={200} stroke="#ef4444" strokeDasharray="4 4" label={{ value: "Target", position: "right", fontSize: 10, fill: "#ef4444" }} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Capacity utilisation */}
        <div style={{ background: "#fff", borderRadius: 10, border: "1px solid #e8ecf0", padding: "20px 24px" }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: "#374151", marginBottom: 16 }}>Capacity Utilisation %</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {weeklyPlan.map(d => (
              <div key={d.day}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                  <span style={{ fontSize: 12, color: "#374151", fontWeight: 500 }}>{d.day}</span>
                  <span style={{ fontSize: 12, fontFamily: "'DM Mono', monospace", color: d.capacity_pct >= 90 ? "#ef4444" : "#374151" }}>{d.capacity_pct}%</span>
                </div>
                <CapacityBar pct={d.capacity_pct} primary={primary} />
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Day-by-day plan table */}
      <div style={{ background: "#fff", borderRadius: 10, border: "1px solid #e8ecf0", padding: "20px 24px", marginBottom: 20 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: "#374151", marginBottom: 16 }}>Day-by-Day Plan</div>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
            <thead>
              <tr style={{ background: "#f7f8fa" }}>
                {["Day", "Date", `${p1Label} MT`, `${p2Label} MT`, "Total MT", "vs Target", "Billet P1 (MT)", "Billet P2 (MT)", "Capacity %", "SKUs"].map(h => (
                  <th key={h} style={{ padding: "9px 12px", textAlign: "left", color: "#8b95a1", fontWeight: 600, fontSize: 11, textTransform: "uppercase", letterSpacing: 0.5, whiteSpace: "nowrap" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {weeklyPlan.map((d, i) => {
                const total = d.p1_mt + d.p2_mt;
                const vsTarget = total - d.target_mt;
                return (
                  <tr key={d.day}
                    onClick={() => setSelectedDay(selectedDay === i ? null : i)}
                    style={{ borderTop: "1px solid #f1f5f9", cursor: "pointer", background: selectedDay === i ? `${primary}08` : "transparent" }}>
                    <td style={{ padding: "10px 12px", fontWeight: 700, color: "#1a2332" }}>{d.day}</td>
                    <td style={{ padding: "10px 12px", color: "#8b95a1" }}>{d.date}</td>
                    <td style={{ padding: "10px 12px", fontFamily: "'DM Mono', monospace", color: primary }}>{d.p1_mt}</td>
                    <td style={{ padding: "10px 12px", fontFamily: "'DM Mono', monospace", color: secondary }}>{d.p2_mt}</td>
                    <td style={{ padding: "10px 12px", fontFamily: "'DM Mono', monospace", fontWeight: 700 }}>{total}</td>
                    <td style={{ padding: "10px 12px", fontFamily: "'DM Mono', monospace", color: vsTarget >= 0 ? "#22c55e" : "#ef4444" }}>
                      {vsTarget >= 0 ? "+" : ""}{vsTarget}
                    </td>
                    <td style={{ padding: "10px 12px", fontFamily: "'DM Mono', monospace" }}>{d.billet_draw_p1}</td>
                    <td style={{ padding: "10px 12px", fontFamily: "'DM Mono', monospace" }}>{d.billet_draw_p2}</td>
                    <td style={{ padding: "10px 12px" }}>
                      <span style={{
                        background: d.capacity_pct >= 90 ? "#fef2f2" : d.capacity_pct >= 75 ? "#fefce8" : "#f0fdf4",
                        color: d.capacity_pct >= 90 ? "#ef4444" : d.capacity_pct >= 75 ? "#ca8a04" : "#16a34a",
                        borderRadius: 4, padding: "2px 8px", fontFamily: "'DM Mono', monospace", fontSize: 11, fontWeight: 700
                      }}>{d.capacity_pct}%</span>
                    </td>
                    <td style={{ padding: "10px 12px" }}>
                      <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                        {d.skus.map(s => (
                          <span key={s} style={{
                            background: s.startsWith("P1") ? `${primary}15` : `${secondary}15`,
                            color: s.startsWith("P1") ? primary : secondary,
                            borderRadius: 4, padding: "2px 6px", fontSize: 10, fontWeight: 600
                          }}>{s}</span>
                        ))}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
            <tfoot>
              <tr style={{ borderTop: "2px solid #e8ecf0", background: "#f7f8fa" }}>
                <td colSpan={2} style={{ padding: "10px 12px", fontWeight: 700, fontSize: 12, color: "#1a2332" }}>WEEK TOTAL</td>
                <td style={{ padding: "10px 12px", fontFamily: "'DM Mono', monospace", fontWeight: 700, color: primary }}>{totalP1}</td>
                <td style={{ padding: "10px 12px", fontFamily: "'DM Mono', monospace", fontWeight: 700, color: secondary }}>{totalP2}</td>
                <td style={{ padding: "10px 12px", fontFamily: "'DM Mono', monospace", fontWeight: 700 }}>{totalMT}</td>
                <td colSpan={5} />
              </tr>
            </tfoot>
          </table>
        </div>
      </div>

      {/* SKU Schedule heatmap + Billet Procurement */}
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 20 }}>
        {/* SKU schedule */}
        <div style={{ background: "#fff", borderRadius: 10, border: "1px solid #e8ecf0", padding: "20px 24px" }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: "#374151", marginBottom: 16 }}>SKU Production Schedule</div>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
              <thead>
                <tr>
                  <th style={{ padding: "8px 10px", textAlign: "left", color: "#8b95a1", fontWeight: 600, fontSize: 11, textTransform: "uppercase" }}>SKU</th>
                  <th style={{ padding: "8px 10px", textAlign: "right", color: "#8b95a1", fontWeight: 600, fontSize: 11, textTransform: "uppercase" }}>Week MT</th>
                  {WEEK_DAYS.map(d => (
                    <th key={d} style={{ padding: "8px 6px", textAlign: "center", color: "#8b95a1", fontWeight: 600, fontSize: 11 }}>{d}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {skuBreakdown.map(row => (
                  <tr key={row.sku} style={{ borderTop: "1px solid #f1f5f9" }}>
                    <td style={{ padding: "8px 10px" }}>
                      <span style={{
                        background: row.brand === "P1" ? `${primary}15` : `${secondary}15`,
                        color: row.brand === "P1" ? primary : secondary,
                        borderRadius: 4, padding: "2px 8px", fontSize: 11, fontWeight: 600
                      }}>{row.sku}</span>
                    </td>
                    <td style={{ padding: "8px 10px", textAlign: "right", fontFamily: "'DM Mono', monospace", fontWeight: 600 }}>{row.qty_mt}</td>
                    {row.days.map((active, di) => (
                      <td key={di} style={{ padding: "8px 6px", textAlign: "center" }}>
                        <DayDot active={active === 1} />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Billet Procurement */}
        <div style={{ background: "#fff", borderRadius: 10, border: "1px solid #e8ecf0", padding: "20px 24px" }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: "#374151", marginBottom: 4 }}>Billet Procurement Recommendation</div>
          <div style={{ fontSize: 11, color: "#8b95a1", marginBottom: 16 }}>Order by Sunday for next week delivery</div>

          {[
            { label: p1Label, colour: primary, opening: billetProcurement.p1_opening, draw: billetProcurement.p1_draw_total, order: billetProcurement.p1_recommend_order, closing: billetProcurement.p1_closing_projected, safety: billetProcurement.p1_safety_stock },
            { label: p2Label, colour: secondary, opening: billetProcurement.p2_opening, draw: billetProcurement.p2_draw_total, order: billetProcurement.p2_recommend_order, closing: billetProcurement.p2_closing_projected, safety: billetProcurement.p2_safety_stock },
          ].map(b => (
            <div key={b.label} style={{ marginBottom: 20 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: b.colour, marginBottom: 10, display: "flex", alignItems: "center", gap: 6 }}>
                <div style={{ width: 8, height: 8, borderRadius: "50%", background: b.colour }} />
                {b.label} Billet
              </div>
              {[
                { label: "Opening Stock", value: `${b.opening} MT` },
                { label: "Week Draw", value: `−${b.draw} MT`, colour: "#ef4444" },
                { label: "Safety Stock", value: `${b.safety} MT` },
                { label: "Order Required", value: `${b.order} MT`, highlight: true, colour: b.colour },
                { label: "Projected Closing", value: `${b.closing} MT`, colour: "#22c55e" },
              ].map(row => (
                <div key={row.label} style={{
                  display: "flex", justifyContent: "space-between", padding: "7px 10px",
                  background: row.highlight ? `${b.colour}10` : "transparent",
                  borderRadius: 6, marginBottom: 2,
                  border: row.highlight ? `1px solid ${b.colour}30` : "none"
                }}>
                  <span style={{ fontSize: 12, color: "#6b7280" }}>{row.label}</span>
                  <span style={{ fontSize: 12, fontFamily: "'DM Mono', monospace", fontWeight: row.highlight ? 700 : 500, color: row.colour || "#1a2332" }}>{row.value}</span>
                </div>
              ))}
            </div>
          ))}

          <div style={{ background: "#f0fdf4", border: "1px solid #bbf7d0", borderRadius: 8, padding: "12px 14px", marginTop: 8 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: "#16a34a", marginBottom: 4 }}>✓ Procurement Order Summary</div>
            <div style={{ fontSize: 12, color: "#15803d" }}>
              {p1Label}: <strong>{billetProcurement.p1_recommend_order} MT</strong> · {p2Label}: <strong>{billetProcurement.p2_recommend_order} MT</strong>
            </div>
            <div style={{ fontSize: 11, color: "#4ade80", marginTop: 4 }}>
              Total: {billetProcurement.p1_recommend_order + billetProcurement.p2_recommend_order} MT · Covers 7-day run + safety buffer
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

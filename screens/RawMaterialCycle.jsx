import { useState, useMemo } from "react";
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, ReferenceLine } from "recharts";
import { useCompany } from "../components/CompanyContext";

const mockMonthlyRM = [
  { month:"Nov", cost_per_ton:4200, yield_pct:91.2, rejection_pct:4.1, supplier_otd:88 },
  { month:"Dec", cost_per_ton:4350, yield_pct:90.8, rejection_pct:4.6, supplier_otd:85 },
  { month:"Jan", cost_per_ton:4180, yield_pct:92.1, rejection_pct:3.8, supplier_otd:91 },
  { month:"Feb", cost_per_ton:4420, yield_pct:91.5, rejection_pct:4.2, supplier_otd:87 },
  { month:"Mar", cost_per_ton:4310, yield_pct:92.8, rejection_pct:3.5, supplier_otd:93 },
  { month:"Apr", cost_per_ton:4290, yield_pct:93.1, rejection_pct:3.3, supplier_otd:94 },
];
const BENCHMARKS = { cost_per_ton:4200, yield_pct:92.0, rejection_pct:4.0, supplier_otd:90 };
const mockSupplierMix = [
  { supplier:"Supplier A", share_pct:38, avg_cost:4150, quality_score:94 },
  { supplier:"Supplier B", share_pct:27, avg_cost:4380, quality_score:89 },
  { supplier:"Supplier C", share_pct:21, avg_cost:4210, quality_score:92 },
  { supplier:"Supplier D", share_pct:14, avg_cost:4490, quality_score:86 },
];
const latest = mockMonthlyRM[mockMonthlyRM.length - 1];
const prev = mockMonthlyRM[mockMonthlyRM.length - 2];
function delta(key, invert=false){ const d=latest[key]-prev[key]; return {value:d,good:invert?d<0:d>0}; }

function KpiCard({ label, value, sub, good }) {
  return (
    <div style={{ background:"var(--color-background-primary)", border:"0.5px solid var(--color-border-tertiary)", borderRadius:12, padding:"20px 24px", flex:1, minWidth:180 }}>
      <p style={{ fontSize:11, fontWeight:600, color:"var(--color-text-tertiary)", textTransform:"uppercase", letterSpacing:"0.08em", margin:0 }}>{label}</p>
      <p style={{ fontSize:28, fontWeight:700, color:"var(--color-text-primary)", margin:"8px 0 4px" }}>{value}</p>
      <p style={{ fontSize:12, color:good?"#22c55e":"#ef4444", margin:0 }}>{good?"▲":"▼"} {Math.abs(sub).toFixed(1)} vs last month</p>
    </div>
  );
}

export default function RawMaterialCycle() {
  const { company } = useCompany();
  const primary = company?.primary_colour ?? "#f59e0b";
  const costDelta=delta("cost_per_ton",true), yieldDelta=delta("yield_pct"), rejDelta=delta("rejection_pct",true), otdDelta=delta("supplier_otd");
  return (
    <div style={{ padding:"32px 40px", maxWidth:1400, margin:"0 auto" }}>
      <div style={{ marginBottom:32 }}>
        <h1 style={{ fontSize:24, fontWeight:700, color:"var(--color-text-primary)", margin:0 }}>Raw Material Cycle</h1>
        <p style={{ fontSize:14, color:"var(--color-text-tertiary)", margin:"4px 0 0" }}>Procurement cost, yield quality &amp; supplier performance · Phase 3</p>
      </div>
      <div style={{ display:"flex", gap:16, flexWrap:"wrap", marginBottom:32 }}>
        <KpiCard label="Cost / Ton (Apr)" value={`₹${latest.cost_per_ton.toLocaleString()}`} sub={costDelta.value} good={costDelta.good} />
        <KpiCard label="Yield %" value={`${latest.yield_pct}%`} sub={yieldDelta.value} good={yieldDelta.good} />
        <KpiCard label="Rejection %" value={`${latest.rejection_pct}%`} sub={rejDelta.value} good={rejDelta.good} />
        <KpiCard label="Supplier OTD %" value={`${latest.supplier_otd}%`} sub={otdDelta.value} good={otdDelta.good} />
      </div>
      <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:24, marginBottom:24 }}>
        <div style={{ background:"var(--color-background-primary)", border:"0.5px solid var(--color-border-tertiary)", borderRadius:12, padding:24 }}>
          <h3 style={{ fontSize:14, fontWeight:600, color:"var(--color-text-primary)", margin:"0 0 20px" }}>RM Cost / Ton Trend</h3>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={mockMonthlyRM}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border-tertiary)" />
              <XAxis dataKey="month" tick={{ fontSize:11, fill:"var(--color-text-tertiary)" }} />
              <YAxis domain={[4000,4600]} tick={{ fontSize:11, fill:"var(--color-text-tertiary)" }} />
              <Tooltip formatter={(v) => [`₹${v.toLocaleString()}`,"Cost/ton"]} />
              <ReferenceLine y={BENCHMARKS.cost_per_ton} stroke="#ef4444" strokeDasharray="4 4" label={{ value:"Target", fontSize:10, fill:"#ef4444" }} />
              <Line type="monotone" dataKey="cost_per_ton" stroke={primary} strokeWidth={2} dot={{ r:4 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div style={{ background:"var(--color-background-primary)", border:"0.5px solid var(--color-border-tertiary)", borderRadius:12, padding:24 }}>
          <h3 style={{ fontSize:14, fontWeight:600, color:"var(--color-text-primary)", margin:"0 0 20px" }}>Yield vs Rejection %</h3>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={mockMonthlyRM}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border-tertiary)" />
              <XAxis dataKey="month" tick={{ fontSize:11, fill:"var(--color-text-tertiary)" }} />
              <YAxis tick={{ fontSize:11, fill:"var(--color-text-tertiary)" }} />
              <Tooltip /><Legend />
              <Line type="monotone" dataKey="yield_pct" stroke="#22c55e" strokeWidth={2} dot={{ r:4 }} name="Yield %" />
              <Line type="monotone" dataKey="rejection_pct" stroke="#ef4444" strokeWidth={2} dot={{ r:4 }} name="Rejection %" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
      <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:24 }}>
        <div style={{ background:"var(--color-background-primary)", border:"0.5px solid var(--color-border-tertiary)", borderRadius:12, padding:24 }}>
          <h3 style={{ fontSize:14, fontWeight:600, color:"var(--color-text-primary)", margin:"0 0 20px" }}>Supplier On-Time Delivery %</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={mockMonthlyRM}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border-tertiary)" />
              <XAxis dataKey="month" tick={{ fontSize:11, fill:"var(--color-text-tertiary)" }} />
              <YAxis domain={[75,100]} tick={{ fontSize:11, fill:"var(--color-text-tertiary)" }} />
              <Tooltip formatter={(v) => [`${v}%`,"OTD"]} />
              <ReferenceLine y={BENCHMARKS.supplier_otd} stroke="#f59e0b" strokeDasharray="4 4" label={{ value:"Target 90%", fontSize:10, fill:"#f59e0b" }} />
              <Bar dataKey="supplier_otd" fill={primary} radius={[4,4,0,0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div style={{ background:"var(--color-background-primary)", border:"0.5px solid var(--color-border-tertiary)", borderRadius:12, padding:24 }}>
          <h3 style={{ fontSize:14, fontWeight:600, color:"var(--color-text-primary)", margin:"0 0 20px" }}>Supplier Mix &amp; Quality</h3>
          <table style={{ width:"100%", borderCollapse:"collapse", fontSize:13 }}>
            <thead><tr>{["Supplier","Share %","Avg Cost/T","Quality"].map(h=>(
              <th key={h} style={{ textAlign:"left", padding:"6px 8px", borderBottom:"1px solid var(--color-border-tertiary)", color:"var(--color-text-tertiary)", fontWeight:600, fontSize:11, textTransform:"uppercase" }}>{h}</th>
            ))}</tr></thead>
            <tbody>{mockSupplierMix.map(s=>(
              <tr key={s.supplier} style={{ borderBottom:"0.5px solid var(--color-border-tertiary)" }}>
                <td style={{ padding:"10px 8px", color:"var(--color-text-primary)" }}>{s.supplier}</td>
                <td style={{ padding:"10px 8px" }}>
                  <div style={{ display:"flex", alignItems:"center", gap:8 }}>
                    <div style={{ flex:1, height:6, background:"var(--color-background-secondary)", borderRadius:3 }}>
                      <div style={{ width:`${s.share_pct}%`, height:"100%", background:primary, borderRadius:3 }} />
                    </div>
                    <span style={{ color:"var(--color-text-secondary)", minWidth:30 }}>{s.share_pct}%</span>
                  </div>
                </td>
                <td style={{ padding:"10px 8px", color:"var(--color-text-secondary)" }}>₹{s.avg_cost.toLocaleString()}</td>
                <td style={{ padding:"10px 8px" }}>
                  <span style={{ background:s.quality_score>=92?"#dcfce7":s.quality_score>=89?"#fef9c3":"#fee2e2", color:s.quality_score>=92?"#166534":s.quality_score>=89?"#854d0e":"#991b1b", borderRadius:6, padding:"2px 8px", fontSize:12, fontWeight:600 }}>{s.quality_score}</span>
                </td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

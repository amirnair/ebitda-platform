/**
 * RawMaterialCycle.jsx - Wired to Supabase (raw_material_data)
 */
import { useState, useEffect, useMemo } from "react";
import {
  LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from "recharts";
import { supabase } from "../lib/supabaseClient";
import { useCompany } from "../components/CompanyContext";

const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
const BM = { cost_per_ton: 2700, yield_pct: 92.0, rejection_pct: 2.0, supplier_otd: 90 };
const CS = { background:"var(--color-background-primary)", border:"0.5px solid var(--color-border-tertiary)", borderRadius:12, padding:"20px 24px" };
const TK = { fill:"var(--color-text-tertiary)", fontSize:11 };
const TP = { contentStyle:{ background:"#1f2937", border:"none", borderRadius:8 }, labelStyle:{ color:"#f9fafb" } };

function useRawMaterialData() {
  const { company } = useCompany();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  useEffect(() => {
    if (!company?.id) return;
    async function load() {
      setLoading(true); setError(null);
      const { data, error: err } = await supabase
        .from("raw_material_data").select("*")
        .eq("company_id", company.id)
        .order("year", { ascending: true }).order("month", { ascending: true });
      if (err) { setError(err.message); setLoading(false); return; }
      setRows(data || []); setLoading(false);
    }
    load();
  }, [company?.id]);
  const monthlyData = useMemo(() => rows.map(r => ({
    month: MONTHS[r.month - 1] + " '" + String(r.year).slice(2),
    cost_per_ton: parseFloat(r.cost_per_ton),
    yield_pct: parseFloat(r.yield_pct),
    rejection_pct: parseFloat(r.rejection_pct),
    supplier_otd: parseFloat(r.supplier_otd),
  })), [rows]);
  const supplierData = useMemo(() => {
    const lat = rows[rows.length - 1];
    if (!lat?.supplier_breakdown) return [];
    return Object.entries(lat.supplier_breakdown).map(([s, p]) => ({ supplier: s, share_pct: Number(p) }));
  }, [rows]);
  return { monthlyData, supplierData, loading, error };
}

function KpiCard({ label, value, sub, good }) {
  return (
    <div style={{ background:"var(--color-background-primary)", border:"0.5px solid var(--color-border-tertiary)", borderRadius:12, padding:"20px 24px", flex:1, minWidth:180 }}>
      <p style={{ fontSize:11, fontWeight:600, color:"var(--color-text-tertiary)", textTransform:"uppercase", letterSpacing:"0.08em", margin:0 }}>{label}</p>
      <p style={{ fontSize:28, fontWeight:700, color:"var(--color-text-primary)", margin:"8px 0 4px" }}>{value}</p>
      <p style={{ fontSize:12, color:good?"#4ade80":"#f87171", margin:0 }}>{sub}</p>
    </div>
  );
}

export default function RawMaterialCycle() {
  const { company } = useCompany();
  const { monthlyData, supplierData, loading, error } = useRawMaterialData();
  if (!company) return <div className="p-8 text-gray-400">Loading...</div>;
  if (loading) return <div className="flex items-center justify-center h-64"><div className="animate-spin rounded-full h-10 w-10 border-b-2 border-indigo-500" /></div>;
  if (error) return <div className="p-8 text-red-400">Error: {error}</div>;
  if (!monthlyData.length) return <div className="p-8 text-gray-400">No raw material data found.</div>;
  const lat = monthlyData[monthlyData.length - 1];
  const prv = monthlyData[monthlyData.length - 2];
  const d = (k, inv = false) => { if (!prv) return { v:0, g:true }; const diff = lat[k] - prv[k]; return { v:diff, g:inv ? diff < 0 : diff > 0 }; };
  const fmt = (k, inv, unit) => { const r = d(k, inv); return (r.v >= 0 ? "+" : "") + r.v?.toFixed(unit === "pct" ? 1 : 0) + (unit === "pct" ? "pp" : "") + " vs last month"; };
  return (
    <div style={{ padding:"24px 32px", display:"flex", flexDirection:"column", gap:24 }}>
      <div>
        <h1 style={{ fontSize:22, fontWeight:700, color:"var(--color-text-primary)", margin:0 }}>Raw Material Cycle</h1>
        <p style={{ fontSize:13, color:"var(--color-text-tertiary)", margin:"4px 0 0" }}>{company.name} &middot; Live data</p>
      </div>
      <div style={{ display:"flex", gap:16, flexWrap:"wrap" }}>
        <KpiCard label="Cost / Ton" value={"₹" + lat.cost_per_ton?.toLocaleString()} sub={fmt("cost_per_ton",true,"num")} good={d("cost_per_ton",true).g} />
        <KpiCard label="Yield %" value={lat.yield_pct?.toFixed(1) + "%"} sub={fmt("yield_pct",false,"pct")} good={d("yield_pct").g} />
        <KpiCard label="Rejection %" value={lat.rejection_pct?.toFixed(1) + "%"} sub={fmt("rejection_pct",true,"pct")} good={d("rejection_pct",true).g} />
        <KpiCard label="Supplier OTD" value={lat.supplier_otd?.toFixed(1) + "%"} sub={fmt("supplier_otd",false,"pct")} good={d("supplier_otd").g} />
      </div>
      <div style={CS}>
        <p style={{ fontSize:14, fontWeight:600, color:"var(--color-text-primary)", margin:"0 0 16px" }}>Cost per Ton Trend</p>
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={monthlyData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis dataKey="month" tick={TK} />
            <YAxis tick={TK} tickFormatter={v => "₹" + v.toLocaleString()} domain={["auto","auto"]} />
            <Tooltip {...TP} formatter={v => ["₹" + v?.toLocaleString(), "Cost/Ton"]} />
            <ReferenceLine y={BM.cost_per_ton} stroke="#ef4444" strokeDasharray="4 4" />
            <Line type="monotone" dataKey="cost_per_ton" stroke="#6366f1" strokeWidth={2} dot={{ fill:"#6366f1", r:4 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div style={{ display:"flex", gap:16, flexWrap:"wrap" }}>
        <div style={{ ...CS, flex:1, minWidth:280 }}>
          <p style={{ fontSize:14, fontWeight:600, color:"var(--color-text-primary)", margin:"0 0 16px" }}>Yield %</p>
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={monthlyData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="month" tick={TK} />
              <YAxis tick={TK} unit="%" domain={[88, 96]} />
              <Tooltip {...TP} formatter={v => [v?.toFixed(1) + "%", "Yield"]} />
              <ReferenceLine y={BM.yield_pct} stroke="#10b981" strokeDasharray="4 4" />
              <Line type="monotone" dataKey="yield_pct" stroke="#10b981" strokeWidth={2} dot={{ fill:"#10b981", r:4 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div style={{ ...CS, flex:1, minWidth:280 }}>
          <p style={{ fontSize:14, fontWeight:600, color:"var(--color-text-primary)", margin:"0 0 16px" }}>Rejection %</p>
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={monthlyData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="month" tick={TK} />
              <YAxis tick={TK} unit="%" domain={[0, 4]} />
              <Tooltip {...TP} formatter={v => [v?.toFixed(1) + "%", "Rejection"]} />
              <ReferenceLine y={BM.rejection_pct} stroke="#f59e0b" strokeDasharray="4 4" />
              <Line type="monotone" dataKey="rejection_pct" stroke="#ef4444" strokeWidth={2} dot={{ fill:"#ef4444", r:4 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
      {supplierData.length > 0 && (
        <div style={CS}>
          <p style={{ fontSize:14, fontWeight:600, color:"var(--color-text-primary)", margin:"0 0 16px" }}>Supplier Mix</p>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={supplierData} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis type="number" tick={TK} unit="%" domain={[0, 60]} />
              <YAxis type="category" dataKey="supplier" tick={TK} width={80} />
              <Tooltip {...TP} formatter={v => [v + "%", "Share"]} />
              <Bar dataKey="share_pct" fill="#6366f1" radius={[0,4,4,0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

/**
 * EbitdaCommandCentre.jsx - Wired to Supabase
 */
import { useState, useEffect, useMemo } from "react";
import { AreaChart, Area, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { supabase } from "../lib/supabaseClient";
import { useCompany } from "../components/CompanyContext";
import { useClaudeInsight } from "../hooks/useClaudeInsight";
import { formatCurrency, formatDelta } from "../utils/formatCurrency";

const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

function useEbitdaData(period) {
  const { company } = useCompany();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  useEffect(() => {
    if (!company?.id) return;
    async function load() {
      setLoading(true); setError(null);
      const { data, error: err } = await supabase.from("ebitda_monthly").select("*")
        .eq("company_id", company.id).order("year",{ascending:true}).order("month",{ascending:true});
      if (err) { setError(err.message); setLoading(false); return; }
      setRows(data || []); setLoading(false);
    }
    load();
  }, [company?.id]);
  const trendData = useMemo(() => {
    const n = period === "3M" ? 3 : period === "6M" ? 6 : rows.length;
    return rows.slice(-n).map(r => ({
      month: MONTHS[r.month - 1] + " '" + String(r.year).slice(2),
      actual: parseFloat(r.ebitda_pct),
      revenue: parseFloat(r.revenue),
      ebitda: parseFloat(r.ebitda),
    }));
  }, [rows, period]);
  return { trendData, loading, error };
}

export default function EbitdaCommandCentre() {
  const { company } = useCompany();
  const [period, setPeriod] = useState("6M");
  const { trendData, loading, error } = useEbitdaData(period);
  const latest = trendData[trendData.length - 1] || null;
  const prev = trendData[trendData.length - 2] || null;
  const kpis = latest ? [
    { label:"Revenue", value:formatCurrency(latest.revenue), delta:prev?formatDelta(latest.revenue-prev.revenue):null, up:prev?latest.revenue>=prev.revenue:true },
    { label:"EBITDA", value:formatCurrency(latest.ebitda), delta:prev?formatDelta(latest.ebitda-prev.ebitda):null, up:prev?latest.ebitda>=prev.ebitda:true },
    { label:"EBITDA %", value:(latest.actual||0).toFixed(1)+"%", delta:prev?((latest.actual||0)-(prev.actual||0)).toFixed(1)+"pp":null, up:prev?(latest.actual||0)>=(prev.actual||0):true },
  ] : [];
  const ip = latest ? `AC Industries. EBITDA: ${(latest.actual||0).toFixed(1)}%. Revenue: ${formatCurrency(latest.revenue)}. Trend: ${trendData.map(d=>(d.actual||0).toFixed(1)+"%").join(", ")}. 2-sentence executive summary.` : null;
  const { insight, loading: il } = useClaudeInsight(ip);
  if (!company) return <div className="p-8 text-gray-400">Loading company...</div>;
  if (loading) return <div className="flex items-center justify-center h-64"><div className="animate-spin rounded-full h-10 w-10 border-b-2 border-indigo-500" /></div>;
  if (error) return <div className="p-8 text-red-400">Error: {error}</div>;
  if (!trendData.length) return <div className="p-8 text-gray-400">No EBITDA data found.</div>;
  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">EBITDA Command Centre</h1>
          <p className="text-gray-400 text-sm mt-1">{company.name} &middot; Live data</p>
        </div>
        <div className="flex gap-2">
          {["3M","6M","ALL"].map(p => (
            <button key={p} onClick={() => setPeriod(p)}
              className={`px-3 py-1 rounded text-sm font-medium ${period===p?"bg-indigo-600 text-white":"bg-gray-800 text-gray-400 hover:bg-gray-700"}`}
            >{p}</button>
          ))}
        </div>
      </div>
      <div className="grid grid-cols-3 gap-4">
        {kpis.map(k => (
          <div key={k.label} className="bg-gray-800 rounded-xl p-4">
            <p className="text-gray-400 text-xs uppercase tracking-wide">{k.label}</p>
            <p className="text-2xl font-bold text-white mt-1">{k.value}</p>
            {k.delta && <p className={`text-xs mt-1 ${k.up?"text-emerald-400":"text-red-400"}`}>{k.up?"▲":"▼"} {k.delta} vs prev</p>}
          </div>
        ))}
      </div>
      <div className="bg-gray-800 rounded-xl p-5">
        <h2 className="text-white font-semibold mb-4">EBITDA % Trend</h2>
        <ResponsiveContainer width="100%" height={220}>
          <AreaChart data={trendData}>
            <defs><linearGradient id="eG" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3}/>
              <stop offset="95%" stopColor="#6366f1" stopOpacity={0}/>
            </linearGradient></defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis dataKey="month" tick={{fill:"#9ca3af",fontSize:11}} />
            <YAxis tick={{fill:"#9ca3af",fontSize:11}} unit="%" domain={[0,30]} />
            <Tooltip contentStyle={{background:"#1f2937",border:"none",borderRadius:8}} formatter={(v)=>[(v||0).toFixed(1)+"%","EBITDA %"]} />
            <Area type="monotone" dataKey="actual" stroke="#6366f1" fill="url(#eG)" strokeWidth={2} dot={{fill:"#6366f1",r:4}} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <div className="bg-gray-800 rounded-xl p-5">
        <h2 className="text-white font-semibold mb-4">Monthly Revenue</h2>
        <ResponsiveContainer width="100%" height={180}>
          <LineChart data={trendData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis dataKey="month" tick={{fill:"#9ca3af",fontSize:11}} />
            <YAxis tick={{fill:"#9ca3af",fontSize:11}} tickFormatter={v=>(v/1e6).toFixed(1)+"M"} />
            <Tooltip contentStyle={{background:"#1f2937",border:"none",borderRadius:8}} formatter={(v)=>[formatCurrency(v),"Revenue"]} />
            <Line type="monotone" dataKey="revenue" stroke="#10b981" strokeWidth={2} dot={{fill:"#10b981",r:4}} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      {ip && (
        <div className="bg-indigo-950 border border-indigo-800 rounded-xl p-4">
          <p className="text-indigo-300 text-xs font-semibold uppercase tracking-wide mb-2">Claude AI Insight</p>
          {il ? <p className="text-gray-400 text-sm animate-pulse">Generating...</p> : <p className="text-gray-200 text-sm leading-relaxed">{insight}</p>}
        </div>
      )}
    </div>
  );
}

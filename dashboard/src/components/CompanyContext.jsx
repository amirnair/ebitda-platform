/**
 * CompanyContext.jsx
 * ─────────────────────────────────────────────────────────────────────────────
 * Provides company config (primary_colour, brand names, SKU master, etc.)
 * to every screen without prop drilling.
 *
 * In production: fetched from GET /api/companies/{company_id} on app boot,
 * cached here. The fallback is the local AC_INDUSTRIES_CONFIG for dev/offline.
 * ─────────────────────────────────────────────────────────────────────────────
 */
import { createContext, useContext, useState, useEffect } from "react";
import AC_INDUSTRIES_CONFIG from "../config/companyConfig";

const CompanyContext = createContext(null);

export function CompanyProvider({ companyId, children }) {
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // TODO Session 7: replace with real fetch once auth is wired
    // const res = await fetch(`/api/companies/${companyId}`);
    // const data = await res.json();
    // setConfig(data);
    setConfig(AC_INDUSTRIES_CONFIG);
    setLoading(false);
  }, [companyId]);

  if (loading) return null;

  return (
    <CompanyContext.Provider value={config}>
      {children}
    </CompanyContext.Provider>
  );
}

export function useCompany() {
  const ctx = useContext(CompanyContext);
  if (!ctx) throw new Error("useCompany must be used inside <CompanyProvider>");
  return ctx;
}

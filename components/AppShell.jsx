/**
 * AppShell.jsx — Fixed with null-safe company references
 */
import { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useCompany } from "./CompanyContext";
import { useAuth } from "./AuthContext";

const NAV_ITEMS = [
  { id: "ebitda-command-centre", path: "/dashboard", label: "EBITDA Command Centre", shortLabel: "Command Centre", icon: IconCommandCentre, audience: "Owner / Finance", phase: 1, built: true },
  { id: "raw-material-cycle", path: "/raw-material-cycle", label: "Raw Material Cycle", shortLabel: "Raw Material", icon: IconRawMaterial, audience: "Procurement", phase: 3, built: true },
  { id: "production-cycle", path: "/production", label: "Production Cycle", shortLabel: "Production", icon: IconProduction, audience: "Production Mgr", phase: 2, built: false },
  { id: "sales-cycle", path: "/sales", label: "Sales Cycle", shortLabel: "Sales", icon: IconSales, audience: "Sales Mgr", phase: 1, built: false },
  { id: "daily-rolling-plan", path: "/daily-plan", label: "Daily Rolling Plan", shortLabel: "Daily Plan", icon: IconDailyPlan, audience: "Production Sup.", phase: 2, built: false },
  { id: "weekly-production-plan", path: "/weekly-plan", label: "Weekly Production Plan", shortLabel: "Weekly Plan", icon: IconWeeklyPlan, audience: "Production Mgr", phase: 2, built: false },
  { id: "model-comparison", path: "/model-comparison", label: "Model Comparison", shortLabel: "Models", icon: IconModels, audience: "Analyst / Owner", phase: 2, built: false },
  { id: "ebitda-simulator", path: "/simulator", label: "EBITDA Simulator", shortLabel: "Simulator", icon: IconSimulator, audience: "Owner / Finance", phase: 1, built: false },
  { id: "strategy-dashboard", path: "/strategy", label: "Strategy Dashboard", shortLabel: "Strategy", icon: IconStrategy, audience: "Senior Mgmt", phase: 2, built: false },
  { id: "settings", path: "/settings", label: "Settings", shortLabel: "Settings", icon: IconSettings, audience: "Admin", phase: 1, built: false, isBottom: true },
];

function SvgIcon({ children, size = 16 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      {children}
    </svg>
  );
}
function IconCommandCentre() { return <SvgIcon><rect x="1" y="1" width="6" height="6" rx="1.5" fill="currentColor" opacity=".9"/><rect x="9" y="1" width="6" height="6" rx="1.5" fill="currentColor" opacity=".5"/><rect x="1" y="9" width="6" height="6" rx="1.5" fill="currentColor" opacity=".5"/><rect x="9" y="9" width="6" height="6" rx="1.5" fill="currentColor" opacity=".3"/></SvgIcon>; }
function IconRawMaterial() { return <SvgIcon><circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.5" fill="none"/><path d="M8 4v4l3 2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></SvgIcon>; }
function IconProduction() { return <SvgIcon><rect x="2" y="10" width="3" height="4" rx="0.5" fill="currentColor" opacity=".9"/><rect x="6.5" y="7" width="3" height="7" rx="0.5" fill="currentColor" opacity=".7"/><rect x="11" y="4" width="3" height="10" rx="0.5" fill="currentColor" opacity=".5"/></SvgIcon>; }
function IconSales() { return <SvgIcon><path d="M2 12L6 7l3 3 5-7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/><circle cx="14" cy="3" r="1.5" fill="currentColor"/></SvgIcon>; }
function IconDailyPlan() { return <SvgIcon><rect x="2" y="3" width="12" height="11" rx="1.5" stroke="currentColor" strokeWidth="1.5" fill="none"/><path d="M5 2v2M11 2v2M2 7h12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/><circle cx="6" cy="10" r="1" fill="currentColor"/><circle cx="10" cy="10" r="1" fill="currentColor" opacity=".5"/></SvgIcon>; }
function IconWeeklyPlan() { return <SvgIcon><rect x="2" y="3" width="12" height="11" rx="1.5" stroke="currentColor" strokeWidth="1.5" fill="none"/><path d="M5 2v2M11 2v2M2 7h12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/><path d="M5 10h6M5 12.5h4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" opacity=".6"/></SvgIcon>; }
function IconModels() { return <SvgIcon><circle cx="4" cy="8" r="2.5" stroke="currentColor" strokeWidth="1.5" fill="none"/><circle cx="12" cy="4" r="2.5" stroke="currentColor" strokeWidth="1.5" fill="none"/><circle cx="12" cy="12" r="2.5" stroke="currentColor" strokeWidth="1.5" fill="none"/><path d="M6.5 7L9.5 4.8M6.5 9L9.5 11.2" stroke="currentColor" strokeWidth="1" opacity=".5"/></SvgIcon>; }
function IconSimulator() { return <SvgIcon><path d="M2 14h12M4 14V9M8 14V5M12 14V2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/><circle cx="8" cy="5" r="1.5" fill="currentColor"/><circle cx="12" cy="2" r="1.5" fill="currentColor" opacity=".5"/></SvgIcon>; }
function IconStrategy() { return <SvgIcon><path d="M2 8h2.5l2-5 3 10 2-7L13.5 8H14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></SvgIcon>; }
function IconSettings() { return <SvgIcon><circle cx="8" cy="8" r="2.5" stroke="currentColor" strokeWidth="1.5" fill="none"/><path d="M8 1.5v1.8M8 12.7v1.8M1.5 8h1.8M12.7 8h1.8M3.7 3.7l1.3 1.3M11 11l1.3 1.3M3.7 12.3l1.3-1.3M11 5l1.3-1.3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/></SvgIcon>; }

function ComingSoonScreen({ item }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: 400, gap: 12, color: "var(--color-text-secondary)" }}>
      <div style={{ opacity: 0.3, transform: "scale(2.5)" }}><item.icon /></div>
      <p style={{ fontSize: 15, fontWeight: 500, marginTop: 24 }}>{item.label}</p>
      <p style={{ fontSize: 13, color: "var(--color-text-tertiary)" }}>
        Session {item.phase + 5} — coming soon{item.phaseNote ? ` · ${item.phaseNote}` : ""}
      </p>
    </div>
  );
}

export default function AppShell({ screens, children }) {
  const navigate = useNavigate();
  const { company } = useCompany();
  const { profile, signOut } = useAuth();
  const location = useLocation();
  const activeId = location.pathname.slice(1) || "ebitda-command-centre";

  // Null-safe fallbacks — prevents crash when company hasn't loaded yet
  const primary = company?.primary_colour ?? '#f59e0b';
  const primaryLight = company?.primary_colour_light ?? '#fef3c7';
  const companyName = company?.company_name ?? company?.name ?? 'EBITDA Platform';
  const companyInitials = companyName.slice(0, 2).toUpperCase();
  const userName = profile?.full_name ?? profile?.email ?? 'User';
  const userInitials = userName.slice(0, 2).toUpperCase();
  const userRole = profile?.role ?? '';

  const mainItems = NAV_ITEMS.filter(n => !n.isBottom);
  const bottomItems = NAV_ITEMS.filter(n => n.isBottom);
  const activeItem = NAV_ITEMS.find(n => n.id === activeId);
  const ActiveScreen = screens?.[activeId];

  return (
    <div style={{ display: "flex", minHeight: "100vh", fontFamily: "'Syne', var(--font-sans), sans-serif", background: "var(--color-background-tertiary)" }}>
      {/* Sidebar */}
      <aside style={{ width: 232, flexShrink: 0, background: "var(--color-background-primary)", borderRight: "0.5px solid var(--color-border-tertiary)", display: "flex", flexDirection: "column", position: "sticky", top: 0, height: "100vh", overflowY: "auto" }}>
        {/* Logo */}
        <div style={{ padding: "20px 16px 16px", borderBottom: "0.5px solid var(--color-border-tertiary)", display: "flex", alignItems: "center", gap: 10 }}>
          {company?.logo_url ? (
            <img src={company.logo_url} alt={companyName} style={{ width: 32, height: 32, borderRadius: 6, objectFit: "contain" }} />
          ) : (
            <div style={{ width: 32, height: 32, borderRadius: 6, background: primary, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, fontWeight: 700, color: "#fff", letterSpacing: "0.05em", flexShrink: 0 }}>
              {companyInitials}
            </div>
          )}
          <div style={{ minWidth: 0 }}>
            <p style={{ fontSize: 13, fontWeight: 600, color: "var(--color-text-primary)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", margin: 0 }}>
              {companyName}
            </p>
            <p style={{ fontSize: 11, color: "var(--color-text-tertiary)", margin: 0, letterSpacing: "0.04em" }}>EBITDA Platform</p>
          </div>
        </div>

        {/* Nav label */}
        <div style={{ padding: "12px 16px 4px" }}>
          <p style={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.1em", textTransform: "uppercase", color: "var(--color-text-tertiary)", margin: 0 }}>Dashboards</p>
        </div>

        {/* Main nav */}
        <nav style={{ flex: 1, padding: "0 8px" }}>
          {mainItems.map(item => (
            <NavItem key={item.id} item={item} active={activeId === item.id} primary={primary} primaryLight={primaryLight} onClick={() => navigate(item.path)} />
          ))}
        </nav>

        {/* Bottom nav */}
        <div style={{ padding: "8px 8px 16px", borderTop: "0.5px solid var(--color-border-tertiary)" }}>
          {bottomItems.map(item => (
            <NavItem key={item.id} item={item} active={activeId === item.id} primary={primary} primaryLight={primaryLight} onClick={() => navigate(item.path)} />
          ))}
        </div>

        {/* User identity */}
        <div style={{ padding: "12px 16px", borderTop: "0.5px solid var(--color-border-tertiary)", display: "flex", alignItems: "center", gap: 8 }}>
          <div style={{ width: 26, height: 26, borderRadius: "50%", background: "var(--color-background-secondary)", border: "0.5px solid var(--color-border-secondary)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 10, fontWeight: 600, color: "var(--color-text-secondary)", flexShrink: 0 }}>
            {userInitials}
          </div>
          <div style={{ minWidth: 0, flex: 1 }}>
            <p style={{ fontSize: 12, fontWeight: 500, color: "var(--color-text-primary)", margin: 0, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{userName}</p>
            <p style={{ fontSize: 10, color: "var(--color-text-tertiary)", margin: 0, textTransform: "capitalize" }}>{userRole}</p>
          </div>
          {signOut && (
            <button onClick={signOut} title="Sign out" style={{ background: "none", border: "none", cursor: "pointer", color: "var(--color-text-tertiary)", fontSize: 16, padding: 2 }}>⏻</button>
          )}
        </div>
      </aside>

      {/* Main content */}
      <main style={{ flex: 1, overflowY: "auto", padding: "28px 32px" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 24 }}>
          <div>
            <h1 style={{ fontSize: 20, fontWeight: 600, color: "var(--color-text-primary)", margin: 0 }}>{activeItem?.label}</h1>
            <p style={{ fontSize: 12, color: "var(--color-text-tertiary)", margin: "2px 0 0", letterSpacing: "0.04em" }}>{activeItem?.audience}</p>
          </div>
          <div style={{ fontSize: 12, color: "var(--color-text-tertiary)", fontFamily: "'DM Mono', monospace" }}>
            {new Date().toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}
          </div>
        </div>

        {children ?? (ActiveScreen ? <ActiveScreen /> : <ComingSoonScreen item={activeItem} />)}
      </main>
    </div>
  );
}

function NavItem({ item, active, primary, primaryLight, onClick }) {
  return (
    <button onClick={onClick} style={{ display: "flex", alignItems: "center", gap: 10, width: "100%", padding: "7px 10px", borderRadius: 7, border: "none", cursor: "pointer", textAlign: "left", background: active ? primaryLight : "transparent", color: active ? primary : "var(--color-text-secondary)", marginBottom: 1, transition: "background 0.12s, color 0.12s" }}
      onMouseEnter={e => { if (!active) { e.currentTarget.style.background = "var(--color-background-secondary)"; e.currentTarget.style.color = "var(--color-text-primary)"; } }}
      onMouseLeave={e => { if (!active) { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "var(--color-text-secondary)"; } }}
      aria-current={active ? "page" : undefined}
    >
      <span style={{ flexShrink: 0, color: active ? primary : "currentColor", opacity: active ? 1 : 0.7 }}><item.icon /></span>
      <span style={{ fontSize: 13, fontWeight: active ? 600 : 400, flex: 1, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{item.shortLabel}</span>
      {item.phaseNote && (
        <span style={{ fontSize: 9, fontWeight: 600, padding: "2px 5px", borderRadius: 4, background: "#FAEEDA", color: "#854F0B", letterSpacing: "0.04em", flexShrink: 0 }}>{item.phaseNote}</span>
      )}
      {active && <span style={{ width: 4, height: 4, borderRadius: "50%", background: primary, flexShrink: 0 }} />}
    </button>
  );
}

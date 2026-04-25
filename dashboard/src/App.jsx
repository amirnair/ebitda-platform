/**
 * App.jsx
 * ─────────────────────────────────────────────────────────────────────────────
 * Root component for the EBITDA Intelligence Platform.
 *
 * Pattern:
 *   CompanyProvider  → loads company config (multi-tenant)
 *   AppShell         → sidebar nav + page header + content area
 *   screens map      → { screen_id: ScreenComponent } passed to AppShell
 *
 * Adding a new screen in a future session:
 *   1. Build the screen in src/screens/
 *   2. Import it here
 *   3. Add its id to the screens map
 *   AppShell handles the rest — no nav changes needed.
 * ─────────────────────────────────────────────────────────────────────────────
 */
import { CompanyProvider } from "./components/CompanyContext";
import AppShell from "./components/AppShell";
import EbitdaCommandCentre from "./screens/EbitdaCommandCentre";

// Screens registry
// key = nav item id from AppShell NAV_ITEMS
// value = React component (no required props — reads from CompanyContext)
const SCREENS = {
  "ebitda-command-centre": EbitdaCommandCentre,
  // Session 6+: add screens here as they are built
  // "production-cycle":      ProductionCycle,
  // "sales-cycle":           SalesCycle,
  // "daily-rolling-plan":    DailyRollingPlan,
  // "weekly-production-plan": WeeklyProductionPlan,
  // "model-comparison":      ModelComparison,
  // "ebitda-simulator":      EbitdaSimulator,
  // "strategy-dashboard":    StrategyDashboard,
  // "settings":              Settings,
};

export default function App() {
  // company_id will come from Supabase Auth in Session 7
  // For now, "AC001" is the pilot client
  const companyId = "AC001";

  return (
    <CompanyProvider companyId={companyId}>
      <AppShell screens={SCREENS} />
    </CompanyProvider>
  );
}

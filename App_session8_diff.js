// ─── Session 8 additions to App.jsx ─────────────────────────────────────────
// Add these 4 imports at the top of App.jsx alongside existing screen imports:

import WeeklyProductionPlan from "./screens/WeeklyProductionPlan";
import ModelComparison      from "./screens/ModelComparison";
import EbitdaSimulator      from "./screens/EbitdaSimulator";
import StrategyDashboard    from "./screens/StrategyDashboard";

// ─── Updated SCREENS map (replace ComingSoonScreen stubs for 6, 7, 8, 9) ────
// In your existing SCREENS object, replace the 4 pending entries:

const SCREENS = {
  "ebitda-command-centre":  EbitdaCommandCentre,   // Screen 1 — Session 6 ✓
  "raw-material-cycle":     ComingSoonScreen,        // Screen 2 — Phase 3 deferred
  "production-cycle":       ProductionCycle,         // Screen 3 — Session 7 ✓
  "sales-cycle":            SalesCycle,              // Screen 4 — Session 7 ✓
  "daily-rolling-plan":     DailyRollingPlan,        // Screen 5 — Session 7 ✓
  "weekly-production-plan": WeeklyProductionPlan,    // Screen 6 — Session 8 ✓  ← NEW
  "model-comparison":       ModelComparison,         // Screen 7 — Session 8 ✓  ← NEW
  "ebitda-simulator":       EbitdaSimulator,         // Screen 8 — Session 8 ✓  ← NEW
  "strategy-dashboard":     StrategyDashboard,       // Screen 9 — Session 8 ✓  ← NEW
  "settings":               ComingSoonScreen,         // Screen 10 — Session 10 pending
};

// No other changes required. Nav is already wired in AppShell.jsx from Session 6.

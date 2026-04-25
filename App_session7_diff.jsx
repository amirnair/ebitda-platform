// ─── App.jsx — Session 7 update ───────────────────────────────────────────────
// Add these imports alongside the existing EbitdaCommandCentre import:
//
//   import ProductionCycle   from "./screens/ProductionCycle";
//   import SalesCycle        from "./screens/SalesCycle";
//   import DailyRollingPlan  from "./screens/DailyRollingPlan";
//
// Then update the SCREENS map.  Only the changed entries are shown below.
// All other entries (Raw Material, Weekly Plan, etc.) remain as ComingSoonScreen stubs.

const SCREENS = {
  // ── Existing ──────────────────────────────────────────
  "ebitda-command-centre": {
    label: "EBITDA Command Centre",
    icon: "◈",
    component: EbitdaCommandCentre,
  },
  "raw-material-cycle": {
    label: "Raw Material Cycle",
    icon: "⬡",
    component: ComingSoonScreen,  // Phase 3 — unchanged
  },

  // ── Session 7: NEW ────────────────────────────────────
  "production-cycle": {
    label: "Production Cycle",
    icon: "⚙",
    component: ProductionCycle,
  },
  "sales-cycle": {
    label: "Sales Cycle",
    icon: "↗",
    component: SalesCycle,
  },
  "daily-rolling-plan": {
    label: "Daily Rolling Plan",
    icon: "▦",
    component: DailyRollingPlan,
  },

  // ── Pending ───────────────────────────────────────────
  "weekly-production-plan": {
    label: "Weekly Production Plan",
    icon: "⊞",
    component: ComingSoonScreen,
  },
  "model-comparison": {
    label: "Model Comparison",
    icon: "⊕",
    component: ComingSoonScreen,
  },
  "ebitda-simulator": {
    label: "EBITDA Simulator",
    icon: "⊘",
    component: ComingSoonScreen,
  },
  "strategy-dashboard": {
    label: "Strategy Dashboard",
    icon: "◎",
    component: ComingSoonScreen,
  },
  "settings": {
    label: "Settings",
    icon: "⚙",
    component: ComingSoonScreen,
  },
};

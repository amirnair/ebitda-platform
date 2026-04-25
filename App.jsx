// src/App.jsx — Session 9 diff
// Changes from Session 8:
//   1. Wrap entire app in <AuthProvider>
//   2. Add /login route → <LoginScreen>
//   3. Wrap all screen routes in <ProtectedRoute screenKey="...">
//   4. Wire Screen 10 — Settings (no longer ComingSoonScreen)
//   5. Add <UserChip> to AppShell header (sign out button)
//   6. Root / redirects to role-appropriate default screen

import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './components/AuthContext'
import ProtectedRoute from './components/ProtectedRoute'
import AppShell from './components/AppShell'
import LoginScreen from './screens/LoginScreen'
import { defaultScreen } from './config/rolePermissions'

// Existing screens (Sessions 6–8) — unchanged imports
import EbitdaCommandCentre    from './screens/EbitdaCommandCentre'
import ProductionCycle        from './screens/ProductionCycle'
import SalesCycle             from './screens/SalesCycle'
import DailyRollingPlan       from './screens/DailyRollingPlan'
import WeeklyProductionPlan   from './screens/WeeklyProductionPlan'
import ModelComparison        from './screens/ModelComparison'
import EbitdaSimulator        from './screens/EbitdaSimulator'
import StrategyDashboard      from './screens/StrategyDashboard'

// Session 9 — new screen
import Settings               from './screens/Settings'

// Placeholder for deferred Screen 2
function ComingSoonScreen({ label }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      height: '100%', color: '#8899AA', fontFamily: 'DM Mono, monospace',
      flexDirection: 'column', gap: '0.5rem',
    }}>
      <div style={{ fontSize: '2rem' }}>🚧</div>
      <div>{label} — Coming in Phase 3</div>
    </div>
  )
}

// Screen map — used by AppShell for nav + by Routes below
export const SCREENS = {
  'ebitda':       { label: 'EBITDA Command Centre',   icon: '◈',  component: EbitdaCommandCentre,  screenKey: 'ebitda' },
  'raw-material': { label: 'Raw Material Cycle',       icon: '⬡',  component: () => <ComingSoonScreen label="Raw Material Cycle" />, screenKey: 'raw-material' },
  'production':   { label: 'Production Cycle',         icon: '⚙',  component: ProductionCycle,      screenKey: 'production' },
  'sales':        { label: 'Sales Cycle',              icon: '📈', component: SalesCycle,           screenKey: 'sales' },
  'daily-plan':   { label: 'Daily Rolling Plan',       icon: '📋', component: DailyRollingPlan,     screenKey: 'daily-plan' },
  'weekly-plan':  { label: 'Weekly Production Plan',   icon: '🗓', component: WeeklyProductionPlan, screenKey: 'weekly-plan' },
  'models':       { label: 'Model Comparison',         icon: '🧮', component: ModelComparison,      screenKey: 'models' },
  'simulator':    { label: 'EBITDA Simulator',         icon: '⚡', component: EbitdaSimulator,      screenKey: 'simulator' },
  'strategy':     { label: 'Strategy Dashboard',       icon: '🎯', component: StrategyDashboard,    screenKey: 'strategy' },
  'settings':     { label: 'Settings',                 icon: '⚙',  component: Settings,             screenKey: 'settings' },
}

// ── Root redirect — sends user to their default screen ────────────────────────
function RootRedirect() {
  const { user, role, loading } = useAuth()
  if (loading) return null
  if (!user)   return <Navigate to="/login" replace />
  return <Navigate to={'/' + defaultScreen(role)} replace />
}

// ── Authenticated layout — AppShell wraps all protected screens ───────────────
function AuthenticatedLayout() {
  return (
    <AppShell screens={SCREENS}>
      <Routes>
        {Object.entries(SCREENS).map(([path, screen]) => (
          <Route
            key={path}
            path={path}
            element={
              <ProtectedRoute screenKey={screen.screenKey}>
                <screen.component />
              </ProtectedRoute>
            }
          />
        ))}
      </Routes>
    </AppShell>
  )
}

// ── App root ──────────────────────────────────────────────────────────────────
export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* Public routes */}
          <Route path="/login" element={<LoginScreen />} />

          {/* Root redirect */}
          <Route path="/" element={<RootRedirect />} />

          {/* All dashboard routes inside AppShell */}
          <Route path="/*" element={<AuthenticatedLayout />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}

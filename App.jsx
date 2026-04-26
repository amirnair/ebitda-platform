// src/App.jsx
import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';

import { AuthProvider, useAuth } from './components/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import AppShell from './components/AppShell';
import LoginScreen from './screens/LoginScreen';

// Dashboard screens
import EbitdaCommandCentre from './screens/EbitdaCommandCentre';
import ProductionCycle from './screens/ProductionCycle';
import SalesCycle from './screens/SalesCycle';
import DailyRollingPlan from './screens/DailyRollingPlan';
import WeeklyProductionPlan from './screens/WeeklyProductionPlan';
import ModelComparison from './screens/ModelComparison';
import EbitdaSimulator from './screens/EbitdaSimulator';
import StrategyDashboard from './screens/StrategyDashboard';
import Settings from './screens/Settings';
import RawMaterialCycle from './screens/RawMaterialCycle';

import { defaultScreen } from './config/rolePermissions';

// ---------------------------------------------------------------------------
// Root redirect — sends authenticated users to their role's default screen
// ---------------------------------------------------------------------------
function RootRedirect() {
  const { user, role, loading } = useAuth();

  if (loading) {
    // Render a minimal loader while session initialises — never return null
    return (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100vh',
        background: '#0f1117',
        color: '#e2e8f0',
        fontFamily: 'DM Mono, monospace',
        fontSize: '14px',
      }}>
        Initialising…
      </div>
    );
  }

  if (!user) return <Navigate to="/login" replace />;

  const target = role ? defaultScreen(role) : '/dashboard';
  return <Navigate to={target} replace />;
}

// ---------------------------------------------------------------------------
// Authenticated layout wrapper
// ---------------------------------------------------------------------------
function AuthenticatedLayout({ screenKey, children }) {
  return (
    <ProtectedRoute screenKey={screenKey}>
      <AppShell>
        {children}
      </AppShell>
    </ProtectedRoute>
  );
}

// ---------------------------------------------------------------------------
// App — router + auth provider
// ---------------------------------------------------------------------------
export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public */}
          <Route path="/login" element={<LoginScreen />} />

          {/* Root → role-aware redirect */}
          <Route path="/" element={<RootRedirect />} />

          {/* Dashboard screens */}
          <Route
            path="/dashboard"
            element={
              <AuthenticatedLayout screenKey="ebitda_command_centre">
                <EbitdaCommandCentre />
              </AuthenticatedLayout>
            }
          />
          <Route
            path="/production"
            element={
              <AuthenticatedLayout screenKey="production_cycle">
                <ProductionCycle />
              </AuthenticatedLayout>
            }
          />
          <Route
          path="/raw-material-cycle"
          element={
            <AuthenticatedLayout screenKey="raw-material-cycle">
              <RawMaterialCycle />
            </AuthenticatedLayout>
          }
        />
          <Route
            path="/sales"
            element={
              <AuthenticatedLayout screenKey="sales_cycle">
                <SalesCycle />
              </AuthenticatedLayout>
            }
          />
          <Route
            path="/daily-plan"
            element={
              <AuthenticatedLayout screenKey="daily_rolling_plan">
                <DailyRollingPlan />
              </AuthenticatedLayout>
            }
          />
          <Route
            path="/weekly-plan"
            element={
              <AuthenticatedLayout screenKey="weekly_production_plan">
                <WeeklyProductionPlan />
              </AuthenticatedLayout>
            }
          />
          <Route
            path="/model-comparison"
            element={
              <AuthenticatedLayout screenKey="model_comparison">
                <ModelComparison />
              </AuthenticatedLayout>
            }
          />
          <Route
            path="/simulator"
            element={
              <AuthenticatedLayout screenKey="ebitda_simulator">
                <EbitdaSimulator />
              </AuthenticatedLayout>
            }
          />
          <Route
            path="/strategy"
            element={
              <AuthenticatedLayout screenKey="strategy_dashboard">
                <StrategyDashboard />
              </AuthenticatedLayout>
            }
          />
          <Route
            path="/settings"
            element={
              <AuthenticatedLayout screenKey="settings">
                <Settings />
              </AuthenticatedLayout>
            }
          />

          {/* Catch-all → root */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

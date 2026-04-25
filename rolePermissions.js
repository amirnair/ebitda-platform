// src/config/rolePermissions.js
// Central definition of which screens each role can access.
// Screen keys must match the keys in App.jsx SCREENS map.

export const ROLES = {
  OWNER:      'owner',
  FINANCE:    'finance',
  PRODUCTION: 'production',
  SALES:      'sales',
  ADMIN:      'admin',
  VIEWER:     'viewer',
}

// Screens each role is ALLOWED to access.
// If a role is not listed here, it defaults to viewer (read-only stub).
export const ROLE_PERMISSIONS = {
  owner: [
    'ebitda',        // Screen 1 — EBITDA Command Centre
    // Screen 2 — Raw Material (deferred, stub)
    'production',    // Screen 3 — Production Cycle
    'sales',         // Screen 4 — Sales Cycle
    'daily-plan',    // Screen 5 — Daily Rolling Plan
    'weekly-plan',   // Screen 6 — Weekly Production Plan
    'models',        // Screen 7 — Model Comparison
    'simulator',     // Screen 8 — EBITDA Simulator
    'strategy',      // Screen 9 — Strategy Dashboard
    'settings',      // Screen 10 — Settings
  ],
  admin: [
    'ebitda',
    'production',
    'sales',
    'daily-plan',
    'weekly-plan',
    'models',
    'simulator',
    'strategy',
    'settings',      // Admins can manage users
  ],
  finance: [
    'ebitda',
    'simulator',
    'strategy',
    'models',
  ],
  production: [
    'production',
    'daily-plan',
    'weekly-plan',
  ],
  sales: [
    'sales',
    'ebitda',        // Read-only summary
  ],
  viewer: [
    'ebitda',        // Read-only summary only
  ],
}

/**
 * Returns true if the given role can access the given screen key.
 */
export function canAccess(role, screenKey) {
  const allowed = ROLE_PERMISSIONS[role] ?? ROLE_PERMISSIONS['viewer']
  return allowed.includes(screenKey)
}

/**
 * Returns the default landing screen key for a given role.
 */
export function defaultScreen(role) {
  const map = {
    owner:      'ebitda',
    admin:      'ebitda',
    finance:    'ebitda',
    production: 'daily-plan',
    sales:      'sales',
    viewer:     'ebitda',
  }
  return map[role] ?? 'ebitda'
}

/**
 * Human-readable role labels for display in Settings > User Management.
 */
export const ROLE_LABELS = {
  owner:      'Owner',
  admin:      'Admin',
  finance:    'Finance',
  production: 'Production',
  sales:      'Sales',
  viewer:     'Viewer',
}

/**
 * Role badge colours (Tailwind-compatible inline style values).
 * Matches the platform's dark/steel aesthetic.
 */
export const ROLE_COLOURS = {
  owner:      { bg: '#1E3A5F', text: '#E8B84B' },
  admin:      { bg: '#2D2D2D', text: '#FFFFFF' },
  finance:    { bg: '#1A472A', text: '#90EE90' },
  production: { bg: '#4A1942', text: '#DDA0DD' },
  sales:      { bg: '#7B3F00', text: '#FFD580' },
  viewer:     { bg: '#3A3A3A', text: '#AAAAAA' },
}

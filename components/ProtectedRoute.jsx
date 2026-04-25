// src/components/ProtectedRoute.jsx
import { Navigate } from 'react-router-dom'
import { useAuth } from './AuthContext'
import { canAccess } from '../config/rolePermissions'

export default function ProtectedRoute({ children, screenKey }) {
  const { user, role, loading } = useAuth()

  // Still loading AND no user yet — show spinner briefly
  if (loading && !user) {
    return (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100vh',
        background: '#0D1B2A',
        color: '#E8B84B',
        fontFamily: 'DM Mono, monospace',
        fontSize: '0.85rem',
        letterSpacing: '0.1em',
      }}>
        AUTHENTICATING...
      </div>
    )
  }

  // Not logged in → send to login
  if (!user) {
    return <Navigate to="/login" replace />
  }

  // Logged in but role not loaded yet — allow through (profile loads in background)
  if (screenKey && role && !canAccess(role, screenKey)) {
    return <AccessDenied screenKey={screenKey} role={role} />
  }

  return children
}

// ── Access Denied screen ──────────────────────────────────────────────────
function AccessDenied({ screenKey, role }) {
  return (
    <div style={{
      display:        'flex',
      flexDirection:  'column',
      alignItems:     'center',
      justifyContent: 'center',
      height:         '100%',
      gap:            '1rem',
      color:          '#8899AA',
      fontFamily:     'DM Mono, monospace',
    }}>
      <div style={{ fontSize: '2.5rem' }}>🔒</div>
      <div style={{ fontSize: '1rem', color: '#FFFFFF', fontWeight: 600 }}>
        Access Restricted
      </div>
      <div style={{ fontSize: '0.8rem', textAlign: 'center', maxWidth: 320 }}>
        Your role (<strong style={{ color: '#E8B84B' }}>{role}</strong>) does not
        have access to this screen.
        Contact your platform admin to request access.
      </div>
    </div>
  )
}

// src/screens/LoginScreen.jsx
// Multi-tenant login page.
// Uses Supabase email+password auth.
// On success → AuthContext loads profile + company → redirects to default screen.

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { supabase } from '../lib/supabaseClient'
import { defaultScreen } from '../config/rolePermissions'
import { useAuth } from '../components/AuthContext'

export default function LoginScreen() {
  const navigate = useNavigate()
  const { role }  = useAuth()

  const [email,    setEmail]    = useState('')
  const [password, setPassword] = useState('')
  const [loading,  setLoading]  = useState(false)
  const [error,    setError]    = useState(null)

  async function handleLogin(e) {
    e.preventDefault()
    setLoading(true)
    setError(null)

    const { error } = await supabase.auth.signInWithPassword({ email, password })

    if (error) {
      setError(error.message)
      setLoading(false)
      return
    }

    // AuthContext will pick up the new session via onAuthStateChange.
    // Navigate to the role's default screen.
    navigate('/' + defaultScreen(role), { replace: true })
    setLoading(false)
  }

  return (
    <div style={styles.page}>
      {/* Background grid texture */}
      <div style={styles.gridOverlay} />

      {/* Card */}
      <div style={styles.card}>
        {/* Logo / wordmark */}
        <div style={styles.logoArea}>
          <div style={styles.logoMark}>◈</div>
          <div>
            <div style={styles.productName}>EBITDA Intelligence</div>
            <div style={styles.tagline}>Steel Manufacturing Platform</div>
          </div>
        </div>

        <div style={styles.divider} />

        <h1 style={styles.heading}>Sign in</h1>
        <p style={styles.subheading}>
          Enter your credentials to access your dashboard.
        </p>

        <form onSubmit={handleLogin} style={styles.form}>
          <div style={styles.fieldGroup}>
            <label style={styles.label}>Email address</label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="you@company.com"
              required
              style={styles.input}
              onFocus={e  => Object.assign(e.target.style, styles.inputFocus)}
              onBlur={e   => Object.assign(e.target.style, styles.input)}
            />
          </div>

          <div style={styles.fieldGroup}>
            <label style={styles.label}>Password</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              style={styles.input}
              onFocus={e => Object.assign(e.target.style, styles.inputFocus)}
              onBlur={e  => Object.assign(e.target.style, styles.input)}
            />
          </div>

          {error && (
            <div style={styles.errorBox}>
              ⚠ {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            style={loading ? { ...styles.button, ...styles.buttonDisabled } : styles.button}
          >
            {loading ? 'SIGNING IN...' : 'SIGN IN'}
          </button>
        </form>

        <p style={styles.footerNote}>
          Don't have an account? Contact your platform administrator.
        </p>
      </div>

      {/* Version stamp */}
      <div style={styles.versionStamp}>v1.7 — Session 9</div>
    </div>
  )
}

// ── Styles ────────────────────────────────────────────────────────────────────
const C = {
  bg:       '#0D1B2A',
  surface:  '#111F30',
  border:   '#1E3A5F',
  gold:     '#E8B84B',
  text:     '#FFFFFF',
  muted:    '#8899AA',
  error:    '#FF6B6B',
  inputBg:  '#0A1520',
}

const styles = {
  page: {
    minHeight:       '100vh',
    background:      C.bg,
    display:         'flex',
    alignItems:      'center',
    justifyContent:  'center',
    fontFamily:      "'DM Mono', monospace",
    position:        'relative',
    overflow:        'hidden',
  },
  gridOverlay: {
    position:   'absolute',
    inset:      0,
    background: `
      linear-gradient(rgba(30,58,95,0.15) 1px, transparent 1px),
      linear-gradient(90deg, rgba(30,58,95,0.15) 1px, transparent 1px)
    `,
    backgroundSize: '40px 40px',
    pointerEvents:  'none',
  },
  card: {
    position:     'relative',
    zIndex:       1,
    width:        '100%',
    maxWidth:     420,
    background:   C.surface,
    border:       `1px solid ${C.border}`,
    borderRadius: 12,
    padding:      '2.5rem 2rem',
    boxShadow:    `0 0 60px rgba(30,58,95,0.4), 0 0 0 1px rgba(232,184,75,0.08)`,
  },
  logoArea: {
    display:    'flex',
    alignItems: 'center',
    gap:        '0.75rem',
    marginBottom: '1.5rem',
  },
  logoMark: {
    fontSize:   '2rem',
    color:      C.gold,
    lineHeight: 1,
  },
  productName: {
    fontSize:   '0.95rem',
    fontWeight: 700,
    color:      C.text,
    letterSpacing: '0.05em',
  },
  tagline: {
    fontSize:   '0.7rem',
    color:      C.muted,
    letterSpacing: '0.08em',
    marginTop:  2,
  },
  divider: {
    height:       1,
    background:   C.border,
    marginBottom: '1.5rem',
  },
  heading: {
    margin:     '0 0 0.25rem',
    fontSize:   '1.4rem',
    fontWeight: 700,
    color:      C.text,
    letterSpacing: '-0.01em',
  },
  subheading: {
    margin:       '0 0 1.75rem',
    fontSize:     '0.78rem',
    color:        C.muted,
    lineHeight:   1.6,
  },
  form: {
    display:       'flex',
    flexDirection: 'column',
    gap:           '1rem',
  },
  fieldGroup: {
    display:       'flex',
    flexDirection: 'column',
    gap:           '0.35rem',
  },
  label: {
    fontSize:      '0.72rem',
    color:         C.muted,
    letterSpacing: '0.08em',
    textTransform: 'uppercase',
  },
  input: {
    background:   C.inputBg,
    border:       `1px solid ${C.border}`,
    borderRadius: 6,
    padding:      '0.65rem 0.85rem',
    color:        C.text,
    fontSize:     '0.85rem',
    fontFamily:   "'DM Mono', monospace",
    outline:      'none',
    transition:   'border-color 0.15s',
    width:        '100%',
    boxSizing:    'border-box',
  },
  inputFocus: {
    background:   C.inputBg,
    border:       `1px solid ${C.gold}`,
    borderRadius: 6,
    padding:      '0.65rem 0.85rem',
    color:        C.text,
    fontSize:     '0.85rem',
    fontFamily:   "'DM Mono', monospace",
    outline:      'none',
    width:        '100%',
    boxSizing:    'border-box',
  },
  errorBox: {
    background:   'rgba(255,107,107,0.1)',
    border:       '1px solid rgba(255,107,107,0.3)',
    borderRadius: 6,
    padding:      '0.6rem 0.85rem',
    color:        C.error,
    fontSize:     '0.78rem',
  },
  button: {
    background:    C.gold,
    color:         '#0D1B2A',
    border:        'none',
    borderRadius:  6,
    padding:       '0.75rem',
    fontSize:      '0.8rem',
    fontFamily:    "'DM Mono', monospace",
    fontWeight:    700,
    letterSpacing: '0.1em',
    cursor:        'pointer',
    marginTop:     '0.5rem',
    transition:    'opacity 0.15s',
  },
  buttonDisabled: {
    opacity: 0.5,
    cursor:  'not-allowed',
  },
  footerNote: {
    marginTop:  '1.25rem',
    fontSize:   '0.73rem',
    color:      C.muted,
    textAlign:  'center',
    lineHeight: 1.6,
  },
  versionStamp: {
    position:   'fixed',
    bottom:     12,
    right:      16,
    fontSize:   '0.65rem',
    color:      'rgba(136,153,170,0.4)',
    fontFamily: "'DM Mono', monospace",
    letterSpacing: '0.06em',
  },
}

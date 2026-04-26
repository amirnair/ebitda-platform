// src/screens/LoginScreen.jsx
import { useState } from 'react'
import { supabase } from '../lib/supabaseClient'

export default function LoginScreen() {
  const [email,    setEmail]    = useState('')
  const [password, setPassword] = useState('')
  const [loading,  setLoading]  = useState(false)
  const [error,    setError]    = useState(null)

  async function handleLogin(e) {
    e.preventDefault()
    setLoading(true)
    setError(null)

    const { data, error } = await supabase.auth.signInWithPassword({ email, password })

    if (error) {
      setError(error.message)
      setLoading(false)
      return
    }

    // Force a full page navigation to dashboard — bypasses React Router/AuthContext timing issues
    window.location.href = '/dashboard'
  }

  return (
    <div style={{
      minHeight: '100vh',
      background: '#0f1117',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      fontFamily: 'DM Mono, monospace',
      padding: '1rem',
    }}>
      <div style={{
        background: '#1a1d2e',
        border: '1px solid #2d3148',
        borderRadius: '12px',
        padding: '2.5rem',
        width: '100%',
        maxWidth: '420px',
      }}>
        <div style={{ marginBottom: '2rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.5rem' }}>
            <div style={{
              width: '32px', height: '32px',
              background: 'linear-gradient(135deg, #f59e0b, #d97706)',
              borderRadius: '8px',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: '16px',
            }}>◆</div>
            <span style={{ color: '#f1f5f9', fontSize: '1.1rem', fontWeight: 600 }}>
              EBITDA Intelligence
            </span>
          </div>
          <div style={{ color: '#64748b', fontSize: '0.8rem' }}>Steel Manufacturing Platform</div>
        </div>

        <div style={{ borderTop: '1px solid #2d3148', marginBottom: '1.5rem' }} />

        <h2 style={{ color: '#f1f5f9', fontSize: '1.5rem', fontWeight: 600, margin: '0 0 0.5rem' }}>
          Sign in
        </h2>
        <p style={{ color: '#94a3b8', fontSize: '0.85rem', margin: '0 0 1.5rem' }}>
          Enter your credentials to access your dashboard.
        </p>

        {error && (
          <div style={{
            background: '#2d1b1b', border: '1px solid #7f1d1d',
            borderRadius: '6px', padding: '0.75rem',
            color: '#fca5a5', fontSize: '0.8rem', marginBottom: '1rem',
          }}>
            {error}
          </div>
        )}

        <form onSubmit={handleLogin}>
          <div style={{ marginBottom: '1rem' }}>
            <label style={{ color: '#94a3b8', fontSize: '0.75rem', letterSpacing: '0.05em', display: 'block', marginBottom: '0.5rem' }}>
              EMAIL ADDRESS
            </label>
            <input
              type="email" value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="you@company.com" required
              style={{
                width: '100%', background: '#0f1117',
                border: '1px solid #2d3148', borderRadius: '6px',
                padding: '0.75rem', color: '#f1f5f9',
                fontSize: '0.9rem', fontFamily: 'inherit',
                boxSizing: 'border-box', outline: 'none',
              }}
            />
          </div>

          <div style={{ marginBottom: '1.5rem' }}>
            <label style={{ color: '#94a3b8', fontSize: '0.75rem', letterSpacing: '0.05em', display: 'block', marginBottom: '0.5rem' }}>
              PASSWORD
            </label>
            <input
              type="password" value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="••••••••" required
              style={{
                width: '100%', background: '#0f1117',
                border: '1px solid #2d3148', borderRadius: '6px',
                padding: '0.75rem', color: '#f1f5f9',
                fontSize: '0.9rem', fontFamily: 'inherit',
                boxSizing: 'border-box', outline: 'none',
              }}
            />
          </div>

          <button
            type="submit" disabled={loading}
            style={{
              width: '100%',
              background: loading ? '#92400e' : '#f59e0b',
              color: '#0f1117', border: 'none', borderRadius: '6px',
              padding: '0.85rem', fontSize: '0.85rem', fontWeight: 700,
              letterSpacing: '0.08em',
              cursor: loading ? 'not-allowed' : 'pointer',
              fontFamily: 'inherit',
            }}
          >
            {loading ? 'SIGNING IN...' : 'SIGN IN'}
          </button>
        </form>

        <p style={{ color: '#475569', fontSize: '0.75rem', textAlign: 'center', marginTop: '1.5rem' }}>
          Don't have an account? Contact your platform administrator.
        </p>
      </div>
    </div>
  )
}

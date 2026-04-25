// src/components/AuthContext.jsx
// Replaces the mock CompanyContext.jsx from Session 6.
// Provides: { user, profile, company, role, loading, signOut }
// to the whole app via useAuth() hook.

import { createContext, useContext, useEffect, useState } from 'react'
import { supabase } from '../lib/supabaseClient'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [session, setSession]   = useState(null)   // Supabase session
  const [profile, setProfile]   = useState(null)   // profiles row
  const [company, setCompany]   = useState(null)   // companies row
  const [loading, setLoading]   = useState(true)   // initial auth check in progress

  // ── Fetch profile + company for a logged-in user ──────────────────────────
  async function loadProfileAndCompany(userId) {
    // Single join query: profiles + companies
    const { data, error } = await supabase
      .from('profiles')
      .select(`
        id,
        full_name,
        role,
        is_active,
        company_id,
        companies (
          id,
          slug,
          name,
          industry,
          primary_colour,
          secondary_colour,
          subscription_tier,
          is_active
        )
      `)
      .eq('id', userId)
      .single()

    if (error || !data) {
      console.error('AuthContext: failed to load profile', error)
      return
    }

    setProfile({
      id:         data.id,
      full_name:  data.full_name,
      role:       data.role,
      is_active:  data.is_active,
      company_id: data.company_id,
    })

    setCompany(data.companies)
  }

  // ── Subscribe to Supabase auth state changes ──────────────────────────────
  useEffect(() => {
    // Initial session check
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session)
      if (session?.user) {
        loadProfileAndCompany(session.user.id).finally(() => setLoading(false))
      } else {
        setLoading(false)
      }
    })

    // Listen for login / logout / token refresh
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      async (_event, session) => {
        setSession(session)
        if (session?.user) {
          await loadProfileAndCompany(session.user.id)
        } else {
          setProfile(null)
          setCompany(null)
        }
        setLoading(false)
      }
    )

    return () => subscription.unsubscribe()
  }, [])

  // ── Sign out ───────────────────────────────────────────────────────────────
  async function signOut() {
    await supabase.auth.signOut()
    setProfile(null)
    setCompany(null)
    setSession(null)
  }

  const value = {
    user:    session?.user ?? null,
    profile,
    company,
    role:    profile?.role ?? 'viewer',
    loading,
    signOut,
  }

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  )
}

// ── Hook ─────────────────────────────────────────────────────────────────────
export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth() must be used inside <AuthProvider>')
  return ctx
}

// ── Backwards-compat shim for existing useCompany() calls (Sessions 6–8) ───
// All screens call useCompany() — this means we DON'T need to edit them.
export function useCompany() {
  const { company, profile } = useAuth()

  // Return the same shape that the old mock CompanyContext returned,
  // so existing screens continue working without modification.
  return {
    company:         company,
    company_id:      company?.id,
    company_name:    company?.name,
    primary_colour:  company?.primary_colour  ?? '#1E3A5F',
    secondary_colour: company?.secondary_colour ?? '#E8B84B',
    subscription_tier: company?.subscription_tier ?? 'starter',
    user_role:       profile?.role ?? 'viewer',
    user_name:       profile?.full_name ?? '',
  }
}

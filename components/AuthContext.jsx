// src/components/AuthContext.jsx
import React, { createContext, useContext, useEffect, useState } from 'react';
import { supabase } from '../lib/supabaseClient';

// ---------------------------------------------------------------------------
// Context definitions
// ---------------------------------------------------------------------------
const AuthContext = createContext(null);
const CompanyContext = createContext(null); // backwards-compat shim

// ---------------------------------------------------------------------------
// AuthProvider
// ---------------------------------------------------------------------------
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [profile, setProfile] = useState(null);
  const [company, setCompany] = useState(null);
  const [role, setRole] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // -------------------------------------------------------------------------
  // Fetch profile + company after we have a user
  // -------------------------------------------------------------------------
  const fetchProfileAndCompany = async (userId) => {
    if (!supabase) return;

    try {
      // Profile row
      const { data: profileData, error: profileError } = await supabase
        .from('profiles')
        .select('*')
        .eq('id', userId)
        .single();

      if (profileError) throw profileError;

      setProfile(profileData);
      setRole(profileData?.role ?? null);

      // Company row
      if (profileData?.company_id) {
        const { data: companyData, error: companyError } = await supabase
          .from('companies')
          .select('*')
          .eq('id', profileData.company_id)
          .single();

        if (companyError) throw companyError;
        setCompany(companyData);
      }
    } catch (err) {
      console.error('[AuthContext] fetchProfileAndCompany error:', err);
      setError(err);
      // Don't block loading — app still renders, just without profile data
    }
  };

  // -------------------------------------------------------------------------
  // Session initialisation — with 3 s fallback timeout so the app NEVER hangs
  // -------------------------------------------------------------------------
  useEffect(() => {
    let mounted = true;

    const finish = (sessionUser) => {
      if (!mounted) return;
      setUser(sessionUser ?? null);
      setLoading(false);
    };

    // Safety timeout: if Supabase doesn't respond within 3 s, unblock the UI
    const timeoutId = setTimeout(() => {
      console.warn('[AuthContext] getSession timed out after 3 s — unblocking render');
      finish(null);
    }, 3000);

    if (!supabase) {
      // No client at all — unblock immediately
      clearTimeout(timeoutId);
      finish(null);
      return;
    }

    supabase.auth
      .getSession()
      .then(({ data, error: sessionError }) => {
        clearTimeout(timeoutId);
        if (sessionError) {
          console.error('[AuthContext] getSession error:', sessionError);
          setError(sessionError);
          finish(null);
          return;
        }
        const sessionUser = data?.session?.user ?? null;
        if (sessionUser && mounted) {
          fetchProfileAndCompany(sessionUser.id).finally(() => finish(sessionUser));
        } else {
          finish(null);
        }
      })
      .catch((err) => {
        clearTimeout(timeoutId);
        console.error('[AuthContext] getSession threw:', err);
        setError(err);
        finish(null);
      });

    // Subscribe to future auth state changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      async (event, session) => {
        if (!mounted) return;
        const changedUser = session?.user ?? null;
        setUser(changedUser);

        if (changedUser) {
          await fetchProfileAndCompany(changedUser.id).catch((err) => {
            console.error('[AuthContext] onAuthStateChange fetchProfile error:', err);
          });
        } else {
          setProfile(null);
          setCompany(null);
          setRole(null);
        }
      }
    );

    return () => {
      mounted = false;
      clearTimeout(timeoutId);
      subscription?.unsubscribe();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // -------------------------------------------------------------------------
  // signOut
  // -------------------------------------------------------------------------
  const signOut = async () => {
    if (!supabase) return;
    try {
      await supabase.auth.signOut();
    } catch (err) {
      console.error('[AuthContext] signOut error:', err);
    }
    setUser(null);
    setProfile(null);
    setCompany(null);
    setRole(null);
  };

  // -------------------------------------------------------------------------
  // Context value
  // -------------------------------------------------------------------------
  const authValue = {
    user,
    profile,
    company,
    role,
    loading,
    error,
    signOut,
    // Convenience derived values
    isAuthenticated: !!user,
    companyId: profile?.company_id ?? null,
  };

  // Backwards-compat CompanyContext value (mirrors old CompanyContext shape)
  const companyValue = {
    company,
    companyId: profile?.company_id ?? null,
    companyConfig: company,  // alias used by older screens
  };

  return (
    <AuthContext.Provider value={authValue}>
      <CompanyContext.Provider value={companyValue}>
        {children}
      </CompanyContext.Provider>
    </AuthContext.Provider>
  );
}

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

/** Primary hook — all auth state */
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}

/** Backwards-compat hook for screens that imported useCompany() */
export function useCompany() {
  const ctx = useContext(CompanyContext);
  if (!ctx) throw new Error('useCompany must be used inside <AuthProvider>');
  return ctx;
}

export default AuthProvider;

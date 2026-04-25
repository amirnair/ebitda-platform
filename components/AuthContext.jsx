// src/components/AuthContext.jsx
import React, { createContext, useContext, useEffect, useState } from 'react';
import { supabase } from '../lib/supabaseClient';

const AuthContext = createContext(null);
const CompanyContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [profile, setProfile] = useState(null);
  const [company, setCompany] = useState(null);
  const [role, setRole] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchProfileAndCompany = async (userId) => {
    if (!supabase) return;
    try {
      const { data: profileData } = await supabase
        .from('profiles')
        .select('*')
        .eq('id', userId)
        .single();

      if (profileData) {
        setProfile(profileData);
        setRole(profileData.role ?? null);

        if (profileData.company_id) {
          const { data: companyData } = await supabase
            .from('companies')
            .select('*')
            .eq('id', profileData.company_id)
            .single();
          if (companyData) setCompany(companyData);
        }
      }
    } catch (err) {
      console.error('[AuthContext] fetchProfileAndCompany error:', err);
    }
  };

  useEffect(() => {
    if (!supabase) {
      setLoading(false);
      return;
    }

    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      async (event, session) => {
        const sessionUser = session?.user ?? null;
        setUser(sessionUser);

        if (sessionUser) {
          await fetchProfileAndCompany(sessionUser.id);
        } else {
          setProfile(null);
          setCompany(null);
          setRole(null);
        }

        setLoading(false);
      }
    );

    const fallback = setTimeout(() => {
      setLoading(false);
    }, 4000);

    return () => {
      subscription?.unsubscribe();
      clearTimeout(fallback);
    };
  }, []);

  const signOut = async () => {
    if (!supabase) return;
    await supabase.auth.signOut().catch(console.error);
    setUser(null);
    setProfile(null);
    setCompany(null);
    setRole(null);
  };

  const authValue = {
    user, profile, company, role, loading, signOut,
    isAuthenticated: !!user,
    companyId: profile?.company_id ?? null,
  };

  const companyValue = {
    company,
    companyId: profile?.company_id ?? null,
    companyConfig: company,
  };

  return (
    <AuthContext.Provider value={authValue}>
      <CompanyContext.Provider value={companyValue}>
        {children}
      </CompanyContext.Provider>
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}

export function useCompany() {
  const ctx = useContext(CompanyContext);
  if (!ctx) throw new Error('useCompany must be used inside <AuthProvider>');
  return ctx;
}

export default AuthProvider;

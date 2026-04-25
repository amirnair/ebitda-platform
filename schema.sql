-- ============================================================
-- AC Industries EBITDA Platform — Session 9
-- Supabase Schema: Multi-Tenant Auth + Company Isolation
-- Run this in Supabase SQL Editor (Dashboard > SQL Editor)
-- ============================================================

-- 1. Companies table
CREATE TABLE IF NOT EXISTS public.companies (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug          TEXT UNIQUE NOT NULL,        -- e.g. 'ac-industries'
  name          TEXT NOT NULL,               -- display name
  industry      TEXT DEFAULT 'steel',
  primary_colour TEXT DEFAULT '#1E3A5F',
  secondary_colour TEXT DEFAULT '#E8B84B',
  subscription_tier TEXT DEFAULT 'starter'
    CHECK (subscription_tier IN ('starter','growth','enterprise')),
  is_active     BOOLEAN DEFAULT TRUE,
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Profiles table (extends Supabase auth.users)
CREATE TABLE IF NOT EXISTS public.profiles (
  id            UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  company_id    UUID NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
  full_name     TEXT,
  role          TEXT NOT NULL DEFAULT 'viewer'
    CHECK (role IN ('owner','finance','production','sales','admin','viewer')),
  is_active     BOOLEAN DEFAULT TRUE,
  created_at    TIMESTAMPTZ DEFAULT NOW(),
  updated_at    TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Indexes
CREATE INDEX IF NOT EXISTS idx_profiles_company_id ON public.profiles(company_id);
CREATE INDEX IF NOT EXISTS idx_profiles_role ON public.profiles(role);

-- ============================================================
-- ROW LEVEL SECURITY — Company Isolation
-- Every tenant can ONLY see their own rows.
-- ============================================================

ALTER TABLE public.companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.profiles  ENABLE ROW LEVEL SECURITY;

-- Helper: get the company_id of the currently logged-in user
CREATE OR REPLACE FUNCTION public.my_company_id()
RETURNS UUID
LANGUAGE SQL STABLE
AS $$
  SELECT company_id FROM public.profiles WHERE id = auth.uid();
$$;

-- Helper: get the role of the currently logged-in user
CREATE OR REPLACE FUNCTION public.my_role()
RETURNS TEXT
LANGUAGE SQL STABLE
AS $$
  SELECT role FROM public.profiles WHERE id = auth.uid();
$$;

-- Companies: user can only see their own company
CREATE POLICY "company_isolation"
  ON public.companies FOR SELECT
  USING (id = public.my_company_id());

-- Profiles: user can only see profiles in their own company
CREATE POLICY "profiles_company_isolation"
  ON public.profiles FOR SELECT
  USING (company_id = public.my_company_id());

-- Profiles: admins and owners can update profiles in their company
CREATE POLICY "profiles_admin_update"
  ON public.profiles FOR UPDATE
  USING (
    company_id = public.my_company_id()
    AND public.my_role() IN ('admin','owner')
  );

-- Profiles: admins and owners can insert new profiles in their company
CREATE POLICY "profiles_admin_insert"
  ON public.profiles FOR INSERT
  WITH CHECK (
    company_id = public.my_company_id()
    AND public.my_role() IN ('admin','owner')
  );

-- ============================================================
-- AUTO-CREATE PROFILE on signup
-- When a user signs up, a trigger fires and creates their profile.
-- company_id and role must be passed in user_metadata at signup time.
-- ============================================================

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  INSERT INTO public.profiles (id, company_id, full_name, role)
  VALUES (
    NEW.id,
    (NEW.raw_user_meta_data->>'company_id')::UUID,
    NEW.raw_user_meta_data->>'full_name',
    COALESCE(NEW.raw_user_meta_data->>'role', 'viewer')
  );
  RETURN NEW;
END;
$$;

CREATE OR REPLACE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- ============================================================
-- SEED DATA — AC Industries (for development)
-- Replace UUIDs with real ones after running this script.
-- ============================================================

INSERT INTO public.companies (id, slug, name, industry, primary_colour, secondary_colour, subscription_tier)
VALUES (
  'a1000000-0000-0000-0000-000000000001',
  'ac-industries',
  'AC Industries',
  'steel',
  '#1E3A5F',
  '#E8B84B',
  'growth'
) ON CONFLICT (slug) DO NOTHING;

-- ============================================================
-- NOTES FOR DEPLOYMENT
-- 1. In Supabase Dashboard > Auth > Settings:
--    - Disable email confirmation for dev (enable for prod)
--    - Set Site URL to your Vercel domain
-- 2. Invite first user via Supabase Dashboard > Auth > Users
--    - Add user_metadata: { "company_id": "a1000000-...", "role": "owner" }
-- 3. For prod invites, use the invite flow in Screen 10 (Settings)
-- ============================================================

-- ============================================================
-- AC Industries EBITDA Platform — Supabase Prod Migration
-- Run this in Supabase SQL Editor (Dashboard → SQL Editor → New Query)
-- Run the four blocks IN ORDER: Schema → RLS → Functions → Seed
-- ============================================================

-- ============================================================
-- BLOCK 1: SCHEMA
-- ============================================================

-- Companies table
CREATE TABLE IF NOT EXISTS public.companies (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug          TEXT UNIQUE NOT NULL,
  name          TEXT NOT NULL,
  industry      TEXT,
  primary_colour      TEXT DEFAULT '#1E40AF',
  secondary_colour    TEXT DEFAULT '#3B82F6',
  subscription_tier   TEXT DEFAULT 'trial'
                      CHECK (subscription_tier IN ('trial','starter','growth','enterprise')),
  is_active     BOOLEAN DEFAULT TRUE,
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Profiles table (one per user, FK to companies)
CREATE TABLE IF NOT EXISTS public.profiles (
  id            UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  company_id    UUID NOT NULL REFERENCES public.companies(id),
  full_name     TEXT,
  role          TEXT DEFAULT 'viewer'
                CHECK (role IN ('owner','admin','finance','production','sales','viewer')),
  is_active     BOOLEAN DEFAULT TRUE,
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Plans table (dynamic pricing — never hardcode)
CREATE TABLE IF NOT EXISTS public.plans (
  id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name                        TEXT NOT NULL,
  slug                        TEXT UNIQUE NOT NULL,
  price_monthly               INTEGER NOT NULL,   -- INR paise? No — store rupees as integer
  price_annual                INTEGER NOT NULL,
  razorpay_plan_id_monthly    TEXT,
  razorpay_plan_id_annual     TEXT,
  features                    JSONB DEFAULT '[]',
  max_users                   INTEGER DEFAULT 5,
  is_active                   BOOLEAN DEFAULT TRUE,
  sort_order                  INTEGER DEFAULT 0,
  created_at                  TIMESTAMPTZ DEFAULT NOW()
);

-- Subscriptions table (one active row per company)
CREATE TABLE IF NOT EXISTS public.subscriptions (
  id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id              UUID NOT NULL REFERENCES public.companies(id),
  plan_id                 UUID NOT NULL REFERENCES public.plans(id),
  razorpay_subscription_id TEXT UNIQUE,
  status                  TEXT DEFAULT 'created'
                          CHECK (status IN ('created','authenticated','active','cancelled','expired','halted','completed')),
  billing_cycle           TEXT DEFAULT 'monthly' CHECK (billing_cycle IN ('monthly','annual')),
  current_start           TIMESTAMPTZ,
  current_end             TIMESTAMPTZ,
  created_at              TIMESTAMPTZ DEFAULT NOW(),
  updated_at              TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- BLOCK 2: RLS (Row Level Security)
-- ============================================================

ALTER TABLE public.companies    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.profiles     ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.plans        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.subscriptions ENABLE ROW LEVEL SECURITY;

-- Helper functions (used in RLS policies)
CREATE OR REPLACE FUNCTION public.my_company_id()
RETURNS UUID LANGUAGE sql STABLE SECURITY DEFINER AS $$
  SELECT company_id FROM public.profiles WHERE id = auth.uid() LIMIT 1;
$$;

CREATE OR REPLACE FUNCTION public.my_role()
RETURNS TEXT LANGUAGE sql STABLE SECURITY DEFINER AS $$
  SELECT role FROM public.profiles WHERE id = auth.uid() LIMIT 1;
$$;

-- Companies: members read own company only
CREATE POLICY "company_read_own"
  ON public.companies FOR SELECT
  USING (id = public.my_company_id());

CREATE POLICY "company_update_admin"
  ON public.companies FOR UPDATE
  USING (id = public.my_company_id() AND public.my_role() IN ('owner','admin'));

-- Profiles: members read own company profiles
CREATE POLICY "profiles_read_own_company"
  ON public.profiles FOR SELECT
  USING (company_id = public.my_company_id());

CREATE POLICY "profiles_insert_admin"
  ON public.profiles FOR INSERT
  WITH CHECK (company_id = public.my_company_id() AND public.my_role() IN ('owner','admin'));

CREATE POLICY "profiles_update_admin"
  ON public.profiles FOR UPDATE
  USING (company_id = public.my_company_id() AND public.my_role() IN ('owner','admin'));

-- Plans: all authenticated users can read active plans
CREATE POLICY "plans_read_active"
  ON public.plans FOR SELECT
  USING (is_active = TRUE);

CREATE POLICY "plans_write_admin"
  ON public.plans FOR ALL
  USING (public.my_role() IN ('owner','admin'));

-- Subscriptions: company members read own; admin/owner write
CREATE POLICY "subscriptions_read_own"
  ON public.subscriptions FOR SELECT
  USING (company_id = public.my_company_id());

CREATE POLICY "subscriptions_write_admin"
  ON public.subscriptions FOR ALL
  USING (company_id = public.my_company_id() AND public.my_role() IN ('owner','admin'));

-- ============================================================
-- BLOCK 3: TRIGGER — auto-create profile on signup
-- ============================================================

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER AS $$
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

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- ============================================================
-- BLOCK 4: SEED DATA
-- ============================================================

-- AC Industries company (fixed UUID for dev/test consistency)
INSERT INTO public.companies (id, slug, name, industry, primary_colour, secondary_colour, subscription_tier)
VALUES (
  'a1000000-0000-0000-0000-000000000001',
  'ac-industries',
  'AC Industries',
  'TMT Rebar Manufacturing',
  '#1E40AF',
  '#3B82F6',
  'trial'
) ON CONFLICT (id) DO NOTHING;

-- Plans seed (prices in INR, not paise)
INSERT INTO public.plans (name, slug, price_monthly, price_annual, features, max_users, is_active, sort_order)
VALUES
  (
    'Starter', 'starter', 6000, 60000,
    '["EBITDA Command Centre","Sales Cycle","Production Cycle","Daily Rolling Plan","Up to 5 users"]',
    5, TRUE, 1
  ),
  (
    'Growth', 'growth', 17500, 175000,
    '["All Starter features","Weekly Production Plan","EBITDA Simulator","Strategy Dashboard","Model Comparison","Up to 15 users"]',
    15, TRUE, 2
  ),
  (
    'Enterprise', 'enterprise', 42500, 425000,
    '["All Growth features","Custom ERP connectors","Priority support","Unlimited users","White-label branding"]',
    9999, TRUE, 3
  )
ON CONFLICT (slug) DO NOTHING;

-- ============================================================
-- VERIFICATION QUERIES (run after above to confirm)
-- ============================================================
-- SELECT * FROM public.companies;
-- SELECT * FROM public.plans;
-- SELECT * FROM public.profiles;

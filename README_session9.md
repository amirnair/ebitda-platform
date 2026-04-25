# Session 9 — Authentication
## AC Industries EBITDA Intelligence Platform

---

## Files Delivered

| File | Purpose |
|------|---------|
| `supabase/schema.sql` | Run in Supabase SQL Editor. Creates companies + profiles tables, RLS policies, auto-profile trigger, seed data. |
| `src/lib/supabaseClient.js` | Supabase singleton — add once, import everywhere. |
| `src/config/rolePermissions.js` | Role → screen access map. Single source of truth for all permission checks. |
| `src/components/AuthContext.jsx` | Replaces mock CompanyContext. Provides `useAuth()` and backwards-compat `useCompany()`. |
| `src/components/CompanyContext.jsx` | **Replace** old file with this shim. Re-exports from AuthContext — zero changes needed in screens 1–9. |
| `src/components/ProtectedRoute.jsx` | Wraps routes. Handles: loading state, unauthenticated redirect, role-denied screen. |
| `src/components/AppShell_session9_diff.jsx` | Patch instructions for AppShell — 4 targeted changes only. |
| `src/screens/LoginScreen.jsx` | Login page. Matches platform aesthetic (dark, DM Mono, gold accent). |
| `src/screens/Settings.jsx` | Screen 10. Tabs: Company / Users / SKU Master / Benchmarks. Full user management for admin/owner. |
| `src/App.jsx` | Updated router with AuthProvider, /login route, ProtectedRoute wrapping all screens. |
| `.env.local.template` | Env var template — copy to `.env.local`. |

---

## Setup Steps (in order)

### Step 1 — Supabase
1. Go to your Supabase project → **SQL Editor**
2. Paste and run `supabase/schema.sql`
3. Go to **Auth → Users** → Create your first user manually
4. Add user metadata (click the user → Edit):
   ```json
   {
     "company_id": "a1000000-0000-0000-0000-000000000001",
     "full_name": "Your Name",
     "role": "owner"
   }
   ```

### Step 2 — Environment variables
```bash
cp .env.local.template .env.local
# Edit .env.local with your Supabase URL and anon key
```

### Step 3 — Install Supabase client
```bash
npm install @supabase/supabase-js
```

### Step 4 — Apply file changes
1. **Replace** `src/components/CompanyContext.jsx` with the new shim
2. **Add** new files: `supabaseClient.js`, `AuthContext.jsx`, `ProtectedRoute.jsx`, `rolePermissions.js`, `LoginScreen.jsx`, `Settings.jsx`
3. **Replace** `src/App.jsx` with Session 9 version
4. **Patch** `src/components/AppShell.jsx` per instructions in `AppShell_session9_diff.jsx`

### Step 5 — Test
```bash
npm run dev
# → should redirect to /login
# → login with the user you created in Supabase
# → should land on EBITDA Command Centre
```

---

## Role → Screen Access Matrix

| Screen | Owner | Admin | Finance | Production | Sales | Viewer |
|--------|-------|-------|---------|------------|-------|--------|
| EBITDA Command Centre | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ |
| Raw Material (Phase 3) | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Production Cycle | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ |
| Sales Cycle | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ |
| Daily Rolling Plan | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ |
| Weekly Production Plan | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ |
| Model Comparison | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| EBITDA Simulator | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| Strategy Dashboard | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| Settings | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |

---

## Architecture Notes

### Company isolation
Every Supabase table has RLS enabled. The `my_company_id()` function ensures
users can only ever read rows that belong to their company. This applies to
`companies` and `profiles` now; Session 11 (deployment) will add it to
`sales_data`, `production_data`, etc.

### Backwards compatibility
`useCompany()` hook is preserved via a re-export in `CompanyContext.jsx`.
Screens 1–9 (Sessions 6–8) need **zero changes** — they still call `useCompany()`
and get the same data shape. The mock data is replaced by real Supabase data.

### Invite flow
User invites use `supabase.auth.admin.inviteUserByEmail()` which requires
the `service_role` key, not the anon key. This means the invite button in
Settings will only work from a backend endpoint in production. For now,
invite users directly from the Supabase dashboard. Session 11 (deployment)
will add a backend `/invite-user` endpoint on Railway.

---

## What's Next — Session 10

Stripe subscription integration:
- Add `stripe_customer_id`, `stripe_subscription_id` to `companies` table
- Tier enforcement: block features above subscription level
- Subscription management screen in Settings → Billing tab

# AC Industries EBITDA Platform — Session 11 Smoke Test Checklist
# Run top to bottom after all three services are deployed.
# Mark each ✅ / ❌ as you go.

## 1. SUPABASE PROD — Database
[ ] Supabase project created (region: ap-south-1 Mumbai for low latency from Tamil Nadu)
[ ] Migration SQL run: companies, profiles, plans, subscriptions tables exist
[ ] RLS enabled on all 4 tables (Settings → Table Editor → each table → RLS toggle = ON)
[ ] my_company_id() and my_role() functions exist (Database → Functions)
[ ] handle_new_user() trigger exists (Database → Triggers → auth.users)
[ ] Seed data: AC Industries company row present (id = a1000000-0000-0000-0000-000000000001)
[ ] Seed data: 3 plans rows present (starter, growth, enterprise)

## 2. RAILWAY — Backend API
[ ] Railway project created, GitHub repo connected
[ ] backend/ directory selected as root (Railway → Service → Settings → Root Directory = backend)
[ ] All backend env vars set in Railway Variables (SUPABASE_URL, SUPABASE_SERVICE_KEY, RAZORPAY_*)
[ ] PORT env var set to 8000 (or left unset — Railway provides $PORT automatically)
[ ] Deploy successful — no build errors in Railway logs
[ ] Health check passes: GET https://your-backend.up.railway.app/health → {"status":"ok"}
[ ] CORS allows your Vercel URL (check main.py allow_origins)

## 3. VERCEL — Frontend
[ ] Vercel project created, GitHub repo connected
[ ] vercel.json present in frontend root (SPA rewrite rule)
[ ] All frontend env vars set in Vercel (VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY, VITE_BACKEND_URL, VITE_ANTHROPIC_API_KEY, VITE_RAZORPAY_KEY_ID)
[ ] Build successful — no build errors in Vercel logs
[ ] App loads at Vercel URL — login screen appears

## 4. AUTH FLOW
[ ] Create first user manually in Supabase Auth Dashboard:
      Dashboard → Authentication → Users → Invite User
      Set user_metadata: { "company_id": "a1000000-0000-0000-0000-000000000001", "full_name": "Test Owner", "role": "owner" }
[ ] User receives invite email, sets password
[ ] Login at Vercel URL with new credentials — redirects to EBITDA Command Centre
[ ] AppShell shows company name "AC Industries" and user role "Owner"
[ ] Nav items visible match owner role (all 10 screens)

## 5. SCREEN SPOT-CHECKS (mock data — no real data yet, that's Session 12)
[ ] Screen 1 — EBITDA Command Centre loads, KPI cards render, no console errors
[ ] Screen 3 — Production Cycle loads
[ ] Screen 4 — Sales Cycle loads
[ ] Screen 5 — Daily Rolling Plan loads
[ ] Screen 10 — Settings loads, Users tab visible (owner role)
[ ] Settings → Billing tab: 3 plan cards render (Starter ₹6,000/mo, Growth ₹17,500/mo, Enterprise ₹42,500/mo)
[ ] AI Insight: at least one screen shows the Claude insight (may take 2–3 seconds)

## 6. INVITE USER ENDPOINT
[ ] POST /api/invite-user called with valid Bearer token (owner) + test email
    curl -X POST https://your-backend.up.railway.app/api/invite-user \
      -H "Authorization: Bearer <owner_jwt_from_supabase>" \
      -H "Content-Type: application/json" \
      -d '{"email":"test@example.com","full_name":"Test Admin","role":"admin","company_id":"a1000000-0000-0000-0000-000000000001"}'
[ ] Response: {"success":true,"message":"Invite sent to test@example.com",...}
[ ] Invited user appears in Supabase Auth → Users
[ ] After invite accepted: profile row auto-created in public.profiles with correct role

## 7. RAZORPAY CHECKOUT (test mode)
[ ] Settings → Billing → click Subscribe on Starter plan
[ ] Razorpay modal opens (requires VITE_RAZORPAY_KEY_ID to be rzp_test_* for testing)
[ ] Use Razorpay test card: 4111 1111 1111 1111, any future expiry, any CVV
[ ] POST /api/create-subscription called — check Railway logs
[ ] Modal shows success
[ ] POST /api/verify-payment called — check Railway logs
[ ] company.subscription_tier updated to 'starter' in Supabase (check Table Editor → companies)
[ ] Subscription row in public.subscriptions with status = 'active'

## 8. ROLE-BASED ACCESS
[ ] Sign in as 'admin' role user — Settings Users tab visible, Billing tab visible
[ ] Sign in as 'sales' role user — Settings tabs show only Billing (no Users tab)
[ ] Sign in as 'viewer' role user — only EBITDA Command Centre accessible via nav

## 9. SECURITY CHECK
[ ] .env.local is NOT committed to git (check .gitignore)
[ ] SUPABASE_SERVICE_KEY is NOT in any frontend file or Vercel env vars
[ ] All Vercel env vars use VITE_ prefix only (backend secrets absent)
[ ] Railway Variables page: service_role key present and marked secret

## 10. POST-DEPLOY
[ ] Update master context document:
    - Session 11 status: Complete
    - Add Vercel prod URL
    - Add Railway prod URL
    - Note: "First user must be created via Supabase Dashboard; subsequent users via /invite-user"
[ ] Ready for Session 12 — Client Testing with AC Industries real data

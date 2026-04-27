// src/lib/supabaseClient.js
import { createClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

let supabase = null;

if (!supabaseUrl || !supabaseAnonKey) {
    console.error('[supabaseClient] Missing env vars: VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY');
} else {
    try {
          supabase = createClient(supabaseUrl, supabaseAnonKey, {
                  auth: {
                            autoRefreshToken: true,
                            persistSession: true,
                            detectSessionInUrl: false,
                            lock: false,
                  },
          });
    } catch (err) {
          console.error('[supabaseClient] Failed to create client:', err);
    }
}

export { supabase };
export default supabase;

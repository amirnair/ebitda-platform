// src/lib/supabaseClient.js
import { createClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

let supabase = null;

if (!supabaseUrl || !supabaseAnonKey) {
  console.error(
    '[supabaseClient] Missing environment variables: VITE_SUPABASE_URL and/or VITE_SUPABASE_ANON_KEY. ' +
    'The app will render but authentication will not work.'
  );
} else {
  try {
    supabase = createClient(supabaseUrl, supabaseAnonKey, {
      auth: {
        autoRefreshToken: true,
        persistSession: true,
        detectSessionInUrl: false,
      },
    });
  } catch (err) {
    console.error('[supabaseClient] Failed to create Supabase client:', err);
    // supabase remains null — AuthContext handles null client gracefully
  }
}

export { supabase };
export default supabase;

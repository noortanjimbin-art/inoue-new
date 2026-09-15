// Public bootstrap. The anon key is designed to be public; RLS and the API
// routes are what protect the data.
import { env, missingEnv } from './_lib.js';

export default function handler(req, res) {
  res.status(200).json({
    supabaseUrl: env('SUPABASE_URL'),
    supabaseAnonKey: env('SUPABASE_ANON_KEY'),
    ready: missingEnv().length === 0 && !!env('SUPABASE_ANON_KEY'),
    missing: missingEnv().concat(env('SUPABASE_ANON_KEY') ? [] : ['SUPABASE_ANON_KEY']),
  });
}

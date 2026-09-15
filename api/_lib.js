import { createClient } from '@supabase/supabase-js';
import { S3Client } from '@aws-sdk/client-s3';

export const env = (k) => process.env[k] || '';

// Which env vars are missing. The frontend shows a setup screen instead of
// failing obscurely when the project hasn't been configured yet.
export function missingEnv() {
  return [
    'SUPABASE_URL', 'SUPABASE_SERVICE_ROLE_KEY',
    'R2_ACCOUNT_ID', 'R2_ACCESS_KEY_ID', 'R2_SECRET_ACCESS_KEY', 'R2_BUCKET',
  ].filter((k) => !env(k));
}

// Service-role client. Never expose this key to the browser: it bypasses RLS.
export const admin = () =>
  createClient(env('SUPABASE_URL'), env('SUPABASE_SERVICE_ROLE_KEY'), {
    auth: { persistSession: false, autoRefreshToken: false },
  });

export const r2 = () =>
  new S3Client({
    region: 'auto',
    endpoint: `https://${env('R2_ACCOUNT_ID')}.r2.cloudflarestorage.com`,
    credentials: {
      accessKeyId: env('R2_ACCESS_KEY_ID'),
      secretAccessKey: env('R2_SECRET_ACCESS_KEY'),
    },
  });

export const json = (res, status, body) => res.status(status).json(body);

// Resolves the caller's Supabase session to their row in `users`, creating it on
// first sign-in. Supabase Auth decides whether the token is valid; this table
// decides what the holder may do.
export async function currentUser(req, res) {
  if (missingEnv().length) {
    json(res, 503, { error: 'not_configured', missing: missingEnv() });
    return null;
  }
  const token = (req.headers.authorization || '').replace(/^Bearer\s+/i, '');
  if (!token) return json(res, 401, { error: 'unauthenticated' }), null;

  const db = admin();
  const { data: auth, error } = await db.auth.getUser(token);
  if (error || !auth?.user) return json(res, 401, { error: 'unauthenticated' }), null;

  const u = auth.user;
  let { data: row } = await db.from('users').select('*').eq('id', u.id).single();
  if (!row) {
    const ins = await db.from('users').insert({
      id: u.id,
      email: u.email,
      name: u.user_metadata?.name || u.email.split('@')[0],
    }).select().single();
    row = ins.data;
    // The trigger may have promoted this row to admin after the insert returned.
    const { data: fresh } = await db.from('users').select('*').eq('id', u.id).single();
    row = fresh || row;
  }
  return row;
}

export const isAdmin = (me) => me && me.role === 'admin';

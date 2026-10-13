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
// The tool's tables live in their own `inoue_new` schema, not `public`, so they
// cannot collide with the annotation tables already in this project.
export const SCHEMA = 'inoue_new';

export const admin = () =>
  createClient(env('SUPABASE_URL'), env('SUPABASE_SERVICE_ROLE_KEY'), {
    auth: { persistSession: false, autoRefreshToken: false },
    db: { schema: SCHEMA },
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

// PostgREST caps a response at 1000 rows and does not signal that it truncated.
// Every list read goes through this, because a silently short list is worse than
// a slow one: the client caches it as the truth. This is what cost a day of
// annotation work when only the annotations read was capped.
export async function allRows(build) {
  // Pages are only consistent if the order is total. Sorting by start time alone
  // leaves rows with the same start (left and right hand together) free to swap
  // between page requests, so one could be returned twice and another never -
  // and a save of that list would write the duplicate back and lose the other.
  // id is unique, so appending it makes the order total.
  //
  // A save can still land between two page requests. Every save rewrites ALL of
  // a task's rows in one statement, with fresh ids and a single shared `at`
  // stamp, so new ids never collide with old ones - a repeated id cannot detect
  // it. A task whose rows carry two different stamps can: that list is half one
  // save and half the next. Start over.
  const PAGE = 1000;
  for (let attempt = 0; attempt < 3; attempt++) {
    let from = 0, out = [], torn = false;
    const seen = new Set(), stamp = new Map();
    for (;;) {
      const { data, error } = await build().order('id').range(from, from + PAGE - 1);
      if (error) throw new Error(error.message);
      for (const row of data || []) {
        if (row.id !== undefined) {
          if (seen.has(row.id)) torn = true;
          seen.add(row.id);
        }
        if (row.task_id !== undefined && row.at !== undefined) {
          const prev = stamp.get(row.task_id);
          if (prev === undefined) stamp.set(row.task_id, row.at);
          else if (prev !== row.at) torn = true;
        }
        out.push(row);
      }
      if (!data || data.length < PAGE) break;
      from += PAGE;
    }
    if (!torn) return out;
  }
  throw new Error('rows kept changing while being read; try again');
}

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

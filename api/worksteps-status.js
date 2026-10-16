// Public health check for the work-step bundle: whether the deployment can read
// it, and how many videos and merges it covers. Counts and names only - never
// the text itself, which stays behind sign-in at /api/worksteps.
import { json, r2, env, missingEnv } from './_lib.js';
import { GetObjectCommand } from '@aws-sdk/client-s3';
import { WORKSTEPS_KEY } from './worksteps.js';

export default async function handler(req, res) {
  res.setHeader('Cache-Control', 'no-store');
  if (missingEnv().length) return json(res, 503, { ok: false, error: 'not_configured' });
  try {
    const obj = await r2().send(new GetObjectCommand({ Bucket: env('R2_BUCKET'), Key: WORKSTEPS_KEY }));
    const data = JSON.parse(await obj.Body.transformToString('utf-8'));
    return json(res, 200, {
      ok: true,
      version: data.version,
      videos: Object.keys(data.videos || {}).length,
      merges: Object.keys(data.merges || {}),
      merge_has_text: Object.keys(data.merges || {}).filter((k) => (data.videos || {})[k]),
    });
  } catch (e) {
    return json(res, 200, { ok: false, error: (e && (e.name || e.message)) || String(e) });
  }
}

// Per-video work-step outlines supplied by the client, placed at the top of each
// video's entry in the JSON export. Stored in R2 next to the videos rather than
// in this repository: they are the client's material and the repository is
// public. Shape: { version, videos: { "<video name>": [lines...] }, unmatched }.
import { currentUser, json, r2, env } from './_lib.js';
import { GetObjectCommand } from '@aws-sdk/client-s3';

export const WORKSTEPS_KEY = 'notes/work_steps.json';

export default async function handler(req, res) {
  const me = await currentUser(req, res);
  if (!me) return;
  if (req.method !== 'GET') return json(res, 405, { error: 'method' });

  try {
    const obj = await r2().send(new GetObjectCommand({ Bucket: env('R2_BUCKET'), Key: WORKSTEPS_KEY }));
    const data = JSON.parse(await obj.Body.transformToString('utf-8'));
    res.setHeader('Cache-Control', 'private, no-store');
    return json(res, 200, data);
  } catch (e) {
    // No outlines uploaded yet is a valid state, not an error.
    if (e && (e.name === 'NoSuchKey' || (e.$metadata && e.$metadata.httpStatusCode === 404))) {
      return json(res, 200, { version: 1, videos: {} });
    }
    // Anything else must fail the export rather than silently drop the outlines.
    return json(res, 500, { error: String((e && e.message) || e) });
  }
}

// Vercel functions cap request bodies at 4.5 MB, so a 500 MB video can never be
// proxied through this route. Instead we hand the browser a presigned PUT and it
// uploads straight to R2. That is why the bucket needs a CORS policy (README).
import { currentUser, isAdmin, json, r2, env } from './_lib.js';
import { PutObjectCommand } from '@aws-sdk/client-s3';
import { getSignedUrl } from '@aws-sdk/s3-request-presigner';

export default async function handler(req, res) {
  const me = await currentUser(req, res);
  if (!me) return;
  if (req.method !== 'POST') return json(res, 405, { error: 'method' });
  if (!isAdmin(me)) return json(res, 403, { error: 'forbidden' });

  const { name, type } = req.body || {};
  if (!name) return json(res, 400, { error: 'name required' });

  const key = `videos/${crypto.randomUUID()}-${String(name).replace(/[^\w.\-]/g, '_')}`;
  const url = await getSignedUrl(
    r2(),
    new PutObjectCommand({
      Bucket: env('R2_BUCKET'),
      Key: key,
      ContentType: type || 'application/octet-stream',
    }),
    { expiresIn: 3600 } // an hour is plenty for 500 MB on a normal connection
  );

  json(res, 200, { key, url });
}

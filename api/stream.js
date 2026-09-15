// Redirects to a short-lived presigned GET rather than piping bytes through the
// function: Vercel caps response bodies at 4.5 MB, and a redirect also lets the
// browser make its own Range requests straight to R2, so seeking works.
import { currentUser, json, r2, env } from './_lib.js';
import { GetObjectCommand } from '@aws-sdk/client-s3';
import { getSignedUrl } from '@aws-sdk/s3-request-presigner';

export default async function handler(req, res) {
  const me = await currentUser(req, res);
  if (!me) return;

  const key = req.query.key;
  if (!key) return json(res, 400, { error: 'key required' });

  const url = await getSignedUrl(
    r2(),
    new GetObjectCommand({ Bucket: env('R2_BUCKET'), Key: key }),
    { expiresIn: 21600 } // 6h: long enough for a full annotation session
  );

  if (req.query.json) return json(res, 200, { url });
  res.setHeader('Cache-Control', 'private, max-age=0, no-store');
  res.redirect(302, url);
}

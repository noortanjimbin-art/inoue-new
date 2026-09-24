// Confirms a freshly uploaded object actually contains video data.
//
// A browser will faithfully upload a file that reads as zeros - the usual cause
// is a cloud-sync placeholder that reports its full size but has never been
// downloaded locally. R2 stores it, the byte count matches what was recorded,
// and nothing looks wrong until an annotator hits the dead region days later.
// E10-S01.mp4 was 64% zeros and cost a day of work before anyone could say why.
import { currentUser, isAdmin, json, r2, env } from './_lib.js';
import { GetObjectCommand, DeleteObjectCommand, HeadObjectCommand } from '@aws-sdk/client-s3';

const WIN = 131072;

async function readRange(client, key, start, end) {
  const out = await client.send(new GetObjectCommand({
    Bucket: env('R2_BUCKET'), Key: key, Range: `bytes=${start}-${end}`,
  }));
  const chunks = [];
  for await (const c of out.Body) chunks.push(c);
  return Buffer.concat(chunks);
}

function zeroFraction(buf) {
  if (!buf.length) return 0;
  let z = 0;
  for (let i = 0; i < buf.length; i++) if (buf[i] === 0) z++;
  return z / buf.length;
}

export default async function handler(req, res) {
  const me = await currentUser(req, res);
  if (!me) return;
  if (req.method !== 'POST') return json(res, 405, { error: 'method' });
  if (!isAdmin(me)) return json(res, 403, { error: 'forbidden' });

  const { key, deleteIfBad } = req.body || {};
  if (!key) return json(res, 400, { error: 'key required' });

  const client = r2();
  let size;
  try {
    const head = await client.send(new HeadObjectCommand({ Bucket: env('R2_BUCKET'), Key: key }));
    size = Number(head.ContentLength || 0);
  } catch (e) {
    return json(res, 404, { error: 'object not found: ' + String(e.message || e) });
  }
  if (!size) return json(res, 422, { ok: false, error: 'zero_filled', size: 0 });

  // Sample across the whole object rather than just the head: the failure mode
  // is a good beginning followed by a long dead tail.
  const fracs = [0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95];
  const holes = [];
  try {
    for (const f of fracs) {
      const start = Math.min(Math.floor(size * f), Math.max(0, size - WIN));
      const buf = await readRange(client, key, start, Math.min(start + WIN, size) - 1);
      if (zeroFraction(buf) > 0.99) holes.push(Math.round(f * 100));
    }
  } catch (e) {
    return json(res, 500, { error: String(e.message || e) });
  }

  if (!holes.length) return json(res, 200, { ok: true, size, sampled: fracs.length });

  // Refuse to register a video nobody can annotate. Removing the object keeps
  // the bucket from filling with dead uploads.
  if (deleteIfBad) {
    try {
      await client.send(new DeleteObjectCommand({ Bucket: env('R2_BUCKET'), Key: key }));
    } catch { /* the rejection stands regardless */ }
  }
  // `error` is what the client's fetch helper throws, so name the code there.
  return json(res, 422, { ok: false, error: 'zero_filled', size, holesAtPercent: holes });
}

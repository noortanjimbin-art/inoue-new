import { admin, currentUser, isAdmin, json, r2, env } from './_lib.js';
import { DeleteObjectCommand } from '@aws-sdk/client-s3';

export default async function handler(req, res) {
  const me = await currentUser(req, res);
  if (!me) return;
  const db = admin();

  if (req.method === 'GET') {
    // Thumbnails are base64 JPEGs of 20-30 KB each, stored inline on the row.
    // The client polls this every 5s, so sending them every time meant megabytes
    // per minute per annotator. They change only when a video is added, so they
    // are opt-in and the client caches them.
    const cols = req.query.thumbs ? '*' : 'id,name,dur,size,added,r2_key';
    const { data } = await db.from('videos').select(cols).order('added', { ascending: false });
    return json(res, 200, data || []);
  }

  if (req.method === 'POST') {
    if (!isAdmin(me)) return json(res, 403, { error: 'forbidden' });
    const v = req.body || {};
    const { data, error } = await db.from('videos').insert({
      name: v.name, dur: v.dur || 0, size: v.size || 0,
      thumb: v.thumb || null, r2_key: v.r2_key,
    }).select().single();
    if (error) return json(res, 400, { error: error.message });
    return json(res, 200, data);
  }

  if (req.method === 'DELETE') {
    if (!isAdmin(me)) return json(res, 403, { error: 'forbidden' });
    const id = req.query.id;
    const { data: v } = await db.from('videos').select('r2_key').eq('id', id).single();
    await db.from('videos').delete().eq('id', id); // tasks/anns cascade
    if (v?.r2_key) {
      try {
        await r2().send(new DeleteObjectCommand({ Bucket: env('R2_BUCKET'), Key: v.r2_key }));
      } catch { /* row is gone either way; a stray object is not worth failing on */ }
    }
    return json(res, 200, { ok: true });
  }

  return json(res, 405, { error: 'method' });
}

import { admin, currentUser, isAdmin, json } from './_lib.js';

export default async function handler(req, res) {
  const me = await currentUser(req, res);
  if (!me) return;
  const db = admin();

  if (req.method === 'GET') {
    // Annotators see only their own queue; admins see everything.
    let q = db.from('tasks').select('*').order('updated', { ascending: false });
    if (!isAdmin(me)) q = q.eq('user_id', me.id);
    const { data } = await q;
    return json(res, 200, data || []);
  }

  if (req.method === 'POST') {
    if (!isAdmin(me)) return json(res, 403, { error: 'forbidden' });
    const t = req.body || {};
    const { data, error } = await db.from('tasks').insert({
      video_id: t.video_id, user_id: t.user_id || null, status: t.status || 'todo',
    }).select().single();
    if (error) return json(res, 400, { error: error.message });
    return json(res, 200, data);
  }

  if (req.method === 'PATCH') {
    const { id, ...patch } = req.body || {};
    const { data: task } = await db.from('tasks').select('*').eq('id', id).single();
    if (!task) return json(res, 404, { error: 'not found' });
    // An annotator may move their own task's status, nothing else.
    if (!isAdmin(me)) {
      if (task.user_id !== me.id) return json(res, 403, { error: 'forbidden' });
      for (const k of Object.keys(patch)) if (k !== 'status') delete patch[k];
    }
    await db.from('tasks').update({ ...patch, updated: new Date().toISOString() }).eq('id', id);
    return json(res, 200, { ok: true });
  }

  if (req.method === 'DELETE') {
    if (!isAdmin(me)) return json(res, 403, { error: 'forbidden' });
    await db.from('tasks').delete().eq('id', req.query.id);
    return json(res, 200, { ok: true });
  }

  return json(res, 405, { error: 'method' });
}

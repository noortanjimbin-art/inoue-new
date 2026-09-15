import { admin, currentUser, isAdmin, json } from './_lib.js';

export default async function handler(req, res) {
  const me = await currentUser(req, res);
  if (!me) return;
  const db = admin();

  if (req.method === 'GET') {
    const { data } = await db.from('users').select('*').order('name');
    return json(res, 200, data || []);
  }

  if (req.method === 'PATCH') {
    if (!isAdmin(me)) return json(res, 403, { error: 'forbidden' });
    const { id, role } = req.body || {};
    // Nobody changes their own role, so an admin cannot lock the team out.
    if (id === me.id) return json(res, 400, { error: 'cannot change your own role' });
    if (!['admin', 'annotator'].includes(role)) return json(res, 400, { error: 'bad role' });
    await db.from('users').update({ role }).eq('id', id);
    return json(res, 200, { ok: true });
  }

  if (req.method === 'DELETE') {
    if (!isAdmin(me)) return json(res, 403, { error: 'forbidden' });
    const id = req.query.id;
    if (id === me.id) return json(res, 400, { error: 'cannot delete yourself' });
    await db.from('users').delete().eq('id', id);
    return json(res, 200, { ok: true });
  }

  return json(res, 405, { error: 'method' });
}

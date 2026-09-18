import { admin, currentUser, isAdmin, json, allRows } from './_lib.js';

export default async function handler(req, res) {
  const me = await currentUser(req, res);
  if (!me) return;
  const db = admin();
  const taskId = req.query.task || (req.body || {}).task;

  // No task given: every annotation the caller may see, in one round trip.
  if (!taskId && req.method === 'GET') {
    try {
      // This lookup was itself unpaged: past 1000 tasks the id list would be cut
      // short and every annotation on the missing tasks would vanish from the
      // response - the same failure one level up.
      const mine = await allRows(() => {
        let q = db.from('tasks').select('id').order('id');
        if (!isAdmin(me)) q = q.eq('user_id', me.id);
        return q;
      });
      const ids = mine.map((t) => t.id);
      if (!ids.length) return json(res, 200, []);
      const rows = await allRows(() =>
        db.from('anns').select('*').in('task_id', ids).order('task_id').order('t_start'));
      return json(res, 200, rows);
    } catch (e) {
      // Never answer 200 with a partial list: the client would cache it as the
      // truth and a later save would write the gap back.
      return json(res, 500, { error: String(e.message || e) });
    }
  }

  if (!taskId) return json(res, 400, { error: 'task required' });

  const { data: task } = await db.from('tasks').select('*').eq('id', taskId).single();
  if (!task) return json(res, 404, { error: 'not found' });
  if (!isAdmin(me) && task.user_id !== me.id) return json(res, 403, { error: 'forbidden' });

  if (req.method === 'GET') {
    try {
      const rows = await allRows(() =>
        db.from('anns').select('*').eq('task_id', taskId).order('t_start'));
      return json(res, 200, rows);
    } catch (e) {
      return json(res, 500, { error: String(e.message || e) });
    }
  }

  if (req.method === 'PUT') {
    const body = req.body || {};
    const items = body.items || [];

    const { count: existing } = await db
      .from('anns').select('id', { count: 'exact', head: true }).eq('task_id', taskId);

    // Optimistic concurrency. `base` is how many rows the client had when it
    // loaded this task. If the stored count has moved, the client is working
    // from a stale or truncated view and its list must not overwrite the store.
    // This is what makes a repeat of the truncation bug unable to destroy data.
    if (body.base != null && Number(body.base) !== Number(existing || 0)) {
      return json(res, 409, {
        error: 'stale', base: Number(body.base), existing: Number(existing || 0),
      });
    }

    // replace_anns does the delete and insert in one transaction, so a failed
    // insert rolls the delete back rather than emptying the task.
    const { data: written, error } = await db.rpc('replace_anns', {
      p_task: taskId, p_items: items,
    });
    if (error) return json(res, 500, { error: error.message });

    await db.from('tasks').update({
      updated: new Date().toISOString(),
      status: items.length && task.status === 'todo' ? 'doing' : task.status,
    }).eq('id', taskId);

    return json(res, 200, { ok: true, count: written });
  }

  return json(res, 405, { error: 'method' });
}

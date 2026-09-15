import { admin, currentUser, isAdmin, json } from './_lib.js';

export default async function handler(req, res) {
  const me = await currentUser(req, res);
  if (!me) return;
  const db = admin();
  const taskId = req.query.task || (req.body || {}).task;

  // No task given: return every annotation the caller may see, in one round
  // trip. The client polls this every 5s, so per-task fetches did not scale.
  if (!taskId && req.method === 'GET') {
    let tq = db.from('tasks').select('id');
    if (!isAdmin(me)) tq = tq.eq('user_id', me.id);
    const { data: mine } = await tq;
    const ids = (mine || []).map((t) => t.id);
    if (!ids.length) return json(res, 200, []);
    const { data } = await db.from('anns').select('*').in('task_id', ids).order('t_start');
    return json(res, 200, data || []);
  }

  if (!taskId) return json(res, 400, { error: 'task required' });

  const { data: task } = await db.from('tasks').select('*').eq('id', taskId).single();
  if (!task) return json(res, 404, { error: 'not found' });
  if (!isAdmin(me) && task.user_id !== me.id) return json(res, 403, { error: 'forbidden' });

  if (req.method === 'GET') {
    const { data } = await db.from('anns').select('*').eq('task_id', taskId).order('t_start');
    return json(res, 200, data || []);
  }

  if (req.method === 'PUT') {
    // Whole-list replace, matching how the workspace persists a task.
    const items = (req.body || {}).items || [];
    await db.from('anns').delete().eq('task_id', taskId);
    if (items.length) {
      const rows = items.map((a) => ({
        task_id: taskId, t_start: a.start, t_end: a.end, caption: a.caption || '',
      }));
      const { error } = await db.from('anns').insert(rows);
      if (error) return json(res, 400, { error: error.message });
    }
    await db.from('tasks').update({
      updated: new Date().toISOString(),
      status: items.length && task.status === 'todo' ? 'doing' : task.status,
    }).eq('id', taskId);
    return json(res, 200, { ok: true, count: items.length });
  }

  return json(res, 405, { error: 'method' });
}

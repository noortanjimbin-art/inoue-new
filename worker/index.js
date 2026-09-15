import { currentUser } from './access.js';

const json = (data, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { 'content-type': 'application/json; charset=utf-8' },
  });

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    if (!url.pathname.startsWith('/api/')) return env.ASSETS.fetch(request);

    const me = await currentUser(request, env);
    if (!me) return json({ error: 'unauthenticated' }, 401);

    try {
      return await route(url, request, env, me);
    } catch (e) {
      return json({ error: String(e && e.message || e) }, 500);
    }
  },
};

const admin = (me) => me.role === 'admin';

async function route(url, request, env, me) {
  const p = url.pathname;
  const m = request.method;

  // ---- identity -----------------------------------------------------------
  if (p === '/api/me') return json(me);

  // ---- users --------------------------------------------------------------
  if (p === '/api/users' && m === 'GET') {
    const { results } = await env.DB.prepare('SELECT * FROM users ORDER BY name').all();
    return json(results);
  }
  if (p.startsWith('/api/users/') && m === 'PATCH') {
    if (!admin(me)) return json({ error: 'forbidden' }, 403);
    const id = p.split('/')[3];
    // Nobody edits their own role, so an admin cannot lock the team out.
    if (id === me.id) return json({ error: 'cannot change your own role' }, 400);
    const { role } = await request.json();
    await env.DB.prepare('UPDATE users SET role = ? WHERE id = ?').bind(role, id).run();
    return json({ ok: true });
  }

  // ---- videos -------------------------------------------------------------
  if (p === '/api/videos' && m === 'GET') {
    const { results } = await env.DB.prepare('SELECT * FROM videos ORDER BY added DESC').all();
    return json(results);
  }
  if (p === '/api/videos' && m === 'POST') {
    if (!admin(me)) return json({ error: 'forbidden' }, 403);
    const v = await request.json();
    const id = 'v' + crypto.randomUUID().slice(0, 8);
    await env.DB.prepare(
      'INSERT INTO videos (id,name,dur,size,added,thumb,r2_key) VALUES (?,?,?,?,?,?,?)'
    ).bind(id, v.name, v.dur || 0, v.size || 0, Date.now(), v.thumb || null, `videos/${id}`).run();
    return json({ id, r2_key: `videos/${id}` });
  }

  // ---- video bytes --------------------------------------------------------
  // Upload and playback both run through this Worker, so the browser only ever
  // talks to its own origin. No R2 CORS policy, no presigned URLs to leak.

  // Multipart upload: the 500 MB case. Browser sends ~10 MB parts.
  if (p === '/api/upload/create' && m === 'POST') {
    if (!admin(me)) return json({ error: 'forbidden' }, 403);
    const { key } = await request.json();
    const up = await env.VIDEOS.createMultipartUpload(key);
    return json({ key: up.key, uploadId: up.uploadId });
  }
  if (p === '/api/upload/part' && m === 'PUT') {
    if (!admin(me)) return json({ error: 'forbidden' }, 403);
    const key = url.searchParams.get('key');
    const uploadId = url.searchParams.get('uploadId');
    const partNumber = Number(url.searchParams.get('partNumber'));
    const up = env.VIDEOS.resumeMultipartUpload(key, uploadId);
    const part = await up.uploadPart(partNumber, request.body);
    return json(part); // { partNumber, etag } — collect these client-side
  }
  if (p === '/api/upload/complete' && m === 'POST') {
    if (!admin(me)) return json({ error: 'forbidden' }, 403);
    const { key, uploadId, parts } = await request.json();
    const up = env.VIDEOS.resumeMultipartUpload(key, uploadId);
    const obj = await up.complete(parts);
    return json({ key, size: obj.size });
  }

  // Playback. Range support is what makes seeking work in a <video> element.
  if (p.startsWith('/api/stream/') && (m === 'GET' || m === 'HEAD')) {
    const key = decodeURIComponent(p.slice('/api/stream/'.length));
    const range = request.headers.get('range');
    const obj = await env.VIDEOS.get(key, range ? { range: request.headers } : undefined);
    if (!obj) return json({ error: 'not found' }, 404);

    const h = new Headers();
    obj.writeHttpMetadata(h);
    h.set('etag', obj.httpEtag);
    h.set('accept-ranges', 'bytes');
    h.set('cache-control', 'private, max-age=3600');
    if (obj.range && 'offset' in obj.range) {
      const start = obj.range.offset;
      const end = start + obj.range.length - 1;
      h.set('content-range', `bytes ${start}-${end}/${obj.size}`);
      return new Response(obj.body, { status: 206, headers: h });
    }
    return new Response(obj.body, { headers: h });
  }

  // ---- tasks --------------------------------------------------------------
  if (p === '/api/tasks' && m === 'GET') {
    // Annotators see only their own queue; admins see everything.
    const q = admin(me)
      ? env.DB.prepare('SELECT * FROM tasks ORDER BY updated DESC')
      : env.DB.prepare('SELECT * FROM tasks WHERE user_id = ? ORDER BY updated DESC').bind(me.id);
    const { results } = await q.all();
    return json(results);
  }
  if (p === '/api/tasks' && m === 'POST') {
    if (!admin(me)) return json({ error: 'forbidden' }, 403);
    const t = await request.json();
    const id = 't' + crypto.randomUUID().slice(0, 8);
    const now = Date.now();
    await env.DB.prepare(
      'INSERT INTO tasks (id,video_id,user_id,status,created,updated) VALUES (?,?,?,?,?,?)'
    ).bind(id, t.videoId, t.userId || null, t.status || 'todo', now, now).run();
    return json({ id });
  }

  // ---- annotations --------------------------------------------------------
  if (p.startsWith('/api/anns/')) {
    const taskId = p.split('/')[3];
    const task = await env.DB.prepare('SELECT * FROM tasks WHERE id = ?').bind(taskId).first();
    if (!task) return json({ error: 'not found' }, 404);
    if (!admin(me) && task.user_id !== me.id) return json({ error: 'forbidden' }, 403);

    if (m === 'GET') {
      const { results } = await env.DB
        .prepare('SELECT * FROM anns WHERE task_id = ? ORDER BY t_start').bind(taskId).all();
      return json(results);
    }
    if (m === 'PUT') {
      // Whole-list replace, matching how the workspace currently persists.
      const items = await request.json();
      const now = Date.now();
      const stmts = [env.DB.prepare('DELETE FROM anns WHERE task_id = ?').bind(taskId)];
      for (const a of items) {
        stmts.push(
          env.DB.prepare(
            'INSERT INTO anns (id,task_id,t_start,t_end,caption,at) VALUES (?,?,?,?,?,?)'
          ).bind('a' + crypto.randomUUID().slice(0, 8), taskId, a.start, a.end, a.caption || '', a.at || now)
        );
      }
      stmts.push(
        env.DB.prepare('UPDATE tasks SET updated = ?, status = ? WHERE id = ?')
          .bind(now, items.length ? 'doing' : task.status, taskId)
      );
      await env.DB.batch(stmts); // atomic: the task is never left half-written
      return json({ ok: true, count: items.length });
    }
  }

  return json({ error: 'no route' }, 404);
}

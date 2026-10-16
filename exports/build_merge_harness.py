"""Snapshot the data the merged export needs, plus a harness page that runs the
shipped export functions from public/index.html on it. Usage:
python build_merge_harness.py <scratch dir> <work_steps.json>"""
import io, os, sys, json, urllib.request, urllib.parse

SP, WS = sys.argv[1], sys.argv[2]
BASE = os.environ['SB_URL'].rstrip('/') + '/rest/v1'
KEY = os.environ['SB_KEY']
H = {'apikey': KEY, 'Authorization': 'Bearer ' + KEY, 'Accept-Profile': 'inoue_new'}


def get(path, q, page=1000):
    out, f = [], 0
    while True:
        u = BASE + '/' + path + '?' + urllib.parse.urlencode(q)
        c = json.loads(urllib.request.urlopen(urllib.request.Request(
            u, headers=dict(H, Range='%d-%d' % (f, f + page - 1))), timeout=120).read())
        out += c
        if len(c) < page:
            return out
        f += page


videos = get('videos', {'select': 'id,name,dur', 'order': 'name'})
tasks = get('tasks', {'select': 'id,video_id,user_id,status', 'order': 'id'})
users = get('users', {'select': 'id,name', 'order': 'id'})
anns = get('anns', {'select': 'task_id,t_start,t_end,caption', 'order': 'task_id,t_start,id'})
db = {'videos': [{'id': v['id'], 'name': v['name'], 'dur': v['dur']} for v in videos],
      'tasks': [{'id': t['id'], 'videoId': t['video_id'], 'userId': t['user_id'], 'status': t['status']} for t in tasks],
      'users': [{'id': u['id'], 'name': u['name']} for u in users],
      'anns': {}}
for a in anns:
    db['anns'].setdefault(a['task_id'], []).append({'start': a['t_start'], 'end': a['t_end'], 'caption': a['caption']})
io.open(os.path.join(SP, 'snap.json'), 'w', encoding='utf-8').write(json.dumps(db, ensure_ascii=False))
io.open(os.path.join(SP, 'ws.json'), 'w', encoding='utf-8').write(io.open(WS, encoding='utf-8').read())

src = io.open('public/index.html', encoding='utf-8').read()


def func(name):
    i = src.index('function %s(' % name)
    return src[i:src.index('\n}', i) + 2]


js = '\n'.join(func(n) for n in ('tcH', 'r3', 'rEven', 'buildMergedExport', 'buildJsonExport', 'annName', 'annOf', 'exRows'))
page = '''<!doctype html><meta charset="utf-8"><title>merge harness</title>
<input id="exVideo"><input id="exUser"><input id="exStatus"><script>
var STR={eMergeNone:'NONE {f}',eMergeMissing:'MISSING {f}',eMergeDur:'DUR {f} {a} {b}'};
function t(k,v){ var s=STR[k]||k; if(v) for(var p in v) s=s.split('{'+p+'}').join(v[p]); return s; }
function $(id){ return document.getElementById(id); }
var DB={videos:[],tasks:[],anns:{}}, USERS={};
function userById(id){ return USERS[id]||null; }
function videoById(id){ var r=null; DB.videos.forEach(function(v){ if(v.id===id) r=v; }); return r; }
''' + js + '''
window.load=async function(){
  var s=await fetch('snap.json').then(r=>r.json());
  DB.videos=s.videos; DB.tasks=s.tasks; DB.anns=s.anns; s.users.forEach(u=>USERS[u.id]=u);
  window.WS=await fetch('ws.json').then(r=>r.json()); return s.tasks.length; };
window.M=buildMergedExport; window.J=buildJsonExport; window.X=exRows;
</script>'''
io.open(os.path.join(SP, 'merge.html'), 'w', encoding='utf-8').write(page)
print('snapshot: %d videos, %d tasks, %d annotations' % (len(videos), len(tasks), len(anns)))

import io, os, json, urllib.request, urllib.parse

BASE = os.environ['SB_URL'].rstrip('/') + '/rest/v1'
KEY  = os.environ['SB_KEY']
H    = {'apikey': KEY, 'Authorization': 'Bearer ' + KEY, 'Accept-Profile': 'inoue_new'}
def get(path, params, page=1000):
    out, frm = [], 0
    while True:
        url = BASE + '/' + path + '?' + urllib.parse.urlencode(params, doseq=True)
        req = urllib.request.Request(url, headers=dict(H, Range='%d-%d' % (frm, frm+page-1)))
        c = json.loads(urllib.request.urlopen(req, timeout=180).read().decode())
        out += c
        if len(c) < page: return out
        frm += page

videos = {v['id']: v['name'] for v in get('videos', {'select': 'id,name'})}
tv     = {t['id']: t['video_id'] for t in get('tasks', {'select': 'id,video_id'})}
anns   = get('anns', {'select': 'task_id,caption', 'order': 'task_id,id'})

frames = {r['name']: r for r in json.load(io.open('exports/frames.json', encoding='utf-8'))}
CORRUPT = 'E10-S01.mp4'

per, allcaps = {}, []
for a in anns:
    name = videos.get(tv.get(a['task_id']))
    if not name: continue
    r = frames.get(name)
    if not r or not r['assigned'] or name == CORRUPT: continue
    cap = (a['caption'] or '').strip()
    per.setdefault(name, []).append(cap)
    allcaps.append(cap)

print('%-18s %9s %10s %9s %9s' % ('video','captions','worked_f','f/caption','cap/min'))
print('-'*62)
TC = TW = 0
for name in sorted(per):
    caps = per[name]; r = frames[name]
    wf = min(int(round(r['covered_sec'] * r['probe']['fps'])), r['probe']['frames'])
    TC += len(caps); TW += wf
    print('%-18s %9d %10d %9.1f %9.1f'
          % (name, len(caps), wf, wf/len(caps), len(caps)/(wf/r['probe']['fps']/60)))
print('-'*62)
print('%-18s %9d %10d %9.1f %9.1f' % ('TOTAL', TC, TW, TW/TC, TC/(TW/30.0/60)))

norm = [c.lower() for c in allcaps]
print()
print('  total captions              %d' % TC)
print('  distinct caption strings    %d' % len(set(allcaps)))
print('  distinct, case-insensitive  %d' % len(set(norm)))
print('  blank captions              %d' % sum(1 for c in allcaps if not c))
print('  mean caption length         %.1f chars' % (sum(len(c) for c in allcaps)/len(allcaps)))
from collections import Counter
print()
print('  most repeated captions:')
for cap, n in Counter(norm).most_common(5):
    print('    %4d x  %s' % (n, cap[:58]))

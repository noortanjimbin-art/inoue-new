import io, os, json, subprocess, urllib.request, urllib.parse

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

videos = get('videos', {'select': 'id,name,dur,r2_key'})
tasks  = get('tasks',  {'select': 'id,video_id,status'})
anns   = get('anns',   {'select': 'task_id,t_start,t_end', 'order': 'task_id,id'})
print('fetched: %d videos, %d tasks, %d annotations' % (len(videos), len(tasks), len(anns)), flush=True)

task_video = {t['id']: t['video_id'] for t in tasks}
spans = {}
for a in anns:
    v = task_video.get(a['task_id'])
    if v: spans.setdefault(v, []).append((a['t_start'], a['t_end']))

def union(iv):
    """Merge overlapping spans. Both hands are annotated, so spans overlap and
       summing durations would count the same footage twice."""
    if not iv: return 0.0, 0, 0.0
    iv = sorted(iv)
    tot, segs, s, e = 0.0, 0, iv[0][0], iv[0][1]
    far = e
    for a, b in iv[1:]:
        far = max(far, b)
        if a > e: tot += e - s; segs += 1; s, e = a, b
        else:     e = max(e, b)
    tot += e - s; segs += 1
    return tot, segs, far

def probe(key):
    u = subprocess.run(['rclone','link','R2:inoue-new-videos/'+key,'--expire','3h'],
                       capture_output=True, text=True, timeout=120).stdout.strip().split('\n')[-1]
    if not u.startswith('http'): return None
    r = subprocess.run(['ffprobe','-v','error','-select_streams','v',
                        '-show_entries','stream=nb_frames,r_frame_rate',
                        '-show_entries','format=duration','-of','json',u],
                       capture_output=True, text=True, timeout=300)
    try:
        j = json.loads(r.stdout); st = j['streams'][0]
        num, den = st['r_frame_rate'].split('/')
        fps = float(num)/float(den)
        nf  = int(st.get('nb_frames') or 0)
        dur = float(j['format']['duration'])
        if not nf: nf = int(round(dur*fps))
        return {'fps': round(fps,3), 'frames': nf, 'dur': round(dur,3)}
    except Exception:
        return None

rows = []
for v in sorted(videos, key=lambda x: x['name']):
    cov, segs, far = union(spans.get(v['id'], []))
    info = probe(v['r2_key'])
    has_task = any(t['video_id'] == v['id'] for t in tasks)
    rows.append({'name': v['name'], 'db_dur': v['dur'], 'probe': info,
                 'covered_sec': round(cov,3), 'segments': segs,
                 'furthest_sec': round(far,3), 'assigned': has_task,
                 'anns': len(spans.get(v['id'], []))})
    print('  %-18s probe=%s cov=%.1fs' % (v['name'], 'ok' if info else 'FAIL', cov), flush=True)

io.open('exports/frames.json','w',encoding='utf-8').write(json.dumps(rows, indent=2))
print('done -> exports/frames.json')

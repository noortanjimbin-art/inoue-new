import io, os, json, urllib.request, urllib.parse, datetime

BASE = os.environ['SB_URL'].rstrip('/') + '/rest/v1'
KEY  = os.environ['SB_KEY']
HDRS = {'apikey': KEY, 'Authorization': 'Bearer ' + KEY, 'Accept-Profile': 'inoue_new'}

def get(path, params, page=1000):
    """Fetch every row, paging past PostgREST's 1000-row ceiling."""
    out, frm = [], 0
    while True:
        url = BASE + '/' + path + '?' + urllib.parse.urlencode(params, doseq=True)
        req = urllib.request.Request(url, headers=dict(HDRS, Range='%d-%d' % (frm, frm + page - 1)))
        chunk = json.loads(urllib.request.urlopen(req, timeout=120).read().decode())
        out += chunk
        if len(chunk) < page:
            return out
        frm += page

FPS = 30.0
# Frame offsets measured from the media files; integers so nothing drifts.
PARTS = [
    (1, 'E02-S01-1.mp4', 0,      27249),
    (2, 'E02-S01-2.mp4', 27249,  27000),
    (3, 'E02-S01-3.mp4', 54249,  27000),
    (4, 'E02-S01-4.mp4', 81249,  27000),
    (5, 'E02-S01-5.mp4', 108182, 27000),
    (6, 'E02-S01-6.mp4', 135182, 27000),
    (7, 'E02-S01-7.mp4', 162182, 27000),
    (8, 'E02-S01-8.mp4', 189182, 23018),
]
# correct the two parts whose true frame counts differ from the nominal 27000
FRAMES = {1: 27249, 2: 27000, 3: 27000, 4: 26933, 5: 27000, 6: 27000, 7: 27000, 8: 23018}

def tc(s):
    if s < 0: s = 0
    h = int(s // 3600); m = int((s % 3600) // 60); sec = s - h*3600 - m*60
    return '%02d:%02d:%06.3f' % (h, m, sec)

names = [p[1] for p in PARTS]
videos = get('videos', {'select': 'id,name,dur', 'name': 'in.(%s)' % ','.join('"%s"' % n for n in names)})
vid_by_name = {v['name']: v for v in videos}
assert len(vid_by_name) == 8, 'expected 8 part videos, got %d' % len(vid_by_name)

tasks = get('tasks', {'select': 'id,video_id,user_id,status'})
users = {u['id']: u for u in get('users', {'select': 'id,name'})}

rows, part_meta, roster = [], [], {}
for idx, fname, foff, _ in PARTS:
    v = vid_by_name[fname]
    ts = [t for t in tasks if t['video_id'] == v['id']]
    assert len(ts) == 1, '%s has %d tasks' % (fname, len(ts))
    t = ts[0]
    u = users.get(t['user_id'], {})
    # display name only; addresses never go into an export
    who = str(u.get('name') or '').strip()
    if '@' in who: who = ''
    frames = FRAMES[idx]
    off_sec = foff / FPS

    anns = get('anns', {'select': 't_start,t_end,caption', 'task_id': 'eq.' + t['id'], 'order': 't_start'})
    for a in anns:
        gs = a['t_start'] + off_sec
        ge = a['t_end']   + off_sec
        rows.append({
            'start_sec': round(gs, 3), 'end_sec': round(ge, 3),
            'duration_sec': round(ge - gs, 3),
            'start_timecode': tc(gs), 'end_timecode': tc(ge),
            'start_frame': int(round(gs * FPS)), 'end_frame': int(round(ge * FPS)),
            'caption': a['caption'],
            'part': idx,
            'part_start_sec': round(a['t_start'], 3), 'part_end_sec': round(a['t_end'], 3),
            'annotator': who,
        })

    part_meta.append({
        'index': idx, 'file': fname,
        'offset_sec': round(off_sec, 3), 'offset_timecode': tc(off_sec), 'offset_frame': foff,
        'duration_sec': round(frames / FPS, 3), 'duration_timecode': tc(frames / FPS),
        'frames': frames, 'annotator': who, 'status': t['status'], 'annotations': len(anns),
    })
    r = roster.setdefault(who, {'name': who, 'parts': [], 'annotations': 0})
    r['parts'].append(idx); r['annotations'] += len(anns)

rows.sort(key=lambda r: (r['start_sec'], r['end_sec']))
total_frames = sum(FRAMES.values())

doc = {
    'export': {
        'generated_at': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'source': 'INOUEE annotation platform',
        'schema_version': 2,
    },
    'video': {
        'name': 'E02-S01.mp4',
        'duration_sec': round(total_frames / FPS, 3),
        'duration_timecode': tc(total_frames / FPS),
        'fps': 30, 'total_frames': total_frames, 'part_count': 8,
    },
    'annotators': sorted(roster.values(), key=lambda a: a['parts'][0]),
    'parts': part_meta,
    'annotation_count': len(rows),
    'annotations': rows,
}

io.open('exports/E02-S01.json', 'w', encoding='utf-8').write(
    json.dumps(doc, ensure_ascii=False, indent=2))
print('wrote exports/E02-S01.json  rows=%d' % len(rows))

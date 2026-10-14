import io, json, re, difflib
FPS_EPS = 1/30.0
STOP = set('the a an of to on in into onto from with and while its it at by for up down over under using use'.split())

S = json.load(io.open('exports/qa_snapshot.json', encoding='utf-8'))
VID  = {v['id']: v for v in S['videos']}
USER = {u['id']: u['name'] for u in S['users']}
TASK = {t['id']: t for t in S['tasks']}
BYTASK = {}
for a in S['anns']:
    BYTASK.setdefault(a['task_id'], []).append(a)
for k in BYTASK: BYTASK[k].sort(key=lambda a: (a['t_start'], a['t_end']))

def hands(c):
    w = (c or '').strip().lower().split()
    if len(w) < 2: return ''
    if re.sub('[^a-z]', '', w[1]) not in ('hand', 'hands'): return ''
    return {'both': 'LR', 'left': 'L', 'right': 'R'}.get(w[0], '')

def body(c):
    """Caption minus the 'left hand' style prefix, normalised for comparison."""
    w = re.sub('[^a-z0-9 ]', ' ', (c or '').lower()).split()
    if len(w) >= 2 and w[0] in ('left', 'right', 'both') and w[1] in ('hand', 'hands'):
        w = w[2:]
    return ' '.join(w)

def stem(w):
    for suf in ('ing', 'es', 's', 'ed'):
        if len(w) > 4 and w.endswith(suf): return w[:-len(suf)]
    return w

def content(c):
    return set(stem(w) for w in body(c).split() if w not in STOP and len(w) > 1)

def sim(a, b):
    ba, bb = body(a), body(b)
    seq = difflib.SequenceMatcher(None, ba, bb).ratio()
    ca, cb = content(a), content(b)
    jac = len(ca & cb) / len(ca | cb) if (ca | cb) else 1.0
    return max(seq, jac), seq, jac

def shared_hand(h1, h2):
    return any(x in h2 for x in h1)

def iou(x, y):
    inter = min(x['t_end'], y['t_end']) - max(x['t_start'], y['t_start'])
    union = max(x['t_end'], y['t_end']) - min(x['t_start'], y['t_start'])
    return (inter / union if union > 0 else 0.0), inter

def tc(s):
    s = max(0.0, s); m = int(s // 60); return '%02d:%05.2f' % (m, s - 60 * m)

def task_label(tid):
    t = TASK[tid]; return VID[t['video_id']]['name'], USER.get(t['user_id'], '(unassigned)'), t['status']

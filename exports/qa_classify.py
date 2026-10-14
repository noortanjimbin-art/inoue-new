import sys, io, re, json, collections
sys.path.insert(0, 'exports')
from qa_core import *
from qa_semantics import parse, same_action, same_kind_diff_id, opposite, is_hold

overlaps, dup_within = [], []
for tid, rows in BYTASK.items():
    for i, x in enumerate(rows):
        hx = hands(x['caption'])
        for y in rows[i + 1:]:
            if y['t_start'] >= x['t_end'] - FPS_EPS:
                break
            hy = hands(y['caption'])
            j, inter = iou(x, y)
            if inter <= FPS_EPS:
                continue
            same_body = body(x['caption']) == body(y['caption'])
            if not (hx and hy and shared_hand(hx, hy)):
                if same_body and not hx and not hy:
                    dup_within.append(dict(kind='Same caption recorded twice', tid=tid, x=x, y=y,
                                           iou=j, inter=inter, hand='?'))
                continue
            hand = hx if hx == hy else hx + '/' + hy
            if same_body:
                kind = 'Same caption recorded twice' if j >= 0.5 else 'Same caption, spans partly overlap'
                dup_within.append(dict(kind=kind, tid=tid, x=x, y=y, iou=j, inter=inter, hand=hand))
                continue
            if j >= 0.5 and same_action(x['caption'], y['caption']):
                dup_within.append(dict(kind='Same action, reworded', tid=tid, x=x, y=y,
                                       iou=j, inter=inter, hand=hand))
                continue
            px, py = parse(x['caption']), parse(y['caption'])
            contained = ((x['t_start'] <= y['t_start'] + FPS_EPS and x['t_end'] >= y['t_end'] - FPS_EPS) or
                         (y['t_start'] <= x['t_start'] + FPS_EPS and y['t_end'] >= x['t_end'] - FPS_EPS))
            if same_kind_diff_id(px, py):
                hint = 'Same kind of object, different identifier (e.g. tube A vs tube C)'
            elif opposite(px, py):
                hint = 'Conflicting direction or side (up/down, on/off, left/right)'
            elif is_hold(px) or is_hold(py):
                held, other = (px, y['caption']) if is_hold(px) else (py, x['caption'])
                # search the whole other caption: "closes the window while holding tube B"
                # mentions the held tube in its trailing clause
                other_words = {w[:-1] if len(w) > 4 and w.endswith('s') else w
                               for w in re.findall(r'[a-z0-9-]+', other.lower())}
                if held['head'] and held['head'] in other_words:
                    hint = 'Holds an object while acting on the same object - probably valid'
                else:
                    hint = 'Holds one thing while doing something else - check'
            else:
                hint = 'Two different actions at once - likely error'
            overlaps.append(dict(tid=tid, x=x, y=y, iou=j, inter=inter, hand=hand,
                                 contained=contained, hint=hint))

by_video = collections.defaultdict(list)
for t in S['tasks']:
    if t['id'] in BYTASK:
        by_video[t['video_id']].append(t['id'])
groups = [(VID[v]['name'], tids) for v, tids in by_video.items() if len(tids) >= 2]
names = {VID[t['video_id']]['name']: t['id'] for t in S['tasks'] if t['id'] in BYTASK}
if 'E10-S01.mp4' in names and 'E10-S01 new.mp4' in names:
    groups.append(('E10-S01 (original + re-upload)', [names['E10-S01.mp4'], names['E10-S01 new.mp4']]))

cross, cross_stats = [], []
for gname, tids in groups:
    for a_i in range(len(tids)):
        for b_i in range(a_i + 1, len(tids)):
            A, B = BYTASK[tids[a_i]], BYTASK[tids[b_i]]
            used, matched = set(), 0
            for x in A:
                hx = hands(x['caption'])
                if not hx:
                    continue
                best = None
                for k, y in enumerate(B):
                    if k in used or hands(y['caption']) != hx:
                        continue
                    j, inter = iou(x, y)
                    if j >= 0.5 and (best is None or j > best[0]):
                        best = (j, k, y, inter)
                if not best:
                    continue
                used.add(best[1]); matched += 1
                y = best[2]
                if body(x['caption']) == body(y['caption']):
                    verdict = 'Agree - same wording'
                elif same_action(x['caption'], y['caption']):
                    verdict = 'Agree - reworded'
                else:
                    verdict = 'Unclear - check video'
                cross.append(dict(group=gname, ta=tids[a_i], tb=tids[b_i], x=x, y=y,
                                  iou=best[0], inter=best[3], hand=hx, verdict=verdict))
            cross_stats.append(dict(group=gname, ta=tids[a_i], tb=tids[b_i],
                                    na=len(A), nb=len(B), matched=matched))

io.open('exports/qa_results.json', 'w', encoding='utf-8').write(json.dumps(
    dict(overlaps=overlaps, dup_within=dup_within, cross=cross, cross_stats=cross_stats), default=str))

if __name__ == '__main__':
    print('OVERLAPS:', len(overlaps))
    for k, v in collections.Counter(o['hint'] for o in overlaps).most_common():
        print('   %4d  %s' % (v, k))
    print('WITHIN-TASK DUPLICATES:', len(dup_within))
    for k, v in collections.Counter(d['kind'] for d in dup_within).most_common():
        print('   %4d  %s' % (v, k))
    print('CROSS-ANNOTATOR:', len(cross))
    for k, v in collections.Counter(c['verdict'] for c in cross).most_common():
        print('   %4d  %s' % (v, k))

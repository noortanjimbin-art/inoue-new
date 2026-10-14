"""Round-trip edited times through the real replace_anns function on a scratch
task, then delete it. Nothing real is touched."""
import os, json, urllib.request

BASE = os.environ['SB_URL'].rstrip('/') + '/rest/v1'
KEY = os.environ['SB_KEY']
H = {'apikey': KEY, 'Authorization': 'Bearer ' + KEY, 'Accept-Profile': 'inoue_new',
     'Content-Profile': 'inoue_new', 'Content-Type': 'application/json', 'Prefer': 'return=representation'}


def call(method, path, body=None):
    req = urllib.request.Request(BASE + path, method=method, headers=H,
                                 data=None if body is None else json.dumps(body).encode())
    raw = urllib.request.urlopen(req, timeout=60).read()
    return json.loads(raw) if raw else None


def read(tid):
    return [(a['t_start'], a['t_end'], a['caption'])
            for a in call('GET', '/anns?select=t_start,t_end,caption&task_id=eq.%s&order=t_start' % tid)]


vid = call('POST', '/videos', {'name': '__time_edit_probe__', 'r2_key': '__probe__'})[0]['id']
tid = call('POST', '/tasks', {'video_id': vid, 'status': 'todo'})[0]['id']
ok = True
try:
    original = [{'start': 17.2134, 'end': 18.2134, 'caption': 'Right hand picks up the pen'},
                {'start': 20.0, 'end': 22.0, 'caption': 'Left hand holds the paper'}]
    n = call('POST', '/rpc/replace_anns', {'p_task': tid, 'p_items': original})
    print('1. saved original      returned=%s  stored=%s' % (n, read(tid)))

    # the user's edit: start 17.21 -> 17.16 (end keeps full precision)
    edited = [dict(original[0], start=17.16), original[1]]
    n = call('POST', '/rpc/replace_anns', {'p_task': tid, 'p_items': edited})
    got = read(tid)
    print('2. saved edited start  returned=%s  stored=%s' % (n, got))
    ok &= got[0][0] == 17.16 and got[0][1] == 18.2134 and len(got) == 2

    # an edit that moves the first row after the second: stored order follows time
    moved = [dict(original[0], start=23.5, end=24.25), original[1]]
    call('POST', '/rpc/replace_anns', {'p_task': tid, 'p_items': moved})
    got = read(tid)
    print('3. moved row past next stored=%s' % got)
    ok &= [g[2][:5] for g in got] == ['Left ', 'Right'] and len(got) == 2

    # what the OLD behaviour did with a null time: the row vanished silently
    call('POST', '/rpc/replace_anns', {'p_task': tid, 'p_items': [dict(original[0], start=None), original[1]]})
    got = read(tid)
    print('4. null start sent DIRECTLY to the DB (bypassing the API guard): rows stored = %d of 2' % len(got))
    print('   -> this is the silent drop the new API check prevents')
finally:
    call('DELETE', '/tasks?id=eq.%s' % tid)
    call('DELETE', '/videos?id=eq.%s' % vid)
    left = call('GET', '/videos?select=id&name=eq.__time_edit_probe__')
    print('cleanup: probe rows remaining = %d' % len(left))
print('ROUND TRIP', 'PASS' if ok else 'FAIL')

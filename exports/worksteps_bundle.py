"""Build notes/work_steps.json from the client's per-video text files.

Each text is stored verbatim as a list of its lines, keyed by the video name as
it appears in the tool. Texts that match no video are kept under `unmatched` so
nothing supplied is lost. Usage: python worksteps_bundle.py <folder of .txt> <out.json>
"""
import io, os, sys, json, glob

src, out = sys.argv[1], sys.argv[2]
# names as they appear in the tool, where they differ from the text file's name
ALIAS = {'E10-S01': 'E10-S01 new.mp4'}

videos, unmatched, report = {}, {}, []
known = set(json.loads(os.environ.get('TOOL_VIDEOS', '[]')))
for path in sorted(glob.glob(os.path.join(src, '*.txt'))):
    raw = io.open(path, 'rb').read()
    text = raw.decode('utf-8-sig').replace('\r\n', '\n').replace('\r', '\n')
    lines = text.split('\n')
    while lines and lines[-1].strip() == '':
        lines.pop()                                   # trailing blank lines only
    assert '\n'.join(lines) == text.rstrip('\n').rstrip(), path   # nothing else altered
    stem = os.path.basename(path)[:-4]
    name = ALIAS.get(stem, stem + '.mp4')
    if name in known:
        videos[name] = lines
        report.append('%-16s -> %s (%d lines)' % (stem, name, len(lines)))
    else:
        unmatched[stem] = lines
        report.append('%-16s -> (no video in the tool, kept unmatched)' % stem)

doc = {'version': 1, 'videos': videos, 'unmatched': unmatched}
io.open(out, 'w', encoding='utf-8').write(json.dumps(doc, ensure_ascii=False, indent=1))
print('\n'.join(report))
print('matched %d, unmatched %d' % (len(videos), len(unmatched)))

"""Build notes/work_steps.json from the client's per-video text files.

Each text is stored verbatim as a list of its lines, keyed by the video name as
it appears in the tool. Texts that match no video are kept under `unmatched` so
nothing supplied is lost. Usage: python worksteps_bundle.py <folder of .txt> <out.json>
"""
import io, os, sys, json, glob

src, out = sys.argv[1], sys.argv[2]
# names as they appear in the tool, where they differ from the text file's name
ALIAS = {'E10-S01': 'E10-S01 new.mp4'}

# Videos recorded as separate part files and exported merged onto one timeline.
# Frame counts are measured from the media files with ffprobe, NOT taken from the
# tool's database, which stores durations rounded to whole seconds - offsets
# built from those would drift by up to 0.3 s (9 frames) by the last part.
# Verified: 8 parts sum to 212,200 frames = 7073.333 s at 30 fps, matching the
# client's own table of part start times to the millisecond.
MERGES = {
    'E02-S01.mp4': {'fps': 30, 'parts': [
        {'file': 'E02-S01-1.mp4', 'frames': 27249},
        {'file': 'E02-S01-2.mp4', 'frames': 27000},
        {'file': 'E02-S01-3.mp4', 'frames': 27000},
        {'file': 'E02-S01-4.mp4', 'frames': 26933},
        {'file': 'E02-S01-5.mp4', 'frames': 27000},
        {'file': 'E02-S01-6.mp4', 'frames': 27000},
        {'file': 'E02-S01-7.mp4', 'frames': 27000},
        {'file': 'E02-S01-8.mp4', 'frames': 23018},
    ]},
}

videos, unmatched, report = {}, {}, []
# a merged video has no row of its own in the tool, but its outline belongs to it
known = set(json.loads(os.environ.get('TOOL_VIDEOS', '[]'))) | set(MERGES)
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

for name, m in MERGES.items():
    assert sum(p['frames'] for p in m['parts']) > 0, name
doc = {'version': 2, 'videos': videos, 'unmatched': unmatched, 'merges': MERGES}
io.open(out, 'w', encoding='utf-8').write(json.dumps(doc, ensure_ascii=False, indent=1))
print('\n'.join(report))
print('matched %d, unmatched %d' % (len(videos), len(unmatched)))

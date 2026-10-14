import re

GROUPS = [
    'take takes taking took get gets getting grab grabs grabbing pick picks picking lift lifts lifting obtain obtains fetch fetches retrieve retrieves',
    'place places placing put puts putting set sets setting lay lays laying position positions return returns lower lowers drop drops',
    'close closes closing shut shuts tighten tightens tightening seal seals cap caps',
    'open opens opening unscrew unscrews loosen loosens uncap uncaps',
    'hold holds holding grip grips grasp grasps keep keeps keeping support supports steady steadies stabilize stabilizes',
    'move moves moving transfer transfers transferring shift shifts slide slides carry carries reposition repositions bring brings',
    'press presses pressing push pushes pushing tap taps click clicks',
    'pour pours pouring dispense dispenses',
    'write writes writing label labels mark marks',
    'remove removes removing detach detaches',
    'insert inserts inserting attach attaches mount mounts',
    'turn turns turning rotate rotates rotating twist twists',
]
VG = {}
for i, g in enumerate(GROUPS):
    for w in g.split():
        VG[w] = i
HOLD_GROUP = VG['hold']

ORD = set('first second third fourth fifth sixth seventh eighth ninth tenth last'.split())
COL = set('red blue green yellow white black orange pink purple brown grey gray clear transparent'.split())
STOP = set(('the a an of to on in into onto from with and while its it at by for up down over under using '
            'use that this then which still again also back out off another other some').split())
GENERIC = set('micro small large big new empty full left right top bottom side front rear'.split())
PREP = set('of on in into onto from with to at by under over inside'.split())
CLAUSE = set('while and then as before after during using whilst'.split())
WORD = re.compile(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*")


def _words(c):
    w = WORD.findall(c or '')
    if len(w) >= 2 and w[0].lower() in ('left', 'right', 'both') and w[1].lower() in ('hand', 'hands'):
        w = w[2:]
    return w


def parse(c):
    """Split a caption into verb group, particle, object words, head noun and identifiers."""
    w = _words(c)
    lo = [x.lower() for x in w]
    verb = lo[0] if lo else ''
    i, particle = 1, ''
    if i < len(lo) and lo[i] in ('up', 'down', 'on', 'off', 'out', 'in', 'over', 'away', 'back'):
        particle = lo[i]
        i += 1
    idents, objs, head, seen_prep = set(), set(), '', False
    for raw, l in zip(w[i:], lo[i:]):
        if l in CLAUSE:
            break                                    # "... while holding X" describes a second action
        if len(raw) == 1 and raw.isupper():
            idents.add('L' + raw); continue          # tube A
        if any(ch.isdigit() for ch in raw):
            idents.add('N' + l); continue            # tube 2, 10ml
        if l in ORD:
            idents.add('O' + l); continue            # second filter
        if l in COL:
            idents.add('C' + l); continue            # blue rack
        if l in PREP:
            seen_prep = True
        if l in STOP or l in GENERIC:
            continue
        base = l[:-1] if len(l) > 4 and l.endswith('s') and not l.endswith('ss') else l
        objs.add(base)
        if not seen_prep:
            head = base                              # head noun of the direct object
    sides = {x for x in lo if x in ('left', 'right')}
    return dict(verb=verb, vg=VG.get(verb, 'v:' + verb), particle=particle,
                idents=idents, objs=objs, head=head, sides=sides)


def jacc(a, b):
    return len(a & b) / len(a | b) if (a | b) else 1.0


def opposite(pa, pb):
    if {pa['particle'], pb['particle']} in ({'on', 'off'}, {'up', 'down'}):
        return True
    return bool(pa['sides'] and pb['sides'] and pa['sides'] != pb['sides'])


def same_kind_diff_id(pa, pb):
    """tube A vs tube C: same head noun, different identifiers."""
    return bool(pa['head'] and pa['head'] == pb['head'] and pa['idents'] and pb['idents']
                and pa['idents'] != pb['idents'])


def same_action(a, b):
    """True when two captions plausibly describe the same action on the same thing."""
    pa, pb = parse(a), parse(b)
    if opposite(pa, pb):
        return False
    if pa['idents'] and pb['idents'] and pa['idents'] != pb['idents']:
        return False
    if pa['vg'] != pb['vg']:
        return False
    # The thing acted on must be the same: "the bottle" and "the cap of the bottle"
    # share most of their words but are different objects.
    if pa['head'] and pb['head']:
        return pa['head'] == pb['head']
    return jacc(pa['objs'], pb['objs']) >= 0.5


def is_hold(p):
    return p['vg'] == HOLD_GROUP

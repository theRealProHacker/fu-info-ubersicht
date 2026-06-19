#!/usr/bin/env python3
"""fetch_vv_people.py — VV-driven people roster (the authoritative teacher list).

The FU Informatik Vorlesungsverzeichnis (VV) publishes, per semester, EVERY CS
course and its instructor(s) on ONE server-rendered page:

    https://www.fu-berlin.de/vv/de/modul?id=130142&sm=<SEMESTER_CODE>

`id=130142` is the node "Gesamtes Lehrangebot der Informatik" (the whole CS
catalogue). Each course is a `<span class="course_link">` block holding
`<b>LV-Nr</b>`, `<span class="category label label-info">Type</span>`,
`<span class="course_name">Title</span>` and `<span class="course_instructor">
(Name, Name)</span>`. Splitting on `course_link` yields one entry per chunk.

This is the INVERSE of fetch_courses.py (name -> courses): it reads the listing
into {instructor -> courses}, which is the authoritative answer to "who teaches
CS, and therefore belongs in the database". Buckets (report-first):

  - teaches & in DB              -> keep; refresh their lehre.kurse  (--apply)
  - teaches & NOT in DB          -> ADD candidate (new person -> run fill_missing)
  - in DB, never teaches, and    -> REMOVE candidate (curation)
    not professor / secretary

`--apply` only refreshes lehre.kurse for matched people (deterministic, safe,
like fetch_courses.py --apply). Adds/removals are ADVISORY — additions go through
fill_missing.py's validate(); removals are a separate, human-reviewed step. This
script never creates or deletes `personen` and never invents facts.

Modes:
  python3 fetch_vv_people.py            # REPORT roster buckets. No write.
  python3 fetch_vv_people.py --apply    # + write lehre.kurse for matched people.
"""
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import fetch_courses as fc   # reuse clean(), normalize(), TYPE_MAP, overrides

D = Path(__file__).resolve().parent
DATASET = D / 'fu-informatik-data.json'
PROV = D / 'provenance.jsonl'

# "Gesamtes Lehrangebot der Informatik" node. Stable for recent semesters; can
# drift across curriculum reforms (override with --module-id if a semester
# returns 0 courses). Newest first; older `sm` codes roll out of the VV window.
CS_MODULE_ID = '130142'
SEMESTERS = [
    ('SS 2026', '965826'), ('WS 25/26', '934771'),
    ('SS 2025', '870180'), ('WS 24/25', '851413'),
    ('SS 2024', '814672'), ('WS 23/24', '754328'),
]

LISTING = 'https://www.fu-berlin.de/vv/de/modul?id={mid}&sm={sm}'
TYPE_RE = re.compile(r'<span class="category label[^"]*">(.*?)</span>', re.S)
INSTR_RE = re.compile(r'<span class="course_instructor">\s*\((.*?)\)\s*</span>', re.S)
# Instructor tokens that are not real people.
NON_PERSON = {'n.n.', 'nn', 'n. n.', 'abgesagt', 'tba', ''}

# Roles always kept regardless of teaching (mirrors classify_visibility intent).
SECRETARY_RE = re.compile(r'sekret|projektassist|office', re.I)


TITLE_STOP = {'prof', 'dr', 'apl', 'jun', 'habil', 'med', 'phd',
              'dipl', 'inf', 'ing', 'msc', 'sc'}


def name_tokens(name):
    """Order-independent name token set (drops titles + single-letter initials)."""
    n = name.lower().replace('.', ' ')
    return frozenset(t for t in re.findall(r'\w+', n, re.U)
                     if len(t) > 1 and t not in TITLE_STOP)


def norm_name(name):
    """Stable string key for grouping VV occurrences of the same instructor."""
    return ' '.join(sorted(name_tokens(name)))


def match_id(vv_toks, ptoks):
    """Resolve a VV instructor's tokens to a person id. Exact match wins; else a
    UNIQUE subset match either direction (handles middle names: 'Benjamin
    Berendsohn' ⊆ 'Benjamin Aram Berendsohn', 'Marius Max Wawerek' ⊇ 'Marius
    Wawerek'). Ambiguous → unmatched (None)."""
    if not vv_toks:
        return None
    exact = [pid for pid, toks in ptoks.items() if toks == vv_toks]
    if exact:
        return exact[0]
    subset = [pid for pid, toks in ptoks.items()
              if toks and len(vv_toks & toks) >= 2
              and (vv_toks <= toks or toks <= vv_toks)]
    return subset[0] if len(subset) == 1 else None


def fetch_listing(sm, mid):
    url = LISTING.format(mid=mid, sm=sm)
    req = urllib.request.Request(url, headers={'User-Agent': fc.UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode('utf-8', 'replace')


def parse_listing(html_text):
    """[(lv_nr, vv_type, code, name, [instructors])] for one semester listing.
    Unknown VV types are returned separately so they're flagged, never dropped
    silently."""
    rows, unknown = [], []
    for chunk in html_text.split('<span class="course_link"')[1:]:
        lv = fc.LV_RE.search(chunk)
        nm = fc.NAME_RE.search(chunk)
        if not (lv and nm):
            continue
        vt = fc.clean(TYPE_RE.search(chunk).group(1)) if TYPE_RE.search(chunk) else ''
        if vt.lower() not in fc.TYPE_MAP:
            unknown.append(vt)
            continue
        im = INSTR_RE.search(chunk)
        instr = fc.clean(im.group(1)) if im else ''
        people = [p.strip() for p in instr.split(',')]
        people = [p for p in people if p.lower() not in NON_PERSON]
        rows.append({'lv_nr': lv.group(1), 'vv_type': vt, 'code': fc.TYPE_MAP[vt.lower()],
                     'name': fc.clean(nm.group(1)), 'instructors': people})
    return rows, unknown


def person_tokens(data):
    """person id -> name token set, including the VV display-name overrides."""
    out = {p['id']: name_tokens(p['name']) for p in data['personen']}
    for pid, vvname in fc.VV_QUERY_OVERRIDES.items():
        out[pid] = name_tokens(vvname)
    return out


def is_protected(p):
    """Professors and secretaries are kept regardless of teaching."""
    rolle = (p.get('rolle') or '')
    return 'professor' in rolle.lower() or bool(SECRETARY_RE.search(rolle))


def main():
    apply = '--apply' in sys.argv
    mid = CS_MODULE_ID
    if '--module-id' in sys.argv:
        mid = sys.argv[sys.argv.index('--module-id') + 1]

    data = json.loads(DATASET.read_text(encoding='utf-8'))
    ptoks = person_tokens(data)
    pmap = {p['id']: p for p in data['personen']}

    # instructor norm-key -> {'display': str, 'sem': {label: [rows]}}
    teachers = {}
    unknown_types = set()
    print(f"Fetching VV listing (module {mid}) x {len(SEMESTERS)} semesters …\n")
    for label, sm in SEMESTERS:
        rows, unk = parse_listing(fetch_listing(sm, mid))
        unknown_types.update(unk)
        if not rows:
            print(f"  !!! {label} ({sm}): 0 courses — check module id / sm code")
            continue
        print(f"  {label}: {len(rows)} courses")
        for r in rows:
            for person in r['instructors']:
                t = teachers.setdefault(norm_name(person),
                                        {'display': person, 'sem': {}})
                t['sem'].setdefault(label, []).append(r)

    if unknown_types:
        print("\n!!! UNKNOWN VV TYPES (add to fetch_courses.TYPE_MAP):")
        for t in sorted(unknown_types):
            print(f"    {t!r}")

    # Resolve each teacher's courses per semester (reuse normalize: merges a
    # lecture with that same person's Übung -> V+Ü, dedups, orders).
    taught_acc = {}        # id -> accumulated lehre.kurse (may span name forms)
    add_candidates = []    # teachers with no matching person
    for key, t in teachers.items():
        courses = []
        for label, _ in SEMESTERS:
            if label in t['sem']:
                courses += fc.normalize(t['sem'][label], label)
        pid = match_id(name_tokens(t['display']), ptoks)
        if pid:
            taught_acc.setdefault(pid, []).extend(courses)
        else:
            add_candidates.append((t['display'], courses))

    # One person can appear under >1 VV name form (e.g. with/without a middle
    # name), which match_id resolves to the same id. Merge those buckets, dedup,
    # and order newest-semester first — never overwrite (would drop courses).
    sem_rank = {label: i for i, (label, _) in enumerate(SEMESTERS)}
    taught_ids = {}
    for pid, courses in taught_acc.items():
        seen, uniq = set(), []
        for c in courses:
            k = (c['typ'], c['name'], c['semester'])
            if k in seen:
                continue
            seen.add(k)
            uniq.append(c)
        uniq.sort(key=lambda c: (sem_rank.get(c['semester'], 99),
                                 fc.TYPE_ORDER.get(c['typ'], 9), c['name']))
        taught_ids[pid] = uniq

    # Removal candidates: visible, in DB, never a VV instructor, not protected.
    remove_candidates = [
        p for p in data['personen']
        if p.get('sichtbar') is not False
        and p['id'] not in taught_ids
        and not is_protected(p)
    ]

    print(f"\n=== TEACHES & IN DB ({len(taught_ids)}) — lehre.kurse refresh ===")
    for pid in sorted(taught_ids, key=lambda i: pmap[i]['name'].split()[-1]):
        print(f"  {pmap[pid]['name']:<28} {len(taught_ids[pid])} course(s)")

    print(f"\n=== TEACHES & NOT IN DB ({len(add_candidates)}) — ADD candidates ===")
    for name, courses in sorted(add_candidates, key=lambda x: x[0].split()[-1]):
        sample = courses[0]['name'] if courses else ''
        print(f"  + {name:<30} {len(courses)} course(s)   e.g. {sample}")

    print(f"\n=== IN DB, NEVER TEACHES, not prof/secretary ({len(remove_candidates)}) "
          f"— REMOVE candidates ===")
    for p in sorted(remove_candidates, key=lambda x: x['name'].split()[-1]):
        print(f"  - {p['name']:<28} {p.get('rolle','?'):<32} {','.join(p.get('gruppen') or [])}")

    print("\nNote: ADD/REMOVE are advisory. Additions go through fill_missing.py "
          "(validate + provenance); removals are a separate reviewed step. "
          f"Teaching window = {SEMESTERS[-1][0]}–{SEMESTERS[0][0]}.")

    if not apply:
        print("\n(report only — re-run with --apply to write lehre.kurse for matched people)")
        return

    ts = datetime.now(timezone.utc).isoformat(timespec='seconds')
    prov = []
    for pid, courses in taught_ids.items():
        if not courses:
            continue
        pmap[pid].setdefault('lehre', {})['kurse'] = courses
        prov.append({'ts': ts, 'id': pid, 'mode': 'person', 'action': 'updated',
                     'field': 'lehre.kurse', 'value': len(courses),
                     'note': f"VV listing module {mid} ({SEMESTERS[-1][0]}–{SEMESTERS[0][0]})",
                     'source': 'https://www.fu-berlin.de/vv/'})
    DATASET.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding='utf-8')
    with PROV.open('a', encoding='utf-8') as f:
        for r in prov:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    print(f"\nWROTE lehre.kurse for {len(prov)} people + {len(prov)} provenance records.")
    print("ADD/REMOVE candidates were NOT applied (review them first).")


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""fetch_courses.py — fetch real Lehrveranstaltungen from the FU Berlin
Vorlesungsverzeichnis (VV) and normalize them into the dataset's
`lehre.kurse` schema: {name, semester, typ, lv_nr}.

The VV is fully server-rendered, so this is a plain HTTP fetch + HTML parse —
deterministic and re-runnable every semester (update SEMESTERS, re-run).

VV facts:
  - URL: /vv/de/search?query=<name>&query_option=1&sm=<SEMESTER_CODE>
  - `sm` selects the SEMESTER (not the person); `query` is a free-text name.
    SS 2026 = 965826,  WS 25/26 = 934771.
  - Each result row is <li class="search_link"> with
        <b>LV-Nr</b><span class="category label">Type</span>
        <a><span class="course_name">Title</span></a>
        <span class="course_instructor">(names)</span>

Normalization (confirmed mapping — keep CONSISTENT + repeatable):
  Vorlesung/RV/Kurs -> V        Übung/Tutorium/Seminar am PC -> Ü
  Seminar/Forschungsseminar/Seminaristischer Unterricht/Praxisseminar -> S
  Seminar/Proseminar -> S/PS    Proseminar -> PS    Projektseminar -> SWP
  Forschungspraktikum/Berufspraktikum -> P
  DROPPED: Praktikum, Kolloquium, Begrüßungs- und Abschlussveranstaltung
  Merge: a lecture + its "Übung zu <same title>" collapse to one V+Ü entry,
         keeping the VORLESUNG title. Exact (title,type) duplicates deduped.
  Unknown VV types are flagged loudly, never silently dropped.

Modes:
  python3 fetch_courses.py            # REPORT: normalized courses per prof. No write.
  python3 fetch_courses.py --apply    # write lehre.kurse to the dataset + provenance.
"""
import json
import re
import sys
import html as htmllib
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

D = Path(__file__).resolve().parent
DATASET = D / 'fu-informatik-data.json'
PROV = D / 'provenance.jsonl'

# (label kept short per spec, sm semester code). Newest first.
SEMESTERS = [('SS 2026', '965826'), ('WS 25/26', '934771')]

# The VV indexes some people under a different name than our dataset.
VV_QUERY_OVERRIDES = {
    'rote-guenter': 'Günther Rothe',   # dataset "Günter Rote"
}

# vv_type (lowercased) -> short code, or None to DROP. Unknown -> flagged.
TYPE_MAP = {
    'vorlesung': 'V', 'rv': 'V', 'kurs': 'V',
    'übung': 'Ü', 'tutorium': 'Ü', 'seminar am pc': 'Ü',
    'zentralübung': 'Ü', 'mentorium': 'Ü',
    'brückenkurs': 'V', 'methodenkurs': 'V',
    'seminar': 'S', 'forschungsseminar': 'S',
    'seminaristischer unterricht': 'S', 'praxisseminar': 'S',
    'seminar/proseminar': 'S/PS',
    'proseminar': 'PS',
    'projektseminar': 'SWP',
    'forschungspraktikum': 'P', 'berufspraktikum': 'P',
    'praktikum': None, 'kolloquium': None,
    'begrüßungs- und abschlussveranstaltung': None,
}
# A lecture's exercise course names it: "<Übung|Tutorium|Seminar am PC> zu[r/m]
# <X>" or "Practice Seminar for <X>". Captures the lecture title X for exact
# pairing (covers "zu", "zur", "zum", and English "for").
MERGE_PREFIX = re.compile(
    r'^(?:Übung|Tutorium|Seminar am PC|Practice Seminar)\s+(?:zu[rm]?|for)\s+(.+)$',
    re.S | re.I)
# Connector words ignored when counting shared words for the fuzzy merge.
_STOP = {'und', 'and', 'der', 'die', 'das', 'den', 'dem', 'des', 'zu', 'zur',
         'zum', 'im', 'in', 'für', 'for', 'of', 'the', 'mit', 'von', 'auf',
         'an', 'am', 'bei', 'als', 'is', 'to'}


def content_tokens(s):
    return {w for w in re.findall(r'\w+', s.lower(), re.U)
            if len(w) >= 2 and w not in _STOP}
# Display/sort priority.
TYPE_ORDER = {'V': 0, 'V+Ü': 1, 'Ü': 2, 'S': 3, 'S/PS': 4, 'PS': 5, 'SWP': 6, 'P': 7}

UA = 'Mozilla/5.0 (compatible; fu-info-uebersicht/1.0; course data refresh)'
SEARCH = ('https://www.fu-berlin.de/vv/de/search?lanloc=de'
          '&query={q}&query_option=1&sm={sm}&utf8=%E2%9C%93')
ROW_RE = re.compile(r'<li class="search_link".*?</li>', re.S)
LV_RE = re.compile(r'<b>\s*(\d{6,})\s*</b>')
TYPE_RE = re.compile(r'<span class="category label">(.*?)</span>', re.S)
NAME_RE = re.compile(r'<span class="course_name">(.*?)</span>', re.S)
INSTR_RE = re.compile(r'<span class="course_instructor">\((.*?)\)</span>', re.S)


def clean(s):
    return htmllib.unescape(re.sub(r'<[^>]+>', '', s or '')).strip()


def professors(data):
    return [{'id': p['id'], 'name': p['name'], 'sichtbar': p.get('sichtbar')}
            for p in data['personen']
            if 'professor' in (p.get('rolle') or '').lower()]


def vv_query(prof):
    return VV_QUERY_OVERRIDES.get(prof['id'], prof['name'])


def fetch(query, sm):
    url = SEARCH.format(q=urllib.parse.quote_plus(query), sm=sm)
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode('utf-8', 'replace')


def parse_rows(html_text, query):
    """Parsed rows, filtered to those actually taught by `query` (all name
    tokens present in the instructor list — guards against namesakes)."""
    want = set(re.findall(r'\w+', query.lower(), re.U))
    rows, unknown = [], []
    for block in ROW_RE.findall(html_text):
        lv, nm = LV_RE.search(block), NAME_RE.search(block)
        if not (lv and nm):
            continue
        instr = clean(INSTR_RE.search(block).group(1)) if INSTR_RE.search(block) else ''
        if not want.issubset(set(re.findall(r'\w+', instr.lower(), re.U))):
            continue
        vt = clean(TYPE_RE.search(block).group(1)) if TYPE_RE.search(block) else ''
        if vt.lower() not in TYPE_MAP:
            unknown.append(vt)
            continue
        rows.append({'lv_nr': lv.group(1), 'vv_type': vt,
                     'name': clean(nm.group(1)), 'code': TYPE_MAP[vt.lower()]})
    return rows, unknown


def normalize(rows, semester):
    """Drop None-coded, dedup, merge V+Ü -> one entry (lecture title)."""
    kept = [r for r in rows if r['code'] is not None]
    # dedup by (code, name): keep first lv_nr
    seen, deduped = set(), []
    for r in kept:
        k = (r['code'], r['name'])
        if k in seen:
            continue
        seen.add(k)
        deduped.append(r)
    lectures = [r for r in deduped if r['code'] == 'V']
    lec_by_name = {r['name']: r for r in lectures}
    consumed = set()
    for r in deduped:
        if r['code'] != 'Ü':
            continue
        m = MERGE_PREFIX.match(r['name'])
        target = lec_by_name.get(m.group(1).strip()) if m else None
        if target is None:
            # Fuzzy fallback: only inside the SAME VV module (the LV-Nr minus
            # its 2-digit component, e.g. 193353|01 vs 193353|02) AND only when
            # more than two content words overlap.
            mod, ut, best = r['lv_nr'][:-2], content_tokens(r['name']), 2
            for lr in lectures:
                if lr['lv_nr'][:-2] != mod:
                    continue
                ov = len(ut & content_tokens(lr['name']))
                if ov > best:
                    target, best = lr, ov
        if target is not None:
            target['code'] = 'V+Ü'
            consumed.add(id(r))
    out = []
    for r in deduped:
        if id(r) in consumed:
            continue
        out.append({'name': r['name'], 'semester': semester,
                    'typ': r['code'], 'lv_nr': r['lv_nr']})
    out.sort(key=lambda e: (TYPE_ORDER.get(e['typ'], 9), e['name']))
    return out


def courses_for(prof):
    q = vv_query(prof)
    all_courses, unknowns = [], []
    for label, sm in SEMESTERS:
        rows, unk = parse_rows(fetch(q, sm), q)
        all_courses += normalize(rows, label)
        unknowns += unk
    return prof['id'], all_courses, unknowns


def main():
    apply = '--apply' in sys.argv
    data = json.loads(DATASET.read_text(encoding='utf-8'))
    profs = professors(data)
    name_by_id = {p['id']: p['name'] for p in profs}

    results, unknown_types = {}, set()
    with ThreadPoolExecutor(max_workers=8) as ex:
        for pid, courses, unk in ex.map(courses_for, profs):
            results[pid] = courses
            unknown_types.update(unk)

    print(f"Fetched {len(profs)} professors x {len(SEMESTERS)} semesters\n")
    if unknown_types:
        print("!!! UNKNOWN VV TYPES (not in TYPE_MAP) — add a mapping:")
        for t in sorted(unknown_types):
            print(f"    {t!r}")
        print()

    updated = 0
    for pid in sorted(results, key=lambda i: name_by_id[i].split()[-1]):
        courses = results[pid]
        if not courses:
            continue
        updated += 1
        print(f"### {name_by_id[pid]}  ({len(courses)} courses)")
        for c in courses:
            print(f"    [{c['typ']:<4}] {c['name']}  ({c['semester']})  #{c['lv_nr']}")
        print()
    skipped = [name_by_id[i] for i in results if not results[i]]
    print(f"{updated} professors with courses; no VV results (left untouched): "
          + ", ".join(sorted(skipped)))

    if not apply:
        print("\n(report only — re-run with --apply to write lehre.kurse)")
        return

    pmap = {p['id']: p for p in data['personen']}
    ts = datetime.now(timezone.utc).isoformat(timespec='seconds')
    prov = []
    for pid, courses in results.items():
        if not courses:
            continue
        p = pmap[pid]
        p.setdefault('lehre', {})['kurse'] = courses
        prov.append({'ts': ts, 'id': pid, 'mode': 'person', 'action': 'updated',
                     'field': 'lehre.kurse', 'value': len(courses),
                     'note': f'Refreshed from FU Vorlesungsverzeichnis ({", ".join(l for l,_ in SEMESTERS)})',
                     'source': 'https://www.fu-berlin.de/vv/'})
    DATASET.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding='utf-8')
    with PROV.open('a', encoding='utf-8') as f:
        for r in prov:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    print(f"\nWROTE lehre.kurse for {len(prov)} professors + {len(prov)} provenance records.")


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""merge_legacy_vita.py — one-off: fold legacy flat `vita.positionen` strings
into the structured `vita.werdegang` / `vita.ausbildung`, then drop positionen.

Per string: parse "<date>: <role>, <institution>" (or "<role> bei <institution>")
into a structured item; education milestones (Dissertation/Diplom/Habilitation/
Promotion/B.A./M.Sc/...) route to `ausbildung`, everything else to `werdegang`.
Items that duplicate an existing structured entry are skipped — either a shared
distinctive institution token, OR (for common institutions like FU Berlin) a
matching year plus an overlapping role word. Legacy strings have no source, so
merged items get `quelle` = the person's FU page (or personal site).

    python research/merge_legacy_vita.py            # DRY-RUN preview (default)
    python research/merge_legacy_vita.py --apply    # write changes
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fill_missing as fm

EDU_RE = re.compile(
    r'(Dissertation|Promotion|Habilitation|Diplomarbeit|Diplom|Diploma|Dipl\.|'
    r'Ph\.?\s?D|Dr\.|Studium|Bachelor|B\.?\s?Sc|B\.?\s?A\b|Master|M\.?\s?Sc|'
    r'M\.?\s?A\b|Magister|Staatsexamen|Vordiplom|Abitur|Bakkalaureat)', re.I)
YEAR_RE = re.compile(r'\d{4}')
SPLITS = (' bei ', ' at ', ' an der ', ' an dem ', ' am ')

GENERIC_STOP = {'und', 'der', 'die', 'das', 'für', 'des', 'von', 'the', 'and',
                'for', 'aus', 'dem', 'den', 'mit', 'in', 'an', 'am', 'bei',
                'at', 'of', 'als'}
INST_STOP = GENERIC_STOP | {
    'freie', 'freien', 'universität', 'university', 'berlin', 'institut',
    'institute', 'fakultät', 'fachbereich', 'mathematik', 'informatik',
    'computer', 'science', 'group', 'arbeitsgruppe', 'center', 'centre',
    'zentrum', 'gmbh', 'department'}


def parse(s):
    s = s.strip()
    # A leading date prefix is the text before the first ":" when it contains a
    # year and is short (e.g. "seit 1. April 1999", "09/2009-02/2011", "2024").
    zeit, rest = None, s
    if ':' in s:
        left, right = s.split(':', 1)
        if YEAR_RE.search(left) and len(left) <= 35:
            zeit, rest = left.strip(), right.strip()
    pos, inst = rest, ''
    for sep in SPLITS:
        if sep in rest:
            pos, inst = rest.split(sep, 1)
            break
    else:
        if ',' in rest:
            parts = [x.strip() for x in rest.split(',')]
            pos, inst = parts[0], ', '.join(parts[1:])
    return zeit, pos.strip(), inst.strip(), bool(EDU_RE.search(rest))


def toks(text, stop):
    return {t.lower() for t in re.findall(r'[A-Za-zÄÖÜäöüß]{3,}|[A-Z]{2,}', text or '')
            if t.lower() not in stop}


def year_of(s):
    m = YEAR_RE.search(s or '')
    return m.group(0) if m else None


def is_dup(zeit, pos, inst, existing, kind):
    p_inst, p_pos, p_year = toks(inst, INST_STOP), toks(pos, GENERIC_STOP), year_of(zeit)
    for it in existing:
        role = it.get('grad' if kind == 'ausbildung' else 'position', '')
        when = it.get('jahr' if kind == 'ausbildung' else 'zeitraum', '') or ''
        e_inst, e_pos = toks(it.get('institution', ''), INST_STOP), toks(role, GENERIC_STOP)
        if p_inst and (p_inst & e_inst):
            return True
        if p_year and p_year in when and (p_pos & e_pos):
            return True
    return False


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    data = fm.load_json(fm.DATASET_PATH, None)
    tot = {'werdegang': 0, 'ausbildung': 0, 'dup': 0, 'noinst': 0, 'people': 0}
    for p in data['personen']:
        positionen = p.get('vita', {}).get('positionen')
        if not positionen:
            continue
        tot['people'] += 1
        links = p.get('links', {}) or {}
        quelle = links.get('fu-berlin') or links.get('persoenlich') or \
            'https://www.mi.fu-berlin.de/inf/index.html'
        vita = p.setdefault('vita', {})
        werd, ausb = vita.setdefault('werdegang', []), vita.setdefault('ausbildung', [])
        added_w, added_a, dups, noinst = [], [], [], []
        for s in positionen:
            zeit, pos, inst, edu = parse(s)
            kind = 'ausbildung' if edu else 'werdegang'
            target = ausb if edu else werd
            if is_dup(zeit, pos, inst, target, kind):
                dups.append(s)
                tot['dup'] += 1
            elif not inst:
                noinst.append(s)
                tot['noinst'] += 1
            elif edu:
                item = {'grad': pos, 'institution': inst, 'quelle': quelle}
                if year_of(zeit):
                    item['jahr'] = year_of(zeit)
                added_a.append(item)
                tot['ausbildung'] += 1
            else:
                item = {'position': pos, 'institution': inst, 'quelle': quelle}
                if zeit:
                    item['zeitraum'] = zeit
                added_w.append(item)
                tot['werdegang'] += 1

        if not args.apply:
            if added_w or added_a or noinst:
                print(f"# {p['id']}")
            for it in added_w:
                z = f" ({it['zeitraum']})" if it.get('zeitraum') else ''
                print(f"   +werdegang : {it['position']} @ {it['institution']}{z}")
            for it in added_a:
                z = f" ({it['jahr']})" if it.get('jahr') else ''
                print(f"   +ausbildung: {it['grad']} @ {it['institution']}{z}")
            for s in noinst:
                print(f"   !no-institution(skip): {s[:75]}")
        else:
            werd.extend(added_w)
            ausb.extend(added_a)
            ausb.sort(key=lambda x: x.get('jahr', '9999'))
            vita.pop('positionen', None)
            fm.set_value(p, fm.LAST_UPDATED_KEY, fm.now_iso())

    print('\n' + '=' * 60)
    print(f"{tot['people']} people | +{tot['werdegang']} werdegang, "
          f"+{tot['ausbildung']} ausbildung | {tot['dup']} dup-skipped, "
          f"{tot['noinst']} no-institution-skipped")
    if args.apply:
        fm.atomic_write_json(fm.DATASET_PATH, data)
        print('APPLIED. Legacy vita.positionen removed.')
    else:
        print('DRY-RUN — re-run with --apply to write.')


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""normalize_data.py — idempotent dataset cleanups for fu-informatik-data.json.

Currently: de-duplicate the publication year between `venue` and `jahr`. Agents
sometimes bake the year into the venue (e.g. venue "CCGrid 2014" + jahr "2014"),
which the modal renders as "...CCGrid 2014, 2014". This strips the redundant year
token out of `venue` (and tidies leftover empty parens / punctuation) so the year
shows once via `jahr`. Safe to run repeatedly.

    python research/normalize_data.py             # apply
    python research/normalize_data.py --dry-run   # report only
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fill_missing as fm


def dedup_venue_year(venue, jahr):
    """Return venue with the redundant `jahr` token removed and tidied."""
    if not venue or not jahr:
        return venue
    year = re.escape(str(jahr))
    if not re.search(r'\b' + year + r'\b', venue):
        return venue
    v = re.sub(r'\b' + year + r'\b', '', venue)
    v = re.sub(r'\(\s*\)', '', v)              # empty parens
    v = re.sub(r'\(\s+', '(', v)                # "( x" -> "(x"
    v = re.sub(r'\s+\)', ')', v)                # "x )" -> "x)"
    v = re.sub(r'\s{2,}', ' ', v)               # collapse spaces
    v = re.sub(r'\s+([,;:])', r'\1', v)         # " ," / " :" -> "," / ":"
    v = re.sub(r'([,;:])\s*([,;:])', r'\1', v)  # ", ;" -> ","
    return v.strip(' ,;:')


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    data = fm.load_json(fm.DATASET_PATH, None)
    if data is None:
        sys.exit(f'ABORT: dataset not found at {fm.DATASET_PATH}')

    changed, people = 0, set()
    for p in data['personen']:
        for pub in p.get('forschung', {}).get('veroeffentlichungen', []) or []:
            ven, jahr = pub.get('venue'), pub.get('jahr')
            if not ven:
                continue
            new = dedup_venue_year(ven, jahr)
            if new != ven:
                changed += 1
                people.add(p['id'])
                if args.dry_run:
                    print(f"  {p['id']}: {ven!r} -> {new!r}")
                elif new:
                    pub['venue'] = new
                else:
                    pub.pop('venue', None)

    if args.dry_run:
        print(f"\n{changed} venue values would change across {len(people)} people.")
        return
    fm.atomic_write_json(fm.DATASET_PATH, data)
    print(f"Normalized {changed} venue values across {len(people)} people.")


if __name__ == '__main__':
    main()

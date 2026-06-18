#!/usr/bin/env python3
"""session_queue.py — print the research queue as compact JSON for the
in-session sub-agent workflow, and (re)create the findings drop directory.

Reuses fill_missing.select(), so it honors fill-only, the deny-list, and the
not_found / rejected gating exactly like the claude -p runner. The workflow
fans one sub-agent out per queue entry; each writes its findings to
research/.session_findings/<id>.json; then apply_findings.py merges them.

    python research/session_queue.py            # people still missing fields
    python research/session_queue.py --groups   # groups (AG descriptions)
    python research/session_queue.py --all       # people + groups
    python research/session_queue.py --ids a,b   # only these ids
    python research/session_queue.py --retry-not-found
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fill_missing as fm
import apply_findings as af


def _args(groups, retry):
    return argparse.Namespace(limit=None, ids=None, dry_run=True, groups=groups,
                              retry_not_found=retry, yes=True, concurrency=1)


def _build(data, state, skip, pics, groups, retry):
    queue, _ = fm.select(data, state, skip, pics, _args(groups, retry))
    mode = 'group' if groups else 'person'
    rows = []
    for entry, missing in queue:
        rows.append({
            'id': entry['id'], 'mode': mode,
            'name': entry.get('name', ''), 'titel': entry.get('titel', ''),
            'rolle': entry.get('rolle', ''),
            'missing': missing,
            'fu_url': (entry.get('links', {}) or {}).get('fu-berlin', ''),
            'website': entry.get('website', ''),
        })
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--groups', action='store_true')
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--ids')
    ap.add_argument('--retry-not-found', action='store_true')
    args = ap.parse_args()

    data = fm.load_json(fm.DATASET_PATH, None)
    if data is None:
        sys.exit(f'ABORT: dataset not found at {fm.DATASET_PATH}')
    fm.migrate_website_key(data)
    state, skip = fm.load_state(), fm.load_skip()
    pics = fm.load_json(fm.PROFILE_PICS_PATH, {})
    af.FINDINGS_DIR.mkdir(exist_ok=True)

    rows = []
    if args.all or not args.groups:
        rows += _build(data, state, skip, pics, False, args.retry_not_found)
    if args.all or args.groups:
        rows += _build(data, state, skip, pics, True, args.retry_not_found)
    if args.ids:
        want = {i.strip() for i in args.ids.split(',') if i.strip()}
        rows = [r for r in rows if r['id'] in want]
    print(json.dumps(rows, ensure_ascii=False))


if __name__ == '__main__':
    main()

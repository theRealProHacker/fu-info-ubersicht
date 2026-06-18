#!/usr/bin/env python3
"""apply_findings.py — merge findings produced by in-session research sub-agents
into research/fu-informatik-data.json, reusing fill_missing.py's validation,
merge, provenance, deny-list and last_updated logic unchanged.

Each sub-agent writes ONE file research/.session_findings/<id>.json containing
either a bare findings object {fields, sources, not_found} or an envelope
{"id": ..., "mode": "person"|"group", "findings": {...}}. This driver loads
them all and runs the EXACT same validate()/merge() pipeline as the claude -p
runner, so the integrity guarantees are identical. Fill-only and the deny-list
are honored; every merged fact is recorded in provenance.jsonl.

The claude -p runner (fill_missing.py) is unchanged and remains the tool for
adding new people later; this is just an alternate research transport.

Usage:
    python research/apply_findings.py             # merge all files in the dir
    python research/apply_findings.py --dir PATH
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fill_missing as fm

FINDINGS_DIR = fm.RESEARCH_DIR / '.session_findings'


def load_findings_files(dir_path):
    """Returns [(entry_id, mode, findings, filename)] from *.json in dir_path."""
    items = []
    for fp in sorted(dir_path.glob('*.json')):
        try:
            # raw_decode tolerates trailing junk after the JSON object (an agent
            # occasionally appends a stray brace or note).
            obj, _ = json.JSONDecoder().raw_decode(
                fp.read_text(encoding='utf-8').lstrip())
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            print(f'  SKIP {fp.name}: unreadable ({exc})')
            continue
        if isinstance(obj, dict) and 'findings' in obj:
            items.append((obj.get('id') or fp.stem, obj.get('mode', 'person'),
                          obj.get('findings'), fp.name))
        else:
            items.append((fp.stem, 'person', obj, fp.name))
    return items


def apply_one(entry, findings, mode, eid, data, state, skip, profile_pics,
              totals, rejection_reasons):
    """Validate → merge → provenance → state for one entry. Returns 1 if a new
    profile picture URL was merged, else 0. Mirrors the runner's record_success
    but reads its findings from a file instead of a live agent."""
    accepted, rejected, not_found = fm.validate(findings, entry, mode)
    # validate() does not consult the deny-list; honor it here (the runner does
    # this earlier, at queue selection).
    for path in [p for p in accepted if fm.is_skipped(skip, mode, eid, p)]:
        del accepted[path]
    merged, conflicts = fm.merge(entry, accepted, profile_pics)

    fm.set_value(entry, fm.LAST_UPDATED_KEY, fm.now_iso())
    # Dataset first, state last (same crash-safety ordering as the runner).
    fm.atomic_write_json(fm.DATASET_PATH, data)
    fm.atomic_write_json(fm.PROFILE_PICS_PATH, profile_pics)

    records = []
    for path, item in merged.items():
        if path in fm.OBJ_ARRAY_FIELDS:
            for idx, element in enumerate(item['value']):
                records.append({'ts': fm.now_iso(), 'id': eid, 'mode': mode,
                                'action': 'merged', 'field': f'{path}[{idx}]',
                                'value': element, 'source': element.get('quelle')})
        else:
            records.append({'ts': fm.now_iso(), 'id': eid, 'mode': mode,
                            'action': 'merged', 'field': path,
                            'value': item['value'], 'source': item['source']})
        fm.set_field_state(state, mode, eid, path, 'filled')
    for rej in rejected:
        records.append({'ts': fm.now_iso(), 'id': eid, 'mode': mode,
                        'action': 'rejected', 'field': rej['path'],
                        'reason': rej['reason']})
        rejection_reasons[rej['reason']] = rejection_reasons.get(rej['reason'], 0) + 1
        prev = fm.field_state(state, mode, eid, rej['path'])
        attempts = prev.get('attempts', 0) + 1
        fm.set_field_state(state, mode, eid, rej['path'],
                           'not_found' if attempts >= 3 else 'rejected',
                           attempts=attempts)
    for path in conflicts:
        records.append({'ts': fm.now_iso(), 'id': eid, 'mode': mode,
                        'action': 'conflict', 'field': path})
    for path in not_found:
        records.append({'ts': fm.now_iso(), 'id': eid, 'mode': mode,
                        'action': 'not_found', 'field': path})
        fm.set_field_state(state, mode, eid, path, 'not_found')

    bucket = fm.state_bucket(state, mode)
    bucket.setdefault(eid, {'fields': {}})
    bucket[eid].update({
        'status': 'done' if not rejected and not not_found else 'partial',
        'last_run': fm.now_iso()})
    fm.atomic_write_json(fm.STATE_PATH, state)
    fm.append_provenance(records)

    totals['entries'] += 1
    totals['filled'] += len(merged)
    totals['not_found'] += len(not_found)
    totals['rejected'] += len(rejected)
    totals['conflicts'] += len(conflicts)
    top = rejected[0]['reason'] if rejected else ''
    print(f"  {eid} ({mode}): {len(merged)} filled, {len(not_found)} not_found, "
          f"{len(rejected)} rejected" + (f' ({top})' if top else ''))
    return 1 if 'profilbild' in merged else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--dir', default=str(FINDINGS_DIR),
                    help='directory of <id>.json findings files')
    args = ap.parse_args()
    sys.stdout.reconfigure(line_buffering=True)

    fm.check_auth_env()
    dir_path = Path(args.dir)
    if not dir_path.exists():
        sys.exit(f'ABORT: findings dir not found: {dir_path}')

    data = fm.load_json(fm.DATASET_PATH, None)
    if data is None:
        sys.exit(f'ABORT: dataset not found at {fm.DATASET_PATH}')
    fm.migrate_website_key(data)
    state = fm.load_state()
    skip = fm.load_skip()
    profile_pics = fm.load_json(fm.PROFILE_PICS_PATH, {})
    by = {'person': {p['id']: p for p in data['personen']},
          'group': {g['id']: g for g in data['gruppen']}}

    totals = {'entries': 0, 'filled': 0, 'not_found': 0, 'rejected': 0,
              'conflicts': 0, 'skipped': 0}
    rejection_reasons = {}
    new_pics = 0

    for eid, mode, findings, fname in load_findings_files(dir_path):
        entry = by.get(mode, {}).get(eid)
        if entry is None:
            print(f'  SKIP {fname}: no {mode} with id {eid!r}')
            totals['skipped'] += 1
            continue
        if not isinstance(findings, dict):
            print(f'  SKIP {fname}: findings is not an object')
            totals['skipped'] += 1
            continue
        skip_bucket = skip['groups' if mode == 'group' else 'people']
        if skip_bucket.get(eid) is True:
            print(f'  SKIP {fname}: {eid} is deny-listed')
            totals['skipped'] += 1
            continue
        new_pics += apply_one(entry, findings, mode, eid, data, state, skip,
                              profile_pics, totals, rejection_reasons)

    if new_pics:
        print(f'\n{new_pics} new profile picture URL(s) found — downloading...')
        subprocess.run([sys.executable, str(fm.REPO_ROOT / 'download_images.py')],
                       cwd=fm.REPO_ROOT)

    print('\n' + '=' * 60)
    print(f"Applied {totals['entries']} entries: {totals['filled']} fields filled, "
          f"{totals['not_found']} not found, {totals['rejected']} rejected, "
          f"{totals['conflicts']} conflicts, {totals['skipped']} skipped.")
    if rejection_reasons:
        print('Rejections by reason:')
        for reason, count in sorted(rejection_reasons.items(), key=lambda kv: -kv[1]):
            print(f'  {count}x {reason}')
    print('=' * 60)


if __name__ == '__main__':
    main()

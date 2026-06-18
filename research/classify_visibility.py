#!/usr/bin/env python3
"""classify_visibility.py — decide which people/groups no longer exist at the
FU Informatik institute and should be hidden from the chart.

Inputs:
  research/fu-informatik-data.json   (the dataset)
  research/.verify_groups.json       (live roster verification, per group)

Rule (agreed with the user):
  GROUP  hide if live status is 'dissolved' or 'moved'; keep 'active'/'vacant'/'renamed'.
  PERSON hide if any of:
     - moved_away to another institution, OR
     - every group they belong to is hidden (orphaned), OR
     - not currently listed on the FU page AND not teaching recently, OR
     - listed only as retired/emeritus/a.D. AND not teaching recently.
  "teaching recently" = a course in CUTOFF or later.
Emeritus professors who STILL teach (Rote, Alt) are therefore kept.
"""
import json, re
from pathlib import Path

D = Path(__file__).resolve().parent
CUTOFF = 2024

data = json.loads((D / 'fu-informatik-data.json').read_text())
groups = json.loads((D / '.verify_groups.json').read_text())
gmap = {g['group_id']: g for g in groups}
pv = {pr['id']: pr for g in groups for pr in g.get('people', [])}


def recent_year(p):
    kurse = (p.get('lehre') or {}).get('kurse') or []
    ys = [int(m) for c in kurse for m in re.findall(r'(20\d{2})', str(c.get('semester', '')))]
    return max(ys) if ys else None


hidden_groups = set()
group_rows = []
for g in data['gruppen']:
    if g.get('type') != 'ag':
        continue
    v = gmap.get(g['id'], {})
    st = v.get('group_status', 'unknown')
    hide = st in ('dissolved', 'moved')
    if hide:
        hidden_groups.add(g['id'])
    group_rows.append((g['id'], hide, st, v.get('group_note', '')))

hidden_people = []
kept_notable = []
for p in data['personen']:
    ry = recent_year(p)
    info = pv.get(p['id'], {})
    listed = info.get('listed_now')
    retired = bool(info.get('listed_as_retired'))
    moved = bool(info.get('moved_away'))
    grps = p.get('gruppen') or []
    orphan = bool(grps) and all(gid in hidden_groups for gid in grps)
    teaches = ry is not None and ry >= CUTOFF

    hide, reason = False, ''
    if moved:
        hide, reason = True, 'moved to another institution'
    elif orphan:
        hide, reason = True, 'group no longer exists (' + ','.join(grps) + ')'
    elif listed is False and not teaches:
        hide, reason = True, f'not on current FU page; last taught {ry}'
    elif retired and not teaches:
        hide, reason = True, f'listed retired/a.D.; last taught {ry}'

    rec = {'id': p['id'], 'name': p['name'], 'reason': reason, 'last_taught': ry,
           'listed_now': listed, 'retired': retired, 'moved': moved, 'groups': grps,
           'note': info.get('note', '')}
    if hide:
        hidden_people.append(rec)
    elif retired or (ry is not None and ry < CUTOFF) or p.get('status'):
        kept_notable.append(rec)

out = {
    'cutoff': CUTOFF,
    'hidden_groups': sorted(hidden_groups),
    'hidden_people': hidden_people,
    'kept_notable': kept_notable,
}
(D / '.visibility_decision.json').write_text(json.dumps(out, ensure_ascii=False, indent=1))

print('GROUPS:')
for gid, hide, st, note in group_rows:
    print(f"  {'HIDE' if hide else 'keep':<4} {gid:<11} {st:<10} {note[:62]}")
print(f"\nHIDE PEOPLE ({len(hidden_people)}):")
for r in hidden_people:
    print(f"  {r['id']:<22} {r['reason']:<42} listed={r['listed_now']} retired={r['retired']} moved={r['moved']}")
print(f"\nKEPT-NOTABLE ({len(kept_notable)}) (emeritus-still-teaching / old data / status flag):")
for r in kept_notable:
    print(f"  {r['id']:<22} last_taught={r['last_taught']} listed={r['listed_now']} retired={r['retired']} :: {r['note'][:40]}")
print(f"\n>>> hide {len(hidden_people)} people + {len(hidden_groups)} groups: {sorted(hidden_groups)}")

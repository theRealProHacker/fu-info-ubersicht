#!/usr/bin/env python3
"""apply_visibility.py — mark departed people and dissolved/moved groups with
`sichtbar: false` so the chart hides them. Curation edit (like the existing
status flags), recorded in provenance.jsonl. Idempotent.

Reads research/.visibility_decision.json (produced by classify_visibility.py)
and patches research/fu-informatik-data.json in place.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

D = Path(__file__).resolve().parent
DATASET = D / 'fu-informatik-data.json'
DECISION = D / '.visibility_decision.json'
PROV = D / 'provenance.jsonl'
TS = datetime.now(timezone.utc).isoformat(timespec='seconds')

data = json.loads(DATASET.read_text())
dec = json.loads(DECISION.read_text())

# Descriptive status to record alongside the visibility flag (only set if the
# entry doesn't already carry one). Functional hiding is driven by `sichtbar`.
PERSON_STATUS = {
    'gerhold-lars': 'ausgeschieden',
    'esponda-margarita': 'ehemalig',
    'shang-zhihao': 'ehemalig', 'wu-han': 'ehemalig',
    'peng-guang': 'ehemalig', 'ma-xuyang': 'ehemalig',
}
GROUP_STATUS = {  # overwrite: these were stale/contradictory
    'ag-intdis': 'aufgeloest', 'ag-kiml': 'aufgeloest', 'ag-pr': 'aufgeloest',
    'ag-ilab': 'professor-gewechselt',
}

prov = []
pmap = {p['id']: p for p in data['personen']}
gmap = {g['id']: g for g in data['gruppen']}

hide_people = {r['id']: r for r in dec['hidden_people']}
for pid, r in hide_people.items():
    p = pmap.get(pid)
    if not p:
        continue
    p['sichtbar'] = False
    if pid in PERSON_STATUS and not p.get('status'):
        p['status'] = PERSON_STATUS[pid]
    prov.append({'ts': TS, 'id': pid, 'mode': 'person', 'action': 'hidden',
                 'field': 'sichtbar', 'value': False, 'note': r['reason'],
                 'source': r.get('note', '') or 'live FU roster verification'})

for gid in dec['hidden_groups']:
    g = gmap.get(gid)
    if not g:
        continue
    g['sichtbar'] = False
    if gid in GROUP_STATUS:
        g['status'] = GROUP_STATUS[gid]
    prov.append({'ts': TS, 'id': gid, 'mode': 'group', 'action': 'hidden',
                 'field': 'sichtbar', 'value': False,
                 'note': 'group no longer active at the institute',
                 'source': 'https://www.mi.fu-berlin.de/inf/research/groups/index.html'})

# Bump metadata
md = data.setdefault('metadaten', {})
md['aktualisiert'] = TS
md['bemerkung'] = (f"Sichtbarkeit aktualisiert {TS[:10]}: {len(hide_people)} ausgeschiedene "
                   f"Personen und {len(dec['hidden_groups'])} aufgeloeste/verschobene Gruppen "
                   f"ausgeblendet (sichtbar:false), per Live-Abgleich mit den FU-Seiten.")

DATASET.write_text(json.dumps(data, ensure_ascii=False, indent=4))
with PROV.open('a') as f:
    for rec in prov:
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')

print(f"Applied: {len(hide_people)} people + {len(dec['hidden_groups'])} groups hidden.")
print("People:", ', '.join(hide_people))
print("Groups:", ', '.join(dec['hidden_groups']))
print(f"Provenance: +{len(prov)} records.")

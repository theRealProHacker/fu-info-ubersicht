#!/usr/bin/env python3
"""fetch_members.py — set each group's `mitarbeiter_url` (the live FU members
page the site's "Weitere Mitarbeiter" link points at) and, advisorily, list a
group's current roster from the uniform FU CMS staff template.

The members-page URL is NOT uniform across AGs (it is *not* always
`…/staff/0Current`), so the working URL per group is curated here from research
and validated through fill_missing.validate_field (host must be fu-berlin.de or
the group's own website host) before writing. Reachability is checked in report
mode.

The FU CMS renders each person as `div.box-staff-list-item` with
`h3.box-staff-list-item-name a` / `p.box-staff-list-item-type` /
`…-item-email`, grouped under `h2.box-staff-list-table-category` — static HTML,
parseable with the stdlib. `--roster <group>` prints that roster. It is ADVISORY
only: new people still go through fill_missing.py's validate(); this script never
creates `personen` and never invents facts.

Modes:
  python3 fetch_members.py              # REPORT mitarbeiter_url per group + reachability
  python3 fetch_members.py --apply      # write group.mitarbeiter_url + provenance
  python3 fetch_members.py --roster ag-ti   # advisory: current roster from the page
"""
import json
import re
import sys
import html as htmllib
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import fill_missing as fm

D = Path(__file__).resolve().parent
DATASET = D / 'fu-informatik-data.json'
PROV = D / 'provenance.jsonl'
UA = 'Mozilla/5.0 (compatible; fu-info-uebersicht/1.0; member roster)'

# Curated per-group live current-members page (researched June 2026). The URL
# pattern is non-uniform — confirm each by fetching before changing.
MEMBER_URLS = {
    'ag-abi':   'https://www.mi.fu-berlin.de/en/inf/groups/abi/members/index.html',
    'ag-bds':   'https://www.mi.fu-berlin.de/en/inf/groups/ag-bds/staff/index.html',
    'ag-dilis': 'https://www.mi.fu-berlin.de/w/DILIS/Team',
    'ag-tech':  'https://www.mi.fu-berlin.de/inf/groups/ag-tech/staff/0Current/',
    'ag-comm':  'https://www.mi.fu-berlin.de/en/inf/groups/ag-comm/team-members/index.html',
    'ag-sse':   'https://www.mi.fu-berlin.de/inf/groups/ag-sse/members/index.html',
    'ag-ki':    'https://www.mi.fu-berlin.de/inf/groups/ag-ki/members/index.html',
    'ag-db':    'https://www.mi.fu-berlin.de/en/inf/groups/ag-db/members/index.html',
    'ag-csw':   'https://www.mi.fu-berlin.de/inf/groups/ag-csw/Members/members/index.html',
    'ag-hcc':   'https://www.mi.fu-berlin.de/en/inf/groups/hcc/members/index.html',
    'ag-ddi':   'https://www.mi.fu-berlin.de/inf/groups/ag-ddi/team/index.html',
    'ag-si':    'https://www.mi.fu-berlin.de/inf/groups/ag-si/members/index.html',
    'ag-idm':   'https://www.mi.fu-berlin.de/inf/groups/ag-idm/members/index.html',
    'ag-se':    'https://www.mi.fu-berlin.de/w/SE/PeopleHome',
    'ag-ti':    'https://www.mi.fu-berlin.de/inf/groups/ag-ti/members/index.html',
    'ag-dds':   'https://www.mi.fu-berlin.de/en/inf/groups/ag-dds/staff/index.html',
    'ag-vct':   'https://www.hhi.fraunhofer.de/abteilungen/vca/forschungsgruppen/'
                'videokodierungstechnologien/team.html',
}

NAME_RE = re.compile(r'box-staff-list-item-name[^>]*>\s*<a[^>]*>(.*?)</a>', re.S)
TYPE_RE = re.compile(r'box-staff-list-item-type[^>]*>(.*?)</p>', re.S)
CAT_RE = re.compile(r'box-staff-list-table-category[^>]*>(.*?)</', re.S)


def clean(s):
    return htmllib.unescape(re.sub(r'<[^>]+>', '', s or '')).strip()


def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, r.read().decode('utf-8', 'replace')


def reachable(url):
    try:
        status, _ = fetch(url)
        return status
    except Exception as e:                       # noqa: BLE001 (report-only)
        return f'ERR {e}'


def parse_roster(html_text):
    """[(name, role)] from the FU box-staff-list template (advisory)."""
    out = []
    for block in re.split(r'box-staff-list-item\b', html_text)[1:]:
        nm = NAME_RE.search('box-staff-list-item-name' + block) \
            or re.search(r'-name[^>]*>\s*<a[^>]*>(.*?)</a>', block, re.S)
        if not nm:
            continue
        tp = TYPE_RE.search(block)
        out.append((clean(nm.group(1)), clean(tp.group(1)) if tp else ''))
    return out


def main():
    args = sys.argv[1:]
    if '--roster' in args:
        gid = args[args.index('--roster') + 1]
        url = MEMBER_URLS.get(gid)
        if not url:
            sys.exit(f'no member URL for {gid}; known: {", ".join(sorted(MEMBER_URLS))}')
        status, html_text = fetch(url)
        roster = parse_roster(html_text)
        print(f'{gid}  {url}  (HTTP {status})')
        if not roster:
            print('  (no box-staff-list items — page uses a non-CMS template, '
                  'e.g. Foswiki; parse manually)')
        for name, role in roster:
            print(f'    {name:<34} {role}')
        print('\nADVISORY only — additions go through fill_missing.py.')
        return

    apply = '--apply' in args
    data = json.loads(DATASET.read_text(encoding='utf-8'))
    gmap = {g['id']: g for g in data['gruppen']}

    prov, changes = [], 0
    ts = datetime.now(timezone.utc).isoformat(timespec='seconds')
    for gid, url in MEMBER_URLS.items():
        g = gmap.get(gid)
        if not g:
            print(f'  ?? {gid}: not in dataset — skipped')
            continue
        if g.get('sichtbar') is False:
            continue
        err = fm.validate_field('mitarbeiter_url', url, url, g, 'group')
        status = '' if apply else f'  [{reachable(url)}]'
        if err:
            print(f'  !! {gid}: REJECTED — {err}')
            continue
        cur = g.get('mitarbeiter_url')
        mark = 'set' if cur != url else 'ok '
        print(f'  {mark} {gid:<9} {url}{status}')
        if cur != url:
            changes += 1
            if apply:
                g['mitarbeiter_url'] = url
                prov.append({'ts': ts, 'id': gid, 'mode': 'group',
                             'action': 'updated', 'field': 'mitarbeiter_url',
                             'value': url, 'note': 'live current-members page',
                             'source': url})

    print(f'\n{changes} group(s) need mitarbeiter_url.')
    if not apply:
        print('(report only — re-run with --apply to write mitarbeiter_url)')
        return
    DATASET.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding='utf-8')
    with PROV.open('a', encoding='utf-8') as f:
        for r in prov:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    print(f'WROTE mitarbeiter_url for {len(prov)} groups + {len(prov)} provenance records.')


if __name__ == '__main__':
    main()

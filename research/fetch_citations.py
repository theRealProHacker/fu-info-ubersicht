#!/usr/bin/env python3
"""fetch_citations.py — add a per-paper citation count
(`forschung.veroeffentlichungen[].zitationen`) via the Semantic Scholar Graph
API, resolved by DOI (from the paper `url`) else by a guarded title match.

Deterministic maintenance tool (like fetch_courses.py): report-first; `--apply`
writes `zitationen` + provenance. A paper is left untouched when it can't be
resolved confidently (logged, never guessed). The citation count powers the
"Meistzitiert" badge and the citation sort in app.js.

Modes:
  python3 fetch_citations.py                 # REPORT resolved counts. No write.
  python3 fetch_citations.py --apply         # write zitationen + provenance.
  python3 fetch_citations.py --ids prechelt-lutz,rote-guenter   # subset
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

D = Path(__file__).resolve().parent
DATASET = D / 'fu-informatik-data.json'
PROV = D / 'provenance.jsonl'

API = 'https://api.semanticscholar.org/graph/v1/paper'
FIELDS = 'fields=citationCount,title,year'
UA = 'Mozilla/5.0 (compatible; fu-info-uebersicht/1.0; citation refresh)'
DOI_RE = re.compile(r'(10\.\d{4,9}/[^\s"<>]+)')
TITLE_MATCH_MIN = 0.6   # token-Jaccard floor for accepting a title search hit


def tokens(s):
    return {w for w in re.findall(r'\w+', (s or '').lower(), re.U) if len(w) > 1}


def jaccard(a, b):
    ta, tb = tokens(a), tokens(b)
    return len(ta & tb) / len(ta | tb) if (ta and tb) else 0.0


def api_get(path):
    """GET with one polite retry on 429/5xx. Returns parsed JSON or None."""
    url = f'{API}/{path}'
    for attempt in range(3):
        req = urllib.request.Request(url, headers={'User-Agent': UA})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode('utf-8', 'replace'))
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and attempt < 2:
                time.sleep(2 + 3 * attempt)
                continue
            return None
        except Exception:                         # noqa: BLE001
            return None
    return None


def resolve(paper):
    """(citationCount, how) for one paper, or (None, reason)."""
    doi_m = DOI_RE.search(paper.get('url', '') or '')
    if doi_m:
        doi = doi_m.group(1).rstrip('.,;)')
        data = api_get(f'DOI:{urllib.parse.quote(doi)}?{FIELDS}')
        if data and data.get('citationCount') is not None:
            return data['citationCount'], f'doi:{doi}'
    # Title search fallback — only accept a strong token match.
    q = urllib.parse.quote(paper.get('titel', ''))
    data = api_get(f'search?query={q}&limit=3&{FIELDS}')
    best = None
    for hit in (data or {}).get('data', []) or []:
        score = jaccard(paper.get('titel'), hit.get('title'))
        if hit.get('citationCount') is not None and (best is None or score > best[1]):
            best = (hit['citationCount'], score, hit.get('title'))
    if best and best[1] >= TITLE_MATCH_MIN:
        return best[0], f'title~{best[1]:.2f}'
    return None, 'unresolved'


def main():
    apply = '--apply' in sys.argv
    only = None
    if '--ids' in sys.argv:
        only = set(sys.argv[sys.argv.index('--ids') + 1].split(','))

    data = json.loads(DATASET.read_text(encoding='utf-8'))
    ts = datetime.now(timezone.utc).isoformat(timespec='seconds')
    prov, total_set = [], 0

    for p in data['personen']:
        if only and p['id'] not in only:
            continue
        pubs = (p.get('forschung') or {}).get('veroeffentlichungen') or []
        if not pubs:
            continue
        print(f"### {p['name']}")
        updated = 0
        for paper in pubs:
            count, how = resolve(paper)
            time.sleep(1.1)        # be polite to the unauthenticated API
            title = paper.get('titel', '')[:60]
            if count is None:
                print(f"    ? {title:<62} ({how})")
                continue
            print(f"    {count:>6}  {title:<62} ({how})")
            if apply:
                paper['zitationen'] = int(count)
            updated += 1
        if apply and updated:
            total_set += updated
            prov.append({'ts': ts, 'id': p['id'], 'mode': 'person',
                         'action': 'updated', 'field': 'forschung.veroeffentlichungen[].zitationen',
                         'value': updated, 'note': 'per-paper citation count',
                         'source': 'https://www.semanticscholar.org/'})
        print()

    if not apply:
        print('(report only — re-run with --apply to write zitationen)')
        return
    DATASET.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding='utf-8')
    with PROV.open('a', encoding='utf-8') as f:
        for r in prov:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    print(f"WROTE zitationen for {total_set} papers across {len(prov)} people.")


if __name__ == '__main__':
    main()

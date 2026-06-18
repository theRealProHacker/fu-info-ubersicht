#!/usr/bin/env python3
"""make_workflow.py — generate the in-session research Workflow script with the
current queue baked in, so no large data has to be passed as workflow args.

Regular flow (also how you add new people later):
    python research/make_workflow.py --all      # prints a scriptPath
    # -> invoke the Workflow tool with that scriptPath (one sub-agent per entry)
    python research/apply_findings.py            # merge what the agents wrote

The queue comes from session_queue/fill_missing.select(), so fill-only, the
deny-list and not_found/rejected gating are all honored. Each sub-agent writes
research/.session_findings/<id>.json; apply_findings.py merges those.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fill_missing as fm
import apply_findings as af
import session_queue as sq

RULES = "\n".join([
    'HARD RULES:',
    '1. Never invent or infer a fact. Only report what you actually read on a page. If you cannot verify a field, put its dotted path in "not_found". Sparse but honest beats complete but guessed.',
    '2. Every field needs a real source URL whose page actually contains the fact.',
    '3. Profile links (github, linkedin, orcid, google-scholar, dblp, mastodon, persoenlich) and scholar metrics: report them ONLY if the page shows an FU Berlin / Informatik affiliation or other strong corroboration. A bare name match is not enough. When unsure -> not_found.',
    '4. Plain text only: never use < > " or backtick characters in any value. Preserve umlauts exactly (Mueller stays Mueller written as Müller). Transcribe, do not paraphrase.',
    '',
    'FIELDS SCHEMA (include in "fields" ONLY the requested missing fields you actually found):',
    'Simple fields (each needs one URL in the "sources" map keyed by the dotted path):',
    '  kontakt.email, kontakt.telefon, kontakt.sprechstunde, links.fu-berlin, links.persoenlich,',
    '  links.github, links.linkedin, links.orcid, links.google-scholar, links.dblp, links.mastodon,',
    '  forschung.interessen (array of 3-8 short research-topic keywords),',
    '  forschung.publikationen (ONE URL to the full publication list),',
    '  lehre.kurse (array of {name, semester}), profilbild (direct image URL),',
    '  beschreibung (GROUPS ONLY: 2-3 German sentences sourced from the group website).',
    'Structured SELF-SOURCING arrays (each ITEM carries its own "quelle" URL inline; do NOT add these to the "sources" map):',
    '  vita.ausbildung  (education, OLDEST first): items {grad, institution, quelle} + optional jahr, ort.',
    '  vita.werdegang   (career, NEWEST first): items {position, institution, quelle} + optional zeitraum, ort.',
    '                   Include postdocs, research/industry/prior/current roles; NOT board seats or committees.',
    '  forschung.veroeffentlichungen (selected papers, NEWEST first, MAX 8): items {titel, quelle} + optional jahr, venue, url.',
    '  Required per item: grad+institution (ausbildung), position+institution (werdegang), titel (veroeffentlichungen), plus quelle always.',
    '  jahr / zeitraum are OPTIONAL -- never invent a year; "Postdoc at Stanford" with no date is valid and useful.',
    'Structured metrics object (sourced via the "sources" map at key "forschung.scholar"):',
    '  forschung.scholar = {zitationen, h_index, i10_index, stand} -- integer metrics + stand "YYYY-MM" (required if any metric present).',
    '  The Scholar profile URL goes in links.google-scholar, NOT inside scholar.',
    '',
    'CV completeness: actively look for Bachelor/Diplom, Master, PhD/Promotion, Habilitation, every postdoc/position, and the current role -- check the FU page, personal site, LinkedIn, Google Scholar, DBLP, Wikipedia. A single German Diplom counts as Bachelor+Master; never split it.',
    'OUTPUT: every requested field must appear either in "fields" or in "not_found".',
])

JS_TEMPLATE = r'''export const meta = {
  name: 'fu-research-insession',
  description: 'Research FU Informatik people/groups via in-session sub-agents; each writes findings to research/.session_findings/<id>.json',
  phases: [{ title: 'Research', detail: 'one web-research sub-agent per entry' }],
}

const repo = "__REPO__"
const entries = __ENTRIES__
const RULES = __RULES__

function buildPrompt(e) {
  const findingsPath = repo + '/research/.session_findings/' + e.id + '.json'
  const who = e.mode === 'group'
    ? 'the FU Berlin Institut fuer Informatik research group "' + (e.name || e.id) + '" (id: ' + e.id + ')'
    : ((e.titel || '') + ' ' + (e.name || e.id)).trim() + ' (id: ' + e.id + '), ' + (e.rolle || '') + ' at FU Berlin Institut fuer Informatik'
  const lines = []
  lines.push('You are a careful web-research agent. Research ' + who + '.')
  if (e.fu_url) lines.push('Start from the FU profile page: ' + e.fu_url)
  if (e.website) lines.push('Group website (the ONLY allowed source for beschreibung): ' + e.website)
  lines.push('')
  lines.push('Research ONLY these missing fields (everything else is already known):')
  for (const m of e.missing) lines.push('  - ' + m)
  lines.push('')
  lines.push(RULES)
  lines.push('')
  lines.push('When finished, use your Write tool to save findings as ONE JSON object to EXACTLY this absolute path:')
  lines.push('  ' + findingsPath)
  lines.push('The file content must be exactly this shape and nothing else:')
  lines.push('  {"id": "' + e.id + '", "mode": "' + e.mode + '", "findings": {"fields": {}, "sources": {}, "not_found": []}}')
  lines.push('(fill in the fields/sources/not_found you actually researched.)')
  lines.push('Use your WebSearch and WebFetch tools. Do NOT edit any other file. Final reply can be a one-line status.')
  return lines.join('\n')
}

phase('Research')
log('Researching ' + entries.length + ' entries via in-session sub-agents (sonnet)...')
const results = await parallel(entries.map(e => () =>
  agent(buildPrompt(e), {
    label: (e.mode === 'group' ? 'group' : 'person') + ':' + e.id,
    phase: 'Research', model: 'sonnet', agentType: 'general-purpose',
  }).then(() => ({ id: e.id, ok: true })).catch(() => ({ id: e.id, ok: false }))
))
return { dispatched: entries.length, completed: results.filter(r => r && r.ok).length }
'''


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--groups', action='store_true')
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--ids')
    ap.add_argument('--retry-not-found', action='store_true')
    ap.add_argument('--out', default=str(af.FINDINGS_DIR / '_workflow.js'))
    args = ap.parse_args()

    data = fm.load_json(fm.DATASET_PATH, None)
    fm.migrate_website_key(data)
    state, skip = fm.load_state(), fm.load_skip()
    pics = fm.load_json(fm.PROFILE_PICS_PATH, {})
    af.FINDINGS_DIR.mkdir(exist_ok=True)

    rows = []
    if args.all or not args.groups:
        rows += sq._build(data, state, skip, pics, False, args.retry_not_found)
    if args.all or args.groups:
        rows += sq._build(data, state, skip, pics, True, args.retry_not_found)
    if args.ids:
        want = {i.strip() for i in args.ids.split(',') if i.strip()}
        rows = [r for r in rows if r['id'] in want]

    js = (JS_TEMPLATE
          .replace('__REPO__', str(fm.REPO_ROOT))
          .replace('__ENTRIES__', json.dumps(rows, ensure_ascii=True))
          .replace('__RULES__', json.dumps(RULES)))
    out = Path(args.out)
    out.write_text(js, encoding='utf-8')
    n_people = sum(1 for r in rows if r['mode'] == 'person')
    n_groups = sum(1 for r in rows if r['mode'] == 'group')
    print(f'wrote workflow for {len(rows)} entries ({n_people} people, {n_groups} groups)')
    print(out)


if __name__ == '__main__':
    main()

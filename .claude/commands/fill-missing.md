---
description: Fill missing person/group data in-session (subscription-only path, no headless agents)
---

Fill missing dataset fields using in-session subagents instead of the
headless runner. Same prompt, same validation, same fill-only merge —
this path draws plain session usage instead of Agent-SDK credits.

1. Get the queue: `python3 research/fill_missing.py --dry-run` (add
   `--groups` for the group pass, `--ids a,b` to scope). If the queue is
   empty, report that and stop.
2. For each queued entry (or the subset the user asked for), spawn ONE
   subagent (general-purpose, WebSearch/WebFetch only) whose prompt is
   `research/research_prompt.md` with the placeholders filled exactly the
   way `build_prompt()` in `research/fill_missing.py` does: `{{MODE}}`,
   `{{ENTRY_JSON}}` (the entry's JSON), `{{MISSING_FIELDS}}` (the dotted
   paths from the dry-run), `{{EXTRA_RULES}}` (rule 7 for restricted roles
   / groups — copy it from `build_prompt()`). The subagent returns the
   findings JSON; it must NEVER edit files.
3. Validate and merge each result through the same code path the runner
   uses — never hand-merge:

   ```bash
   python3 - << 'EOF'
   import json, sys
   sys.path.insert(0, 'research')
   import fill_missing as fm
   findings = json.loads('''<SUBAGENT_JSON_HERE>''')
   data = fm.load_json(fm.DATASET_PATH, None)
   fm.migrate_website_key(data)
   entry = next(p for p in data['personen'] if p['id'] == '<ENTRY_ID>')
   profile_pics = fm.load_json(fm.PROFILE_PICS_PATH, {})
   accepted, rejected, not_found = fm.validate(findings, entry, '<person|group>')
   merged, conflicts = fm.merge(entry, accepted, profile_pics)
   fm.atomic_write_json(fm.DATASET_PATH, data)
   fm.atomic_write_json(fm.PROFILE_PICS_PATH, profile_pics)
   records = [{'ts': fm.now_iso(), 'id': entry['id'], 'mode': '<person|group>',
               'action': 'merged', 'field': p, 'value': i['value'],
               'source': i['source']} for p, i in merged.items()]
   fm.append_provenance(records)
   print('merged:', list(merged), 'rejected:', rejected, 'not_found:', not_found)
   EOF
   ```

4. If any profile pictures were merged, run `python3 download_images.py`.
5. Report per entry: merged / rejected (with reasons) / not_found. Then
   remind the user to commit (checkpoint protocol in README).

Never bypass `validate()` — it is the only thing standing between web
content and the site's innerHTML.

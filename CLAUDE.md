# fu-info-ubersicht

Interactive overview of the FU Berlin Institut für Informatik: 21 research
groups (AGs), ~66 people, external partners. Static site (vanilla JS + HTML +
CSS), single data source: `research/fu-informatik-data.json`.

- Person/group data lives ONLY in `research/fu-informatik-data.json`. Never
  invent facts; every researched fact needs a source URL.
- Profile images: add the URL to `research/profile_pics.json`, then run
  `python3 download_images.py` — it downloads to `research/images/` and
  updates the JSON.
- Filling missing person/group data: `research/fill_missing.py` (see README
  "Daten pflegen") or the `/fill-missing` command. Never edit the dataset
  from agent research directly — everything goes through its `validate()`.
  The legacy `.agent/workflows/deep_research_person.md` is superseded.

## Skill routing

When the user's request matches an available skill, invoke it via the Skill tool. When in doubt, invoke the skill.

Key routing rules:
- Product ideas/brainstorming → invoke /office-hours
- Strategy/scope → invoke /plan-ceo-review
- Architecture → invoke /plan-eng-review
- Design system/plan review → invoke /design-consultation or /plan-design-review
- Full review pipeline → invoke /autoplan
- Bugs/errors → invoke /investigate
- QA/testing site behavior → invoke /qa or /qa-only
- Code review/diff check → invoke /review
- Visual polish → invoke /design-review
- Ship/deploy/PR → invoke /ship or /land-and-deploy
- Save progress → invoke /context-save
- Resume context → invoke /context-restore
- Author a backlog-ready spec/issue → invoke /spec

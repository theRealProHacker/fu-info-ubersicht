# FU-Info Übersicht — Research Spec (v2)

The authoritative rules for any AI workflow that researches people and groups
for this dataset. It governs **what** to collect, **how structured** it must be,
**in what order**, and **how completeness is pursued without ever fabricating**.

- **Audience:** the per-entry research agent (headless `claude -p` via
  `research/fill_missing.py`, or `/fill-missing` in-session) and the validating
  orchestrator that merges its output.
- **Relationship to other files:** this spec is canonical. The runtime prompt
  `research/research_prompt.md`, the validator `research/fill_missing.py`, and
  the renderer `app.js` are all **aligned to** this spec; where they currently
  diverge, see [§8 Implementation deltas](#8-implementation-deltas-todo).
  The legacy `.agent/workflows/deep_research_person.md` is superseded.
- **Single source of truth for data:** `research/fu-informatik-data.json`.
  Agents NEVER edit it directly — they return JSON, the orchestrator validates
  and merges (fill-only; existing values are never overwritten).

---

## 0. Prime directive — honesty over completeness

These laws are absolute. Violating any one makes an entire result worthless,
no matter how complete it looks. They override every other instruction in this
spec, including the completeness checklist in §3.

1. **Never invent or infer a fact.** Report only what you actually read on a
   page (or a search snippet, for link discovery). A sparse, honest answer is
   correct; a complete, guessed answer is a failure.
2. **Every fact carries a source URL**, and the cited page must *actually
   contain* the fact — not merely be a page you visited. (CV items source
   inline via `quelle`; all other fields via the `sources` map — see §6.)
3. **Identity corroboration for profile/social links** (github, linkedin,
   orcid, google-scholar, dblp, mastodon, researchgate, persoenlich): only
   return the link if the page or its snippet shows an FU Berlin / Informatik
   affiliation, or another strong corroborating signal (link *from* the
   person's own FU/personal page; matching research topics **and** location;
   a stated photo match). A bare name-slug match is **not** enough — common
   names surface other people. An empty/near-empty profile that matches only
   by name is not corroborated. When in doubt → `not_found`.
4. **Transcribe, don't paraphrase.** For research interests, degree names,
   subjects, positions and institutions, copy the source's own wording
   (shortening is fine, rewording is not). Preserve umlauts and diacritics
   exactly (für, Müller, Zürich — never fur, Muller, Zurich).
5. **Plain text only.** No HTML in any value. Never the characters
   `<`, `>`, `"`, or backtick. German or English values are both fine — prefer
   the language of the source.

**The completeness checklist (§3) drives *search effort*, never *presence*.**
It tells you what to keep looking for across multiple sources before giving up.
It NEVER licenses filling a gap with a plausible default. A milestone you
cannot verify is reported in `not_found` — full stop.

---

## 1. Scope of research

Raise the detail bar on **all** person fields, not just the CV:

| Field group | What to gather |
|---|---|
| `kontakt` | email, telefon, raum, ort (address), sprechstunde, webex |
| `links` | fu-berlin, persoenlich, github, linkedin, orcid, google-scholar, dblp, researchgate, mastodon, wikipedia |
| `vita.ausbildung` | **structured** education history (§2) |
| `vita.werdegang` | **structured** career history (§2) |
| `forschung` | interessen (research topics, 3–8 keywords), publikationen (URL to full list), **veroeffentlichungen** (selected papers — §3.1), **scholar** (Google Scholar citation metrics — §3.2) |
| `lehre` | kurse `[{name, semester}]`, material URL |
| `auszeichnungen` | `[{name, jahr}]` |
| `sonstiges.positionen` | concurrent functions/memberships (boards, committees) |
| `profilbild` | one image URL → downloaded by `download_images.py` |

(Plus a maintained — not researched — `last_updated` timestamp per entry; see §7.)

For **groups**, the researched fields are `beschreibung` (2–3 German sentences,
sourced ONLY from the group's own website) and `mitarbeiter_url` — the URL of the
group's live current-members/staff page (the target of the site's "Weitere
Mitarbeiter" link). The members-page URL is **not uniform** across AGs (it is *not*
always `…/staff/0Current`), so it is researched per group; it must point at the
group's own website host or any `fu-berlin.de` page. Usually set by
`fetch_members.py`.

**Restricted subjects.** For `Sekretariat` / `Projektassistentin` roles,
research ONLY `kontakt.email`, `kontakt.telefon`, `links.fu-berlin`,
`profilbild`, and ONLY from `fu-berlin.de` pages. Sparse entries here are
correct by policy, not a defect.

---

## 2. The CV — `vita.ausbildung` + `vita.werdegang`

The CV is split into two structured arrays so order and completeness are
machine-checkable. **Education reads forward (oldest first); career reads
backward (newest first).**

### 2.1 `vita.ausbildung` — education, OLDEST first

Array of objects, chronologically ascending (earliest degree first):

```json
"ausbildung": [
  {"grad": "B.Sc. Informatik",     "institution": "TU München",  "ort": "München", "jahr": "2005", "quelle": "https://…"},
  {"grad": "M.Sc. Informatik",     "institution": "TU München",  "jahr": "2007", "quelle": "https://…"},
  {"grad": "Dr. rer. nat.",        "institution": "ETH Zürich",  "jahr": "2011", "quelle": "https://…"}
]
```

| Key | Req? | Notes |
|---|---|---|
| `grad` | ✅ | Degree + subject, transcribed verbatim. e.g. `"B.Sc. Informatik"`, `"Diplom-Informatiker"`, `"Dr. rer. nat."`, `"Habilitation"`. |
| `institution` | ✅ | Awarding institution as named on the source. |
| `jahr` | — | Year awarded (string), **if stated**. A study-period range is allowed: `"2003–2008"`. Never invent it. |
| `ort` | — | City, if stated. Omit if unknown — never guess. |
| `quelle` | ✅ | Source URL that contains *this* entry (CV items are self-sourcing — see §6). |

**German degree reality:** many German academics hold a single **Diplom**
(or Magister / Staatsexamen) instead of a separate Bachelor + Master. Record
exactly what the source states — a Diplom entry satisfies the Bachelor+Master
portion of the checklist. Do not split a Diplom into an invented Bachelor and
Master.

### 2.2 `vita.werdegang` — career, NEWEST first

Array of objects, reverse-chronological (current position first):

```json
"werdegang": [
  {"position": "Professor",          "institution": "Freie Universität Berlin", "ort": "Berlin", "zeitraum": "seit 2015", "quelle": "https://…"},
  {"position": "Postdoc",            "institution": "MIT",                       "zeitraum": "2011–2013", "quelle": "https://…"},
  {"position": "Wissenschaftl. Mitarbeiter", "institution": "ETH Zürich",        "zeitraum": "2007–2011", "quelle": "https://…"}
]
```

| Key | Req? | Notes |
|---|---|---|
| `position` | ✅ | Role title, transcribed verbatim. |
| `institution` | ✅ | Employer / institution — **never blank**. For a freelance / self-employed role use `"freiberuflich"`; if truly unknown, omit the whole item. |
| `zeitraum` | — | `"seit YYYY"`, `"YYYY–YYYY"`, `"YYYY–heute"`, or a single `"YYYY"` — **if stated**. "Postdoc at Stanford" with no dates is valid; never invent dates. |
| `ort` | — | City, if stated. Omit if unknown. |
| `quelle` | ✅ | Source URL that contains *this* entry. |

**What belongs in `werdegang`:** the academic/professional career ladder —
postdocs, research positions, industry roles, prior professorships, the
current position, and an ongoing doctorate (`"seit 2022: Promotion (laufend)"`)
*only if sourced*. **What does NOT:** concurrent honorary functions, board
seats, committee memberships, editorships — those stay in
`sonstiges.positionen` (which already exists).

### 2.3 Completeness checklist (generic — applies to everyone)

For every person, actively search for each milestone below across multiple
sources (FU page → personal site → LinkedIn → Google Scholar → DBLP → Wikipedia)
before concluding it is unavailable:

```
[ Bachelor (or Diplom/Magister/Staatsexamen equivalent) ]
[ Master  (if held separately)                          ]
[ PhD / Promotion (Dr. / Dr.-Ing. / Dr. rer. nat.)      ]
[ Habilitation       (if present)                       ]
[ every Postdoc / research / industry / prior position  ]
[ the current position                                  ]
```

- The checklist is a **search target**, not an assertion that every person has
  all of these. A PhD student has no completed PhD; a research staffer may have
  no postdoc. That is fine — record what exists.
- A milestone you **search for and cannot verify** is reported in `not_found`
  (use the array path, e.g. `vita.ausbildung` when no education at all is
  findable). Never emit a placeholder entry to "represent" a gap.
- Prefer one authoritative CV/Vita page when it exists; otherwise assemble the
  arrays from multiple corroborating sources, each item citing the page it came
  from.

---

## 3. Field conventions (all other fields)

- **`kontakt.email`** — `name@…fu-berlin.de` form; must be a valid address.
- **`kontakt.telefon`** — e.g. `+49 30 838 75100`; must parse as a phone number.
- **`kontakt.raum` / `kontakt.ort`** — room number / postal address as printed.
- **`kontakt.sprechstunde`** — booking URL *or* free-text office hours, as published.
- **`links.fu-berlin`** — the subject's FU Berlin profile page.
- **`links.persoenlich`** — personal website (canonical key is `persoenlich`, NOT `website`).
- **`links.{github,linkedin,orcid,google-scholar,dblp,researchgate,mastodon}`** — profile URLs; **§0 rule 3 (corroboration) applies to every one.**
- **`forschung.interessen`** — array of 3–8 short keywords/phrases naming the person's **research topics**, transcribed in the source's own wording.
- **`forschung.publikationen`** — exactly ONE URL to the *full* publications list (DBLP, Scholar, or an institutional list).
- **`forschung.veroeffentlichungen`** — *structured* list of selected papers (schema in §3.1).
- **`forschung.scholar`** — *structured* Google Scholar citation metrics (schema in §3.2).
- **`lehre.kurse`** — array of `{name, semester}` (both keys required), e.g. `{"name": "Telematik", "semester": "WiSe 24/25"}`.
- **`lehre.material`** — URL to course-material page, if any.
- **`auszeichnungen`** — array of `{name, jahr}`.
- **`sonstiges.positionen`** — array of strings: concurrent functions/memberships.
- **`profilbild`** — direct image URL (jpg/png/webp), ideally from an FU page or the person's own site. Goes through `research/profile_pics.json` → `python3 download_images.py`, which stores it under `research/images/` and rewrites the JSON path. Never inline a remote URL into `profilbild` in the dataset.

### 3.1 `forschung.veroeffentlichungen` — selected publications

Array of selected papers, **newest first, capped at 8**. Prefer the author's
own "Selected Publications" list if they curate one; otherwise the most-cited
and/or most-recent. This is a *curated* list — `forschung.publikationen` still
holds the URL to the *full* list.

```json
"veroeffentlichungen": [
  {"titel": "Attention Is All You Need", "jahr": "2017", "venue": "NeurIPS", "url": "https://doi.org/…", "quelle": "https://…"}
]
```

| Key | Req? | Notes |
|---|---|---|
| `titel` | ✅ | Paper title, transcribed verbatim (preserve diacritics). |
| `jahr` | — | Year of publication, **if stated**. |
| `venue` | — | Conference/journal name, if stated — **WITHOUT the year** (the year lives in `jahr`): `"CCGrid"`, not `"CCGrid 2014"`. |
| `url` | — | DOI or canonical paper URL, if available. |
| `quelle` | ✅ | Page that lists this paper (self-sourcing — see §6). |
| `zitationen` | — | Per-paper citation count (non-negative integer). NOT hand-researched — set by `fetch_citations.py` (Semantic Scholar). Powers the "Meistzitiert" badge + citation sort. |
| `highlight` | — | Boolean curator flag. `true` pins a standout paper to the top of the list with a ★. Set manually, not by an agent. |

### 3.2 `forschung.scholar` — Google Scholar metrics

Citation metrics from the subject's Scholar profile. The profile URL lives in
`links.google-scholar` (don't duplicate it here). Metrics are point-in-time, so
`stand` is mandatory whenever any metric is present.

```json
"scholar": {"zitationen": 12450, "h_index": 58, "i10_index": 210, "stand": "2026-06"}
```

| Key | Req? | Notes |
|---|---|---|
| `zitationen` | — | Total citations, integer, as displayed. |
| `h_index` | — | h-index, integer. |
| `i10_index` | — | i10-index, integer. |
| `stand` | ✅* | As-of month, `YYYY-MM`. *Required if any metric is present. |

Source via the `sources` map (`"forschung.scholar"` → the Scholar profile URL).
**§0 rule 3 (corroboration) applies** — report metrics only from a Scholar
profile confirmed to be the subject's (FU / Informatik affiliation, or linked
from their own page). Empty or ambiguous profiles → `not_found`.

---

## 4. Source quality hierarchy

Prefer, in order:

1. The subject's **FU Berlin profile** page (`*.fu-berlin.de`).
2. The subject's **personal/institutional homepage** or a linked CV/Vita.
3. The subject's **own profiles** (Scholar, ORCID, DBLP, GitHub, LinkedIn) —
   usable as a source for the link itself and for facts they state, subject to
   §0 rule 3.
4. **Aggregators / third parties** (rankings, news, directories) — weakest;
   acceptable only to corroborate, not as the sole source for a CV milestone.

---

## 5. Query playbook

- `FU Berlin <name> <field>` (contact, vita, lehre, …)
- `<name> Informatik FU Berlin`
- `<name> CV` / `<name> Lebenslauf` / `<name> Vita`
- `<name> github` · `<name> linkedin` · `<name> dblp` · `<name> google scholar` · `<name> orcid`
- `<name> Promotion Dissertation` · `<name> Habilitation` (for CV milestones)
- `<name> Google Scholar citations h-index` · `<name> selected publications` (for §3.1/§3.2)
- Start from any `links` already present on the subject and crawl outward.

---

## 6. Output contract (what the agent returns)

Return EXACTLY ONE JSON object as the final message — no prose around it. Only
include fields you actually found; everything else goes in `not_found`.

```json
{
  "fields": {
    "kontakt": {"email": "x@inf.fu-berlin.de"},
    "links": {"github": "https://github.com/x"},
    "forschung": {
      "interessen": ["HCI", "ML"],
      "veroeffentlichungen": [
        {"titel": "…", "jahr": "2021", "venue": "CHI", "url": "https://doi.org/…", "quelle": "https://…"}
      ],
      "scholar": {"zitationen": 4200, "h_index": 31, "i10_index": 64, "stand": "2026-06"}
    },
    "vita": {
      "ausbildung": [
        {"grad": "Dr. rer. nat.", "institution": "ETH Zürich", "jahr": "2011", "quelle": "https://…"}
      ],
      "werdegang": [
        {"position": "Professor", "institution": "FU Berlin", "zeitraum": "seit 2015", "quelle": "https://…"}
      ]
    }
  },
  "sources": {
    "kontakt.email": "https://www.mi.fu-berlin.de/…",
    "links.github": "https://github.com/x",
    "forschung.interessen": "https://example.org/research",
    "forschung.scholar": "https://scholar.google.com/citations?user=…"
  },
  "not_found": ["links.linkedin", "vita.ausbildung"]
}
```

**Sourcing model:**
- Scalar and simple-array fields → one entry in the `sources` map per dotted
  path (array fields get one source for the whole array).
- `vita.ausbildung`, `vita.werdegang` and `forschung.veroeffentlichungen` →
  **self-sourcing**: every item carries its own `quelle`. These paths do **not**
  need an entry in the `sources` map (each item is independently sourced and
  provenance-logged). `forschung.scholar`, by contrast, takes one `sources`
  entry → the Scholar profile URL.
- Every requested field must appear either in `fields` or in `not_found`.

---

## 7. Merge & validation rules (orchestrator side)

- **Fill-only:** existing non-empty values are never overwritten.
- **Last-researched stamp:** every entry gets a `last_updated` ISO timestamp,
  overwritten on each research touch (independent of whether new facts were
  found). It is written by the orchestrator, never researched, and is exempt
  from fill-only.
- **Quarantine:** any field whose value or source fails validation is rejected,
  not merged; valid siblings still merge.
- **Lenient arrays:** within the structured arrays (`ausbildung` / `werdegang` /
  `veroeffentlichungen`), unknown keys and invalid OPTIONAL fields are dropped,
  and only items failing a REQUIRED key (grad/position/institution/titel +
  quelle) are discarded. Order is preserved; the array is rejected only if no
  valid item survives. A stray numeric `jahr` is coerced to a string.
- **Provenance:** every merged fact is appended to `research/provenance.jsonl`
  with its source URL — for self-sourcing arrays (`ausbildung`, `werdegang`,
  `veroeffentlichungen`), one provenance row per item (keyed by its `quelle`).
- **Resume / idempotent:** `not_found` fields are skipped on re-runs unless
  `--retry-not-found` (the semester refresh). `.fill_skip.json` is the takedown
  deny-list and is honored on every merge.
- **No API tokens:** the runner aborts if `ANTHROPIC_API_KEY` (or Bedrock/Vertex
  vars) is set — it must run on subscription auth only.

---

## 8. Implementation deltas (TODO)

This spec introduces structured CV fields. To make the codebase match it:

1. **`research/fill_missing.py`**
   - Add `vita.ausbildung`, `vita.werdegang`, `forschung.veroeffentlichungen`,
     `forschung.scholar` to `PERSON_FIELDS`; **remove the legacy
     `vita.positionen`** (or keep read-only for back-compat).
     (`links.google-scholar` is already in the list.)
   - Add an object-array validator (mirror the existing `lehre.kurse` branch at
     `validate_field`): require `grad/institution/jahr/quelle` for ausbildung,
     `position/institution/zeitraum/quelle` for werdegang, and
     `titel/jahr/quelle` for veroeffentlichungen (`venue`/`url` optional, cap 8);
     `ort` optional; run `check_url` on each item's `quelle` (and `url`);
     `clean_string` every text value; reject empty arrays.
   - Add a `forschung.scholar` object validator: integer `zitationen` /
     `h_index` / `i10_index` (all optional), required `stand` (`YYYY-MM`) when
     any metric is present; sourced via the `sources` map.
   - Teach `validate()` that the self-sourcing arrays (`ausbildung`, `werdegang`,
     `veroeffentlichungen`) need no top-level `sources` entry, and emit per-item
     provenance rows.
2. **`app.js`**
   - Replace the single `Werdegang` block (`person.vita?.positionen`, ~line 443)
     with two sections: **Ausbildung** (render `ausbildung` as-is, oldest→newest)
     and **Werdegang** (render `werdegang` as-is, newest→oldest). Format each
     object as `grad — institution, jahr` / `position — institution, zeitraum`.
   - Add a **Veröffentlichungen** section rendering `forschung.veroeffentlichungen`
     as `titel — venue, jahr` (linked to `url` when present), and a small
     **Zitationen** line from `forschung.scholar`
     (`h-index N · zitationen total · Stand YYYY-MM`).
   - Keep a fallback that renders legacy `vita.positionen` if present, until the
     dataset is fully migrated.
3. **`research/research_prompt.md`** — regenerate from this spec: new schema,
   the §2.3 checklist, the education-forward / career-backward ordering, and the
   self-sourcing CV rule.
4. **One-time data migration** — convert existing `vita.positionen` strings into
   `ausbildung` / `werdegang` objects where parseable; leave the rest for the
   next research pass.

---

*Spec version 2 · supersedes the flat `vita.positionen` model.*

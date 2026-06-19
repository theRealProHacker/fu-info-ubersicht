#!/usr/bin/env python3
"""
fill_missing.py — research loop that fills missing person/group data in
research/fu-informatik-data.json using headless Claude agents.

Agents only research and return JSON; they can never edit the dataset.
Only findings that pass validation are merged, fill-only (existing values
are never overwritten). Every merged fact gets a provenance record with a
source URL. Runs on the machine's Claude subscription login — aborts if an
API-key environment variable is set.

Quickstart:
    python research/fill_missing.py --dry-run        # see the queue
    python research/fill_missing.py --limit 5        # pilot
    python research/fill_missing.py                  # full person pass
    python research/fill_missing.py --groups         # group descriptions
    python research/fill_missing.py --retry-not-found  # semester refresh
"""

import argparse
import concurrent.futures as cf
import difflib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

RESEARCH_DIR = Path(__file__).resolve().parent
REPO_ROOT = RESEARCH_DIR.parent
DATASET_PATH = RESEARCH_DIR / 'fu-informatik-data.json'
STATE_PATH = RESEARCH_DIR / '.fill_state.json'      # gitignored, machine-local
SKIP_PATH = RESEARCH_DIR / '.fill_skip.json'        # committed deny-list
PROFILE_PICS_PATH = RESEARCH_DIR / 'profile_pics.json'
PROVENANCE_PATH = RESEARCH_DIR / 'provenance.jsonl'
PROMPT_PATH = RESEARCH_DIR / 'research_prompt.md'
LOG_DIR = RESEARCH_DIR / '.fill_logs'               # gitignored raw agent output
IMAGES_DIR = RESEARCH_DIR / 'images'

PERSON_FIELDS = [
    'kontakt.email', 'kontakt.telefon', 'kontakt.sprechstunde',
    'links.fu-berlin', 'links.persoenlich', 'links.github', 'links.linkedin',
    'links.orcid', 'links.google-scholar', 'links.dblp', 'links.mastodon',
    'forschung.interessen', 'forschung.publikationen',
    'forschung.veroeffentlichungen', 'forschung.scholar',
    'vita.ausbildung', 'vita.werdegang', 'lehre.kurse', 'profilbild',
]
# Non-research staff: FU-official sources only, contact + photo only.
RESTRICTED_ROLES = {'Sekretariat', 'Projektassistentin'}
RESTRICTED_FIELDS = [
    'kontakt.email', 'kontakt.telefon', 'links.fu-berlin', 'profilbild',
]
GROUP_FIELDS = ['beschreibung', 'mitarbeiter_url']

URL_FIELDS = {
    'links.fu-berlin', 'links.persoenlich', 'links.github', 'links.linkedin',
    'links.orcid', 'links.google-scholar', 'links.dblp', 'links.mastodon',
    'forschung.publikationen', 'profilbild', 'kontakt.sprechstunde',
}
LIST_OF_STR_FIELDS = {'forschung.interessen'}

# Structured "object array" fields (RESEARCH_SPEC.md §2, §3.1): each item is a
# dict that carries its OWN source inline as `quelle` (self-sourcing), so these
# paths need NO entry in the findings `sources` map. `quelle` (and `url`, where
# listed) are validated as URLs; every other key as plain text. `cap` bounds the
# array (extra items are truncated, newest-first); MAX_ARRAY_ITEMS is the hard
# abuse ceiling that rejects outright.
OBJ_ARRAY_FIELDS = {
    'vita.ausbildung': {
        'required_text': ('grad', 'institution'),
        'optional_text': ('jahr', 'ort'), 'optional_url': (), 'cap': None,
    },
    'vita.werdegang': {
        'required_text': ('position', 'institution'),
        'optional_text': ('zeitraum', 'ort'), 'optional_url': (), 'cap': None,
    },
    'forschung.veroeffentlichungen': {
        'required_text': ('titel',),
        'optional_text': ('jahr', 'venue'), 'optional_url': ('url',),
        # zitationen: per-paper citation count (fetched, e.g. Semantic Scholar);
        # highlight: curator flag pinning a standout paper to the top.
        'optional_int': ('zitationen',), 'optional_bool': ('highlight',), 'cap': 8,
    },
}
MAX_ARRAY_ITEMS = 40

# Google Scholar metrics object (RESEARCH_SPEC.md §3.2): sourced via the
# `sources` map (the Scholar profile URL); integer metrics + a mandatory
# `stand` (YYYY-MM) timestamp because the numbers drift over time.
SCHOLAR_FIELD = 'forschung.scholar'
SCHOLAR_METRICS = ('zitationen', 'h_index', 'i10_index')

# Object fields flatten() must keep intact instead of descending into. Object
# ARRAYS are lists, so flatten() already leaves them whole; only the scholar
# DICT needs to be pinned here.
LEAF_OBJECT_FIELDS = {SCHOLAR_FIELD}

# Per-entry "last researched" stamp written into the dataset on every touch.
LAST_UPDATED_KEY = 'last_updated'

FORBIDDEN_AUTH_VARS = [
    'ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN',
    'CLAUDE_CODE_USE_BEDROCK', 'CLAUDE_CODE_USE_VERTEX',
]

# Values must never carry markup — they end up in app.js innerHTML.
# The single quote (') is deliberately allowed: app.js interpolates researched
# values ONLY into double-quoted attributes and text content. Keep it that way.
FORBIDDEN_CHARS = re.compile(r'[<>"`]')
URL_RE = re.compile(r'\Ahttps?://[A-Za-z0-9._~:/?#@!$&()*+,;=%\[\]-]+\Z')
MAX_VALUE_LEN = 1200

# Profile-link fields may only point at their expected host — a prompt-injected
# agent must not be able to place an arbitrary URL on the public site.
LINK_HOST_ALLOWLIST = {
    'links.github': ('github.com',),
    'links.linkedin': ('linkedin.com',),
    'links.orcid': ('orcid.org',),
    'links.google-scholar': ('scholar.google.com', 'scholar.google.de'),
    'links.dblp': ('dblp.org', 'dblp.uni-trier.de'),
    'links.fu-berlin': ('fu-berlin.de',),
}
EMAIL_RE = re.compile(r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
PHONE_RE = re.compile(r'^\+?[0-9][0-9 ()/–.-]{5,}$')
STAND_RE = re.compile(r'^\d{4}-(0[1-9]|1[0-2])$')   # scholar.stand: YYYY-MM

AGENT_TIMEOUT_S = 600
MAX_TURNS = 30
RATE_LIMIT_MARKERS = (
    'rate limit', 'rate-limit', 'usage limit', 'usage-limit',
    'out of credit', 'credit balance', 'overloaded', '429', 'quota',
)


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def atomic_write_json(path, data):
    tmp = path.with_name(path.name + '.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    os.replace(tmp, path)


def load_json(path, default):
    if not path.exists():
        return default
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


# ---------------------------------------------------------------- guards ---

def check_auth_env():
    for var in FORBIDDEN_AUTH_VARS:
        if os.environ.get(var):
            sys.exit(
                f"ABORT: {var} is set.\n"
                f"Cause: with this variable set, claude -p would bill "
                f"pay-per-token API usage instead of the Max subscription.\n"
                f"Fix: unset it for this run, e.g.\n"
                f"  env -u {var} python research/fill_missing.py"
            )


def check_git_clean():
    res = subprocess.run(
        ['git', 'status', '--short', '--',
         str(DATASET_PATH), str(PROFILE_PICS_PATH), str(PROVENANCE_PATH)],
        cwd=REPO_ROOT, capture_output=True, text=True)
    if res.returncode == 0 and res.stdout.strip():
        sys.exit(
            "ABORT: the dataset has uncommitted changes:\n"
            f"{res.stdout.rstrip()}\n"
            "Cause: every research run must be revertible as one git commit.\n"
            "Fix: commit or stash first, e.g.\n"
            '  git commit -am "checkpoint before research run"  (or: git stash)'
        )


# ----------------------------------------------------------------- state ---

def load_state():
    state = load_json(STATE_PATH, {'version': 1, 'people': {}, 'groups': {}})
    state.setdefault('people', {})
    state.setdefault('groups', {})
    return state


def state_bucket(state, mode):
    return state['groups' if mode == 'group' else 'people']


def field_state(state, mode, entry_id, path):
    return state_bucket(state, mode).get(entry_id, {}).get('fields', {}).get(path, {})


def set_field_state(state, mode, entry_id, path, status, attempts=None):
    entry = state_bucket(state, mode).setdefault(
        entry_id, {'status': 'partial', 'last_run': None, 'fields': {}})
    fs = entry['fields'].setdefault(path, {})
    fs['status'] = status
    fs['ts'] = now_iso()
    if attempts is not None:
        fs['attempts'] = attempts


def load_skip():
    skip = load_json(SKIP_PATH, {'people': {}, 'groups': {}})
    skip.setdefault('people', {})
    skip.setdefault('groups', {})
    return skip


def is_skipped(skip, mode, entry_id, path):
    rule = skip['groups' if mode == 'group' else 'people'].get(entry_id)
    if rule is True:
        return True
    if isinstance(rule, list):
        return path in rule
    return False


# ------------------------------------------------------------ data access ---

def get_value(entry, dotted):
    cur = entry
    for part in dotted.split('.'):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def set_value(entry, dotted, value):
    parts = dotted.split('.')
    cur = entry
    for part in parts[:-1]:
        cur = cur.setdefault(part, {})
    cur[parts[-1]] = value


def is_empty(value):
    return value is None or value == '' or value == [] or value == {}


def migrate_website_key(data):
    """Normalize the legacy links.website key to links.persoenlich (idempotent)."""
    for person in data.get('personen', []):
        links = person.get('links')
        if isinstance(links, dict) and 'website' in links:
            links.setdefault('persoenlich', links['website'])
            del links['website']


def image_on_disk(entry_id):
    for ext in ('.jpg', '.jpeg', '.png', '.gif', '.webp'):
        if (IMAGES_DIR / f'{entry_id}{ext}').exists():
            return True
    return False


def target_fields_for(entry, mode):
    if mode == 'group':
        return GROUP_FIELDS
    if entry.get('rolle') in RESTRICTED_ROLES:
        return RESTRICTED_FIELDS
    return PERSON_FIELDS


# ---------------------------------------------------------------- select ---

def field_reason(entry, mode, path, state, skip, profile_pics, retry_not_found):
    """Why a field is/isn't queued. Returns (queue: bool, reason: str)."""
    if is_skipped(skip, mode, entry['id'], path):
        return False, 'deny-listed'
    value = get_value(entry, path)
    if path == 'profilbild':
        if not is_empty(value) or image_on_disk(entry['id']):
            return False, 'filled'
        if entry['id'] in profile_pics:
            # URL known but file missing: download_images.py retries it.
            return False, 'pending download'
    elif not is_empty(value):
        return False, 'filled'
    fs = field_state(state, mode, entry['id'], path)
    if fs.get('status') == 'not_found' and not retry_not_found:
        return False, 'not_found (skipped; use --retry-not-found)'
    if fs.get('status') == 'rejected' and fs.get('attempts', 0) >= 3 and not retry_not_found:
        return False, 'rejected 3x (skipped; use --retry-not-found)'
    return True, 'missing'


def select(data, state, skip, profile_pics, args):
    """Returns (queue, report). queue: [(entry, [paths])]; report: per-entry field reasons."""
    mode = 'group' if args.groups else 'person'
    if mode == 'group':
        entries = [g for g in data['gruppen'] if g.get('type') == 'ag']
    else:
        entries = data['personen']

    if args.ids:
        wanted = [i.strip() for i in args.ids.split(',') if i.strip()]
        known = {e['id'] for e in entries}
        for wid in wanted:
            if wid not in known:
                close = difflib.get_close_matches(wid, known, n=3)
                hint = f" Closest: {', '.join(close)}" if close else ''
                sys.exit(f"ABORT: unknown {mode} id {wid!r}.{hint}")
        entries = [e for e in entries if e['id'] in wanted]

    queue, report = [], []
    for entry in entries:
        if skip['groups' if mode == 'group' else 'people'].get(entry['id']) is True:
            report.append((entry['id'], [('(entire entry)', 'deny-listed')]))
            continue
        reasons = []
        missing = []
        for path in target_fields_for(entry, mode):
            queued, reason = field_reason(
                entry, mode, path, state, skip, profile_pics, args.retry_not_found)
            reasons.append((path, reason))
            if queued:
                missing.append(path)
        report.append((entry['id'], reasons))
        if missing:
            queue.append((entry, missing))

    if args.limit:
        queue = queue[:args.limit]
    return queue, report


# ----------------------------------------------------------------- agent ---

def build_prompt(entry, missing, mode):
    template = PROMPT_PATH.read_text(encoding='utf-8')
    extra = ''
    if mode == 'group':
        extra = (
            "7. **Group rule:** research ONLY the group's own website "
            f"({entry.get('website', '(see entry)')}). The source URL for "
            "`beschreibung` must be a page on that same site."
        )
    elif entry.get('rolle') in RESTRICTED_ROLES:
        extra = (
            "7. **Restricted subject:** this person is non-research staff. "
            "Use ONLY official fu-berlin.de pages as sources; do not search "
            "for or report social media or private information."
        )
    return (template
            .replace('{{MODE}}', 'research group' if mode == 'group' else 'person')
            .replace('{{ENTRY_JSON}}', json.dumps(entry, ensure_ascii=False, indent=2))
            .replace('{{MISSING_FIELDS}}', '\n'.join(f'- `{p}`' for p in missing))
            .replace('{{EXTRA_RULES}}', extra))


def extract_findings(result_text):
    """Pull the findings JSON object out of the agent's final message."""
    text = result_text.strip()
    fence = re.search(r'```(?:json)?\s*(\{.*\})\s*```', text, re.S)
    if fence:
        text = fence.group(1)
    else:
        start, end = text.find('{'), text.rfind('}')
        if start == -1 or end <= start:
            raise ValueError('no JSON object in agent output')
        text = text[start:end + 1]
    findings = json.loads(text)
    if not isinstance(findings, dict):
        raise ValueError('agent output is not a JSON object')
    return findings


def classify_error(text):
    lowered = (text or '').lower()
    if any(marker in lowered for marker in RATE_LIMIT_MARKERS):
        return 'rate_limit'
    return 'agent_error'


def run_agent_once(prompt):
    """One claude -p call. Returns (findings|None, meta)."""
    cmd = [
        'claude', '-p', prompt,
        '--model', 'sonnet',
        '--output-format', 'json',
        '--max-turns', str(MAX_TURNS),
        '--allowedTools', 'WebSearch,WebFetch',
    ]
    started = time.monotonic()
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=AGENT_TIMEOUT_S,
            cwd=REPO_ROOT)
    except subprocess.TimeoutExpired:
        return None, {'error_class': 'timeout', 'raw': f'timeout after {AGENT_TIMEOUT_S}s',
                      'duration_ms': int((time.monotonic() - started) * 1000), 'num_turns': 0}
    except FileNotFoundError:
        sys.exit("ABORT: 'claude' CLI not found on PATH.\n"
                 "Fix: install Claude Code and log in with the subscription "
                 "(smoke test: claude -p \"hi\").")
    raw = (proc.stdout or '') + ('\n--- stderr ---\n' + proc.stderr if proc.stderr else '')
    meta = {'duration_ms': int((time.monotonic() - started) * 1000),
            'num_turns': 0, 'raw': raw, 'error_class': None}
    if proc.returncode != 0:
        # Classify from stderr only — stdout may echo fetched web content
        # that legitimately contains words like "quota" or "429".
        meta['error_class'] = classify_error(proc.stderr or proc.stdout)
        return None, meta
    try:
        envelope = json.loads(proc.stdout)
    except (json.JSONDecodeError, TypeError):
        meta['error_class'] = 'parse_error'
        return None, meta
    meta['duration_ms'] = envelope.get('duration_ms', meta['duration_ms'])
    meta['num_turns'] = envelope.get('num_turns', 0)
    if envelope.get('is_error'):
        if envelope.get('api_error_status') in (429, 529):
            meta['error_class'] = 'rate_limit'
        else:
            meta['error_class'] = classify_error(
                str(envelope.get('result', '')) + str(envelope.get('subtype', '')))
        return None, meta
    result_text = envelope.get('result', '')
    if not result_text or not str(result_text).strip():
        meta['error_class'] = 'empty_result'
        return None, meta
    try:
        return extract_findings(str(result_text)), meta
    except (ValueError, json.JSONDecodeError):
        meta['error_class'] = 'parse_error'
        return None, meta


def run_agent(prompt):
    """claude -p with one retry on parse/empty failures."""
    findings, meta = run_agent_once(prompt)
    if findings is None and meta['error_class'] in ('parse_error', 'empty_result'):
        findings, meta = run_agent_once(prompt)
    return findings, meta


# -------------------------------------------------------------- validate ---

def flatten(fields, prefix=''):
    # Recursion stops at lists (so lehre.kurse / vita.ausbildung items stay
    # intact) and at LEAF_OBJECT_FIELDS (so forschung.scholar stays one object).
    flat = {}
    for key, value in fields.items():
        path = f'{prefix}{key}'
        if isinstance(value, dict) and path not in LEAF_OBJECT_FIELDS:
            flat.update(flatten(value, f'{path}.'))
        else:
            flat[path] = value
    return flat


def clean_string(value):
    """Returns an error string or None if the value is acceptable."""
    if not isinstance(value, str):
        return 'not a string'
    if not value.strip():
        return 'empty'
    if len(value) > MAX_VALUE_LEN:
        return f'value too long (>{MAX_VALUE_LEN} chars)'
    if FORBIDDEN_CHARS.search(value):
        return 'forbidden characters (<, >, \", `)'
    return None


def check_url(value):
    err = clean_string(value)
    if err:
        return err
    if not URL_RE.match(value):
        return 'not a valid http(s) URL'
    if not urlparse(value).hostname:
        return 'URL has no host'
    return None


def host_of(url):
    try:
        return (urlparse(url).hostname or '').lower()
    except ValueError:
        return ''


def host_matches(host, domain):
    """True for the domain itself or its subdomains — never for lookalikes
    like evilfu-berlin.de, which a plain endswith() would accept."""
    return host == domain or host.endswith('.' + domain)


def validate_field(path, value, source, entry, mode):
    """Returns an error string or None if (value, source) is acceptable."""
    err = check_url(source)
    if err:
        return f'bad source URL: {err}'

    fu_only = mode == 'person' and entry.get('rolle') in RESTRICTED_ROLES
    if fu_only and not host_matches(host_of(source), 'fu-berlin.de'):
        return 'restricted subject: source must be a fu-berlin.de page'

    if path in LINK_HOST_ALLOWLIST:
        err = check_url(value)
        if err:
            return err
        if not any(host_matches(host_of(value), d)
                   for d in LINK_HOST_ALLOWLIST[path]):
            return f'host not allowed for {path}'
        return None
    if path in URL_FIELDS:
        # kontakt.sprechstunde may be a free-text time instead of a URL
        if path == 'kontakt.sprechstunde' and not str(value).startswith('http'):
            return clean_string(value)
        return check_url(value)
    if path == 'kontakt.email':
        err = clean_string(value)
        if err:
            return err
        return None if EMAIL_RE.match(value) else 'not a valid email'
    if path == 'kontakt.telefon':
        err = clean_string(value)
        if err:
            return err
        return None if PHONE_RE.match(value) else 'not a valid phone number'
    if path in LIST_OF_STR_FIELDS:
        if not isinstance(value, list) or not value:
            return 'must be a non-empty array of strings'
        for item in value:
            err = clean_string(item)
            if err:
                return f'array item: {err}'
        return None
    if path == 'lehre.kurse':
        if not isinstance(value, list) or not value:
            return 'must be a non-empty array of {name, semester}'
        for item in value:
            if not isinstance(item, dict) or set(item) != {'name', 'semester'}:
                return 'each course needs exactly name and semester'
            for key in ('name', 'semester'):
                err = clean_string(item[key])
                if err:
                    return f'course {key}: {err}'
        return None
    if path == 'mitarbeiter_url':
        err = check_url(value)
        if err:
            return err
        # The group's live member roster: same host as the group website
        # (covers external homepages like hhi.fraunhofer.de) or any fu-berlin.de.
        site_host = host_of(entry.get('website', ''))
        val_host = host_of(value)
        if host_matches(val_host, 'fu-berlin.de'):
            return None
        if site_host and host_matches(val_host, site_host):
            return None
        return f'mitarbeiter_url host must be fu-berlin.de or the group site ({site_host})'
    if path == 'beschreibung':
        err = clean_string(value)
        if err:
            return err
        # Same host, or same institution: FU group "websites" are often
        # stubs whose real homepage lives on another fu-berlin.de host.
        site_host = host_of(entry.get('website', ''))
        src_host = host_of(source)
        same_institution = (host_matches(site_host, 'fu-berlin.de')
                            and host_matches(src_host, 'fu-berlin.de'))
        if site_host and src_host != site_host and not same_institution:
            return f'source host must match group website ({site_host})'
        return None
    return clean_string(value)


def validate_obj_array(path, value, entry, mode):
    """Validate a self-sourcing object-array field (ausbildung / werdegang /
    veroeffentlichungen) AS LENIENTLY AS POSSIBLE while preserving order:
      - unknown keys are dropped,
      - an invalid OPTIONAL field is dropped but the item is kept,
      - an item is dropped only if a REQUIRED key (grad/position/institution/
        titel, plus quelle) is missing or invalid,
      - the array is rejected only if NO valid item survives.
    Numeric values (e.g. jahr) are coerced to strings. `value` is mutated in
    place to the cleaned, order-preserved list. Returns an error string or None."""
    spec = OBJ_ARRAY_FIELDS[path]
    if not isinstance(value, list) or not value:
        return 'must be a non-empty array of objects'
    if len(value) > MAX_ARRAY_ITEMS:
        del value[MAX_ARRAY_ITEMS:]   # abuse guard; order preserved

    req_text = spec['required_text']
    url_keys = set(spec['optional_url']) | {'quelle'}
    int_keys = set(spec.get('optional_int', ()))
    bool_keys = set(spec.get('optional_bool', ()))
    allowed_keys = (set(req_text) | set(spec['optional_text']) | url_keys
                    | int_keys | bool_keys)
    required_keys = set(req_text) | {'quelle'}
    fu_only = mode == 'person' and entry.get('rolle') in RESTRICTED_ROLES

    def field_ok(item, key):
        # Coerce a stray numeric (jahr as 2011) to a string, then validate.
        if key in url_keys:
            return check_url(item[key]) is None
        if key in int_keys:
            v = item[key]
            return isinstance(v, int) and not isinstance(v, bool) and v >= 0
        if key in bool_keys:
            return isinstance(item[key], bool)
        if isinstance(item[key], (int, float)) and not isinstance(item[key], bool):
            item[key] = str(item[key])
        return clean_string(item[key]) is None

    kept = []
    for item in value:
        if not isinstance(item, dict):
            continue
        for key in [k for k in item if k not in allowed_keys]:
            del item[key]                                  # drop unknown keys
        if any(k not in item or not field_ok(item, k) for k in required_keys):
            continue                                       # a required key failed
        for key in [k for k in item if k not in required_keys]:
            if not field_ok(item, key):
                del item[key]                              # drop a bad optional field
        if fu_only and not host_matches(host_of(item['quelle']), 'fu-berlin.de'):
            continue
        kept.append(item)

    if not kept:
        return 'no valid items'
    cap = spec['cap']
    if cap is not None:
        del kept[cap:]                                     # keep up to `cap`, order preserved
    value[:] = kept
    return None


def validate_scholar(value, source, entry, mode):
    """Validate the forschung.scholar metrics object. Returns an error or None."""
    err = check_url(source)
    if err:
        return f'bad source URL: {err}'
    if not isinstance(value, dict) or not value:
        return 'must be a non-empty object'
    extra = set(value) - (set(SCHOLAR_METRICS) | {'stand'})
    if extra:
        return f'unexpected keys: {", ".join(sorted(extra))}'
    for key in SCHOLAR_METRICS:
        if key in value:
            num = value[key]
            if isinstance(num, bool) or not isinstance(num, int) or num < 0:
                return f'{key} must be a non-negative integer'
    if not any(key in value for key in SCHOLAR_METRICS):
        return 'scholar object has no metrics'
    stand = value.get('stand')
    if not isinstance(stand, str) or not STAND_RE.match(stand):
        return 'stand must be present and formatted YYYY-MM'
    return None


def validate(findings, entry, mode):
    """Quarantine check. Returns (accepted, rejected, not_found_paths)."""
    allowed = set(target_fields_for(entry, mode))
    accepted, rejected = {}, []

    if not isinstance(findings.get('fields', {}), dict) or \
            not isinstance(findings.get('sources', {}), dict):
        return {}, [{'path': '(all)', 'reason': 'malformed findings object'}], []

    sources = findings.get('sources', {})
    for path, value in flatten(findings.get('fields', {})).items():
        if path not in allowed:
            rejected.append({'path': path, 'reason': 'not a requested field'})
            continue
        if is_empty(value):
            rejected.append({'path': path, 'reason': 'empty value'})
            continue
        if path in OBJ_ARRAY_FIELDS:
            # Self-sourcing: the source lives in each item's `quelle`, so no
            # entry in the `sources` map is required.
            err = validate_obj_array(path, value, entry, mode)
            if err:
                rejected.append({'path': path, 'reason': err})
                continue
            accepted[path] = {'value': value, 'source': None}
            continue
        source = sources.get(path)
        if not source:
            rejected.append({'path': path, 'reason': 'no source URL'})
            continue
        if path == SCHOLAR_FIELD:
            err = validate_scholar(value, source, entry, mode)
        else:
            err = validate_field(path, value, source, entry, mode)
        if err:
            rejected.append({'path': path, 'reason': err})
            continue
        accepted[path] = {'value': value, 'source': source}

    nf = findings.get('not_found', [])
    not_found = [p for p in nf if isinstance(p, str) and p in allowed] \
        if isinstance(nf, list) else []
    return accepted, rejected, not_found


# ----------------------------------------------------------------- merge ---

def merge(entry, accepted, profile_pics):
    """Fill-only merge into the entry. Returns (merged, conflicts)."""
    merged, conflicts = {}, []
    for path, item in accepted.items():
        if path == 'profilbild':
            # Fill-only applies here too: a manually set profilbild or an
            # image already on disk must never be overwritten via the
            # profile_pics route.
            if entry['id'] in profile_pics \
                    or not is_empty(get_value(entry, 'profilbild')) \
                    or image_on_disk(entry['id']):
                conflicts.append(path)
            else:
                profile_pics[entry['id']] = item['value']
                merged[path] = item
            continue
        if not is_empty(get_value(entry, path)):
            conflicts.append(path)
            continue
        set_value(entry, path, item['value'])
        merged[path] = item
    return merged, conflicts


# ---------------------------------------------------------------- record ---

def append_provenance(records):
    with open(PROVENANCE_PATH, 'a', encoding='utf-8') as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')


def log_raw_output(entry_id, raw):
    LOG_DIR.mkdir(exist_ok=True)
    log_path = LOG_DIR / f'{entry_id}.txt'
    log_path.write_text(raw or '(no output)', encoding='utf-8')
    return log_path


# ------------------------------------------------------------------ main ---

def print_dry_run(report, queue):
    queued_ids = {e['id'] for e, _ in queue}
    for entry_id, reasons in report:
        pending = [(p, r) for p, r in reasons if r == 'missing']
        mark = '→' if entry_id in queued_ids else ' '
        print(f'{mark} {entry_id}: {len(pending)} field(s) to research')
        for path, reason in reasons:
            if reason != 'filled':
                print(f'      {path}: {reason}')
    print(f'\nQueue: {len(queue)} entries, '
          f'{sum(len(m) for _, m in queue)} fields total.')


def confirm_or_exit(queue, args):
    n_fields = sum(len(m) for _, m in queue)
    workers = max(1, getattr(args, 'concurrency', 1) or 1)
    est_low = 2 * len(queue) // workers
    est_high = 5 * len(queue) // workers
    print(f'Queued: {len(queue)} entries ({n_fields} missing fields), '
          f'~{workers}x parallel, estimated {est_low}-{est_high} min.')
    print('Ctrl-C anytime; progress is saved per entry.')
    if len(queue) > 10 and not args.yes:
        if sys.stdin.isatty():
            answer = input(f'Run all {len(queue)} now? [y/N] ').strip().lower()
            if answer not in ('y', 'yes'):
                sys.exit('Aborted. Tip: --dry-run shows the queue, '
                         '--limit 5 runs a pilot.')
        else:
            sys.exit(f'ABORT: queue has {len(queue)} entries and no TTY to '
                     'confirm. Re-run with --yes to proceed non-interactively.')


def main():
    parser = argparse.ArgumentParser(
        description='Fill missing FU Informatik person/group data via '
                    'headless Claude research agents (subscription auth).',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='examples:\n'
               '  python research/fill_missing.py --dry-run\n'
               '  python research/fill_missing.py --limit 5        # pilot\n'
               '  python research/fill_missing.py --retry-not-found  # semester refresh\n'
               '  python research/fill_missing.py --groups          # AG descriptions\n')
    parser.add_argument('--limit', type=int, metavar='N',
                        help='research at most N entries (pilot mechanism)')
    parser.add_argument('--ids', metavar='a,b,c',
                        help='research only these entry ids')
    parser.add_argument('--dry-run', action='store_true',
                        help='print the queue with per-field reasons, change nothing')
    parser.add_argument('--retry-not-found', action='store_true',
                        help='re-research fields previously recorded as not '
                             'found (otherwise they are skipped forever)')
    parser.add_argument('--groups', action='store_true',
                        help='run the group-description pass INSTEAD of the person pass')
    parser.add_argument('--yes', action='store_true',
                        help='skip the large-queue confirmation prompt')
    parser.add_argument('--concurrency', type=int, default=1, metavar='N',
                        help='research up to N entries in parallel via separate '
                             'claude -p subprocesses (default 1; merges to the '
                             'dataset stay serialized in the main thread)')
    args = parser.parse_args()

    # Progress lines must appear live even when stdout is piped/redirected.
    sys.stdout.reconfigure(line_buffering=True)

    mode = 'group' if args.groups else 'person'
    check_auth_env()
    if not args.dry_run:
        check_git_clean()

    data = load_json(DATASET_PATH, None)
    if data is None:
        sys.exit(f'ABORT: dataset not found at {DATASET_PATH}')
    migrate_website_key(data)
    state = load_state()
    skip = load_skip()
    profile_pics = load_json(PROFILE_PICS_PATH, {})

    queue, report = select(data, state, skip, profile_pics, args)

    if args.dry_run:
        print_dry_run(report, queue)
        return
    if not queue:
        print('Nothing to do (all fields filled, not_found, or deny-listed).')
        print('Use --dry-run to see per-field reasons'
              + ('' if args.groups else '; group descriptions are a separate '
                 'pass: --groups') + '.')
        return

    confirm_or_exit(queue, args)

    totals = {'filled': 0, 'not_found': 0, 'rejected': 0, 'conflicts': 0,
              'failed': 0, 'duration_ms': 0, 'num_turns': 0}
    rejection_reasons = {}
    new_pics = 0
    processed = 0
    rate_limit_hits = 0
    aborted = None                       # None | 'interrupt' | 'rate_limit'
    run_start = time.monotonic()
    workers = max(1, args.concurrency)

    # Research runs in parallel (one claude -p subprocess per worker thread),
    # but every mutation below runs serially in the main thread as each future
    # completes — so the dataset / state / provenance have a single writer and
    # the atomic-write invariants are preserved unchanged.

    def record_failure(entry, meta, prefix):
        totals['failed'] += 1
        log_path = log_raw_output(entry['id'], meta.get('raw'))
        bucket = state_bucket(state, mode)
        bucket.setdefault(entry['id'], {'fields': {}})
        bucket[entry['id']].update({'status': 'failed', 'last_run': now_iso()})
        atomic_write_json(STATE_PATH, state)
        append_provenance([{
            'ts': now_iso(), 'id': entry['id'], 'mode': mode,
            'action': 'failed', 'reason': meta['error_class'],
            'log': str(log_path.relative_to(REPO_ROOT))}])
        print(f"{prefix} {entry['id']} ... FAILED "
              f"({meta['error_class']}) — raw output: {log_path}")

    def record_success(entry, meta, findings, prefix):
        nonlocal new_pics
        accepted, rejected, not_found = validate(findings, entry, mode)
        merged, conflicts = merge(entry, accepted, profile_pics)
        new_pics += 1 if 'profilbild' in merged else 0

        # Stamp when this entry was last researched (overwrite, not fill-only).
        set_value(entry, LAST_UPDATED_KEY, now_iso())
        # Write order matters: dataset first, state last. A crash in between
        # can only cause a harmless fill-only re-research, never a state that
        # claims a merge that didn't happen.
        atomic_write_json(DATASET_PATH, data)
        atomic_write_json(PROFILE_PICS_PATH, profile_pics)

        records = []
        for path, item in merged.items():
            if path in OBJ_ARRAY_FIELDS:
                # Self-sourcing arrays: one provenance row per item, keyed by
                # the item's own inline `quelle`.
                for idx, element in enumerate(item['value']):
                    records.append({'ts': now_iso(), 'id': entry['id'],
                                    'mode': mode, 'action': 'merged',
                                    'field': f'{path}[{idx}]', 'value': element,
                                    'source': element.get('quelle')})
            else:
                records.append({'ts': now_iso(), 'id': entry['id'],
                                'mode': mode, 'action': 'merged', 'field': path,
                                'value': item['value'], 'source': item['source']})
            set_field_state(state, mode, entry['id'], path, 'filled')
        for rej in rejected:
            records.append({'ts': now_iso(), 'id': entry['id'],
                            'mode': mode, 'action': 'rejected',
                            'field': rej['path'], 'reason': rej['reason']})
            rejection_reasons[rej['reason']] = \
                rejection_reasons.get(rej['reason'], 0) + 1
            prev = field_state(state, mode, entry['id'], rej['path'])
            attempts = prev.get('attempts', 0) + 1
            status = 'not_found' if attempts >= 3 else 'rejected'
            set_field_state(state, mode, entry['id'], rej['path'],
                            status, attempts=attempts)
        for path in conflicts:
            records.append({'ts': now_iso(), 'id': entry['id'],
                            'mode': mode, 'action': 'conflict', 'field': path})
        for path in not_found:
            records.append({'ts': now_iso(), 'id': entry['id'],
                            'mode': mode, 'action': 'not_found', 'field': path})
            set_field_state(state, mode, entry['id'], path, 'not_found')

        bucket = state_bucket(state, mode)
        bucket.setdefault(entry['id'], {'fields': {}})
        bucket[entry['id']].update({
            'status': 'done' if not rejected and not not_found else 'partial',
            'last_run': now_iso()})
        atomic_write_json(STATE_PATH, state)
        append_provenance(records)

        totals['filled'] += len(merged)
        totals['not_found'] += len(not_found)
        totals['rejected'] += len(rejected)
        totals['conflicts'] += len(conflicts)
        top_reason = rejected[0]['reason'] if rejected else ''
        elapsed = int(time.monotonic() - run_start)
        print(f"{prefix} {entry['id']} ... "
              f"{len(merged)} filled, {len(not_found)} not_found, "
              f"{len(rejected)} rejected"
              + (f' ({top_reason})' if top_reason else '')
              + f" — {meta.get('duration_ms', 0) // 1000}s, "
                f"total {elapsed // 60}m{elapsed % 60:02d}s")

    pool = cf.ThreadPoolExecutor(max_workers=workers)
    futures = {pool.submit(run_agent, build_prompt(entry, missing, mode)): entry
               for entry, missing in queue}
    try:
        for future in cf.as_completed(futures):
            entry = futures[future]
            findings, meta = future.result()
            processed += 1
            totals['duration_ms'] += meta.get('duration_ms', 0)
            totals['num_turns'] += meta.get('num_turns', 0)
            prefix = f'[{processed}/{len(queue)}]'
            if findings is None:
                record_failure(entry, meta, prefix)
                if meta['error_class'] == 'rate_limit':
                    rate_limit_hits += 1
                    if rate_limit_hits >= 3:
                        aborted = 'rate_limit'
                        break
                continue
            record_success(entry, meta, findings, prefix)
    except KeyboardInterrupt:
        aborted = 'interrupt'
    finally:
        for future in futures:
            future.cancel()
        pool.shutdown(wait=False, cancel_futures=True)

    if aborted == 'interrupt':
        done = sum(1 for e, _ in queue
                   if state_bucket(state, mode).get(e['id'], {}).get('last_run'))
        print(f'\nInterrupted. Progress saved ({done} entries recorded). '
              'Re-run the same command to resume.')
        return
    if aborted == 'rate_limit':
        print('\nABORT: 3 rate-limit failures — the Claude usage window looks '
              'exhausted.\nProgress is saved; pending entries were cancelled.\n'
              'Fix: wait for the window to reset, then re-run the exact same '
              'command — finished entries are skipped automatically.')
        return

    if new_pics:
        print(f'\n{new_pics} new profile picture URL(s) found — downloading...')
        subprocess.run([sys.executable, str(REPO_ROOT / 'download_images.py')],
                       cwd=REPO_ROOT)

    print('\n' + '=' * 60)
    print(f"Run complete ({mode} pass): "
          f"{totals['filled']} fields filled, {totals['not_found']} not found, "
          f"{totals['rejected']} rejected, {totals['conflicts']} conflicts, "
          f"{totals['failed']} entries failed.")
    if rejection_reasons:
        print('Rejections by reason:')
        for reason, count in sorted(rejection_reasons.items(),
                                    key=lambda kv: -kv[1]):
            print(f'  {count}x {reason}')
    print(f"Usage: {totals['num_turns']} agent turns, "
          f"{totals['duration_ms'] // 60000} min agent time.")
    print('\nNext steps:')
    print('  1. Spot-check merged facts against research/provenance.jsonl')
    print('  2. Open index.html and click through 3 enriched modals')
    print('  3. git add -A && git commit -m "research run: '
          + ('group descriptions"' if args.groups else 'person data"'))
    if not args.groups:
        print('  4. Group descriptions are a separate pass: --groups')
    print('=' * 60)


if __name__ == '__main__':
    main()

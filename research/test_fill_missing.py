#!/usr/bin/env python3
"""Unit tests for the pure core of fill_missing.py (no network, no agents).

Run: python -m unittest research.test_fill_missing -v   (from repo root)
  or: python research/test_fill_missing.py
"""

import argparse
import json
import multiprocessing
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fill_missing as fm


def make_args(**overrides):
    args = argparse.Namespace(limit=None, ids=None, dry_run=False,
                              retry_not_found=False, groups=False, yes=True)
    for key, value in overrides.items():
        setattr(args, key, value)
    return args


def full_person():
    return {
        'id': 'voll-vera', 'name': 'Vera Voll', 'rolle': 'Professorin',
        'kontakt': {'email': 'v@inf.fu-berlin.de', 'telefon': '+49 30 838 1',
                    'sprechstunde': 'https://fu-berlin.de/termin'},
        'links': {'fu-berlin': 'https://www.mi.fu-berlin.de/v',
                  'persoenlich': 'https://vera.example.org',
                  'github': 'https://github.com/v',
                  'linkedin': 'https://linkedin.com/in/v',
                  'orcid': 'https://orcid.org/0000-0001',
                  'google-scholar': 'https://scholar.google.com/v',
                  'dblp': 'https://dblp.org/pid/v',
                  'mastodon': 'https://mastodon.social/@v'},
        'forschung': {'interessen': ['HCI'],
                      'publikationen': 'https://dblp.org/pid/v.html'},
        'vita': {'positionen': ['seit 2020: Professorin, FU Berlin']},
        'lehre': {'kurse': [{'name': 'ALP 1', 'semester': 'WS 2025/26'}]},
        'profilbild': 'research/images/voll-vera.jpg',
    }


def make_data():
    return {
        'personen': [
            full_person(),
            {'id': 'leer-lena', 'name': 'Lena Leer', 'rolle': 'Professorin'},
            {'id': 'halb-hans', 'name': 'Hans Halb',
             'rolle': 'Wissenschaftlicher Mitarbeiter',
             'forschung': {'interessen': []},   # empty == missing
             'kontakt': {'email': ''}},
            {'id': 'sek-sabine', 'name': 'Sabine Sek', 'rolle': 'Sekretariat'},
            {'id': 'alt-albert', 'name': 'Albert Alt', 'rolle': 'Professor',
             'links': {'website': 'https://albert.example.org'}},
        ],
        'gruppen': [
            {'id': 'ag-test', 'type': 'ag', 'name': 'Testologie',
             'website': 'https://www.mi.fu-berlin.de/ag-test'},
            {'id': 'ext-partner', 'type': 'extern', 'name': 'Partner'},
        ],
    }


def empty_state():
    return {'version': 1, 'people': {}, 'groups': {}}


def empty_skip():
    return {'people': {}, 'groups': {}}


class SelectTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._orig_images = fm.IMAGES_DIR
        fm.IMAGES_DIR = Path(self.tmp.name)

    def tearDown(self):
        fm.IMAGES_DIR = self._orig_images
        self.tmp.cleanup()

    def queue_ids(self, queue):
        return [entry['id'] for entry, _ in queue]

    def test_complete_entry_skipped(self):
        queue, _ = fm.select(make_data(), empty_state(), empty_skip(), {},
                             make_args())
        self.assertNotIn('voll-vera', self.queue_ids(queue))
        self.assertIn('leer-lena', self.queue_ids(queue))

    def test_empty_values_count_as_missing(self):
        queue, _ = fm.select(make_data(), empty_state(), empty_skip(), {},
                             make_args(ids='halb-hans'))
        _, missing = queue[0]
        self.assertIn('forschung.interessen', missing)
        self.assertIn('kontakt.email', missing)

    def test_denylist_entire_person(self):
        skip = empty_skip()
        skip['people']['leer-lena'] = True
        queue, _ = fm.select(make_data(), empty_state(), skip, {}, make_args())
        self.assertNotIn('leer-lena', self.queue_ids(queue))

    def test_denylist_single_field(self):
        skip = empty_skip()
        skip['people']['leer-lena'] = ['links.linkedin']
        queue, _ = fm.select(make_data(), empty_state(), skip, {},
                             make_args(ids='leer-lena'))
        _, missing = queue[0]
        self.assertNotIn('links.linkedin', missing)
        self.assertIn('links.github', missing)

    def test_not_found_gated_without_flag(self):
        state = empty_state()
        fm.set_field_state(state, 'person', 'leer-lena', 'links.github',
                           'not_found')
        queue, _ = fm.select(make_data(), state, empty_skip(), {},
                             make_args(ids='leer-lena'))
        _, missing = queue[0]
        self.assertNotIn('links.github', missing)
        queue, _ = fm.select(make_data(), state, empty_skip(), {},
                             make_args(ids='leer-lena', retry_not_found=True))
        _, missing = queue[0]
        self.assertIn('links.github', missing)

    def test_rejected_cap_skipped_until_retry_flag(self):
        state = empty_state()
        fm.set_field_state(state, 'person', 'leer-lena', 'vita.positionen',
                           'rejected', attempts=3)
        queue, _ = fm.select(make_data(), state, empty_skip(), {},
                             make_args(ids='leer-lena'))
        self.assertNotIn('vita.positionen', queue[0][1])
        queue, _ = fm.select(make_data(), state, empty_skip(), {},
                             make_args(ids='leer-lena', retry_not_found=True))
        self.assertIn('vita.positionen', queue[0][1])

    def test_restricted_role_gets_restricted_fields(self):
        queue, _ = fm.select(make_data(), empty_state(), empty_skip(), {},
                             make_args(ids='sek-sabine'))
        _, missing = queue[0]
        self.assertEqual(set(missing), set(fm.RESTRICTED_FIELDS))

    def test_profilbild_handled_when_file_on_disk(self):
        (fm.IMAGES_DIR / 'leer-lena.jpg').write_bytes(b'x')
        queue, _ = fm.select(make_data(), empty_state(), empty_skip(), {},
                             make_args(ids='leer-lena'))
        self.assertNotIn('profilbild', queue[0][1])

    def test_profilbild_pending_when_url_known_but_no_file(self):
        queue, _ = fm.select(make_data(), empty_state(), empty_skip(),
                             {'leer-lena': 'https://example.org/x.jpg'},
                             make_args(ids='leer-lena'))
        self.assertNotIn('profilbild', queue[0][1])

    def test_unknown_id_aborts_with_suggestion(self):
        with self.assertRaises(SystemExit) as ctx:
            fm.select(make_data(), empty_state(), empty_skip(), {},
                      make_args(ids='leer-lina'))
        self.assertIn('leer-lena', str(ctx.exception))

    def test_groups_mode_selects_only_ag(self):
        queue, _ = fm.select(make_data(), empty_state(), empty_skip(), {},
                             make_args(groups=True))
        self.assertEqual(self.queue_ids(queue), ['ag-test'])
        self.assertEqual(queue[0][1], ['beschreibung'])

    def test_limit_truncates_queue(self):
        queue, _ = fm.select(make_data(), empty_state(), empty_skip(), {},
                             make_args(limit=1))
        self.assertEqual(len(queue), 1)


class ValidateTests(unittest.TestCase):
    def person(self):
        return {'id': 'leer-lena', 'name': 'Lena Leer', 'rolle': 'Professorin'}

    def findings(self, fields, sources):
        return {'fields': fields, 'sources': sources, 'not_found': []}

    def test_accepts_valid_nested_findings(self):
        accepted, rejected, _ = fm.validate(self.findings(
            {'kontakt': {'email': 'l@inf.fu-berlin.de'},
             'lehre': {'kurse': [{'name': 'ALP 1', 'semester': 'WS 25/26'}]}},
            {'kontakt.email': 'https://fu-berlin.de/l',
             'lehre.kurse': 'https://fu-berlin.de/l'}),
            self.person(), 'person')
        self.assertEqual(rejected, [])
        self.assertIn('kontakt.email', accepted)
        self.assertIn('lehre.kurse', accepted)

    def test_rejects_html_chars_but_accepts_apostrophe(self):
        accepted, rejected, _ = fm.validate(self.findings(
            {'vita': {'positionen': ["2010: PhD, King's College London"]},
             'forschung': {'interessen': ['<script>alert(1)</script>']}},
            {'vita.positionen': 'https://example.org/cv',
             'forschung.interessen': 'https://example.org/r'}),
            self.person(), 'person')
        self.assertIn('vita.positionen', accepted)
        self.assertEqual(rejected[0]['path'], 'forschung.interessen')

    def test_rejects_missing_source(self):
        accepted, rejected, _ = fm.validate(self.findings(
            {'links': {'github': 'https://github.com/x'}}, {}),
            self.person(), 'person')
        self.assertEqual(accepted, {})
        self.assertEqual(rejected[0]['reason'], 'no source URL')

    def test_rejects_unknown_field(self):
        _, rejected, _ = fm.validate(self.findings(
            {'geheim': 'x'}, {'geheim': 'https://example.org'}),
            self.person(), 'person')
        self.assertEqual(rejected[0]['reason'], 'not a requested field')

    def test_rejects_empty_values(self):
        _, rejected, _ = fm.validate(self.findings(
            {'forschung': {'interessen': []}, 'kontakt': {'email': ''}},
            {'forschung.interessen': 'https://example.org',
             'kontakt.email': 'https://example.org'}),
            self.person(), 'person')
        self.assertEqual({r['reason'] for r in rejected}, {'empty value'})

    def test_rejects_bad_url_and_quote_breakout(self):
        _, rejected, _ = fm.validate(self.findings(
            {'links': {'github': 'https://github.com/x" onmouseover="evil'}},
            {'links.github': 'https://github.com/x'}),
            self.person(), 'person')
        self.assertEqual(len(rejected), 1)

    def test_kurse_require_name_and_semester(self):
        _, rejected, _ = fm.validate(self.findings(
            {'lehre': {'kurse': [{'name': 'ALP 1'}]}},
            {'lehre.kurse': 'https://example.org'}),
            self.person(), 'person')
        self.assertIn('name and semester', rejected[0]['reason'])

    def test_email_and_phone_format(self):
        _, rejected, _ = fm.validate(self.findings(
            {'kontakt': {'email': 'not-an-email', 'telefon': 'call me'}},
            {'kontakt.email': 'https://example.org',
             'kontakt.telefon': 'https://example.org'}),
            self.person(), 'person')
        self.assertEqual(len(rejected), 2)

    def test_restricted_role_requires_fu_berlin_source(self):
        sek = {'id': 'sek-sabine', 'rolle': 'Sekretariat'}
        accepted, rejected, _ = fm.validate(self.findings(
            {'kontakt': {'email': 's@inf.fu-berlin.de',
                         'telefon': '+49 30 838 2'}},
            {'kontakt.email': 'https://www.linkedin.com/in/sabine',
             'kontakt.telefon': 'https://www.mi.fu-berlin.de/sek'}),
            sek, 'person')
        self.assertIn('kontakt.telefon', accepted)
        self.assertIn('fu-berlin.de', rejected[0]['reason'])

    def test_group_beschreibung_host_must_match_website(self):
        group = {'id': 'ag-test', 'type': 'ag',
                 'website': 'https://www.mi.fu-berlin.de/ag-test'}
        accepted, rejected, _ = fm.validate(
            {'fields': {'beschreibung': 'Die AG forscht an Tests.'},
             'sources': {'beschreibung': 'https://www.wikipedia.org/ag'},
             'not_found': []}, group, 'group')
        self.assertEqual(accepted, {})
        self.assertIn('host must match', rejected[0]['reason'])

    def test_not_found_filtered_to_allowed_paths(self):
        _, _, not_found = fm.validate(
            {'fields': {}, 'sources': {},
             'not_found': ['links.github', 'geheim', 42]},
            self.person(), 'person')
        self.assertEqual(not_found, ['links.github'])


class MergeTests(unittest.TestCase):
    def test_fill_only_never_overwrites(self):
        entry = full_person()
        merged, conflicts = fm.merge(
            entry, {'kontakt.email': {'value': 'other@example.org',
                                      'source': 'https://example.org'}}, {})
        self.assertEqual(merged, {})
        self.assertEqual(conflicts, ['kontakt.email'])
        self.assertEqual(entry['kontakt']['email'], 'v@inf.fu-berlin.de')

    def test_nested_sibling_keys_survive(self):
        entry = {'id': 'x', 'vita': {'promotion': {'jahr': 2008}}}
        fm.merge(entry, {'vita.positionen': {
            'value': ['seit 2020: Prof'], 'source': 'https://example.org'}}, {})
        self.assertEqual(entry['vita']['promotion'], {'jahr': 2008})
        self.assertEqual(entry['vita']['positionen'], ['seit 2020: Prof'])

    def test_profilbild_routes_to_profile_pics_not_dataset(self):
        entry = {'id': 'leer-lena'}
        pics = {}
        merged, _ = fm.merge(entry, {'profilbild': {
            'value': 'https://example.org/l.jpg',
            'source': 'https://example.org'}}, pics)
        self.assertNotIn('profilbild', entry)
        self.assertEqual(pics['leer-lena'], 'https://example.org/l.jpg')
        self.assertIn('profilbild', merged)

    def test_post_merge_select_returns_empty_for_field(self):
        data = make_data()
        entry = data['personen'][1]   # leer-lena
        fm.merge(entry, {'links.github': {'value': 'https://github.com/l',
                                          'source': 'https://example.org'}}, {})
        queue, _ = fm.select(data, empty_state(), empty_skip(), {},
                             make_args(ids='leer-lena'))
        self.assertNotIn('links.github', queue[0][1])


class HelperTests(unittest.TestCase):
    def test_migrate_website_key_idempotent(self):
        data = make_data()
        fm.migrate_website_key(data)
        albert = data['personen'][4]
        self.assertEqual(albert['links']['persoenlich'],
                         'https://albert.example.org')
        self.assertNotIn('website', albert['links'])
        fm.migrate_website_key(data)   # second run: no change, no error
        self.assertEqual(albert['links']['persoenlich'],
                         'https://albert.example.org')

    def test_extract_findings_fenced_and_bare(self):
        obj = {'fields': {}, 'sources': {}, 'not_found': []}
        fenced = 'Here you go:\n```json\n' + json.dumps(obj) + '\n```'
        self.assertEqual(fm.extract_findings(fenced), obj)
        bare = 'Result: ' + json.dumps(obj)
        self.assertEqual(fm.extract_findings(bare), obj)

    def test_extract_findings_junk_raises(self):
        with self.assertRaises((ValueError, json.JSONDecodeError)):
            fm.extract_findings('I could not find anything, sorry.')

    def test_classify_error(self):
        self.assertEqual(fm.classify_error('Usage limit reached'), 'rate_limit')
        self.assertEqual(fm.classify_error('boom'), 'agent_error')

    def test_atomic_write_produces_valid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'x.json'
            fm.atomic_write_json(path, {'ä': 1})
            self.assertEqual(json.loads(path.read_text(encoding='utf-8')),
                             {'ä': 1})
            self.assertFalse((Path(tmp) / 'x.json.tmp').exists())


def _churn_writes(path_str, rounds):
    path = Path(path_str)
    for i in range(rounds):
        fm.atomic_write_json(path, {'round': i, 'payload': 'x' * 5000})


class ChaosTests(unittest.TestCase):
    def test_kill_mid_write_never_corrupts(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'data.json'
            fm.atomic_write_json(path, {'round': -1, 'payload': 'x' * 5000})
            for _ in range(10):
                proc = multiprocessing.Process(
                    target=_churn_writes, args=(str(path), 10000))
                proc.start()
                proc.join(timeout=0.02)
                proc.kill()
                proc.join()
                # After every kill the file must still be valid JSON.
                json.loads(path.read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main(verbosity=2)

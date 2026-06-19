#!/usr/bin/env python3
"""Unit tests for the pure normalization core of fetch_courses.py (no network).

Run: python -m unittest research.test_fetch_courses -v   (from repo root)
  or: python research/test_fetch_courses.py
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_courses as fc


def row(name, code, lv_nr, vv_type=None):
    return {'name': name, 'code': code, 'lv_nr': lv_nr, 'vv_type': vv_type or code}


def by_name(courses):
    return {c['name']: c['typ'] for c in courses}


class NormalizeMergeTests(unittest.TestCase):
    def test_exact_uebung_merges_into_single_vplusue(self):
        rows = [row('Telematik', 'V', '19305101'),
                row('Übung zu Telematik', 'Ü', '19305102')]
        out = fc.normalize(rows, 'WS 25/26')
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]['name'], 'Telematik')
        self.assertEqual(out[0]['typ'], 'V+Ü')

    def test_fuzzy_same_module_merges(self):
        # No "Übung zu <title>"/"Tutorium zu" prefix, but same VV module AND
        # more than two shared content words (the fuzzy threshold).
        rows = [row('Diskrete Mathematik für Informatik', 'V', '19300101'),
                row('Tutorium Diskrete Mathematik für Informatik', 'Ü', '19300102')]
        out = fc.normalize(rows, 'WS 25/26')
        self.assertEqual([c['typ'] for c in out], ['V+Ü'])

    def test_fuzzy_does_not_merge_across_modules(self):
        rows = [row('Algorithmen', 'V', '19300101'),
                row('Übung zu Etwas Anderes', 'Ü', '19399902')]
        out = fc.normalize(rows, 'WS 25/26')
        self.assertEqual(sorted(c['typ'] for c in out), ['V', 'Ü'])

    def test_combined_uebung_absorbs_subpart_lectures(self):
        # The real ProInformatik IV case (Larissa Groth, SS 2024).
        rows = [
            row('ProInformatik IVa: Rechnerarchitektur', 'V', '19307801'),
            row('ProInformatik IVb: Betriebs- u. Kommunikationssysteme', 'V', '19327601'),
            row('ProInformatik IVb: Einführung in die Programmierung', 'Ü', '19327602'),
            row('Übung zu ProInformatik IV: Rechnerarchitektur und '
                'Betriebs- u. Kommunikationssysteme', 'Ü', '19307802'),
        ]
        out = fc.normalize(rows, 'SS 2024')
        names = by_name(out)
        self.assertEqual(
            names.get('ProInformatik IV: Rechnerarchitektur und '
                      'Betriebs- u. Kommunikationssysteme'), 'V+Ü')
        # The unrelated "Einführung" Übung is a different topic — left alone.
        self.assertEqual(
            names.get('ProInformatik IVb: Einführung in die Programmierung'), 'Ü')
        self.assertNotIn('ProInformatik IVa: Rechnerarchitektur', names)
        self.assertNotIn('ProInformatik IVb: Betriebs- u. Kommunikationssysteme', names)

    def test_combined_absorption_needs_two_shared_words(self):
        # A single-content-word Übung must NOT swallow a thin-overlap lecture.
        rows = [row('Algorithmen II', 'V', '19300101'),
                row('Übung zu Algorithmen', 'Ü', '19399902')]
        out = fc.normalize(rows, 'WS 25/26')
        self.assertEqual(sorted(c['typ'] for c in out), ['V', 'Ü'])

    def test_redundant_uebung_beside_existing_vplusue_dropped(self):
        # A V+Ü already covers the exercise; a same-title Übung is redundant.
        rows = [row('ProInformatik II: Konzepte der Programmierung', 'V+Ü', '19307601'),
                row('Übung zu ProInformatik II: Konzepte der Programmierung', 'Ü', '19307602')]
        out = fc.normalize(rows, 'SS 2025')
        self.assertEqual([c['typ'] for c in out], ['V+Ü'])

    def test_module_mate_with_different_title_not_dropped(self):
        # Same VV module, DIFFERENT topic — must survive as its own Übung.
        rows = [row('Approximationsalgorithmen', 'V+Ü', '19315401'),
                row('Übung zu Fortgeschrittene Themen der Algorithmik', 'Ü', '19315402')]
        out = fc.normalize(rows, 'SS 2026')
        self.assertEqual(sorted(c['typ'] for c in out), ['V+Ü', 'Ü'])

    def test_dedup_exact_title_and_type(self):
        rows = [row('Seminar: Foo', 'S', '19300111'),
                row('Seminar: Foo', 'S', '19300111')]
        out = fc.normalize(rows, 'WS 25/26')
        self.assertEqual(len(out), 1)

    def test_none_coded_dropped(self):
        rows = [row('Kolloquium X', None, '19300199'),
                row('Telematik', 'V', '19305101')]
        out = fc.normalize(rows, 'WS 25/26')
        self.assertEqual([c['name'] for c in out], ['Telematik'])


class RenormalizeTests(unittest.TestCase):
    def test_legacy_entries_preserved_structured_remerged(self):
        kurse = [
            {'name': 'ProInformatik IVa: Rechnerarchitektur',
             'semester': 'SS 2024', 'typ': 'V', 'lv_nr': '19307801'},
            {'name': 'ProInformatik IVb: Betriebs- u. Kommunikationssysteme',
             'semester': 'SS 2024', 'typ': 'V', 'lv_nr': '19327601'},
            {'name': 'Übung zu ProInformatik IV: Rechnerarchitektur und '
                     'Betriebs- u. Kommunikationssysteme',
             'semester': 'SS 2024', 'typ': 'Ü', 'lv_nr': '19307802'},
            {'name': 'Eine alte Vorlesung', 'semester': 'WS 2012/13'},  # legacy
        ]
        out = fc.renormalize_person(kurse)
        names = by_name([c for c in out if c.get('typ')])
        self.assertEqual(
            names.get('ProInformatik IV: Rechnerarchitektur und '
                      'Betriebs- u. Kommunikationssysteme'), 'V+Ü')
        # Legacy {name, semester} entry survives untouched.
        self.assertIn({'name': 'Eine alte Vorlesung', 'semester': 'WS 2012/13'}, out)

    def test_idempotent_on_already_clean_data(self):
        kurse = [{'name': 'Telematik', 'semester': 'WS 25/26',
                  'typ': 'V+Ü', 'lv_nr': '19305101'}]
        self.assertEqual(fc.renormalize_person(kurse), kurse)


class SemKeyTests(unittest.TestCase):
    def test_recency_ordering(self):
        labels = ['SS 2024', 'WS 25/26', 'WS 23/24', 'SS 2026', 'WS 24/25', 'SS 2025']
        ordered = sorted(labels, key=fc._sem_key, reverse=True)
        self.assertEqual(ordered,
                         ['SS 2026', 'WS 25/26', 'SS 2025', 'WS 24/25', 'SS 2024', 'WS 23/24'])

    def test_two_digit_and_four_digit_years_agree(self):
        self.assertEqual(fc._sem_key('WS 25/26'), fc._sem_key('WS 2025/26'))

    def test_winter_sorts_after_summer_same_year(self):
        self.assertGreater(fc._sem_key('WS 2024/25'), fc._sem_key('SS 2024'))


if __name__ == '__main__':
    unittest.main()

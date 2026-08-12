"""Tests fuer den zugangsdatenfreien Stepstone-Kalibrierer."""

import io
import unittest
from contextlib import contextmanager
from unittest import mock

from unterricht.job_portal import lade_portale
from unterricht.mvps.stepstone_calib import kalibriere


class _Locator:
    @property
    def first(self):
        return self

    def wait_for(self, state=None, timeout=None):
        return None


class _Page:
    def __init__(self):
        self.urls = []

    def goto(self, url, wait_until=None, timeout=None):
        self.urls.append(url)

    def locator(self, _auswahl):
        return _Locator()

    def eval_on_selector_all(self, _auswahl, _skript):
        return []

    def close(self):
        return None


class _Context:
    def __init__(self, zweite_seite):
        self.zweite_seite = zweite_seite

    def new_page(self):
        return self.zweite_seite


class _Engine:
    def __init__(self, erste_seite, zweite_seite):
        self.erste_seite = erste_seite
        self.context = _Context(zweite_seite)

    @contextmanager
    def oeffne_sitzung(self, headless=True):
        yield self.erste_seite, self.context


class StepstoneKalibrierungTest(unittest.TestCase):
    def test_lauf_nutzt_robots_kompatible_oeffentliche_urls(self):
        login_page = _Page()
        search_page = _Page()
        engine = _Engine(login_page, search_page)

        with mock.patch("sys.stdout", new_callable=io.StringIO):
            kalibriere(
                engine_factory=lambda _name: engine,
                portal_loader=lade_portale,
            )

        self.assertEqual(
            login_page.urls,
            ["https://www.stepstone.de/de-DE/candidate/login"],
        )
        self.assertEqual(
            search_page.urls,
            ["https://www.stepstone.de/jobs/in-deutschland?q=java"],
        )
        self.assertNotIn("radius=", search_page.urls[0])


if __name__ == "__main__":
    unittest.main()

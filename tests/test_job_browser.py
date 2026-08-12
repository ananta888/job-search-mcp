"""Tests fuer die schmale Browser-Port des JOB-Agenten (job_browser)."""

import subprocess
import sys
import unittest
from pathlib import Path

from job_search_mcp.infrastructure.browser import (
    BrowserEngine,
    CamoufoxEngine,
    PlaywrightChromiumEngine,
    UiSelectors,
    engine_fuer,
)


class EngineFactoryTest(unittest.TestCase):
    def test_playwright_engine_wird_geliefert(self):
        engine = engine_fuer("playwright")
        self.assertIsInstance(engine, PlaywrightChromiumEngine)
        self.assertEqual(engine.name, "playwright")

    def test_camoufox_engine_wird_geliefert(self):
        engine = engine_fuer("camoufox")
        self.assertIsInstance(engine, CamoufoxEngine)
        self.assertEqual(engine.name, "camoufox")

    def test_unbekannte_engine_wird_abgelehnt(self):
        with self.assertRaises(ValueError):
            engine_fuer("gibts-nicht")

    def test_beide_engines_teilen_die_port(self):
        for engine in (engine_fuer("playwright"), engine_fuer("camoufox")):
            self.assertIsInstance(engine, BrowserEngine)
            self.assertTrue(hasattr(engine, "suche_ui"))


class LazyImportTest(unittest.TestCase):
    """Die Module importieren weder playwright noch camoufox beim Import."""

    def test_module_importiert_ohne_browser_bibliotheken(self):
        projekt_root = Path(__file__).resolve().parents[1]
        code = (
            "import sys; import job_search_mcp.infrastructure.browser; "
            "assert 'playwright' not in sys.modules; "
            "assert 'camoufox' not in sys.modules"
        )
        subprocess.run(
            [sys.executable, "-c", code],
            cwd=projekt_root,
            check=True,
            capture_output=True,
            text=True,
        )


class SucheUiTest(unittest.TestCase):
    """suche_ui treibt fill -> click -> read ueber ein Fake-Browser-Objekt."""

    def test_suche_ui_fuehrt_lernkette_aus_und_raeumt_auf(self):
        seite = _FakePage()
        context = _FakeContext(seite)
        browser = _FakeBrowser(context)
        engine = _EngineMitBrowser(browser)

        result = engine.suche_ui(
            "http://127.0.0.1:1",
            UiSelectors(
                input_label="Suchbegriff",
                submit_role="button",
                submit_name="Suchen",
                output_css="#result",
            ),
            "OCR",
        )

        self.assertEqual(result, "OCR: Text aus Bildern extrahieren")
        self.assertEqual(seite.gestellte_query, "OCR")
        self.assertTrue(seite.geklickt)
        self.assertTrue(seite.gelesen)
        self.assertTrue(context.geschlossen)

    def test_unvollstaendige_selectors_werden_abgelehnt(self):
        engine = _EngineMitBrowser(_FakeBrowser(_FakeContext(_FakePage())))
        with self.assertRaises(ValueError):
            engine.suche_ui(
                "http://127.0.0.1:1",
                UiSelectors(input_label="Suchbegriff"),
                "OCR",
            )

    def test_css_input_wird_als_alternative_zum_label_verwendet(self):
        seite = _FakePage()
        engine = _EngineMitBrowser(_FakeBrowser(_FakeContext(seite)))

        result = engine.suche_ui(
            "http://127.0.0.1:1",
            UiSelectors(
                input_css="input[placeholder*='Jobtitel']",
                submit_name="Jobs finden",
                output_css="#result",
            ),
            "Java",
        )

        self.assertEqual(result, "OCR: Text aus Bildern extrahieren")
        self.assertEqual(seite.gestellte_query, "Java")


class _FakePage:
    def __init__(self) -> None:
        self.gestellte_query: str | None = None
        self.geklickt = False
        self.gelesen = False

    def goto(self, url: str, wait_until: str) -> None:
        pass

    def get_by_label(self, label: str) -> "_FakeFill":
        return _FakeFill(self, label)

    def get_by_role(self, role: str, name: str) -> "_FakeKlick":
        return _FakeKlick(self)

    def locator(self, css: str) -> "_FakeLocator":
        return _FakeLocator(self)


class _FakeFill:
    def __init__(self, page: _FakePage, label: str) -> None:
        self._page = page
        self._label = label

    def fill(self, query: str) -> None:
        self._page.gestellte_query = query


class _FakeKlick:
    def __init__(self, page: _FakePage) -> None:
        self._page = page

    def click(self) -> None:
        self._page.geklickt = True


class _FakeLocator:
    def __init__(self, page: _FakePage) -> None:
        self._page = page

    def wait_for(self, state: str) -> None:
        pass

    def fill(self, query: str) -> None:
        self._page.gestellte_query = query

    def inner_text(self) -> str:
        self._page.gelesen = True
        return "OCR: Text aus Bildern extrahieren"


class _FakeContext:
    def __init__(self, seite: _FakePage) -> None:
        self._seite = seite
        self.geschlossen = False

    def new_page(self) -> _FakePage:
        return self._seite

    def close(self) -> None:
        self.geschlossen = True


class _FakeBrowser:
    def __init__(self, context: _FakeContext) -> None:
        self._context = context

    def new_context(self) -> _FakeContext:
        return self._context


class _EngineMitBrowser(BrowserEngine):
    name = "fake"

    def __init__(self, browser: _FakeBrowser) -> None:
        self._browser = browser

    def _oeffne(self, headless: bool):
        from contextlib import contextmanager

        @contextmanager
        def _kontext():
            yield self._browser

        return _kontext()


if __name__ == "__main__":
    unittest.main()

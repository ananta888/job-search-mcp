"""Schmale Browser-Port fuer den JOB-Agenten (echte Portal-Laeufe).

Domain- und Flow-Code haengen nur von der Port ``BrowserEngine`` ab, nicht von
Playwright oder Camoufox direkt. Beide Browser-Bibliotheken werden lazy
importiert, damit Tests und die Dry-Run-Planung ohne Installation laufen.

Engines:
- ``PlaywrightChromiumEngine``: Standard-Chromium (bisheriges Verhalten).
- ``CamoufoxEngine``: Anti-Detect-Firefox als Playwright-Drop-in
  (camoufox.sync_api.Camoufox).

Jede Engine oeffnet einen isolierten Browser-Kontext und raeumt ihn
deterministisch wieder auf (fill -> click -> read).
"""

from abc import ABC, abstractmethod
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class UiSelectors:
    """Selektoren fuer die UI-Suche (fill -> click -> read)."""

    input_label: str | None = None
    input_css: str | None = None
    submit_role: Literal["button"] = "button"
    submit_name: str | None = None
    output_css: str | None = None


class BrowserEngine(ABC):
    """Port: oeffnet einen Browser und fuehrt eine UI-Suche aus."""

    name: str

    @abstractmethod
    @contextmanager
    def _oeffne(self, headless: bool) -> Iterator[Any]:
        """Liefert ein Playwright-kompatibles Browser-Objekt als Contextmanager."""
        raise NotImplementedError

    def suche_ui(
        self,
        base_url: str,
        selectors: UiSelectors,
        query: str,
        headless: bool = True,
    ) -> str:
        """Fill -> click -> read in einem isolierten BrowserContext."""
        if not (selectors.input_label or selectors.input_css):
            raise ValueError("Selectors unvollstaendig: input_label/input_css fehlen")
        if not selectors.submit_name or not selectors.output_css:
            raise ValueError("Selectors unvollstaendig: submit_name/output_css fehlen")
        with self._oeffne(headless) as browser:
            context = browser.new_context()
            try:
                page = context.new_page()
                page.goto(base_url, wait_until="domcontentloaded")
                if selectors.input_css:
                    page.locator(selectors.input_css).fill(query)
                else:
                    page.get_by_label(selectors.input_label).fill(query)
                page.get_by_role(
                    selectors.submit_role, name=selectors.submit_name
                ).click()
                page.locator(selectors.output_css).wait_for(state="visible")
                return page.locator(selectors.output_css).inner_text()
            finally:
                context.close()

    @contextmanager
    def oeffne_sitzung(
        self,
        storage_state: dict | None = None,
        headless: bool = True,
    ) -> Iterator[Any]:
        """Oeffnet einen BrowserContext, der einen gespeicherten Sitzungszustand
        wiederverwendet (Cookies + localStorage). Liefert ``(page, context)``.

        Der Context wird unabhaengig vom Ausgang deterministisch geschlossen.
        ``storage_state`` ist das Dict, wie es Playwrights
        ``context.storage_state()`` liefert.
        """
        with self._oeffne(headless) as browser:
            context = browser.new_context(storage_state=storage_state or None)
            try:
                page = context.new_page()
                yield page, context
            finally:
                context.close()


class PlaywrightChromiumEngine(BrowserEngine):
    """Standard-Engine: Chromium ueber Playwright."""

    name = "playwright"

    @contextmanager
    def _oeffne(self, headless: bool) -> Iterator[Any]:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=headless)
            try:
                yield browser
            finally:
                browser.close()


class CamoufoxEngine(BrowserEngine):
    """Camoufox: Anti-Detect-Firefox als Playwright-Drop-in."""

    name = "camoufox"

    @contextmanager
    def _oeffne(self, headless: bool) -> Iterator[Any]:
        from camoufox.sync_api import Camoufox

        with Camoufox(headless=headless) as browser:
            yield browser


ENGINES: dict[str, type[BrowserEngine]] = {
    PlaywrightChromiumEngine.name: PlaywrightChromiumEngine,
    CamoufoxEngine.name: CamoufoxEngine,
}


def engine_fuer(name: str) -> BrowserEngine:
    """Liefert die registrierte Engine oder lehnt unbekannte Namen ab."""
    try:
        return ENGINES[name]()
    except KeyError as error:
        raise ValueError(f"Unbekannte Browser-Engine: {name!r}") from error

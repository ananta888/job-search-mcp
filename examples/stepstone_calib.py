"""Stepstone-Kalibrierungs-MVP: Selektoren gegen die Live-Seite ermitteln.

Standard ist ein Dry-Run, der nur die konfigurierten Werte aus
``profiles/portals/stepstone.yaml`` zeigt. Mit ``--run`` oeffnet Camoufox
(Anti-Detect-Firefox) die Login- und Suchseite und sammelt die dort tatsaechlich
vorhandenen Formularfelder und Ergebnis-Karten, damit die ``selectors``/
``login``/``suche``-Werte des Portal-Profils kalibriert werden koennen.

Kein Zugangsdaten-Login: Es werden nur oeffentlich zugängliche Seiten
analysiert. ToS und robots.txt von Stepstone beachten.
"""

import argparse
import json
from collections.abc import Callable
from typing import Any

from job_search_mcp.infrastructure.browser import engine_fuer
from job_search_mcp.infrastructure.browser_session import such_url
from job_search_mcp.infrastructure.portal_config import PortalProfil, lade_portale


def _werte_json(seite: Any, auswahl: str) -> list[dict[str, object]]:
    return seite.eval_on_selector_all(
        auswahl,
        "els => els.map(e => ({"
        "text: (e.innerText || '').trim().slice(0, 60),"
        "type: e.getAttribute('type') || e.tagName,"
        "name: e.getAttribute('name'),"
        "id: e.getAttribute('id'),"
        "placeholder: e.getAttribute('placeholder'),"
        "ariaLabel: e.getAttribute('aria-label'),"
        "dataTestid: e.getAttribute('data-testid')"
        "}))",
    )


def _warte_auf_kandidaten(seite: Any, auswahl: str, timeout_ms: int) -> None:
    """Best effort: Die Kalibrierung darf auch eine leere Kandidatenliste zeigen."""
    try:
        seite.locator(auswahl).first.wait_for(state="attached", timeout=timeout_ms)
    except Exception:  # noqa: BLE001 -- Diagnose darf leere Kandidaten zeigen
        return


def kalibriere(
    engine_name: str = "camoufox",
    *,
    engine_factory: Callable[[str], Any] = engine_fuer,
    portal_loader: Callable[[], list[PortalProfil]] = lade_portale,
) -> None:
    stepstone = next(p for p in portal_loader() if p.name == "stepstone")
    print(f"Konfigurierte Selektoren ({engine_name}):")
    print(
        json.dumps(
            stepstone.model_dump(exclude_none=True), indent=2, ensure_ascii=False
        )
    )

    engine = engine_factory(engine_name)
    with engine.oeffne_sitzung(headless=True) as (page, _context):
        login_url = (
            stepstone.login.url
            if stepstone.login is not None
            else "https://www.stepstone.de/de-DE/candidate/login"
        )
        page.goto(
            login_url,
            wait_until="domcontentloaded",
            timeout=90000,
        )
        _warte_auf_kandidaten(page, "input, button", timeout_ms=15000)
        print("\n=== LOGIN: Input-Felder ===")
        print(json.dumps(_werte_json(page, "input"), ensure_ascii=False, indent=1))
        print("\n=== LOGIN: Buttons ===")
        print(json.dumps(_werte_json(page, "button"), ensure_ascii=False, indent=1))
        page.close()

        page = _context.new_page()
        page.goto(
            such_url(stepstone, "java"),
            wait_until="domcontentloaded",
            timeout=90000,
        )
        _warte_auf_kandidaten(
            page,
            "h2, [data-testid*='jobTitle'], [data-testid*='title']",
            timeout_ms=20000,
        )
        print("\n=== SUCHE: data-testid-Knoten der Trefferliste ===")
        testids = page.eval_on_selector_all(
            "[data-testid*='searchResult'], [data-testid*='jobCard'], [data-testid*='searchResultItem']",
            "els => els.slice(0, 8).map(e => e.getAttribute('data-testid'))",
        )
        print(json.dumps(list(testids), ensure_ascii=False, indent=1))
        print("\n=== SUCHE: Titel der ersten Karten ===")
        titel = page.eval_on_selector_all(
            "h2, [data-testid*='jobTitle'], [data-testid*='title']",
            "els => els.slice(0, 5).map(e => (e.innerText || '').trim().slice(0, 80))",
        )
        print(json.dumps(list(titel), ensure_ascii=False, indent=1))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--run", action="store_true", help="Wirklich gegen stepstone.de kalibrieren"
    )
    args = parser.parse_args()
    if not args.run:
        print(
            "Dry-Run. Kalibrierung starten mit: python -m examples.stepstone_calib --run"
        )
        return
    kalibriere()


if __name__ == "__main__":
    main()

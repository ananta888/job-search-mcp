"""Camoufox-MVP: Anti-Detect-Firefox als Playwright-Drop-in im JOB-Agenten.

Die Engine (unterricht.job_browser.CamoufoxEngine) laeuft gegen die lokale
Sandbox auf 127.0.0.1 - der sichere Lernweg des Unterrichtslabors. Standard ist
ein Dry-Run; der echte Lauf wird mit --run gestartet und benoetigt eine
installierte Camoufox-Browser-Binary (pip install -U camoufox; camoufox fetch).
"""

import argparse
from importlib.metadata import PackageNotFoundError, version

from unterricht.job_browser import UiSelectors, engine_fuer
from unterricht.profile import load_profile
from unterricht.server import DemoServer


def run(echt: bool = False) -> None:
    try:
        installed = version("camoufox")
    except PackageNotFoundError as error:
        raise RuntimeError(
            "Camoufox ist nicht installiert. Installieren mit: pip install -U camoufox; camoufox fetch"
        ) from error

    profil = load_profile()
    selectors = UiSelectors(
        input_label=profil.selectors.input_label,
        submit_role=profil.selectors.submit_role,
        submit_name=profil.selectors.submit_name,
        output_css=profil.selectors.output_css,
    )
    print(f"Camoufox {installed}: UI-Suche gegen die lokale Sandbox vorbereitet.")
    if not echt:
        print("Dry-Run; echter Lauf optional mit --run")
        return

    with DemoServer() as server:
        engine = engine_fuer("camoufox")
        ui_output = engine.suche_ui(server.base_url, selectors, "OCR", headless=True)
    print(f"Camoufox: {ui_output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true", help="Camoufox wirklich starten")
    run(parser.parse_args().run)

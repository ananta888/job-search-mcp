"""Job-Flow: Profil -> Portal-Suche -> Policy -> Validierung -> Match -> Bericht.

Der sichere Kernpfad laeuft ausschliesslich gegen die lokale Sandbox. Echte
Portale (kind=real) sind nur optional und zusaetzlich durch die Umgebungsvariable
ALLOW_EXTERNAL_PORTALS=1 sowie ein Dry-Run-Verhalten geschuetzt.
"""

import os
from dataclasses import replace
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

from unterricht.job_browser import UiSelectors, engine_fuer
from unterricht.job_match import angebot_aus_dict, bewerte_angebote
from unterricht.job_models import JobAngebot, JobMatch, JobProfil
from unterricht.job_portal import PortalProfil, lade_portale
from unterricht.job_profile import STANDARD_PROFIL, lade_profil
from unterricht.job_report import schreibe_bericht
from unterricht.models import ReplayRequest
from unterricht.policy import assert_replay_allowed
from unterricht.server import DemoServer
from unterricht.validation import validate_schema

ROOT = Path(__file__).resolve().parent
BERICHT_DIR = ROOT / "berichte"
EXTERNAL_ALLOWED = "ALLOW_EXTERNAL_PORTALS"


def filtere_nach_suchbegriffen(
    profil: JobProfil, angebote: list[JobAngebot]
) -> list[JobAngebot]:
    if not profil.suchbegriffe:
        return angebote
    gefiltert: list[JobAngebot] = []
    for angebot in angebote:
        suchtext = " ".join(
            [
                angebot.titel.casefold(),
                angebot.beschreibung.casefold(),
                " ".join(sorted(angebot.skills)),
            ]
        )
        if any(begriff in suchtext for begriff in profil.suchbegriffe):
            gefiltert.append(angebot)
    return gefiltert


def suche_portal(portal: PortalProfil, base_url: str | None = None) -> list[JobAngebot]:
    """Ruft ein Portal direkt per HTTPX auf: Normalisierung -> Policy -> Replay -> Validierung."""
    url = (base_url or portal.base_url) + portal.search_path
    replay = ReplayRequest(
        method="GET",
        url=url,
        headers={"accept": "application/json"},
        json_body={},
    )
    assert_replay_allowed(replay, portal.policy)
    with httpx.Client(timeout=5, follow_redirects=False) as client:
        response = client.request(method="GET", url=url, headers=replay.headers)
    response.raise_for_status()
    payload: Any = response.json()
    if not isinstance(payload, dict):
        raise TypeError("Die Portalantwort muss ein JSON-Objekt sein")
    validate_schema(payload, portal.validation.schema_file)

    angebote: list[JobAngebot] = []
    for rohdaten in payload.get("jobs", []):
        if not isinstance(rohdaten, dict):
            raise TypeError("Jedes Angebot muss ein JSON-Objekt sein")
        angebote.append(replace(angebot_aus_dict(rohdaten), portal=portal.portal_id))
    return angebote


def crawl_erlaubt(portal: PortalProfil) -> bool:
    if not portal.erlaubt:
        return False
    if portal.kind == "real":
        return os.getenv(EXTERNAL_ALLOWED) == "1"
    return True


def crawl_lokale_portale(
    portale: list[PortalProfil],
    base_url: str,
) -> tuple[list[JobAngebot], list[str]]:
    angebote: list[JobAngebot] = []
    quellen: list[str] = []
    for portal in portale:
        if portal.kind != "local" or not portal.erlaubt:
            continue
        angebote.extend(suche_portal(portal, base_url))
        quellen.append(portal.name)
    return angebote, quellen


def plan_echtes_portal(portal: PortalProfil) -> dict[str, object]:
    """Beschreibt, was ein echter Portal-Lauf taete - ohne Netzwerkzugriff."""
    return {
        "portal": portal.name,
        "kind": portal.kind,
        "base_url": portal.base_url,
        "search_path": portal.search_path,
        "browser": portal.browser,
        "hinweis": (
            "Dry-Run. Fuer einen echten Lauf kind=real + enabled=true + "
            f"{EXTERNAL_ALLOWED}=1 + Engine '{portal.browser}' erforderlich."
        ),
    }


def crawle_echtes_portal(
    portal: PortalProfil,
    query: str,
    allow_external: bool = False,
) -> dict[str, object]:
    """Gated echte Portal-Analyse: standardmaessig Dry-Run, sonst UI-Suche
    ueber die konfigurierte Browser-Engine (playwright oder camoufox)."""
    if portal.kind != "real":
        raise ValueError(
            f"analysiere_echtes_portal erwartet kind=real, erhalten: {portal.kind}"
        )
    if not allow_external:
        return plan_echtes_portal(portal)
    if not portal.enabled:
        raise ValueError(f"Portal ist deaktiviert (enabled=false): {portal.name}")
    if os.getenv(EXTERNAL_ALLOWED) != "1":
        raise ValueError(f"Echter Lauf verlangt {EXTERNAL_ALLOWED}=1")
    if not portal.selectors or not (
        portal.selectors.input_label or portal.selectors.input_css
    ):
        raise ValueError(f"Portal hat keine Selectors fuer UI-Discovery: {portal.name}")

    engine = engine_fuer(portal.browser)
    ui_selectors = UiSelectors(
        input_label=portal.selectors.input_label,
        input_css=portal.selectors.input_css,
        submit_role=portal.selectors.submit_role,
        submit_name=portal.selectors.submit_name,
        output_css=portal.selectors.output_css,
    )
    ziel = urlsplit(portal.base_url + portal.search_path)
    ui_output = engine.suche_ui(
        portal.base_url,
        ui_selectors,
        query,
        headless=True,
    )
    return {
        "portal": portal.name,
        "ziel": f"{ziel.scheme}://{ziel.netloc}{ziel.path}",
        "browser": portal.browser,
        "ui_output": ui_output,
        "hinweis": "Echter Lauf ausgefuehrt; ToS und robots.txt des Portals beachten.",
    }


def sammle_angebote(
    profil_pfad: Path = STANDARD_PROFIL,
    portal_ids: list[str] | None = None,
) -> tuple[JobProfil, list[JobAngebot], list[str]]:
    """Sammelt Angebote aller (lokal erlaubten) Portale und filtert per Suchbegriff."""
    profil = lade_profil(profil_pfad)
    portale = lade_portale()
    if portal_ids:
        auswahl = {portal_id.casefold() for portal_id in portal_ids}
        portale = [
            portal for portal in portale if portal.portal_id.casefold() in auswahl
        ]
    with DemoServer() as server:
        angebote, quellen = crawl_lokale_portale(portale, server.base_url)
    angebote = filtere_nach_suchbegriffen(profil, angebote)
    return profil, angebote, quellen


def lauf(
    profil_pfad: Path = STANDARD_PROFIL,
    bericht_pfad: Path | None = None,
) -> tuple[JobProfil, list[JobMatch], Path]:
    """Fuehrt den vollstaendigen lokalen Job-Flow aus und schreibt den Bericht."""
    profil, angebote, quellen = sammle_angebote(profil_pfad)
    matches = bewerte_angebote(profil, angebote)
    ziel = bericht_pfad or (BERICHT_DIR / "job-report.md")
    pfad = schreibe_bericht(ziel, profil, matches, quellen)
    return profil, matches, pfad


def run() -> None:
    profil, matches, pfad = lauf()
    passende = sum(1 for match in matches if match.passt)
    print(f"Job-Flow: Profil {profil.name!r}")
    print(f"Passende Angebote: {passende}, ausgeschlossen: {len(matches) - passende}")
    print(f"Bericht: {pfad}")


if __name__ == "__main__":
    run()

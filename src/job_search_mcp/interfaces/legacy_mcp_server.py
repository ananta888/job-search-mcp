"""Eigener MCP-Server fuer den JOB-Agenten (stdio-Transport).

Die Tools sind duenne Schalen ueber die Kernfunktionen des Unterrichtslabors
und damit direkt und ohne MCP-Protokoll testbar.

Der Server bleibt als kompatible, kleinere Werkzeugoberfläche erhalten. Der
primäre CLI-Einstieg ist ``job-search-mcp``.
"""

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from job_search_mcp.application.job_flow import (
    BERICHT_DIR,
    crawl_erlaubt,
    crawle_echtes_portal,
    lade_portale,
    sammle_angebote,
)
from job_search_mcp.application.reporting import schreibe_bericht
from job_search_mcp.domain.matching import angebot_aus_dict
from job_search_mcp.domain.matching import bewerte_angebote as bewerte_angebote_kern
from job_search_mcp.domain.models import JobAngebot, JobMatch, JobProfil
from job_search_mcp.infrastructure.profile_repository import (
    lade_profil as lade_profil_modell,
)
from job_search_mcp.paths import resolve_profile_path

mcp = FastMCP("job-crawler")


def _abs_profil_pfad(pfad: str) -> Path:
    return resolve_profile_path(pfad)


def profil_zu_dict(profil: JobProfil) -> dict[str, object]:
    return {
        "name": profil.name,
        "suchbegriffe": list(profil.suchbegriffe),
        "skills_pflicht": sorted(profil.skills_pflicht),
        "skills_wunsch": sorted(profil.skills_wunsch),
        "orte": list(profil.orte),
        "arbeitsmodelle": list(profil.arbeitsmodelle),
        "gehalt_min": profil.gehalt_min,
        "gehalt_max": profil.gehalt_max,
        "sprachen": sorted(profil.sprachen),
        "min_erfahrung_jahre": profil.min_erfahrung_jahre,
        "min_pflicht_skills": profil.min_pflicht_skills,
    }


def angebot_zu_dict(angebot: JobAngebot) -> dict[str, object]:
    link = angebot.id if angebot.id.startswith(("https://", "http://")) else ""
    return {
        "id": angebot.id,
        "link": link,
        "portal": angebot.portal,
        "firma": angebot.firma,
        "titel": angebot.titel,
        "ort": angebot.ort,
        "arbeitsmodell": angebot.arbeitsmodell,
        "skills": sorted(angebot.skills),
        "gehalt_min": angebot.gehalt_min,
        "gehalt_max": angebot.gehalt_max,
        "sprachen": sorted(angebot.sprachen),
        "erfahrungsjahre": angebot.erfahrungsjahre,
        "beschreibung": angebot.beschreibung,
    }


def match_zu_dict(match: JobMatch) -> dict[str, object]:
    return {
        "score": match.score,
        "passt": match.passt,
        "angebot": angebot_zu_dict(match.angebot),
        "gefundene_skills": list(match.gefundene_skills),
        "fehlende_pflicht_skills": list(match.fehlende_pflicht_skills),
        "gruende": list(match.gruende),
    }


def angebote_aus_dicts(roh: list[dict]) -> list[JobAngebot]:
    return [angebot_aus_dict(eintrag) for eintrag in roh]


@mcp.tool()
def lade_profil(profil_pfad: str = "job-profile.json") -> dict[str, object]:
    """Liest und validiert das vorgegebene Jobsuchprofil (JSON + JSON-Schema)."""
    return profil_zu_dict(lade_profil_modell(_abs_profil_pfad(profil_pfad)))


@mcp.tool()
def liste_portale() -> list[dict[str, object]]:
    """Listet alle konfigurierten Job-Portale mit Erlaubnisstatus."""
    return [
        {
            "name": portal.name,
            "kind": portal.kind,
            "enabled": portal.enabled,
            "erlaubt": crawl_erlaubt(portal),
            "portal_id": portal.portal_id,
            "base_url": portal.base_url,
            "search_path": portal.search_path,
            "browser": portal.browser,
        }
        for portal in lade_portale()
    ]


@mcp.tool()
def suche_angebote(
    profil_pfad: str = "job-profile.json",
    portal_ids: list[str] | None = None,
) -> dict[str, object]:
    """Crawlt lokale Portale ueber Policy+Validierung und filtert per Suchbegriff."""
    profil, angebote, quellen = sammle_angebote(
        _abs_profil_pfad(profil_pfad), portal_ids
    )
    return {
        "profil": profil_zu_dict(profil),
        "quellen": quellen,
        "angebote": [angebot_zu_dict(angebot) for angebot in angebote],
    }


@mcp.tool()
def bewerte_angebote(
    profil_pfad: str = "job-profile.json",
    angebote: list[dict] | None = None,
) -> dict[str, object]:
    """Bewertet Angebote gegen das Profil und liefert sortierte Matches."""
    profil = lade_profil_modell(_abs_profil_pfad(profil_pfad))
    matches = bewerte_angebote_kern(profil, angebote_aus_dicts(angebote or []))
    return {"matches": [match_zu_dict(match) for match in matches]}


@mcp.tool()
def erstelle_bericht(
    profil_pfad: str = "job-profile.json",
    angebote: list[dict] | None = None,
    quellen: list[str] | None = None,
    bericht_pfad: str | None = None,
) -> str:
    """Bewertet Angebote und schreibt den Markdown-Bericht; liefert den Pfad."""
    profil = lade_profil_modell(_abs_profil_pfad(profil_pfad))
    matches = bewerte_angebote_kern(profil, angebote_aus_dicts(angebote or []))
    ziel = Path(bericht_pfad) if bericht_pfad else BERICHT_DIR / "job-report.md"
    pfad = schreibe_bericht(ziel, profil, matches, quellen or [])
    return str(pfad)


@mcp.tool()
def analysiere_echtes_portal(
    portal_name: str,
    query: str,
    allow_external: bool = False,
) -> dict[str, object]:
    """Analysiert ein echtes Portal; standardmaessig Dry-Run, echter Zugriff nur
    mit ALLOW_EXTERNAL_PORTALS=1 und allow_external=true."""
    for portal in lade_portale():
        if portal.name == portal_name:
            return crawle_echtes_portal(portal, query, allow_external)
    raise ValueError(f"Unbekanntes Portal: {portal_name}")


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()

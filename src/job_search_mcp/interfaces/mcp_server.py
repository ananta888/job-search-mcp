"""MCP-Server fuer die Jobsuche (Login + Sitzung + Suche) ueber echte Portale.

Erweitert den bestehenden ``job-crawler``-Server um browserbasierte Werkzeuge:

- Anmeldedaten verschluesselt hinterlegen (Fernet, nie loggen).
- Oeffentliche Suchen headless ohne Login; Ortsfilter ueber kanonische Pfade.
- Optionaler Login interaktiv (sichtbares Camoufox-Fenster) oder per Auto-Fill.
- Sitzungszustand fuer kontogebundene Funktionen speichern und wiederverwenden.
- Suche auf Basis des Jobprofils, Bewertung und Markdown-Bericht.

Treiber: camoufox primaer, browser-use als Fallback. Laeuft lokal ohne Docker.
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from job_search_mcp.application.job_flow import (
    BERICHT_DIR,
    crawl_erlaubt,
    crawle_echtes_portal,
    lade_portale,
)
from job_search_mcp.application.reporting import schreibe_bericht
from job_search_mcp.domain.matching import angebot_aus_dict
from job_search_mcp.domain.matching import bewerte_angebote as bewerte_kern
from job_search_mcp.domain.models import JobAngebot, JobProfil
from job_search_mcp.infrastructure.browser_session import (
    BrowserSessionFehler,
    BrowserSessionManager,
    BrowserUseTreiber,
)
from job_search_mcp.infrastructure.credentials import CredentialStore
from job_search_mcp.infrastructure.feeds import suche_feed
from job_search_mcp.infrastructure.portal_config import (
    PortalProfil,
    lade_portal_katalog,
)
from job_search_mcp.infrastructure.profile_repository import (
    lade_profil as lade_profil_modell,
)
from job_search_mcp.interfaces.legacy_mcp_server import (
    angebot_zu_dict,
    match_zu_dict,
    profil_zu_dict,
)
from job_search_mcp.paths import resolve_profile_path

mcp = FastMCP("job-search")


def _projekt_pfad(pfad: str | Path) -> Path:
    gewaehlt = Path(pfad).expanduser()
    if gewaehlt.is_absolute():
        return gewaehlt
    return gewaehlt.resolve()


def _profil_pfad(pfad: str | Path) -> Path:
    return resolve_profile_path(pfad)


def _state_dir() -> Path:
    konfiguriert = os.getenv("JOB_MCP_STATE_DIR")
    if konfiguriert:
        return _projekt_pfad(konfiguriert)
    xdg_state = os.getenv("XDG_STATE_HOME")
    basis = (
        Path(xdg_state).expanduser() if xdg_state else Path.home() / ".local" / "state"
    )
    return basis / "job-search-mcp"


def _manager() -> BrowserSessionManager:
    return BrowserSessionManager(_state_dir(), CredentialStore(_state_dir()))


def _portal(portal_id: str) -> PortalProfil:
    for portal in lade_portale():
        if portal.portal_id == portal_id:
            return portal
    raise ValueError(f"Unbekanntes Portal: {portal_id}")


def _engine_verfuegbar(modul: str) -> bool:
    try:
        __import__(modul)
        return True
    except ImportError:
        return False


def _sichtbarer_browser_status() -> dict[str, object]:
    """Beschreibt den lokalen Anzeigeweg fuer einen interaktiven Browser."""
    if os.name == "nt" or sys.platform == "darwin":
        return {
            "verfuegbar": True,
            "technik": "Desktop",
            "hinweis": "Ein sichtbares Browserfenster kann lokal geoeffnet werden.",
        }
    if os.getenv("DISPLAY") or os.getenv("WAYLAND_DISPLAY"):
        technik = "WSLg/X11" if os.getenv("WSL_DISTRO_NAME") else "X11/Wayland"
        return {
            "verfuegbar": True,
            "technik": technik,
            "hinweis": "portal_login(sichtbar=true) oeffnet den verwendeten Browser.",
        }
    return {
        "verfuegbar": False,
        "technik": None,
        "hinweis": (
            "Keine grafische Anzeige gefunden. Unter WSL WSLg aktivieren und "
            "OpenCode aus einem Terminal mit DISPLAY/Wayland neu starten."
        ),
    }


def _text_enthaelt(text: str, begriff: str) -> bool:
    muster = re.escape(begriff).replace(r"\ ", r"\s+")
    return re.search(rf"(?<!\w){muster}(?!\w)", text, re.IGNORECASE) is not None


def _reichere_eintrag_an(
    eintrag: dict[str, Any],
    profil: JobProfil,
) -> dict[str, Any]:
    """Ergaenzt nur profilbekannte Werte, die im sichtbaren Kartentext stehen."""
    angereichert = dict(eintrag)
    text = " ".join(
        str(eintrag.get(feld, "")) for feld in ("titel", "firma", "ort", "beschreibung")
    )

    vorhandene_skills = eintrag.get("skills")
    skills = (
        {str(wert) for wert in vorhandene_skills}
        if isinstance(vorhandene_skills, (list, tuple, set))
        else set()
    )
    for skill in profil.skills_pflicht | profil.skills_wunsch:
        if _text_enthaelt(text, skill):
            skills.add(skill)
    angereichert["skills"] = sorted(skills, key=str.casefold)

    vorhandene_sprachen = eintrag.get("sprachen")
    sprachen = (
        {str(wert) for wert in vorhandene_sprachen}
        if isinstance(vorhandene_sprachen, (list, tuple, set))
        else set()
    )
    for sprache in profil.sprachen:
        if _text_enthaelt(text, sprache):
            sprachen.add(sprache)
    angereichert["sprachen"] = sorted(sprachen, key=str.casefold)

    if not str(eintrag.get("arbeitsmodell", "")).strip():
        for arbeitsmodell in profil.arbeitsmodelle:
            if _text_enthaelt(text, arbeitsmodell):
                angereichert["arbeitsmodell"] = arbeitsmodell
                break
    return angereichert


@mcp.tool()
def browser_status(portal_id: str | None = None) -> dict[str, object]:
    """Zeigt verfuegbare Browser-Treiber und den Sitzungsstatus der Portale."""
    if portal_id is not None:
        _portal(portal_id)
    manager = _manager()
    portal_status: list[dict[str, object]] = []
    for portal in lade_portale():
        if (
            portal.kind != "real"
            or portal.feed is not None
            or (portal_id and portal.portal_id != portal_id)
        ):
            continue
        status = manager.status(portal)
        portal_status.append(
            {
                "portal_id": status.portal_id,
                "treiber": status.treiber,
                "treiber_verfuegbar": status.treiber_verfuegbar,
                "sitzung_vorhanden": status.sitzung_vorhanden,
                "anmeldedaten_vorhanden": status.anmeldedaten_vorhanden,
                "login_fuer_suche_erforderlich": (status.login_fuer_suche_erforderlich),
                "anmerkungen": list(status.anmerkungen),
            }
        )
    fallback = BrowserUseTreiber()
    return {
        "state_dir": str(_state_dir()),
        "sichtbarer_browser": _sichtbarer_browser_status(),
        "engines": {
            "camoufox": _engine_verfuegbar("camoufox"),
            "playwright": _engine_verfuegbar("playwright"),
            "browser_use": _engine_verfuegbar("browser_use"),
        },
        "browser_use_fallback_bereit": fallback.verfuegbar(),
        "portale": portal_status,
    }


@mcp.tool()
def anmeldedaten_hinterlegen(
    portal_id: str,
    benutzername: str,
    passwort: str,
) -> dict[str, object]:
    """Hinterlegt Anmeldedaten verschluesselt (Fernet). Klartext wird nie geloggt."""
    portal = _portal(portal_id)
    _gate_check(portal)
    store = CredentialStore(_state_dir())
    war_vorhanden = store.vorhanden(portal_id)
    store.hinterlege(portal_id, benutzername, passwort)
    return {
        "status": "gespeichert",
        "portal_id": portal_id,
        "ersetzt": war_vorhanden,
        "hinweis": "Anmeldedaten liegen verschluesselt vor und werden beim Login verwendet.",
    }


@mcp.tool()
def anmeldedaten_entfernen(portal_id: str) -> dict[str, object]:
    """Loescht hinterlegte Anmeldedaten eines Portals."""
    _portal(portal_id)
    entfernt = CredentialStore(_state_dir()).entferne(portal_id)
    return {"status": "entfernt" if entfernt else "keine_daten", "portal_id": portal_id}


def portal_login(
    portal_id: str,
    sichtbar: bool = True,
    auto: bool = True,
) -> dict[str, object]:
    """Loggt in ein echtes Portal ein und speichert die Sitzung.

    Mit hinterlegten Anmeldedaten (auto=true) wird Auto-Fill versucht; sonst
    oeffnet sich ein sichtbares Browserfenster fuer den manuellen Login.
    """
    portal = _portal(portal_id)
    _gate_check(portal)
    if sichtbar:
        anzeige = _sichtbarer_browser_status()
        if not anzeige["verfuegbar"]:
            raise BrowserSessionFehler(str(anzeige["hinweis"]))
    manager = _manager()
    if auto and manager.anmeldedaten_vorhanden(portal_id):
        return manager.anmelden(portal, sichtbar=sichtbar)
    return manager.login_interaktiv(portal, sichtbar=sichtbar)


@mcp.tool()
def portal_sitzung_loeschen(portal_id: str) -> dict[str, object]:
    """Loescht die gespeicherte Sitzung eines Portals (Logout auf Client-Seite)."""
    _portal(portal_id)
    entfernt = _manager().sitzung_loeschen(portal_id)
    return {
        "status": "entfernt" if entfernt else "keine_sitzung",
        "portal_id": portal_id,
    }


def portal_suche(
    portal_id: str,
    query: str | None = None,
    ort: str | None = None,
    profil_pfad: str = "job-profile.json",
    engine: str = "auto",
) -> dict[str, object]:
    """Sucht in einem Portal und liefert Treffer als Angebote.

    ``query`` ist optional; ohne Angabe wird das erste Suchbegriff-Feld des
    Jobprofils verwendet. ``ort`` setzt, soweit das Portal dies unterstützt,
    einen echten Ortsfilter. ``engine``: auto (camoufox, Fallback browser-use)
    oder browser-use. Ein Login wird nur verlangt, wenn das Portalprofil die
    Suche als ``login_erforderlich`` kennzeichnet.
    """
    portal = _portal(portal_id)
    _gate_check(portal)
    profil = lade_profil_modell(_profil_pfad(profil_pfad))
    if query is None:
        suchtext = profil.suchbegriffe[0] if profil.suchbegriffe else ""
    else:
        suchtext = query.strip()
    if not suchtext:
        raise ValueError("Es ist weder query noch ein Suchbegriff im Profil angegeben.")
    if portal.feed is not None:
        if engine != "auto":
            raise ValueError("Feed-Portale unterstuetzen nur engine='auto'.")
        roh = suche_feed(portal, suchtext, ort)
        sitzungsmodus = "oeffentlicher_feed"
    elif engine == "browser-use":
        manager = _manager()
        login_erforderlich = bool(portal.suche and portal.suche.login_erforderlich)
        if login_erforderlich and not manager.sitzung_vorhanden(portal_id):
            raise BrowserSessionFehler(
                f"Keine Sitzung fuer {portal_id!r}; erst portal_login ausfuehren."
            )
        sitzung = manager.sitzung_laden(portal_id) or {}
        roh = BrowserUseTreiber().suchen(portal, suchtext, sitzung, "", ort=ort)
    elif engine == "auto":
        manager = _manager()
        roh = manager.suche_mit_fallback(portal, suchtext, anmerkung="", ort=ort)
    else:
        raise ValueError(f"Unbekannte Engine: {engine} (auto | browser-use)")
    angebote = [
        angebot_aus_dict(_reichere_eintrag_an(eintrag, profil))
        for eintrag in roh
        if eintrag.get("titel")
    ]
    if portal.feed is None:
        sitzungsmodus = (
            "gespeichert" if manager.sitzung_vorhanden(portal_id) else "oeffentlich"
        )
    return {
        "portal": portal_id,
        "zugriffsart": _zugangsart(portal_id),
        "query": suchtext,
        "ort": ort,
        "engine": engine,
        "sitzungsmodus": sitzungsmodus,
        "angebote": [angebot_zu_dict(angebot) for angebot in angebote],
        "roh_anzahl": len(roh),
    }


def portal_recherche(
    portal_id: str,
    profil_pfad: str = "job-profile.json",
    max_begriffe: int = 3,
    bericht_pfad: str | None = None,
    ort: str | None = None,
) -> dict[str, object]:
    """Vollstaendige Recherche ueber das Profil: Suche -> Bewertung -> Bericht.

    Sucht mit den ersten ``max_begriffe`` Suchbegriffen des Profils,
    dedupliziert, bewertet gegen das Profil und schreibt den Markdown-Bericht.
    Ein Login ist nur bei entsprechend konfigurierten Portalen erforderlich.
    """
    portal = _portal(portal_id)
    _gate_check(portal)
    if max_begriffe < 1:
        raise ValueError("max_begriffe muss mindestens 1 sein.")
    profil = lade_profil_modell(_profil_pfad(profil_pfad))
    begriffe = profil.suchbegriffe[:max_begriffe]
    if not begriffe:
        raise ValueError("Das Jobprofil enthaelt keine Suchbegriffe.")
    manager = None
    if portal.feed is None:
        manager = _manager()
        login_erforderlich = bool(portal.suche and portal.suche.login_erforderlich)
        if login_erforderlich and not manager.sitzung_vorhanden(portal_id):
            raise BrowserSessionFehler(
                f"Keine Sitzung fuer {portal_id!r}; erst portal_login ausfuehren."
            )
    gesammelt: dict[str, JobAngebot] = {}
    for begriff in begriffe:
        if portal.feed is not None:
            roh = suche_feed(portal, begriff, ort)
        else:
            assert manager is not None
            roh = manager.suche_mit_fallback(
                portal, begriff, anmerkung="profilbasiert", ort=ort
            )
        for eintrag in roh:
            if not eintrag.get("titel"):
                continue
            angebot = angebot_aus_dict(_reichere_eintrag_an(eintrag, profil))
            gesammelt.setdefault(angebot.id, angebot)
    angebote = list(gesammelt.values())
    matches = _bewerte(profil, angebote)
    ziel = (
        _projekt_pfad(bericht_pfad)
        if bericht_pfad
        else BERICHT_DIR / f"{portal_id}-report.md"
    )
    pfad = schreibe_bericht(ziel, profil, matches, [portal_id])
    passende = sum(1 for match in matches if match.passt)
    return {
        "portal": portal_id,
        "zugriffsart": _zugangsart(portal_id),
        "ort": ort,
        "sitzungsmodus": (
            "oeffentlicher_feed"
            if portal.feed is not None
            else (
                "gespeichert"
                if manager is not None and manager.sitzung_vorhanden(portal_id)
                else "oeffentlich"
            )
        ),
        "suchbegriffe": list(begriffe),
        "angebote_gefunden": len(angebote),
        "passende": passende,
        "ausgeschlossen": len(matches) - passende,
        "bericht": str(pfad),
        "matches": [match_zu_dict(match) for match in matches],
    }


def _bewerte(profil, angebote):
    return bewerte_kern(profil, angebote)


def _zugangsart(portal_id: str) -> str:
    for eintrag in lade_portal_katalog():
        if eintrag.portal_id == portal_id:
            return eintrag.zugangsart
    return "lokal_oder_nicht_katalogisiert"


@mcp.tool()
def lade_profil(profil_pfad: str = "job-profile.json") -> dict[str, object]:
    """Liest und validiert das vorgegebene Jobsuchprofil (JSON + JSON-Schema)."""
    return profil_zu_dict(lade_profil_modell(_profil_pfad(profil_pfad)))


@mcp.tool()
def liste_portale() -> list[dict[str, object]]:
    """Listet aktive Adapter und weitere Portale mit transparentem Zugangsstatus."""
    profile = {portal.portal_id: portal for portal in lade_portale()}
    ergebnis: list[dict[str, object]] = []
    katalog_ids: set[str] = set()
    for eintrag in lade_portal_katalog():
        katalog_ids.add(eintrag.portal_id)
        portal = profile.get(eintrag.profil_id or eintrag.portal_id)
        ergebnis.append(_portal_zeile(portal, eintrag.model_dump()))
    for portal_id, portal in profile.items():
        if portal_id not in katalog_ids:
            ergebnis.append(
                _portal_zeile(
                    portal,
                    {
                        "portal_id": portal_id,
                        "name": portal.name,
                        "homepage": portal.base_url,
                        "zugangsart": "lokal_oder_nicht_katalogisiert",
                        "status": "aktiv" if portal.enabled else "nicht_angebunden",
                        "hinweis": "Technisches Portalprofil ohne Katalogeintrag.",
                    },
                )
            )
    return ergebnis


def _portal_zeile(
    portal: PortalProfil | None,
    katalog: dict[str, object],
) -> dict[str, object]:
    return {
        **katalog,
        "kind": portal.kind if portal else None,
        "enabled": portal.enabled if portal else False,
        "erlaubt": crawl_erlaubt(portal) if portal else False,
        "base_url": portal.base_url if portal else katalog.get("homepage"),
        "search_path": portal.search_path if portal else None,
        "browser": portal.browser if portal and portal.feed is None else None,
        "feed_adapter": portal.feed.adapter if portal and portal.feed else None,
        "login_konfiguriert": portal.login is not None if portal else False,
        "suche_konfiguriert": (
            portal.suche is not None or portal.feed is not None if portal else False
        ),
        "login_fuer_suche_erforderlich": (
            portal.suche.login_erforderlich if portal and portal.suche else None
        ),
    }


def mehrportal_suche(
    portal_ids: list[str] | None = None,
    query: str | None = None,
    ort: str | None = None,
    profil_pfad: str = "job-profile.json",
) -> dict[str, object]:
    """Durchsucht mehrere aktive Quellen; einzelne Ausfaelle werden isoliert."""
    profil = lade_profil_modell(_profil_pfad(profil_pfad))
    suchtext = query.strip() if query is not None else ""
    if not suchtext:
        suchtext = profil.suchbegriffe[0] if profil.suchbegriffe else ""
    if not suchtext:
        raise ValueError("Es ist weder query noch ein Suchbegriff im Profil angegeben.")
    if portal_ids is None:
        portal_ids = [
            portal.portal_id
            for portal in lade_portale()
            if portal.kind == "real"
            and portal.enabled
            and portal.suchart in {"browser", "feed"}
        ]
    angebote: list[dict[str, object]] = []
    quellen: list[dict[str, object]] = []
    for portal_id in dict.fromkeys(portal_ids):
        try:
            ergebnis = portal_suche(
                portal_id,
                query=suchtext,
                ort=ort,
                profil_pfad=profil_pfad,
            )
            treffer = ergebnis.get("angebote", [])
            if not isinstance(treffer, list):
                treffer = []
            angebote.extend(treffer)
            quellen.append(
                {
                    "portal_id": portal_id,
                    "status": "ok",
                    "zugriffsart": ergebnis.get("zugriffsart"),
                    "angebote": len(treffer),
                }
            )
        # Die Aggregation muss auch unbekannte anbieterspezifische Fehler isolieren.
        except Exception as exc:  # noqa: BLE001
            quellen.append(
                {
                    "portal_id": portal_id,
                    "status": "fehler",
                    "fehler": str(exc),
                    "angebote": 0,
                }
            )
    erfolgreich = sum(1 for quelle in quellen if quelle["status"] == "ok")
    return {
        "query": suchtext,
        "ort": ort,
        "portal_ids": list(dict.fromkeys(portal_ids)),
        "angebote": angebote,
        "angebote_gefunden": len(angebote),
        "quellen": quellen,
        "quellen_erfolgreich": erfolgreich,
        "quellen_fehlgeschlagen": len(quellen) - erfolgreich,
    }


@mcp.tool()
def bewerte_angebote(
    profil_pfad: str = "job-profile.json",
    angebote: list[dict] | None = None,
) -> dict[str, object]:
    """Bewertet Angebote gegen das Profil und liefert sortierte Matches."""
    profil = lade_profil_modell(_profil_pfad(profil_pfad))
    matches = _bewerte(
        profil, [angebot_aus_dict(eintrag) for eintrag in angebote or []]
    )
    return {"matches": [match_zu_dict(match) for match in matches]}


@mcp.tool()
def erstelle_bericht(
    profil_pfad: str = "job-profile.json",
    angebote: list[dict] | None = None,
    quellen: list[str] | None = None,
    bericht_pfad: str | None = None,
) -> str:
    """Bewertet Angebote und schreibt den Markdown-Bericht; liefert den Pfad."""
    profil = lade_profil_modell(_profil_pfad(profil_pfad))
    matches = _bewerte(
        profil, [angebot_aus_dict(eintrag) for eintrag in angebote or []]
    )
    ziel = (
        _projekt_pfad(bericht_pfad) if bericht_pfad else BERICHT_DIR / "job-report.md"
    )
    return str(schreibe_bericht(ziel, profil, matches, quellen or []))


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


def _gate_check(portal: PortalProfil) -> None:
    if portal.kind != "real":
        raise ValueError(
            f"Die Sitzungs-Werkzeuge sind nur fuer echte Portale gedacht: {portal.portal_id}"
        )
    if not crawl_erlaubt(portal):
        raise ValueError(
            f"Portal ist nicht fuer echte Laeufe freigegeben: {portal.portal_id}. "
            "ALLOW_EXTERNAL_PORTALS=1 und enabled=true erforderlich."
        )


@mcp.tool(name="portal_login")
async def _portal_login_tool(
    portal_id: str,
    sichtbar: bool = True,
    auto: bool = True,
) -> dict[str, object]:
    """Oeffnet den Portalbrowser sichtbar fuer den Nutzer und speichert den Login."""
    return await asyncio.to_thread(portal_login, portal_id, sichtbar, auto)


@mcp.tool(name="portal_suche")
async def _portal_suche_tool(
    portal_id: str,
    query: str | None = None,
    ort: str | None = None,
    profil_pfad: str = "job-profile.json",
    engine: str = "auto",
) -> dict[str, object]:
    """Sucht headless nach Stellen; Login wird nur bei Portalpflicht verwendet."""
    return await asyncio.to_thread(
        portal_suche,
        portal_id,
        query,
        ort,
        profil_pfad,
        engine,
    )


@mcp.tool(name="portal_recherche")
async def _portal_recherche_tool(
    portal_id: str,
    profil_pfad: str = "job-profile.json",
    max_begriffe: int = 3,
    bericht_pfad: str | None = None,
    ort: str | None = None,
) -> dict[str, object]:
    """Recherchiert, bewertet und schreibt einen Bericht ausserhalb des MCP-Loops."""
    return await asyncio.to_thread(
        portal_recherche,
        portal_id,
        profil_pfad,
        max_begriffe,
        bericht_pfad,
        ort,
    )


@mcp.tool(name="mehrportal_suche")
async def _mehrportal_suche_tool(
    portal_ids: list[str] | None = None,
    query: str | None = None,
    ort: str | None = None,
    profil_pfad: str = "job-profile.json",
) -> dict[str, object]:
    """Durchsucht aktive Browser- und Feed-Quellen in einem Worker-Thread."""
    return await asyncio.to_thread(
        mehrportal_suche,
        portal_ids,
        query,
        ort,
        profil_pfad,
    )


@mcp.tool(name="analysiere_echtes_portal")
async def _analysiere_echtes_portal_tool(
    portal_name: str,
    query: str,
    allow_external: bool = False,
) -> dict[str, object]:
    """Fuehrt den aelteren echten Browserpfad ausserhalb des MCP-Eventloops aus."""
    return await asyncio.to_thread(
        analysiere_echtes_portal,
        portal_name,
        query,
        allow_external,
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()

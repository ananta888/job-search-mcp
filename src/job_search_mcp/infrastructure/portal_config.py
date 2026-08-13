"""Portal-Profile fuer lokale und (optional) echte Job-Seiten."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator

from job_search_mcp.infrastructure.crawler_config import PolicyProfile
from job_search_mcp.paths import PORTAL_CATALOG_FILE, PORTALS_DIR

PORTALE_DIR = PORTALS_DIR
PORTAL_KATALOG_DATEI = PORTAL_CATALOG_FILE


class PortalFeed(BaseModel):
    """Offiziell angebotener maschinenlesbarer Stellenfeed."""

    adapter: Literal[
        "arbeitnow",
        "remotive",
        "weworkremotely",
        "arbeitsagentur",
        "bw_karriere",
        "jobriver",
        "freelancermap",
        "interamt",
    ]
    endpoint: str
    max_treffer: int = Field(default=20, ge=1, le=100)
    headers: dict[str, str] = Field(default_factory=dict)
    attribution: str | None = None


class PortalKatalogEintrag(BaseModel):
    """Fachliche Einordnung eines Portals, unabhängig von einem Adapter."""

    portal_id: str
    name: str
    homepage: str
    kategorie: Literal[
        "jobboerse",
        "aggregator",
        "remote_jobboerse",
        "matching_plattform",
        "berufsnetzwerk",
        "oeffentliche_vermittlung",
        "suchoberflaeche",
        "freelance_boerse",
    ]
    zugangsart: Literal[
        "browser_oeffentlich",
        "oeffentliche_api",
        "rss_feed",
        "interaktives_konto",
        "partner_api",
        "manuelle_websuche",
    ]
    status: Literal["aktiv", "manuell", "partnerzugang", "gesperrt", "nicht_angebunden"]
    hinweis: str
    profil_id: str | None = None
    dokumentation_url: str | None = None
    bedingungen_url: str | None = None
    attribution: str | None = None


class PortalSelectors(BaseModel):
    input_label: str | None = None
    input_css: str | None = None
    submit_role: Literal["button"] = "button"
    submit_name: str | None = None
    output_css: str | None = None


class PortalLogin(BaseModel):
    """Konfiguration fuer den Login ueber den Sitzungs-Manager."""

    url: str
    benutzername_css: str
    passwort_css: str
    submit_css: str | None = None
    submit_role: Literal["button"] = "button"
    submit_name: str | None = None
    erfolg_url: str | None = None
    erfolg_selector: str | None = None
    timeout_s: int = 240


class PortalSuche(BaseModel):
    """Konfiguration fuer die Extraktion von Ergebnis-Karten aus der Trefferliste."""

    login_erforderlich: bool = True
    ort_pfad_template: str | None = None
    pfad: str | None = None
    query_param: str = "q"
    karte_css: str
    titel_css: str
    firma_css: str | None = None
    ort_css: str | None = None
    arbeitsmodell_css: str | None = None
    gehalt_css: str | None = None
    link_css: str | None = None
    beschreibung_css: str | None = None
    max_treffer: int = Field(default=10, ge=1, le=50)


class PortalPolicy(PolicyProfile):
    """Portal-spezifischer Name fuer die gemeinsame Replay-Allowlist."""


class PortalValidation(BaseModel):
    schema_file: str


class PortalProfil(BaseModel):
    name: str
    kind: Literal["local", "real"] = "local"
    enabled: bool = True
    base_url: str
    portal_id: str
    search_path: str
    policy: PortalPolicy
    validation: PortalValidation
    selectors: PortalSelectors | None = None
    login: PortalLogin | None = None
    suche: PortalSuche | None = None
    feed: PortalFeed | None = None
    browser: Literal["playwright", "camoufox"] = "playwright"

    @model_validator(mode="after")
    def _suchweg_konfiguriert(self) -> "PortalProfil":
        if self.feed is not None and self.suche is not None:
            raise ValueError(
                "Ein Portalprofil darf nicht Feed und Browsersuche mischen."
            )
        return self

    @property
    def erlaubt(self) -> bool:
        return self.kind == "local" or self.enabled

    def suchpfad(self) -> str:
        if self.suche and self.suche.pfad:
            return self.suche.pfad
        return self.search_path

    @property
    def suchart(self) -> Literal["browser", "feed", "keine"]:
        if self.feed is not None:
            return "feed"
        if self.suche is not None:
            return "browser"
        return "keine"


def lade_portale(verzeichnis: Path = PORTALE_DIR) -> list[PortalProfil]:
    """Liest alle Portal-Profile eines Verzeichnisses, sortiert nach Name."""
    if not verzeichnis.is_dir():
        raise ValueError(f"Portal-Verzeichnis fehlt: {verzeichnis}")
    portale: list[PortalProfil] = []
    for pfad in sorted(verzeichnis.glob("*.yaml")):
        raw = yaml.safe_load(pfad.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise TypeError(f"Portalprofil muss ein YAML-Mapping sein: {pfad}")
        portale.append(PortalProfil.model_validate(raw))
    return portale


def lade_portal_katalog(
    datei: Path = PORTAL_KATALOG_DATEI,
) -> list[PortalKatalogEintrag]:
    """Liest den fachlichen Katalog und erzwingt eindeutige Portal-IDs."""
    raw = yaml.safe_load(datei.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise TypeError(f"Portal-Katalog muss eine YAML-Liste sein: {datei}")
    eintraege = [PortalKatalogEintrag.model_validate(eintrag) for eintrag in raw]
    ids = [eintrag.portal_id for eintrag in eintraege]
    if len(ids) != len(set(ids)):
        raise ValueError("Portal-Katalog enthaelt doppelte portal_id-Werte.")
    return eintraege

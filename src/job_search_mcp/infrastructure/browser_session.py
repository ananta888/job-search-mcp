"""Sitzungs-Manager fuer echte Portal-Laeufe (Login + Suche).

Kernidee: Oeffentliche Portal-Suchen laufen headless ohne Login. Wenn ein
Portal oder eine kontogebundene Funktion eine Anmeldung verlangt, kann der
Nutzer sich interaktiv im sichtbaren Camoufox-Fenster oder mit explizit
hinterlegten Daten einloggen. Der optionale Sitzungszustand (Cookies und
localStorage) wird auf der Platte gespeichert und wiederverwendet.

Treiber (Fallback-Kette):
1. ``CamoufoxTreiber``: Anti-Detect-Firefox ueber die job_browser-Port.
   ``portal.browser == 'camoufox'`` ist die primaere Engine fuer Stepstone.
2. ``BrowserUseTreiber``: browser-use-Agent als Fallback, wenn kein
   browserbasierter Treiber verfuegbar ist. Benoetigt eine LLM-Konfiguration
   (``BROWSER_USE_API_KEY`` oder ein OpenAI-kompatibles/ollama-``BASE_URL``).
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote, urljoin

from job_search_mcp.infrastructure.browser import engine_fuer
from job_search_mcp.infrastructure.credentials import (
    CredentialStore,
    PortalCredential,
    validiere_portal_id,
)
from job_search_mcp.infrastructure.portal_config import (
    PortalLogin,
    PortalProfil,
    PortalSuche,
)


class BrowserSessionFehler(RuntimeError):
    """Fehler in der Browser-Sitzungsverwaltung (nicht wiederholbar ohne Aenderung)."""


@dataclass(frozen=True)
class PortalStatus:
    portal_id: str
    treiber: str
    treiber_verfuegbar: bool
    sitzung_vorhanden: bool
    anmeldedaten_vorhanden: bool
    login_fuer_suche_erforderlich: bool | None
    anmerkungen: tuple[str, ...]


class _EngineTreiber:
    """Gemeinsame Basis der browserbasierten Treiber ueber die job_browser-Port."""

    @property
    def name(self) -> str:
        raise NotImplementedError

    def verfuegbar(self) -> bool:
        raise NotImplementedError

    def beschreibung(self) -> str:
        raise NotImplementedError


_LOGIN_BESTAETIGT_SELECTOR = "html[data-job-mcp-login-bestaetigt='ja']"
_LOGIN_UEBERGABE_SCRIPT = r"""
(() => {
  const ID = 'job-mcp-login-uebergabe';
  const mount = () => {
    if (!document.documentElement || document.getElementById(ID)) return;
    const panel = document.createElement('section');
    panel.id = ID;
    panel.setAttribute('aria-label', 'Job-MCP Login-Übergabe');
    panel.style.cssText = [
      'position:fixed', 'right:20px', 'bottom:20px', 'z-index:2147483647',
      'max-width:360px', 'padding:16px', 'border:3px solid #166534',
      'border-radius:12px', 'background:#f0fdf4', 'color:#052e16',
      'font:600 16px/1.35 system-ui,sans-serif',
      'box-shadow:0 8px 30px rgba(0,0,0,.35)'
    ].join(';');
    const text = document.createElement('p');
    text.textContent = 'Bitte zuerst vollständig bei StepStone einloggen. Danach hier bestätigen:';
    text.style.cssText = 'margin:0 0 10px';
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = 'Anmeldung abgeschlossen – Sitzung speichern';
    button.style.cssText = [
      'padding:10px 14px', 'border:0', 'border-radius:8px',
      'background:#166534', 'color:white', 'cursor:pointer',
      'font:700 15px system-ui,sans-serif'
    ].join(';');
    button.addEventListener('click', () => {
      document.documentElement.setAttribute('data-job-mcp-login-bestaetigt', 'ja');
      button.disabled = true;
      button.textContent = 'Sitzung wird gespeichert …';
    });
    panel.append(text, button);
    document.documentElement.appendChild(panel);
  };
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mount, {once:true});
  } else {
    mount();
  }
  new MutationObserver(mount).observe(document, {childList:true, subtree:true});
})();
"""


def _warte_auf_login(page: Any, login: PortalLogin) -> bool:
    """Wartet ohne Sleep-Schleifen auf das Login-Ende (Selector oder URL)."""
    timeout_ms = int(login.timeout_s) * 1000
    if login.erfolg_selector:
        try:
            page.locator(login.erfolg_selector).wait_for(
                state="visible", timeout=timeout_ms
            )
            return True
        except Exception:  # noqa: BLE001 -- Browser-Adapter verschiedener Engines
            if not login.erfolg_url:
                return False
    if login.erfolg_url:
        try:
            page.wait_for_url(f"{login.erfolg_url}*", timeout=timeout_ms)
            return True
        except Exception:  # noqa: BLE001 -- Browser-Adapter verschiedener Engines
            return False
    return False


def _warte_auf_manuelle_bestaetigung(page: Any, login: PortalLogin) -> bool:
    """Wartet darauf, dass der Nutzer den sichtbaren Übergabe-Button klickt."""
    try:
        page.locator(_LOGIN_BESTAETIGT_SELECTOR).wait_for(
            state="attached", timeout=int(login.timeout_s) * 1000
        )
        return True
    except Exception:  # noqa: BLE001 -- Browser-Adapter verschiedener Engines
        return False


def _gehalt_parse(text: str) -> tuple[int | None, int | None]:
    """Best-Effort-Extraktion von Gehaltsspannen aus Freitext."""
    if not text:
        return None, None
    zahlen = [
        int(z) for z in re.findall(r"\d{2,6}", text.replace(".", "").replace(",", ""))
    ]
    if not zahlen:
        return None, None
    return min(zahlen), max(zahlen)


class CamoufoxTreiber(_EngineTreiber):
    """Browserbasierter Treiber fuer Camoufox oder Playwright."""

    def __init__(
        self, engine_factory=engine_fuer, engine_name: str = "camoufox"
    ) -> None:
        self._engine_factory = engine_factory
        self._engine_name = engine_name

    @property
    def name(self) -> str:
        return self._engine_name

    def verfuegbar(self) -> bool:
        if self._engine_factory is not engine_fuer:
            return True
        if self._engine_name not in {"camoufox", "playwright"}:
            return False
        return importlib.util.find_spec(self._engine_name) is not None

    def beschreibung(self) -> str:
        if self._engine_name == "camoufox":
            return "Anti-Detect-Firefox (camoufox) als Playwright-Drop-in"
        return "Chromium ueber Playwright"

    def login_interaktiv(
        self,
        portal: PortalProfil,
        manager: BrowserSessionManager,
        sichtbar: bool = True,
    ) -> dict[str, object]:
        """Oeffnet ein sichtbares Fenster, in dem der Nutzer den Login selbst
        abschliesst; anschliessend wird die Sitzung gespeichert."""
        login = _portal_login(portal)
        engine = self._engine_factory(portal.browser)
        try:
            with engine.oeffne_sitzung(
                storage_state=manager.sitzung_laden(portal.portal_id),
                headless=not sichtbar,
            ) as (page, context):
                context.add_init_script(_LOGIN_UEBERGABE_SCRIPT)
                page.goto(login.url, wait_until="domcontentloaded")
                if _warte_auf_manuelle_bestaetigung(page, login):
                    state = context.storage_state()
                    manager.sitzung_speichern(portal.portal_id, state)
                    return {
                        "status": "eingeloggt",
                        "portal": portal.portal_id,
                        "sitzung_gespeichert": True,
                        "hinweis": "Sitzung gespeichert und wird fuer Suchen wiederverwendet.",
                    }
        except BrowserSessionFehler:
            raise
        except Exception as error:
            raise BrowserSessionFehler(
                f"Browser-Login fuer {portal.portal_id!r} ist fehlgeschlagen "
                f"({type(error).__name__})."
            ) from error
        return {
            "status": "timeout",
            "portal": portal.portal_id,
            "sitzung_gespeichert": False,
            "hinweis": (
                "Der Übergabe-Button wurde nicht rechtzeitig bestätigt. Fenster "
                "geschlossen; portal_login erneut starten."
            ),
        }

    def anmelden(
        self,
        portal: PortalProfil,
        credential: PortalCredential,
        manager: BrowserSessionManager,
        sichtbar: bool = False,
    ) -> dict[str, object]:
        """Fuehrt den Login mit hinterlegten Anmeldedaten aus (Auto-Fill)."""
        login = _portal_login(portal)
        engine = self._engine_factory(portal.browser)
        try:
            with engine.oeffne_sitzung(
                storage_state=manager.sitzung_laden(portal.portal_id),
                headless=not sichtbar,
            ) as (page, context):
                page.goto(login.url, wait_until="domcontentloaded")
                page.locator(login.benutzername_css).fill(credential.benutzername)
                page.locator(login.passwort_css).fill(credential.passwort)
                if login.submit_css:
                    page.locator(login.submit_css).click()
                else:
                    page.get_by_role(login.submit_role, name=login.submit_name).click()
                if not _warte_auf_login(page, login):
                    return {
                        "status": "fehlgeschlagen",
                        "portal": portal.portal_id,
                        "sitzung_gespeichert": False,
                        "hinweis": (
                            "Login-Check nicht erreicht (Captcha/2FA?). "
                            "Interaktiven Login verwenden."
                        ),
                    }
                state = context.storage_state()
                manager.sitzung_speichern(portal.portal_id, state)
                return {
                    "status": "eingeloggt",
                    "portal": portal.portal_id,
                    "sitzung_gespeichert": True,
                    "hinweis": "Login mit hinterlegten Anmeldedaten erfolgreich.",
                }
        except BrowserSessionFehler:
            raise
        except Exception as error:
            raise BrowserSessionFehler(
                f"Auto-Fill-Login fuer {portal.portal_id!r} ist fehlgeschlagen "
                f"({type(error).__name__})."
            ) from error

    def suchen(
        self,
        portal: PortalProfil,
        query: str,
        manager: BrowserSessionManager,
        headless: bool = True,
        ort: str | None = None,
    ) -> list[dict[str, object]]:
        """Sucht optional mit Sitzung und extrahiert die Ergebnis-Karten."""
        suche = _portal_suche(portal)
        engine = self._engine_factory(portal.browser)
        url = such_url(portal, query, ort=ort)
        sitzung = manager.sitzung_laden(portal.portal_id)
        if suche.login_erforderlich and sitzung is None:
            raise BrowserSessionFehler(
                f"Keine gespeicherte Sitzung fuer {portal.portal_id!r}; erst einloggen."
            )
        try:
            with engine.oeffne_sitzung(storage_state=sitzung, headless=headless) as (
                page,
                _context,
            ):
                page.goto(url, wait_until="domcontentloaded")
                page.locator(suche.karte_css).first.wait_for(
                    state="visible", timeout=30000
                )
                karten = page.locator(suche.karte_css)
                anzahl = min(karten.count(), suche.max_treffer)
                angebote: list[dict[str, object]] = []
                for index in range(anzahl):
                    eintrag = _karte_lesen(
                        karten.nth(index), suche, portal.portal_id, portal.base_url
                    )
                    if eintrag is not None:
                        angebote.append(eintrag)
        except BrowserSessionFehler:
            raise
        except Exception as error:
            raise BrowserSessionFehler(
                f"Browsersuche fuer {portal.portal_id!r} ist fehlgeschlagen "
                f"({type(error).__name__})."
            ) from error
        return angebote


def _portal_login(portal: PortalProfil) -> PortalLogin:
    if portal.login is None:
        raise BrowserSessionFehler(
            f"Portal hat keine login-Konfiguration: {portal.portal_id}"
        )
    return portal.login


def _portal_suche(portal: PortalProfil) -> PortalSuche:
    if portal.suche is None:
        raise BrowserSessionFehler(
            f"Portal hat keine suche-Konfiguration: {portal.portal_id}"
        )
    return portal.suche


def _pfad_segment(wert: str, feld: str) -> str:
    normalisiert = re.sub(r"\s+", "-", wert.strip().casefold())
    if not normalisiert:
        raise ValueError(f"{feld} darf nicht leer sein.")
    return quote(normalisiert, safe="-")


def such_url(portal: PortalProfil, query: str, ort: str | None = None) -> str:
    suche = _portal_suche(portal)
    if ort is not None:
        if not suche.ort_pfad_template:
            raise BrowserSessionFehler(
                f"Portal {portal.portal_id!r} unterstuetzt keinen Ortsfilter."
            )
        pfad = suche.ort_pfad_template.format(
            query=_pfad_segment(query, "query"),
            ort=_pfad_segment(ort, "ort"),
        )
        return f"{portal.base_url}{pfad}"
    pfad = portal.suchpfad()
    trenner = "&" if "?" in pfad else "?"
    return (
        f"{portal.base_url}{pfad}{trenner}"
        f"{quote(suche.query_param, safe='')}={quote(query, safe='')}"
    )


def _karte_lesen(
    karte: Any,
    suche: PortalSuche,
    portal_id: str,
    base_url: str,
) -> dict[str, object] | None:
    def text(css: str | None) -> str:
        if not css:
            return ""
        try:
            return karte.locator(css).first.inner_text(timeout=3000).strip()
        except Exception:  # noqa: BLE001 -- fehlendes optionales Kartenfeld
            return ""

    titel = text(suche.titel_css)
    if not titel:
        return None
    link = ""
    if suche.link_css:
        try:
            link = karte.locator(suche.link_css).first.get_attribute("href") or ""
        except Exception:  # noqa: BLE001 -- fehlender optionaler Link
            link = ""
    if link:
        link = urljoin(base_url, link)
    firma = text(suche.firma_css)
    ort = text(suche.ort_css)
    beschreibung = text(suche.beschreibung_css)
    gehalt_min, gehalt_max = _gehalt_parse(text(suche.gehalt_css))
    fingerabdruck = hashlib.sha256(
        f"{portal_id}\x1f{titel}\x1f{firma}\x1f{ort}".encode()
    ).hexdigest()[:20]
    return {
        "id": link or f"{portal_id}-{fingerabdruck}",
        "portal": portal_id,
        "titel": titel,
        "firma": firma,
        "ort": ort,
        "arbeitsmodell": text(suche.arbeitsmodell_css),
        "skills": [],
        "gehalt_min": gehalt_min,
        "gehalt_max": gehalt_max,
        "sprachen": [],
        "beschreibung": beschreibung,
        "link": link,
    }


class BrowserUseTreiber:
    """Fallback-Treiber ueber den browser-use-Agenten (experimentell).

    Benoetigt eine LLM-Konfiguration: ``BROWSER_USE_API_KEY`` fuer den
    Cloud-Chat oder ``BROWSER_USE_BASE_URL``/``OLLAMA_HOST`` fuer ein
    OpenAI-kompatibles bzw. ollama-Modell. Der Agent fuehrt die Suche aus; das
    Ergebnis wird als JSON-Liste erwartet.
    """

    name = "browser-use"

    def verfuegbar(self) -> bool:
        if importlib.util.find_spec("browser_use") is None:
            return False
        return bool(
            os.getenv("BROWSER_USE_API_KEY")
            or os.getenv("BROWSER_USE_BASE_URL")
            or os.getenv("OLLAMA_HOST")
        )

    def beschreibung(self) -> str:
        return "browser-use-Agent (LLM-basiert), experimenteller Fallback"

    def status(self, portal: PortalProfil) -> dict[str, object]:
        return {
            "portal_id": portal.portal_id,
            "treiber": self.name,
            "verfuegbar": self.verfuegbar(),
            "konfiguration": {
                "api_key": bool(os.getenv("BROWSER_USE_API_KEY")),
                "base_url": bool(os.getenv("BROWSER_USE_BASE_URL")),
                "ollama_host": bool(os.getenv("OLLAMA_HOST")),
            },
        }

    def suchen(
        self,
        portal: PortalProfil,
        query: str,
        storage_state: dict[str, Any],
        anmerkung: str,
        ort: str | None = None,
    ) -> list[dict[str, object]]:
        """Fuehrt eine browser-use-Aufgabe aus und parst das JSON-Ergebnis."""
        if not self.verfuegbar():
            raise BrowserSessionFehler(
                "Browser-Use-Fallback ist nicht konfiguriert "
                "(BROWSER_USE_API_KEY oder BASE_URL/OLLAMA_HOST)."
            )
        import asyncio

        return asyncio.run(
            self._ausfuehren(portal, query, storage_state, anmerkung, ort)
        )

    async def _ausfuehren(
        self,
        portal: PortalProfil,
        query: str,
        storage_state: dict[str, Any],
        anmerkung: str,
        ort: str | None,
    ) -> list[dict[str, object]]:
        from browser_use import Agent, Browser

        zusatz = f" Zusatzanforderung: {anmerkung}" if anmerkung else ""
        ziel_url = such_url(portal, query, ort=ort)
        aufgabe = (
            f"Oeffne {ziel_url} und erfasse die dort sichtbaren Treffer "
            f"und gib ausschliesslich eine JSON-Liste mit den Treffern zurueck. "
            "Jeder Eintrag enthaelt: titel, firma, ort, link, beschreibung, "
            "skills (Liste), arbeitsmodell, sprachen (Liste), gehalt_min und "
            f"gehalt_max als ganze Jahresbetraege oder null.{zusatz}"
        )
        browser = Browser(
            headless=True,
            storage_state=storage_state,
            allowed_domains=list(portal.policy.allowed_hosts),
        )
        try:
            agent: Any = Agent(
                task=aufgabe,
                llm=_browser_use_llm(),
                browser=browser,
                use_vision=False,
            )
            history = await agent.run(max_steps=12)
            ergebnis = history.final_result() or "[]"
            return _browser_use_parse(str(ergebnis), portal.portal_id)
        finally:
            await browser.stop()


def _browser_use_llm() -> Any:
    """Waehlt das LLM fuer browser-use anhand der Umgebung aus."""
    if os.getenv("BROWSER_USE_API_KEY"):
        from browser_use import ChatBrowserUse

        return ChatBrowserUse(api_key=os.environ["BROWSER_USE_API_KEY"])
    if os.getenv("BROWSER_USE_BASE_URL"):
        from browser_use import ChatOpenAI

        return ChatOpenAI(
            model=os.getenv("BROWSER_USE_MODEL", "gpt-4o"),
            base_url=os.getenv("BROWSER_USE_BASE_URL"),
            api_key=os.getenv("BROWSER_USE_OPENAI_API_KEY", "local"),
        )
    if os.getenv("OLLAMA_HOST"):
        from browser_use import ChatOllama

        return ChatOllama(
            model=os.getenv("OLLAMA_MODEL", "llama3.1"),
            host=os.getenv("OLLAMA_HOST"),
        )
    raise BrowserSessionFehler("Keine browser-use-LLM-Konfiguration gefunden.")


def _browser_use_parse(text: str, portal_id: str) -> list[dict[str, object]]:
    """Parst das JSON aus dem Agent-Ergebnis (best effort)."""
    import json as _json

    start = text.find("[")
    if start == -1:
        raise BrowserSessionFehler("Browser-Use-Ergebnis enthaelt keine JSON-Liste.")
    ende = text.rfind("]")
    try:
        roh = _json.loads(text[start : ende + 1])
    except _json.JSONDecodeError as error:
        raise BrowserSessionFehler(f"Browser-Use-JSON nicht lesbar: {error}") from error
    if not isinstance(roh, list):
        raise BrowserSessionFehler("Browser-Use-Ergebnis ist keine Liste.")
    angebote: list[dict[str, object]] = []
    for index, eintrag in enumerate(roh):
        if not isinstance(eintrag, dict):
            continue
        link = str(eintrag.get("link", ""))
        gehalt_min = eintrag.get("gehalt_min")
        gehalt_max = eintrag.get("gehalt_max")
        skills = eintrag.get("skills")
        sprachen = eintrag.get("sprachen")
        angebote.append(
            {
                "id": link or f"{portal_id}-{index}",
                "portal": portal_id,
                "titel": str(eintrag.get("titel", "")),
                "firma": str(eintrag.get("firma", "")),
                "ort": str(eintrag.get("ort", "")),
                "arbeitsmodell": str(eintrag.get("arbeitsmodell", "")),
                "skills": [str(wert) for wert in skills]
                if isinstance(skills, list)
                else [],
                "gehalt_min": gehalt_min if isinstance(gehalt_min, int) else None,
                "gehalt_max": gehalt_max if isinstance(gehalt_max, int) else None,
                "sprachen": (
                    [str(wert) for wert in sprachen]
                    if isinstance(sprachen, list)
                    else []
                ),
                "beschreibung": str(eintrag.get("beschreibung", "")),
                "link": link,
            }
        )
    return angebote


class BrowserSessionManager:
    """Orchestriert Login, Sitzungspersistenz und Suche fuer echte Portale."""

    def __init__(
        self,
        state_dir: Path,
        credentials: CredentialStore | None = None,
        treiber_factory=None,
        fallback_factory=None,
    ) -> None:
        self.state_dir = Path(state_dir)
        self._credentials = credentials
        self._treiber_factory = treiber_factory or (
            lambda portal: CamoufoxTreiber(engine_name=portal.browser)
        )
        self._fallback_factory = fallback_factory or BrowserUseTreiber

    def _sitzung_pfad(self, portal_id: str) -> Path:
        return self.state_dir / f"{validiere_portal_id(portal_id)}-sitzung.json"

    def anmeldedaten_vorhanden(self, portal_id: str) -> bool:
        return bool(self._credentials and self._credentials.vorhanden(portal_id))

    def sitzung_vorhanden(self, portal_id: str) -> bool:
        return self._sitzung_pfad(portal_id).exists()

    def sitzung_laden(self, portal_id: str) -> dict[str, Any] | None:
        pfad = self._sitzung_pfad(portal_id)
        if not pfad.exists():
            return None
        try:
            roh = json.loads(pfad.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return roh if isinstance(roh, dict) else None

    def sitzung_speichern(self, portal_id: str, state: dict[str, Any]) -> Path:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir.chmod(0o700)
        pfad = self._sitzung_pfad(portal_id)
        pfad.write_text(json.dumps(state), encoding="utf-8")
        pfad.chmod(0o600)
        return pfad

    def sitzung_loeschen(self, portal_id: str) -> bool:
        pfad = self._sitzung_pfad(portal_id)
        if pfad.exists():
            pfad.unlink()
            return True
        return False

    def status(self, portal: PortalProfil) -> PortalStatus:
        treiber = self._treiber(portal)
        suche = portal.suche
        sitzung_vorhanden = self.sitzung_vorhanden(portal.portal_id)
        anmerkungen: list[str] = []
        if not treiber.verfuegbar():
            anmerkungen.append(f"Treiber {treiber.name} nicht verfuegbar.")
        if suche is None:
            anmerkungen.append("Keine Browsersuche konfiguriert.")
        elif not sitzung_vorhanden:
            if suche.login_erforderlich:
                anmerkungen.append("Keine Sitzung gespeichert; Login erforderlich.")
            else:
                anmerkungen.append("Oeffentliche Suche ohne Login moeglich.")
        return PortalStatus(
            portal_id=portal.portal_id,
            treiber=treiber.name,
            treiber_verfuegbar=treiber.verfuegbar(),
            sitzung_vorhanden=sitzung_vorhanden,
            anmeldedaten_vorhanden=self.anmeldedaten_vorhanden(portal.portal_id),
            login_fuer_suche_erforderlich=(
                suche.login_erforderlich if suche is not None else None
            ),
            anmerkungen=tuple(anmerkungen),
        )

    def login_interaktiv(
        self, portal: PortalProfil, sichtbar: bool = True
    ) -> dict[str, object]:
        treiber = self._treiber(portal)
        if not treiber.verfuegbar():
            raise BrowserSessionFehler(f"Treiber {treiber.name} ist nicht installiert.")
        if not isinstance(treiber, CamoufoxTreiber):
            raise BrowserSessionFehler(
                "Interaktiver Login ist nur mit einem browserbasierten Treiber moeglich."
            )
        return treiber.login_interaktiv(portal, self, sichtbar=sichtbar)

    def anmelden(
        self,
        portal: PortalProfil,
        sichtbar: bool = False,
    ) -> dict[str, object]:
        if self._credentials is None:
            raise BrowserSessionFehler("Kein Credential-Speicher konfiguriert.")
        credential = self._credentials.lese(portal.portal_id)
        if credential is None:
            raise BrowserSessionFehler(
                f"Keine Anmeldedaten fuer {portal.portal_id!r} hinterlegt."
            )
        treiber = self._treiber(portal)
        if not isinstance(treiber, CamoufoxTreiber):
            raise BrowserSessionFehler(
                "Auto-Fill-Login nur mit browserbasiertem Treiber."
            )
        return treiber.anmelden(portal, credential, self, sichtbar=sichtbar)

    def suche(
        self,
        portal: PortalProfil,
        query: str,
        headless: bool = True,
        ort: str | None = None,
    ) -> list[dict[str, object]]:
        suche = _portal_suche(portal)
        if suche.login_erforderlich and not self.sitzung_vorhanden(portal.portal_id):
            raise BrowserSessionFehler(
                f"Keine gespeicherte Sitzung fuer {portal.portal_id!r}. "
                "Zuerst einloggen (portal_login)."
            )
        treiber = self._treiber(portal)
        if not treiber.verfuegbar():
            raise BrowserSessionFehler(f"Treiber {treiber.name} ist nicht installiert.")
        if not isinstance(treiber, CamoufoxTreiber):
            raise BrowserSessionFehler("Suche nur mit browserbasiertem Treiber.")
        return treiber.suchen(portal, query, self, headless=headless, ort=ort)

    def suche_mit_fallback(
        self,
        portal: PortalProfil,
        query: str,
        headless: bool = True,
        anmerkung: str = "",
        ort: str | None = None,
    ) -> list[dict[str, object]]:
        """Primaer ueber den konfigurierten Treiber; faellt auf browser-use zurueck."""
        try:
            return self.suche(portal, query, headless=headless, ort=ort)
        except BrowserSessionFehler:
            suche = _portal_suche(portal)
            if suche.login_erforderlich and not self.sitzung_vorhanden(
                portal.portal_id
            ):
                raise
            fallback = self._fallback_factory()
            if not fallback.verfuegbar():
                raise
            sitzung = self.sitzung_laden(portal.portal_id) or {}
            return fallback.suchen(portal, query, sitzung, anmerkung, ort=ort)

    def _treiber(self, portal: PortalProfil) -> _EngineTreiber:
        return self._treiber_factory(portal)

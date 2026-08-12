"""Tests fuer den Sitzungs-Manager der echten Portal-Laeufe (browser_session).

Die Browser-Interaktion wird ueber Fake-Engines deterministisch ersetzt;
echtes Netzwerk ist hier nie noetig.
"""

import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

from job_search_mcp.infrastructure.browser_session import (
    BrowserSessionFehler,
    BrowserSessionManager,
    CamoufoxTreiber,
    _browser_use_parse,
    _gehalt_parse,
    such_url,
)
from job_search_mcp.infrastructure.credentials import CredentialStore
from job_search_mcp.infrastructure.portal_config import (
    PortalLogin,
    PortalPolicy,
    PortalProfil,
    PortalSuche,
    PortalValidation,
)


def _portal(*, login_erforderlich: bool = False) -> PortalProfil:
    return PortalProfil(
        name="stepstone",
        kind="real",
        enabled=True,
        base_url="https://www.stepstone.de",
        portal_id="stepstone",
        search_path="/jobs",
        policy=PortalPolicy(
            allowed_hosts=["www.stepstone.de"], allowed_paths=["/jobs"]
        ),
        validation=PortalValidation(schema_file="schemas/x.json"),
        browser="camoufox",
        login=PortalLogin(
            url="https://www.stepstone.de/login/",
            benutzername_css="input[name='email']",
            passwort_css="input[name='password']",
            submit_css="button[type='submit']",
            erfolg_url="https://www.stepstone.de/account/",
            erfolg_selector="[data-testid='account-menu']",
            timeout_s=3,
        ),
        suche=PortalSuche(
            login_erforderlich=login_erforderlich,
            ort_pfad_template="/jobs/{query}/in-{ort}",
            karte_css="[data-testid='searchResultItem']",
            titel_css="h2",
            firma_css="[data-testid*='company']",
            ort_css="[data-testid*='location']",
            arbeitsmodell_css="[data-testid*='work-model']",
            gehalt_css="[data-testid*='salary']",
            link_css="a",
        ),
    )


class FakePage:
    def __init__(self, login_erfolg: bool = True, texte: dict | None = None) -> None:
        self.login_erfolg = login_erfolg
        self.texte = texte or {}
        self.geladene_urls: list[str] = []
        self.fill_protokoll: list[tuple[str, str]] = []
        self.klicks: list[str] = []
        self.erfolg_selector_css: str | None = None
        self.verwendete_sitzungen: list[dict | None] = []

    def goto(self, url: str, wait_until: str | None = None) -> None:
        self.geladene_urls.append(url)

    def locator(self, css: str):
        return FakeLocator(css, self)

    def get_by_role(self, role: str, name: str | None = None):
        return FakeRoleClick(role, name, self)

    def wait_for_url(self, pattern: str, timeout: int | None = None) -> None:
        if not self.login_erfolg:
            raise TimeoutError(f"URL nicht erreicht: {pattern}")


class FakeLocator:
    def __init__(
        self,
        css: str,
        page: FakePage,
        inner: str = "",
        href: str = "https://x.example/job/1",
    ) -> None:
        self.css = css
        self.page = page
        self._inner = inner
        self._href = href

    @property
    def first(self) -> "FakeLocator":
        return self

    def fill(self, wert: str) -> None:
        self.page.fill_protokoll.append((self.css, wert))

    def click(self) -> None:
        self.page.klicks.append(self.css)

    def wait_for(self, state: str | None = None, timeout: int | None = None) -> None:
        ist_login_pruefung = (
            self.css == self.page.erfolg_selector_css
            or "data-job-mcp-login-bestaetigt" in self.css
        )
        if ist_login_pruefung and not self.page.login_erfolg:
            raise TimeoutError(f"nicht sichtbar: {self.css}")

    def inner_text(self, timeout: int | None = None) -> str:
        return self.page.texte.get(self.css, self._inner)

    def get_attribute(self, name: str) -> str | None:
        return self._href if name == "href" else None

    def count(self) -> int:
        return 0

    def nth(self, index: int):
        return self


class FakeKarte(FakeLocator):
    """Locator fuer eine einzelne Ergebnis-Karte mit pro-Selektor-Text."""

    def __init__(self, daten: dict, page: FakePage) -> None:
        super().__init__(
            "karte", page, href=daten.get("_href", "https://x.example/job/1")
        )
        self._daten = daten

    def locator(self, css: str) -> FakeLocator:
        return FakeLocator(
            css,
            self.page,
            inner=self._daten.get(css, ""),
            href=self._daten.get("_href", ""),
        )


class FakeKarten(FakeLocator):
    def __init__(self, css: str, karten: list[dict], page: FakePage) -> None:
        super().__init__(css, page)
        self._karten = karten

    def count(self) -> int:
        return len(self._karten)

    def nth(self, index: int) -> FakeLocator:
        return FakeKarte(self._karten[index], self.page)


class FakeRoleClick:
    def __init__(self, role: str, name: str | None, page: FakePage) -> None:
        self.role = role
        self.name = name
        self.page = page

    def click(self) -> None:
        self.page.klicks.append(f"role:{self.role}:{self.name}")


class FakeContext:
    def __init__(self, state: dict) -> None:
        self._state = state
        self.init_scripts: list[str] = []

    def add_init_script(self, script: str) -> None:
        self.init_scripts.append(script)

    def storage_state(self) -> dict:
        return self._state


class FakeEngine:
    name = "fake"

    def __init__(self, page: FakePage, context: FakeContext) -> None:
        self.page = page
        self.context = context

    @contextmanager
    def oeffne_sitzung(self, storage_state=None, headless: bool = True):
        self.page.verwendete_sitzungen.append(storage_state)
        yield self.page, self.context


class BrowserSessionTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.state_dir = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _manager(self, page: FakePage, context: FakeContext) -> BrowserSessionManager:
        def treiber_factory(_portal):
            return CamoufoxTreiber(
                engine_factory=lambda _name: FakeEngine(page, context)
            )

        return BrowserSessionManager(self.state_dir, treiber_factory=treiber_factory)

    def test_interaktiver_login_speichert_sitzung(self):
        zustand = {"cookies": [{"name": "ss", "value": "x"}]}
        page = FakePage(login_erfolg=True)
        page.erfolg_selector_css = "[data-testid='account-menu']"
        manager = self._manager(page, FakeContext(zustand))

        ergebnis = manager.login_interaktiv(_portal(), sichtbar=False)

        self.assertEqual(ergebnis["status"], "eingeloggt")
        self.assertTrue(manager.sitzung_vorhanden("stepstone"))
        self.assertEqual(manager.sitzung_laden("stepstone"), zustand)
        self.assertIn("https://www.stepstone.de/login/", page.geladene_urls[0])

    def test_interaktiver_login_blendet_bestaetigungsbutton_ein(self):
        page = FakePage(login_erfolg=True)
        context = FakeContext({"cookies": []})
        manager = self._manager(page, context)

        manager.login_interaktiv(_portal(), sichtbar=True)

        self.assertTrue(
            any("Anmeldung abgeschlossen" in script for script in context.init_scripts)
        )

    def test_interaktiver_login_timeout_schliesst_ohne_sitzung(self):
        page = FakePage(login_erfolg=False)
        page.erfolg_selector_css = "[data-testid='account-menu']"
        manager = self._manager(page, FakeContext({"cookies": []}))

        ergebnis = manager.login_interaktiv(_portal(), sichtbar=False)

        self.assertEqual(ergebnis["status"], "timeout")
        self.assertFalse(manager.sitzung_vorhanden("stepstone"))

    def test_anmelden_mit_hinterlegten_daten(self):
        credentials = CredentialStore(self.state_dir)
        credentials.hinterlege("stepstone", "max@beispiel.de", "geheim")
        page = FakePage(login_erfolg=True)
        page.erfolg_selector_css = "[data-testid='account-menu']"
        manager = BrowserSessionManager(
            self.state_dir,
            credentials=credentials,
            treiber_factory=lambda _p: CamoufoxTreiber(
                engine_factory=lambda _name: FakeEngine(
                    page, FakeContext({"cookies": [{"name": "ss", "value": "1"}]})
                )
            ),
        )

        ergebnis = manager.anmelden(_portal(), sichtbar=False)

        self.assertEqual(ergebnis["status"], "eingeloggt")
        self.assertEqual(
            page.fill_protokoll,
            [
                ("input[name='email']", "max@beispiel.de"),
                ("input[name='password']", "geheim"),
            ],
        )
        self.assertTrue(manager.sitzung_vorhanden("stepstone"))

    def test_anmelden_ohne_hinterlegte_daten_wirft(self):
        manager = BrowserSessionManager(
            self.state_dir, credentials=CredentialStore(self.state_dir)
        )
        with self.assertRaises(BrowserSessionFehler):
            manager.anmelden(_portal())

    def test_suche_extrahiert_karten_aus_sitzung(self):
        karte_java = {
            "h2": "Java Backend Developer",
            "[data-testid*='company']": "Acme GmbH",
            "[data-testid*='location']": "Berlin",
            "[data-testid*='work-model']": "Remote",
            "[data-testid*='salary']": "70.000 EUR - 85.000 EUR",
            "_href": "https://www.stepstone.de/jobs/4711",
        }
        karte_python = {
            "h2": "Python Entwickler",
            "[data-testid*='company']": "Beispiel AG",
            "_href": "https://www.stepstone.de/jobs/4712",
        }
        page = FakePage()
        page.locator = lambda css: (  # type: ignore[method-assign]
            FakeKarten(css, [karte_java, karte_python], page)
            if css == "[data-testid='searchResultItem']"
            else FakeLocator(css, page)
        )
        manager = self._manager(page, FakeContext({}))
        manager.sitzung_speichern("stepstone", {"cookies": []})

        angebote = manager.suche(_portal(), "java")

        self.assertEqual(len(angebote), 2)
        self.assertEqual(angebote[0]["titel"], "Java Backend Developer")
        self.assertEqual(angebote[0]["firma"], "Acme GmbH")
        self.assertEqual(angebote[0]["arbeitsmodell"], "Remote")
        self.assertEqual(angebote[0]["gehalt_min"], 70000)
        self.assertEqual(angebote[0]["gehalt_max"], 85000)
        self.assertEqual(angebote[0]["link"], "https://www.stepstone.de/jobs/4711")
        self.assertEqual(angebote[1]["titel"], "Python Entwickler")
        self.assertTrue(all("stepstone" == a["portal"] for a in angebote))

    def test_oeffentliche_suche_funktioniert_ohne_sitzung(self):
        page = FakePage()
        page.locator = lambda css: (  # type: ignore[method-assign]
            FakeKarten(
                css,
                [{"h2": "Informatiker", "_href": "/jobs/4713"}],
                page,
            )
            if css == "[data-testid='searchResultItem']"
            else FakeLocator(css, page)
        )
        manager = self._manager(page, FakeContext({}))

        angebote = manager.suche(_portal(), "informatiker nürnberg")

        self.assertEqual(angebote[0]["titel"], "Informatiker")
        self.assertEqual(angebote[0]["link"], "https://www.stepstone.de/jobs/4713")
        self.assertEqual(page.verwendete_sitzungen, [None])

    def test_loginpflichtige_suche_ohne_sitzung_wirft(self):
        manager = self._manager(FakePage(), FakeContext({}))
        with self.assertRaises(BrowserSessionFehler):
            manager.suche(_portal(login_erforderlich=True), "java")

    def test_suche_mit_fallback_wirft_wenn_fallback_fehlkonfiguriert(self):
        class _KeinTreiber(CamoufoxTreiber):
            def verfuegbar(self) -> bool:
                return False

        manager = BrowserSessionManager(
            self.state_dir, treiber_factory=lambda _portal: _KeinTreiber()
        )
        manager.sitzung_speichern("stepstone", {"cookies": []})
        with self.assertRaises(BrowserSessionFehler):
            manager.suche_mit_fallback(_portal(), "java")

    def test_sitzung_loeschen(self):
        manager = self._manager(FakePage(), FakeContext({}))
        manager.sitzung_speichern("stepstone", {"cookies": []})
        self.assertTrue(manager.sitzung_loeschen("stepstone"))
        self.assertFalse(manager.sitzung_loeschen("stepstone"))

    def test_such_url_mit_query_param(self):
        url = such_url(_portal(), "java spring")
        self.assertEqual(url, "https://www.stepstone.de/jobs?q=java%20spring")

    def test_such_url_kodiert_sonderzeichen(self):
        url = such_url(_portal(), "c#/.net & cloud")
        self.assertEqual(
            url, "https://www.stepstone.de/jobs?q=c%23%2F.net%20%26%20cloud"
        )

    def test_such_url_verwendet_kanonischen_ortspfad(self):
        url = such_url(_portal(), "Informatiker", ort="Nürnberg")
        self.assertEqual(
            url,
            "https://www.stepstone.de/jobs/informatiker/in-n%C3%BCrnberg",
        )

    def test_fallback_erhaelt_nur_sitzungszustand(self):
        class _KeinTreiber(CamoufoxTreiber):
            def verfuegbar(self) -> bool:
                return False

        class _Fallback:
            name = "fake-fallback"

            def __init__(self):
                self.aufruf = None

            def verfuegbar(self) -> bool:
                return True

            def suchen(self, portal, query, storage_state, anmerkung, ort=None):
                self.aufruf = (portal.portal_id, query, storage_state, anmerkung)
                return [{"id": "1", "portal": portal.portal_id, "titel": "Java"}]

        fallback = _Fallback()
        manager = BrowserSessionManager(
            self.state_dir,
            treiber_factory=lambda _portal: _KeinTreiber(),
            fallback_factory=lambda: fallback,
        )
        manager.sitzung_speichern("stepstone", {"cookies": [{"name": "sid"}]})

        ergebnis = manager.suche_mit_fallback(
            _portal(), "java", anmerkung="profilbasiert"
        )

        self.assertEqual(ergebnis[0]["titel"], "Java")
        self.assertEqual(
            fallback.aufruf,
            (
                "stepstone",
                "java",
                {"cookies": [{"name": "sid"}]},
                "profilbasiert",
            ),
        )

    def test_oeffentlicher_fallback_erhaelt_leeren_sitzungszustand(self):
        class _KeinTreiber(CamoufoxTreiber):
            def verfuegbar(self) -> bool:
                return False

        class _Fallback:
            def verfuegbar(self) -> bool:
                return True

            def suchen(self, portal, query, storage_state, anmerkung, ort=None):
                self.storage_state = storage_state
                return [{"id": "1", "portal": portal.portal_id, "titel": query}]

        fallback = _Fallback()
        manager = BrowserSessionManager(
            self.state_dir,
            treiber_factory=lambda _portal: _KeinTreiber(),
            fallback_factory=lambda: fallback,
        )

        ergebnis = manager.suche_mit_fallback(_portal(), "informatiker")

        self.assertEqual(ergebnis[0]["titel"], "informatiker")
        self.assertEqual(fallback.storage_state, {})

    def test_browser_use_parser_uebernimmt_matching_felder(self):
        ergebnis = _browser_use_parse(
            '[{"titel":"Java Developer","firma":"Acme","skills":["Java",'
            '"Spring"],"arbeitsmodell":"remote","sprachen":["Deutsch"],'
            '"gehalt_min":70000,"gehalt_max":85000}]',
            "stepstone",
        )
        self.assertEqual(ergebnis[0]["skills"], ["Java", "Spring"])
        self.assertEqual(ergebnis[0]["arbeitsmodell"], "remote")
        self.assertEqual(ergebnis[0]["gehalt_min"], 70000)

    def test_gehalt_parse(self):
        self.assertEqual(
            _gehalt_parse("70.000 EUR - 85.000 EUR pro Jahr"), (70000, 85000)
        )
        self.assertEqual(_gehalt_parse(""), (None, None))
        self.assertEqual(_gehalt_parse("keine Angabe"), (None, None))


if __name__ == "__main__":
    unittest.main()

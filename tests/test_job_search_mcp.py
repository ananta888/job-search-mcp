"""Tests fuer den neuen Job-Search-MCP-Server (Login/Sitzung/Suche)."""

import asyncio
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from job_search_mcp.infrastructure.browser_session import BrowserSessionFehler
from job_search_mcp.interfaces.mcp_server import (
    anmeldedaten_entfernen,
    anmeldedaten_hinterlegen,
    browser_status,
    liste_portale,
    mcp,
    mehrportal_suche,
    portal_login,
    portal_recherche,
    portal_suche,
)


def _freigabe():
    os.environ["ALLOW_EXTERNAL_PORTALS"] = "1"


def _temp_state_dir():
    tmp = tempfile.TemporaryDirectory()
    os.environ["JOB_MCP_STATE_DIR"] = tmp.name
    return tmp


class _UmgebungsTest(unittest.TestCase):
    def setUp(self):
        self._umgebung = {
            name: os.environ.get(name)
            for name in ("ALLOW_EXTERNAL_PORTALS", "JOB_MCP_STATE_DIR")
        }

    def tearDown(self):
        for name, wert in self._umgebung.items():
            if wert is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = wert


class RegistrierungTest(unittest.TestCase):
    def test_alle_tools_sind_registriert(self):
        tools = asyncio.run(mcp.list_tools())
        namen = {getattr(tool, "name", str(tool)) for tool in tools}
        erwartet = {
            "browser_status",
            "anmeldedaten_hinterlegen",
            "anmeldedaten_entfernen",
            "portal_login",
            "portal_sitzung_loeschen",
            "portal_suche",
            "portal_recherche",
            "lade_profil",
            "liste_portale",
            "mehrportal_suche",
            "bewerte_angebote",
            "erstelle_bericht",
            "analysiere_echtes_portal",
        }
        self.assertTrue(erwartet.issubset(namen), f"fehlen: {erwartet - namen}")


class PortalToolsTest(_UmgebungsTest):
    def test_liste_portale_zeigt_login_und_suche_konfiguration(self):
        portale = {p["portal_id"]: p for p in liste_portale()}
        self.assertTrue(portale["stepstone"]["login_konfiguriert"])
        self.assertTrue(portale["stepstone"]["suche_konfiguriert"])
        self.assertEqual(portale["stepstone"]["browser"], "camoufox")
        self.assertEqual(portale["arbeitnow"]["zugangsart"], "oeffentliche_api")
        self.assertEqual(portale["indeed"]["status"], "gesperrt")
        self.assertEqual(portale["instaffo"]["status"], "manuell")

    def test_browser_status_listet_nur_echte_portale(self):
        tmp = _temp_state_dir()
        try:
            status = browser_status()
            self.assertIn("engines", status)
            self.assertTrue(status["sichtbarer_browser"]["verfuegbar"])
            self.assertEqual(status["sichtbarer_browser"]["technik"], "WSLg/X11")
            self.assertIn("portale", status)
            portal_ids = [p["portal_id"] for p in status["portale"]]
            self.assertNotIn("acme-karriere", portal_ids)
            self.assertIn("stepstone", portal_ids)
            stepstone = next(
                p for p in status["portale"] if p["portal_id"] == "stepstone"
            )
            self.assertFalse(stepstone["login_fuer_suche_erforderlich"])
            self.assertIn(
                "Oeffentliche Suche ohne Login moeglich.", stepstone["anmerkungen"]
            )
        finally:
            tmp.cleanup()

    def test_browser_status_lehnt_unbekanntes_portal_ab(self):
        with self.assertRaises(ValueError):
            browser_status("unbekannt")

    def test_anmeldedaten_hinterlegen_und_entfernen(self):
        tmp = _temp_state_dir()
        _freigabe()
        try:
            ergebnis = anmeldedaten_hinterlegen(
                "stepstone", "max@beispiel.de", "geheim"
            )
            self.assertEqual(ergebnis["status"], "gespeichert")
            status = browser_status("stepstone")
            portal = status["portale"][0]
            self.assertTrue(portal["anmeldedaten_vorhanden"])
            entfernt = anmeldedaten_entfernen("stepstone")
            self.assertEqual(entfernt["status"], "entfernt")
        finally:
            tmp.cleanup()

    def test_lokales_portal_ist_fuer_anmeldedaten_gesperrt(self):
        tmp = _temp_state_dir()
        try:
            with self.assertRaises(ValueError):
                anmeldedaten_hinterlegen("acme-karriere", "u", "w")
        finally:
            tmp.cleanup()

    def test_echtes_portal_ohne_freigabe_ist_gesperrt(self):
        tmp = _temp_state_dir()
        os.environ.pop("ALLOW_EXTERNAL_PORTALS", None)
        try:
            with self.assertRaises(ValueError):
                anmeldedaten_hinterlegen("stepstone", "u", "w")
        finally:
            tmp.cleanup()

    def test_portal_login_ohne_daten_startet_interaktiv(self):
        tmp = _temp_state_dir()
        _freigabe()
        try:
            with mock.patch(
                "job_search_mcp.interfaces.mcp_server._manager"
            ) as manager_factory:
                manager = manager_factory.return_value
                manager.anmeldedaten_vorhanden.return_value = False
                manager.login_interaktiv.return_value = {"status": "eingeloggt"}
                ergebnis = portal_login("stepstone", sichtbar=True, auto=True)
            self.assertEqual(ergebnis["status"], "eingeloggt")
            manager.login_interaktiv.assert_called_once()
        finally:
            tmp.cleanup()

    def test_sichtbarer_login_ohne_display_liefert_klare_anweisung(self):
        tmp = _temp_state_dir()
        _freigabe()
        try:
            with (
                mock.patch.dict(os.environ, {"DISPLAY": "", "WAYLAND_DISPLAY": ""}),
                mock.patch(
                    "job_search_mcp.interfaces.mcp_server._manager"
                ) as manager_factory,
                self.assertRaisesRegex(BrowserSessionFehler, "WSLg|DISPLAY"),
            ):
                portal_login("stepstone", sichtbar=True, auto=False)
            manager_factory.assert_not_called()
        finally:
            tmp.cleanup()

    def test_portal_suche_ohne_sitzung_verwendet_oeffentlichen_pfad(self):
        tmp = _temp_state_dir()
        _freigabe()
        try:
            with mock.patch(
                "job_search_mcp.interfaces.mcp_server._manager",
                return_value=FakeManager([], sitzung=False),
            ):
                ergebnis = portal_suche(
                    "stepstone", query="informatiker", ort="nürnberg"
                )
            self.assertEqual(ergebnis["query"], "informatiker")
            self.assertEqual(ergebnis["ort"], "nürnberg")
            self.assertEqual(ergebnis["sitzungsmodus"], "oeffentlich")
        finally:
            tmp.cleanup()

    def test_feed_suche_benoetigt_keinen_browser_manager(self):
        tmp = _temp_state_dir()
        _freigabe()
        roh = [
            {
                "id": "https://www.arbeitnow.com/jobs/python",
                "portal": "arbeitnow",
                "titel": "Python Developer",
                "firma": "Acme GmbH",
                "ort": "Berlin",
                "arbeitsmodell": "remote",
                "skills": ["Python"],
                "sprachen": [],
                "beschreibung": "Python remote",
                "link": "https://www.arbeitnow.com/jobs/python",
            }
        ]
        try:
            with (
                mock.patch(
                    "job_search_mcp.interfaces.mcp_server._manager"
                ) as manager_factory,
                mock.patch(
                    "job_search_mcp.interfaces.mcp_server.suche_feed", return_value=roh
                ) as feed_suche,
            ):
                ergebnis = portal_suche("arbeitnow", query="python", ort="berlin")
            manager_factory.assert_not_called()
            feed_suche.assert_called_once()
            self.assertEqual(ergebnis["sitzungsmodus"], "oeffentlicher_feed")
            self.assertEqual(len(ergebnis["angebote"]), 1)
        finally:
            tmp.cleanup()

    def test_mehrportal_suche_isoliert_quellenfehler(self):
        _freigabe()

        def fake_suche(portal_id, **_kwargs):
            if portal_id == "remotive":
                raise RuntimeError("Quelle voruebergehend nicht erreichbar")
            return {
                "portal": portal_id,
                "zugriffsart": "oeffentliche_api",
                "angebote": [
                    {
                        "id": f"https://example.test/{portal_id}/1",
                        "portal": portal_id,
                        "titel": "Backend Developer",
                    }
                ],
            }

        with mock.patch(
            "job_search_mcp.interfaces.mcp_server.portal_suche", side_effect=fake_suche
        ):
            ergebnis = mehrportal_suche(
                portal_ids=["arbeitnow", "remotive"], query="backend"
            )

        self.assertEqual(ergebnis["angebote_gefunden"], 1)
        self.assertEqual(ergebnis["quellen_erfolgreich"], 1)
        self.assertEqual(ergebnis["quellen_fehlgeschlagen"], 1)
        remotive = next(
            quelle
            for quelle in ergebnis["quellen"]
            if quelle["portal_id"] == "remotive"
        )
        self.assertEqual(remotive["status"], "fehler")


class FakeManager:
    def __init__(self, angebote, sitzung=True):
        self._angebote = angebote
        self._sitzung = sitzung
        self.aufruf_thread = None

    def sitzung_vorhanden(self, portal_id):
        return self._sitzung

    def sitzung_laden(self, portal_id):
        return {"cookies": []} if self._sitzung else None

    def suche_mit_fallback(self, portal, query, anmerkung="", ort=None):
        self.aufruf_thread = threading.get_ident()
        return [
            {
                "id": "https://x.example/job/1",
                "portal": portal.portal_id,
                "titel": f"Java Developer ({query})",
                "firma": "Acme GmbH",
                "ort": "Berlin",
                "gehalt_min": 70000,
                "gehalt_max": 85000,
                "skills": [],
                "arbeitsmodell": "",
                "sprachen": [],
                "beschreibung": (
                    "Gesucht werden Java, Spring, SQL und REST. "
                    "Remote-Arbeit; Teamsprachen Deutsch und Englisch."
                ),
                "link": "https://x.example/job/1",
            }
        ]


class PortalSucheMitManagerTest(_UmgebungsTest):
    def test_mcp_browserwerkzeug_laeuft_in_worker_thread(self):
        tmp = _temp_state_dir()
        _freigabe()
        manager = FakeManager([], sitzung=False)
        haupt_thread = threading.get_ident()
        try:
            with mock.patch(
                "job_search_mcp.interfaces.mcp_server._manager", return_value=manager
            ):
                asyncio.run(
                    mcp.call_tool(
                        "portal_suche",
                        {
                            "portal_id": "stepstone",
                            "query": "informatiker",
                            "ort": "nürnberg",
                        },
                    )
                )
            self.assertIsNotNone(manager.aufruf_thread)
            self.assertNotEqual(manager.aufruf_thread, haupt_thread)
        finally:
            tmp.cleanup()

    def test_portal_suche_liefert_angebote(self):
        tmp = _temp_state_dir()
        _freigabe()
        try:
            with mock.patch(
                "job_search_mcp.interfaces.mcp_server._manager",
                return_value=FakeManager([]),
            ):
                ergebnis = portal_suche("stepstone", query="java")
            self.assertEqual(ergebnis["portal"], "stepstone")
            self.assertEqual(ergebnis["query"], "java")
            self.assertEqual(len(ergebnis["angebote"]), 1)
            self.assertEqual(ergebnis["angebote"][0]["titel"], "Java Developer (java)")
            self.assertEqual(ergebnis["angebote"][0]["link"], "https://x.example/job/1")
            self.assertEqual(
                ergebnis["angebote"][0]["skills"],
                ["java", "rest", "spring", "sql"],
            )
            self.assertEqual(ergebnis["angebote"][0]["arbeitsmodell"], "remote")
            self.assertEqual(
                ergebnis["angebote"][0]["sprachen"],
                ["deutsch", "englisch"],
            )
        finally:
            tmp.cleanup()

    def test_portal_suche_verwendet_ersten_suchbegriff_des_profils(self):
        tmp = _temp_state_dir()
        _freigabe()
        try:
            with mock.patch(
                "job_search_mcp.interfaces.mcp_server._manager",
                return_value=FakeManager([]),
            ):
                ergebnis = portal_suche("stepstone", profil_pfad="job-profile.json")
            self.assertEqual(ergebnis["query"], "backend")
        finally:
            tmp.cleanup()

    def test_portal_recherche_schreibt_bericht(self):
        tmp = _temp_state_dir()
        _freigabe()
        try:
            with (
                mock.patch(
                    "job_search_mcp.interfaces.mcp_server._manager",
                    return_value=FakeManager([]),
                ),
                tempfile.TemporaryDirectory() as bericht_dir,
            ):
                ziel = str(Path(bericht_dir) / "stepstone.md")
                ergebnis = portal_recherche(
                    "stepstone", bericht_pfad=ziel, max_begriffe=2
                )
                self.assertGreaterEqual(ergebnis["angebote_gefunden"], 1)
                self.assertEqual(ergebnis["bericht"], ziel)
                self.assertTrue(Path(ziel).exists())
                self.assertIn(
                    "https://x.example/job/1",
                    Path(ziel).read_text(encoding="utf-8"),
                )
        finally:
            tmp.cleanup()

    def test_portal_recherche_funktioniert_oeffentlich_ohne_sitzung(self):
        tmp = _temp_state_dir()
        _freigabe()
        try:
            with (
                mock.patch(
                    "job_search_mcp.interfaces.mcp_server._manager",
                    return_value=FakeManager([], sitzung=False),
                ),
                tempfile.TemporaryDirectory() as bericht_dir,
            ):
                ergebnis = portal_recherche(
                    "stepstone",
                    bericht_pfad=str(Path(bericht_dir) / "stepstone.md"),
                    max_begriffe=1,
                )
            self.assertEqual(ergebnis["sitzungsmodus"], "oeffentlich")
            self.assertGreaterEqual(ergebnis["angebote_gefunden"], 1)
        finally:
            tmp.cleanup()

    def test_portal_recherche_lehnt_null_suchbegriffe_ab(self):
        tmp = _temp_state_dir()
        _freigabe()
        try:
            with self.assertRaises(ValueError):
                portal_recherche("stepstone", max_begriffe=0)
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()

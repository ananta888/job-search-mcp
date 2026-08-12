"""Tests fuer den MCP-Server des JOB-Agenten."""

import asyncio
import tempfile
import unittest
from pathlib import Path

from job_search_mcp.interfaces.legacy_mcp_server import (
    analysiere_echtes_portal,
    bewerte_angebote,
    erstelle_bericht,
    lade_profil,
    liste_portale,
    mcp,
    suche_angebote,
)


class RegistrierungTest(unittest.TestCase):
    def test_alle_tools_sind_registriert(self):
        tools = asyncio.run(mcp.list_tools())
        namen = {getattr(tool, "name", str(tool)) for tool in tools}
        erwartet = {
            "lade_profil",
            "liste_portale",
            "suche_angebote",
            "bewerte_angebote",
            "erstelle_bericht",
            "analysiere_echtes_portal",
        }
        self.assertTrue(erwartet.issubset(namen), f"fehlen: {erwartet - namen}")


class WerkzeugTest(unittest.TestCase):
    def test_lade_profil(self):
        profil = lade_profil()
        self.assertEqual(profil["name"], "Java-Backend-Entwickler")
        self.assertIn("java", profil["skills_pflicht"])

    def test_liste_portale(self):
        portale = liste_portale()
        by_name = {portal["name"]: portal for portal in portale}
        self.assertTrue(by_name["acme-karriere"]["erlaubt"])
        self.assertFalse(by_name["beispiel-karriere"]["erlaubt"])
        self.assertEqual(by_name["beispiel-karriere"]["kind"], "real")

    def test_suche_angebote(self):
        ergebnis = suche_angebote()
        self.assertIn("java", ergebnis["profil"]["skills_pflicht"])
        self.assertGreater(len(ergebnis["angebote"]), 0)
        self.assertTrue(any("acme" in quelle for quelle in ergebnis["quellen"]))

    def test_bewerte_angebote(self):
        ergebnis = suche_angebote()
        bewertung = bewerte_angebote(angebote=ergebnis["angebote"])
        matches = bewertung["matches"]
        self.assertGreater(len(matches), 0)
        erster = matches[0]
        self.assertIn("score", erster)
        self.assertIn("angebot", erster)
        self.assertIn("gruende", erster)

    def test_erstelle_bericht_schreibt_datei(self):
        ergebnis = suche_angebote()
        with tempfile.TemporaryDirectory() as tmp:
            ziel = str(Path(tmp) / "mcp-report.md")
            pfad = erstelle_bericht(
                angebote=ergebnis["angebote"],
                quellen=ergebnis["quellen"],
                bericht_pfad=ziel,
            )
            self.assertEqual(pfad, ziel)
            self.assertTrue(Path(ziel).exists())

    def test_echtes_portal_dry_run(self):
        plan = analysiere_echtes_portal("beispiel-karriere", "Java")
        self.assertIn("Dry-Run", plan["hinweis"])

    def test_unbekanntes_portal_wird_abgelehnt(self):
        with self.assertRaises(ValueError):
            analysiere_echtes_portal("gibt-es-nicht", "Java")


if __name__ == "__main__":
    unittest.main()

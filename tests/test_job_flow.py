"""Integrationstests fuer den lokalen Job-Flow."""

import json
import tempfile
import unittest
from pathlib import Path

from job_search_mcp.application.job_flow import (
    crawl_erlaubt,
    crawle_echtes_portal,
    filtere_nach_suchbegriffen,
    lade_portale,
    lauf,
    plan_echtes_portal,
    suche_portal,
)
from job_search_mcp.domain.models import JobAngebot, JobProfil
from job_search_mcp.infrastructure.policy import PolicyViolation
from job_search_mcp.interfaces.demo_server import DemoServer


def _mini_profil() -> JobProfil:
    return JobProfil(
        name="Test",
        suchbegriffe=("java",),
        skills_pflicht={"java"},
    )


def _schreibe_java_profil(tmp: str) -> Path:
    """Temporaeres Java-Profil, das zur lokalen Demo-Sandbox passt."""
    pfad = Path(tmp) / "profil.json"
    pfad.write_text(
        json.dumps(
            {
                "name": "Dev",
                "suchbegriffe": ["backend", "java"],
                "skills_pflicht": ["java", "spring", "sql"],
                "skills_wunsch": ["docker"],
            }
        ),
        encoding="utf-8",
    )
    return pfad


class PortalLadenTest(unittest.TestCase):
    def test_portale_werden_gefunden_und_klassifiziert(self):
        portale = lade_portale()
        by_name = {portal.name: portal for portal in portale}
        self.assertIn("acme-karriere", by_name)
        self.assertIn("jobvermittlung", by_name)
        self.assertEqual(by_name["acme-karriere"].kind, "local")
        self.assertTrue(by_name["acme-karriere"].erlaubt)

    def test_echtes_portal_ist_standardmaessig_nicht_erlaubt(self):
        portale = lade_portale()
        beispiel = next(p for p in portale if p.portal_id == "beispiel")
        self.assertFalse(beispiel.enabled)
        self.assertFalse(crawl_erlaubt(beispiel))


class PortalSucheTest(unittest.TestCase):
    def test_suche_portal_liefert_normalisierte_angebote(self):
        portale = lade_portale()
        acme = next(p for p in portale if p.portal_id == "acme")
        with DemoServer() as server:
            angebote = suche_portal(acme, server.base_url)
        self.assertGreaterEqual(len(angebote), 3)
        self.assertTrue(all(angebot.portal == "acme" for angebot in angebote))
        self.assertIn("java", angebote[0].skills)

    def test_policy_blockt_unbekannten_pfad(self):
        from unittest.mock import MagicMock

        portal = MagicMock()
        portal.base_url = "http://127.0.0.1:1"
        portal.search_path = "/nicht-erlaubt"
        portal.policy.allowed_hosts = ["127.0.0.1"]
        portal.policy.allowed_paths = ["/portal/acme/jobs"]
        with self.assertRaises(PolicyViolation):
            suche_portal(portal, "http://127.0.0.1:1")


class FilterTest(unittest.TestCase):
    def test_filter_nach_suchbegriffen(self):
        profil = _mini_profil()
        ja = JobAngebot(
            id="1",
            portal="p",
            firma="F",
            titel="Java Developer",
            ort="X",
            arbeitsmodell="remote",
            skills={"java"},
        )
        nein = JobAngebot(
            id="2",
            portal="p",
            firma="F",
            titel="QA Engineer",
            ort="X",
            arbeitsmodell="onsite",
            skills={"test"},
        )
        gefiltert = filtere_nach_suchbegriffen(profil, [ja, nein])
        self.assertEqual([a.id for a in gefiltert], ["1"])

    def test_ohne_suchbegriffe_kein_filter(self):
        profil = _mini_profil().__class__(
            name="T", suchbegriffe=(), skills_pflicht={"java"}
        )
        self.assertEqual(
            len(
                filtere_nach_suchbegriffen(
                    profil,
                    [
                        JobAngebot(
                            id="1",
                            portal="p",
                            firma="F",
                            titel="x",
                            ort="y",
                            arbeitsmodell="o",
                            skills={"java"},
                        )
                    ],
                )
            ),
            1,
        )


class LaufTest(unittest.TestCase):
    def test_lauf_erzeugt_bericht_mit_treffern_und_quellen(self):
        with tempfile.TemporaryDirectory() as tmp:
            ziel = Path(tmp) / "bericht.md"
            profil, matches, pfad = lauf(
                profil_pfad=_schreibe_java_profil(tmp), bericht_pfad=ziel
            )
            self.assertTrue(pfad.exists())
            text = pfad.read_text(encoding="utf-8")
            self.assertIn(profil.name, text)
            self.assertIn("acme-karriere", text)
            self.assertIn("jobvermittlung", text)
            self.assertTrue(any(match.passt for match in matches))
            self.assertTrue(any(not match.passt for match in matches))

    def test_lauf_erzeugt_standardbericht(self):
        _profil, _matches, pfad = lauf()
        self.assertEqual(pfad.name, "job-report.md")
        self.assertTrue(pfad.parent.name == "reports")


class EchtPortalGateTest(unittest.TestCase):
    def test_echtes_portal_dry_run(self):
        portale = lade_portale()
        beispiel = next(p for p in portale if p.portal_id == "beispiel")
        plan = crawle_echtes_portal(beispiel, "Java", allow_external=False)
        self.assertEqual(plan["portal"], "beispiel-karriere")
        self.assertIn("Dry-Run", plan["hinweis"])

    def test_lokales_portal_darf_nicht_echt_crawlt_werden(self):
        portale = lade_portale()
        acme = next(p for p in portale if p.portal_id == "acme")
        with self.assertRaises(ValueError):
            crawle_echtes_portal(acme, "Java")

    def test_plan_fuer_echtes_portal_ohne_netzwerk(self):
        portale = lade_portale()
        beispiel = next(p for p in portale if p.portal_id == "beispiel")
        plan = plan_echtes_portal(beispiel)
        self.assertIn("ALLOW_EXTERNAL_PORTALS", plan["hinweis"])


class EchtePortaleIndeedStepstoneTest(unittest.TestCase):
    """Indeed bleibt deaktiviert; Stepstone wurde per Nutzerfreigabe (2026-08-12)
    fuer echte Laeufe mit Camoufox freigeschaltet. Siehe
    todos/archiv/job-agent-camoufox-stepstone.json."""

    def test_indeed_ist_geladen_und_deaktiviert(self):
        portale = lade_portale()
        indeed = next(p for p in portale if p.name == "indeed")
        self.assertEqual(indeed.kind, "real")
        self.assertFalse(indeed.enabled)
        self.assertIsNone(indeed.selectors)
        self.assertFalse(crawl_erlaubt(indeed))

    def test_stepstone_ist_freigeschaltet_mit_camoufox(self):
        portale = lade_portale()
        stepstone = next(p for p in portale if p.name == "stepstone")
        self.assertEqual(stepstone.kind, "real")
        self.assertTrue(stepstone.enabled)
        self.assertEqual(stepstone.browser, "camoufox")
        self.assertIsNotNone(stepstone.selectors)
        self.assertIsNotNone(stepstone.selectors.input_css)

    def test_stepstone_bleibt_ohne_freigabe_nicht_crawl_erlaubt(self):
        portale = lade_portale()
        stepstone = next(p for p in portale if p.name == "stepstone")
        self.assertTrue(stepstone.enabled)
        self.assertFalse(crawl_erlaubt(stepstone))

    def test_indeed_und_stepstone_liefern_dry_run_plan(self):
        portale = lade_portale()
        by_name = {portal.name: portal for portal in portale}
        for name in ("indeed", "stepstone"):
            plan = crawle_echtes_portal(by_name[name], "Java", allow_external=False)
            self.assertEqual(plan["portal"], name)
            self.assertIn("Dry-Run", plan["hinweis"])

    def test_stepstone_plan_nennt_camoufox_engine(self):
        portale = lade_portale()
        stepstone = next(p for p in portale if p.name == "stepstone")
        plan = plan_echtes_portal(stepstone)
        self.assertEqual(plan["browser"], "camoufox")
        self.assertIn("camoufox", plan["hinweis"])

    def test_indeed_echter_lauf_bleibt_ohne_selectors_blockiert(self):
        """Indeed hat weiterhin keine selectors - der echte Lauf bleibt auch
        bei voller Freigabe technisch blockiert (AGB, JAP-01 bleibt bestehen)."""
        portale = lade_portale()
        indeed = next(p for p in portale if p.name == "indeed")
        freigegeben = indeed.model_copy(update={"enabled": True})
        with self.assertRaises(ValueError):
            crawle_echtes_portal(freigegeben, "Java", allow_external=True)


if __name__ == "__main__":
    unittest.main()

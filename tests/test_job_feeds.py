"""Vertragstests fuer offizielle Job-Feeds und den Portal-Katalog."""

import unittest

import httpx

from job_search_mcp.infrastructure.feeds import suche_feed
from job_search_mcp.infrastructure.portal_config import (
    lade_portal_katalog,
    lade_portale,
)


def _portal(portal_id: str):
    return next(portal for portal in lade_portale() if portal.portal_id == portal_id)


class PortalKatalogTest(unittest.TestCase):
    def test_katalog_ordnet_aktive_und_nicht_automatisierte_portale_ein(self):
        katalog = {eintrag.portal_id: eintrag for eintrag in lade_portal_katalog()}

        self.assertGreaterEqual(len(katalog), 15)
        self.assertEqual(katalog["arbeitnow"].status, "aktiv")
        self.assertEqual(katalog["arbeitnow"].zugangsart, "oeffentliche_api")
        self.assertEqual(katalog["indeed"].status, "gesperrt")
        self.assertEqual(katalog["instaffo"].status, "manuell")
        self.assertEqual(katalog["linkedin"].status, "partnerzugang")

    def test_katalog_ids_sind_eindeutig(self):
        ids = [eintrag.portal_id for eintrag in lade_portal_katalog()]
        self.assertEqual(len(ids), len(set(ids)))


class FeedSucheTest(unittest.TestCase):
    def test_arbeitnow_wird_normalisiert_und_lokal_gefiltert(self):
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/api/job-board-api")
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "slug": "python-berlin",
                            "company_name": "Beispiel GmbH",
                            "title": "Python Backend Developer",
                            "description": f"<p>Python und FastAPI in Berlin. {'x' * 2200}</p>",
                            "remote": False,
                            "url": "https://www.arbeitnow.com/jobs/python-berlin",
                            "tags": ["Python", "FastAPI"],
                            "job_types": ["full_time"],
                            "location": "Berlin",
                        },
                        {
                            "slug": "sales-hamburg",
                            "company_name": "Andere AG",
                            "title": "Sales Manager",
                            "description": "Vertrieb",
                            "remote": False,
                            "url": "https://www.arbeitnow.com/jobs/sales-hamburg",
                            "tags": ["Sales"],
                            "location": "Hamburg",
                        },
                    ]
                },
            )

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            angebote = suche_feed(_portal("arbeitnow"), "python", "berlin", client)

        self.assertEqual(len(angebote), 1)
        self.assertEqual(angebote[0]["portal"], "arbeitnow")
        self.assertEqual(angebote[0]["firma"], "Beispiel GmbH")
        self.assertEqual(angebote[0]["skills"], ["FastAPI", "Python"])
        self.assertNotIn("<p>", angebote[0]["beschreibung"])
        self.assertLessEqual(len(angebote[0]["beschreibung"]), 2000)

    def test_remotive_nutzt_suchparameter_und_behaelt_quellenlink(self):
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.params["search"], "backend")
            return httpx.Response(
                200,
                json={
                    "jobs": [
                        {
                            "id": 42,
                            "url": "https://remotive.com/remote-jobs/software-dev/backend-42",
                            "title": "Backend Engineer",
                            "company_name": "Remote GmbH",
                            "candidate_required_location": "Germany",
                            "description": "<p>Python APIs</p>",
                            "tags": ["Python", "API"],
                            "job_type": "full_time",
                            "salary": "",
                        }
                    ]
                },
            )

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            angebote = suche_feed(_portal("remotive"), "backend", "germany", client)

        self.assertEqual(len(angebote), 1)
        self.assertEqual(angebote[0]["arbeitsmodell"], "remote")
        self.assertTrue(angebote[0]["link"].startswith("https://remotive.com/"))

    def test_weworkremotely_liefert_rss_angebote(self):
        rss = """<?xml version="1.0" encoding="UTF-8"?>
        <rss xmlns:wwr="https://weworkremotely.com" version="2.0">
          <channel><item>
            <title>Acme: Senior Backend Engineer</title>
            <link>https://weworkremotely.com/remote-jobs/acme-backend</link>
            <description><![CDATA[<p>Python and distributed systems</p>]]></description>
            <wwr:company>Acme</wwr:company>
            <wwr:region>Anywhere in the World</wwr:region>
            <wwr:category>Back-End Programming</wwr:category>
            <wwr:type>Full-Time</wwr:type>
          </item></channel>
        </rss>"""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text=rss)

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            angebote = suche_feed(
                _portal("weworkremotely"), "backend", "nürnberg", client
            )

        self.assertEqual(len(angebote), 1)
        self.assertEqual(angebote[0]["firma"], "Acme")
        self.assertEqual(angebote[0]["arbeitsmodell"], "remote")
        self.assertIn("Back-End Programming", angebote[0]["skills"])


if __name__ == "__main__":
    unittest.main()

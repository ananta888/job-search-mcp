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
        self.assertEqual(katalog["arbeitsagentur"].status, "aktiv")
        self.assertEqual(katalog["arbeitsagentur"].zugangsart, "oeffentliche_api")
        self.assertEqual(katalog["bw-karriere"].status, "aktiv")
        self.assertEqual(katalog["jobriver"].status, "aktiv")
        self.assertEqual(katalog["jobriver"].zugangsart, "browser_oeffentlich")
        self.assertEqual(katalog["freelancermap"].status, "aktiv")
        self.assertEqual(katalog["freelancermap"].zugangsart, "browser_oeffentlich")
        self.assertEqual(katalog["freelancermap"].kategorie, "freelance_boerse")
        self.assertEqual(katalog["freelance-de"].status, "gesperrt")
        self.assertEqual(katalog["jobsheise"].status, "manuell")
        self.assertEqual(katalog["jobvector"].status, "manuell")
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

    def test_arbeitsagentur_nutzt_keyword_ort_und_loest_seiten_auf(self):
        anfragen: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            anfragen.append(request)
            self.assertEqual(request.headers["X-API-Key"], "jobboerse-jobsuche")
            self.assertEqual(request.url.params["was"], "ki")
            self.assertEqual(request.url.params["wo"], "Karlsruhe")
            self.assertEqual(request.url.params["size"], "20")
            seite = int(request.url.params["page"])
            if seite == 1:
                return httpx.Response(
                    200,
                    json={
                        "ergebnisliste": [
                            {
                                "stellenangebotsTitel": "KI Ressourcement (m/w/d)",
                                "firma": "Bertrandt AG",
                                "referenznummer": "12288-4910294258-S",
                                "hauptberuf": "KI-Manager/in",
                                "alleBerufe": ["KI-Manager/in"],
                                "homeofficemoeglich": False,
                                "vertragsdauer": "UNBEFRISTET",
                                "externeURL": "https://www.persy.jobs/persy/l/job-jciri-b",
                                "stellenlokationen": [
                                    {
                                        "adresse": {
                                            "plz": "76187",
                                            "ort": "Karlsruhe, Baden",
                                        }
                                    }
                                ],
                            }
                        ],
                        "page": 1,
                        "size": 5,
                        "maxErgebnisse": 2,
                    },
                )
            return httpx.Response(
                200,
                json={
                    "ergebnisliste": [
                        {
                            "stellenangebotsTitel": "Referent Digitalisierung (w/m/d)",
                            "firma": "Landesverwaltung",
                            "referenznummer": "12288-999-S",
                            "hauptberuf": "Referent/in",
                            "alleBerufe": ["Referent/in"],
                            "homeofficemoeglich": True,
                            "vertragsdauer": "UNBEFRISTET",
                            "externeURL": "",
                            "stellenlokationen": [
                                {
                                    "adresse": {
                                        "plz": "70173",
                                        "ort": "Stuttgart, Baden",
                                    }
                                }
                            ],
                        }
                    ],
                    "page": 2,
                    "size": 5,
                    "maxErgebnisse": 2,
                },
            )

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            angebote = suche_feed(_portal("arbeitsagentur"), "ki", "Karlsruhe", client)

        self.assertEqual(len(angebote), 1)
        self.assertEqual(angebote[0]["firma"], "Bertrandt AG")
        self.assertIn("KI-Manager/in", angebote[0]["skills"])
        self.assertNotIn("Stuttgart", angebote[0]["ort"])
        self.assertEqual(len(anfragen), 1)

    def test_bw_karriere_liest_alle_seiten_und_filtert_lokal(self):
        def handler(request: httpx.Request) -> httpx.Response:
            seite = int(request.url.params.get("page", "1"))
            if seite == 1:
                return httpx.Response(
                    200,
                    json={
                        "listings": [
                            {
                                "id": 1575,
                                "title": "IT-Referent/in (w/m/d) im Referat Digitalisierung",
                                "location": "Karlsruhe",
                                "department": "Innenministerium",
                                "field_of_activity": "IT und Digitalisierung",
                                "compensation_short": "E13",
                                "application_deadline": "30. August 2026",
                                "url": "https://karriere.baden-wuerttemberg.de/job/1575",
                            },
                            {
                                "id": 1576,
                                "title": "Forstinspektor/in (w/m/d)",
                                "location": "Stuttgart",
                                "department": "Ministerium",
                                "field_of_activity": "Forst",
                                "url": "https://karriere.baden-wuerttemberg.de/job/1576",
                            },
                        ],
                        "pagination": {
                            "page": 1,
                            "per_page": 5,
                            "total_items": 6,
                            "total_pages": 2,
                            "has_next": True,
                        },
                    },
                )
            return httpx.Response(
                200,
                json={
                    "listings": [
                        {
                            "id": 1577,
                            "title": "Sachbearbeitung Automatisierung (w/m/d)",
                            "location": "Karlsruhe",
                            "department": "Finanzministerium",
                            "field_of_activity": "IT und Digitalisierung",
                            "url": "https://karriere.baden-wuerttemberg.de/job/1577",
                        }
                    ],
                    "pagination": {
                        "page": 2,
                        "per_page": 5,
                        "total_items": 6,
                        "total_pages": 2,
                        "has_next": False,
                    },
                },
            )

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            angebote = suche_feed(
                _portal("bw-karriere"), "digitalisierung", "karlsruhe", client
            )

        self.assertEqual(len(angebote), 2)
        self.assertEqual(
            angebote[0]["titel"], "IT-Referent/in (w/m/d) im Referat Digitalisierung"
        )
        self.assertEqual(angebote[0]["firma"], "Innenministerium")
        self.assertIn("IT und Digitalisierung", angebote[0]["beschreibung"])
        self.assertEqual(
            angebote[1]["titel"], "Sachbearbeitung Automatisierung (w/m/d)"
        )
        self.assertNotIn("Stuttgart", angebote[1]["ort"])

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

    @staticmethod
    def _jobriver_karte(
        slug: str,
        angebots_id: str,
        titel: str,
        firma: str,
        *meta: str,
    ) -> str:
        meta_html = '<span class="alle-jobs-card-dot">·</span>'.join(
            f'<span class="alle-jobs-card-location">'
            f'<span class="alle-jobs-card-text">{teil}</span></span>'
            for teil in meta
        )
        return (
            f'<a href="/jobs/{slug}-{angebots_id}" class="alle-jobs-card alle-jobs-card-standard">'
            f'<div class="alle-jobs-card-header"><div class="alle-jobs-card-title-wrapper">'
            f'<h2 class="alle-jobs-card-title">{titel}</h2></div></div>'
            f'<div class="alle-jobs-card-content">'
            f'<p class="alle-jobs-card-company">{firma}</p>'
            f'<div class="alle-jobs-card-meta">{meta_html}</div></div></a>'
        )

    def test_jobriver_liest_karten_und_folgt_seiten(self):
        anfragen: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            anfragen.append(request)
            if request.url.path == "/stellenangebote/seite/2":
                return httpx.Response(
                    200,
                    text=self._jobriver_karte(
                        "automatisierungsexperte",
                        "456",
                        "Automatisierungsexperte (m/w/d)",
                        "Prozess AG",
                        "Karlsruhe",
                        "Remote",
                        "Vollzeit",
                    ),
                )
            self.assertEqual(request.url.path, "/stellenangebote")
            return httpx.Response(
                200,
                text=(
                    '<html><head><link rel="next" href="/stellenangebote/seite/2">'
                    "</head><body>"
                    + self._jobriver_karte(
                        "senior-ki-entwickler",
                        "123",
                        "Senior KI-Entwickler (m/w/d)",
                        "Beispiel GmbH",
                        "Heidelberg",
                        "Hybrid",
                        "Vollzeit",
                    )
                    + self._jobriver_karte(
                        "sales-manager",
                        "789",
                        "Sales Manager (m/w/d)",
                        "Andere AG",
                        "Hamburg",
                        "Vor Ort",
                        "Vollzeit",
                    )
                    + "</body></html>"
                ),
            )

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            angebote = suche_feed(_portal("jobriver"), "ki", "Heidelberg", client)

        self.assertEqual(len(anfragen), 2)
        self.assertEqual(len(angebote), 1)
        treffer = angebote[0]
        self.assertEqual(treffer["portal"], "jobriver")
        self.assertEqual(treffer["titel"], "Senior KI-Entwickler (m/w/d)")
        self.assertEqual(treffer["firma"], "Beispiel GmbH")
        self.assertEqual(treffer["ort"], "Heidelberg")
        self.assertEqual(treffer["arbeitsmodell"], "hybrid")
        self.assertTrue(treffer["link"].endswith("/jobs/senior-ki-entwickler-123"))

    def test_freelancermap_nutzt_query_city_und_mappt_projektfelder(self):
        import json

        def projekte_seite(projekte: list[dict]) -> str:
            blob = json.dumps(
                {"initialResults": projekte, "currentPage": 1},
                ensure_ascii=False,
            )
            return (
                '<html><body><script type="application/json" class="js-react-on-rails-component" '
                'data-component-name="ProjectSearch" data-dom-id="sfreact-project-search">'
                + blob
                + "</script></body></html>"
            )

        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/projekte")
            self.assertEqual(request.url.params["query"], "ki")
            self.assertEqual(request.url.params["city"], "Karlsruhe")
            return httpx.Response(
                200,
                text=projekte_seite(
                    [
                        {
                            "slug": "ki-automatisierungsexperte",
                            "title": "KI-Automatisierungsexperte (m/w/d)",
                            "city": "Karlsruhe",
                            "description": "<p>Automatisierung von Prozessen mit Python.</p>",
                            "links": {
                                "company": {
                                    "name": "Prozess Consulting GmbH",
                                    "url": "/projektanbieter/Prozess-123.html",
                                },
                                "project": "/projekt/ki-automatisierungsexperte",
                            },
                            "projectContractType": {
                                "type": "contracting",
                                "remoteInPercent": 80,
                            },
                            "beginningText": "ab sofort",
                            "durationText": "6 Monate",
                            "skills": [{"de": "Python"}, {"de": "Automatisierung"}],
                        },
                        {
                            "slug": "ki-vertriebsmitarbeiter",
                            "title": "KI-Vertriebsmitarbeiter (m/w/d)",
                            "city": "Karlsruhe",
                            "description": "<p>Vertriebsinnendienst mit KI-Unterstuetzung</p>",
                            "links": {"company": {"name": "Andere AG"}},
                            "projectContractType": {
                                "type": "permanent_position",
                                "remoteInPercent": 0,
                            },
                            "skills": [],
                        },
                    ]
                ),
            )

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            angebote = suche_feed(_portal("freelancermap"), "ki", "Karlsruhe", client)

        self.assertEqual(len(angebote), 1)
        treffer = angebote[0]
        self.assertEqual(treffer["portal"], "freelancermap")
        self.assertEqual(treffer["titel"], "KI-Automatisierungsexperte (m/w/d)")
        self.assertEqual(treffer["firma"], "Prozess Consulting GmbH")
        self.assertEqual(treffer["ort"], "Karlsruhe")
        self.assertEqual(treffer["arbeitsmodell"], "hybrid")
        self.assertEqual(treffer["skills"], ["Automatisierung", "Python"])
        self.assertIn("Auftragsart: Freiberuflicher Auftrag", treffer["beschreibung"])
        self.assertTrue(treffer["link"].endswith("/projekt/ki-automatisierungsexperte"))


class PolicyTest(unittest.TestCase):
    def test_pfadpraefix_erlaubt_unterseiten(self):
        from job_search_mcp.domain.crawler_models import ReplayRequest
        from job_search_mcp.infrastructure.crawler_config import PolicyProfile
        from job_search_mcp.infrastructure.policy import (
            PolicyViolation,
            assert_replay_allowed,
        )

        policy = PolicyProfile(
            allowed_hosts=["jobriver.de"],
            allowed_paths=["/stellenangebote"],
        )
        assert_replay_allowed(
            ReplayRequest(
                method="GET",
                url="https://jobriver.de/stellenangebote/seite/2",
                headers={},
                json_body={},
            ),
            policy,
        )
        with self.assertRaises(PolicyViolation):
            assert_replay_allowed(
                ReplayRequest(
                    method="GET",
                    url="https://jobriver.de/kontakt",
                    headers={},
                    json_body={},
                ),
                policy,
            )


if __name__ == "__main__":
    unittest.main()

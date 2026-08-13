"""Adapter fuer offiziell angebotene Job-APIs und RSS-Feeds.

Die Adapter liefern denselben Rohvertrag wie die Browser-Suche. Transport,
Anbieterformat und HTML-Bereinigung bleiben damit ausserhalb der Domaenenmodelle.
"""

from __future__ import annotations

import base64
import json
import re
from collections.abc import Callable
from html.parser import HTMLParser
from typing import Any
from xml.etree import ElementTree

import httpx

from job_search_mcp.domain.crawler_models import ReplayRequest
from job_search_mcp.infrastructure.policy import assert_replay_allowed
from job_search_mcp.infrastructure.portal_config import PortalFeed, PortalProfil

MAX_BESCHREIBUNG_ZEICHEN = 2000
MAX_SEITEN = 20


class JobFeedFehler(RuntimeError):
    """Ein offizieller Feed konnte nicht gelesen oder validiert werden."""


class _HtmlText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.teile: list[str] = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self.teile.append(text)


class _JobriverKarte(HTMLParser):
    """Sammelt Text innerhalb der Jobriver-Trefferkarten-Klassen."""

    ZIELE = frozenset(
        {"alle-jobs-card-title", "alle-jobs-card-company", "alle-jobs-card-meta"}
    )

    def __init__(self) -> None:
        super().__init__()
        self._text: dict[str, list[str]] = {ziel: [] for ziel in self.ZIELE}
        self._aktiv: str | None = None
        self._tiefe = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        klassen = set((dict(attrs).get("class") or "").split())
        if self._aktiv is None:
            treffer = klassen & self.ZIELE
            if treffer:
                self._aktiv = sorted(treffer)[0]
                self._tiefe = 1
        else:
            self._tiefe += 1

    def handle_endtag(self, tag: str) -> None:
        if self._aktiv is not None:
            self._tiefe -= 1
            if self._tiefe == 0:
                self._aktiv = None

    def handle_data(self, data: str) -> None:
        if self._aktiv is not None:
            self._text[self._aktiv].append(data)

    def wert(self, klasse: str) -> str:
        return " ".join(" ".join(self._text[klasse]).split())


def _html_zu_text(wert: object) -> str:
    parser = _HtmlText()
    parser.feed(str(wert or ""))
    return " ".join(parser.teile)[:MAX_BESCHREIBUNG_ZEICHEN]


def _liste(wert: object) -> list[str]:
    if not isinstance(wert, list):
        return []
    return sorted({str(eintrag).strip() for eintrag in wert if str(eintrag).strip()})


def _ort_passt(angebot: dict[str, Any], ort: str | None) -> bool:
    if not ort:
        return True
    angebot_ort = str(angebot.get("ort", "")).casefold()
    if ort.casefold().strip() in angebot_ort:
        return True
    weltweite_marker = ("anywhere", "worldwide", "anywhere in the world", "global")
    return angebot.get("arbeitsmodell") == "remote" and any(
        marker in angebot_ort for marker in weltweite_marker
    )


def _passt(angebot: dict[str, Any], query: str, ort: str | None) -> bool:
    suchtext = " ".join(
        str(angebot.get(feld, ""))
        for feld in ("titel", "firma", "beschreibung", "skills")
    ).casefold()
    begriffe = [begriff for begriff in query.casefold().split() if begriff]
    if begriffe and not all(begriff in suchtext for begriff in begriffe):
        return False
    return _ort_passt(angebot, ort)


def _basis_angebot(
    *,
    portal: PortalProfil,
    link: object,
    titel: object,
    firma: object,
    ort: object,
    arbeitsmodell: object,
    skills: list[str],
    beschreibung: object,
) -> dict[str, Any]:
    link_text = str(link or "").strip()
    return {
        "id": link_text,
        "link": link_text,
        "portal": portal.portal_id,
        "titel": str(titel or "").strip(),
        "firma": str(firma or "").strip(),
        "ort": str(ort or "").strip(),
        "arbeitsmodell": str(arbeitsmodell or "").strip(),
        "skills": skills,
        "sprachen": [],
        "beschreibung": _html_zu_text(beschreibung),
        "gehalt_min": None,
        "gehalt_max": None,
    }


def _arbeitnow(
    portal: PortalProfil,
    payload: object,
    query: str,
    ort: str | None,
) -> list[dict[str, Any]]:
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise JobFeedFehler("Arbeitnow-Antwort enthaelt keine data-Liste.")
    angebote: list[dict[str, Any]] = []
    for roh in payload["data"]:
        if not isinstance(roh, dict):
            continue
        angebot = _basis_angebot(
            portal=portal,
            link=roh.get("url"),
            titel=roh.get("title"),
            firma=roh.get("company_name"),
            ort=roh.get("location"),
            arbeitsmodell="remote" if roh.get("remote") is True else "",
            skills=_liste(roh.get("tags")),
            beschreibung=roh.get("description"),
        )
        if angebot["id"] and angebot["titel"] and _passt(angebot, query, ort):
            angebote.append(angebot)
    return angebote


def _remotive(
    portal: PortalProfil,
    payload: object,
    query: str,
    ort: str | None,
) -> list[dict[str, Any]]:
    if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
        raise JobFeedFehler("Remotive-Antwort enthaelt keine jobs-Liste.")
    angebote: list[dict[str, Any]] = []
    for roh in payload["jobs"]:
        if not isinstance(roh, dict):
            continue
        angebot = _basis_angebot(
            portal=portal,
            link=roh.get("url"),
            titel=roh.get("title"),
            firma=roh.get("company_name"),
            ort=roh.get("candidate_required_location"),
            arbeitsmodell="remote",
            skills=_liste(roh.get("tags")),
            beschreibung=roh.get("description"),
        )
        if angebot["id"] and angebot["titel"] and _passt(angebot, query, ort):
            angebote.append(angebot)
    return angebote


def _xml_wert(element: ElementTree.Element, name: str) -> str:
    for kind in element:
        if kind.tag.rsplit("}", 1)[-1] == name:
            return (kind.text or "").strip()
    return ""


def _weworkremotely(
    portal: PortalProfil,
    payload: object,
    query: str,
    ort: str | None,
) -> list[dict[str, Any]]:
    if not isinstance(payload, str):
        raise JobFeedFehler("We Work Remotely lieferte keinen XML-Text.")
    try:
        wurzel = ElementTree.fromstring(payload)
    except ElementTree.ParseError as exc:
        raise JobFeedFehler("We Work Remotely lieferte ungueltiges XML.") from exc
    angebote: list[dict[str, Any]] = []
    for item in wurzel.findall("./channel/item"):
        titel = _xml_wert(item, "title")
        firma = _xml_wert(item, "company")
        if not firma and ":" in titel:
            firma, titel = (teil.strip() for teil in titel.split(":", 1))
        kategorie = _xml_wert(item, "category")
        angebot = _basis_angebot(
            portal=portal,
            link=_xml_wert(item, "link"),
            titel=titel,
            firma=firma,
            ort=_xml_wert(item, "region"),
            arbeitsmodell="remote",
            skills=[kategorie] if kategorie else [],
            beschreibung=_xml_wert(item, "description"),
        )
        if angebot["id"] and angebot["titel"] and _passt(angebot, query, ort):
            angebote.append(angebot)
    return angebote


def _ba_link(roh: dict[str, Any]) -> str:
    link = str(roh.get("externeURL") or "").strip()
    if link:
        return link
    referenznummer = str(roh.get("referenznummer") or "").strip()
    if not referenznummer:
        return ""
    kodiert = base64.urlsafe_b64encode(referenznummer.encode()).decode().rstrip("=")
    return f"https://www.arbeitsagentur.de/jobsuche/jobdetail/{kodiert}"


def _arbeitsagentur(
    portal: PortalProfil,
    payload: object,
    query: str,
    ort: str | None,
) -> list[dict[str, Any]]:
    if not isinstance(payload, dict) or not isinstance(
        payload.get("ergebnisliste"), list
    ):
        raise JobFeedFehler(
            "Arbeitsagentur-Antwort enthaelt keine ergebnisliste-Liste."
        )
    angebote: list[dict[str, Any]] = []
    for roh in payload["ergebnisliste"]:
        if not isinstance(roh, dict):
            continue
        lokationen = roh.get("stellenlokationen")
        adresse = {}
        if (
            isinstance(lokationen, list)
            and lokationen
            and isinstance(lokationen[0], dict)
        ):
            erste = lokationen[0].get("adresse")
            if isinstance(erste, dict):
                adresse = erste
        ort_ba = ", ".join(
            teil.strip()
            for teil in (str(adresse.get("plz") or ""), str(adresse.get("ort") or ""))
            if teil.strip()
        )
        hauptberuf = str(roh.get("hauptberuf") or "").strip()
        skills = {hauptberuf} if hauptberuf else set()
        skills.update(_liste(roh.get("alleBerufe")))
        beschreibungs_teile = [
            hauptberuf,
            str(roh.get("vertragsdauer") or ""),
            "Homeoffice" if roh.get("homeofficemoeglich") else "",
        ]
        angebot = _basis_angebot(
            portal=portal,
            link=_ba_link(roh),
            titel=roh.get("stellenangebotsTitel"),
            firma=roh.get("firma"),
            ort=ort_ba,
            arbeitsmodell="homeoffice" if roh.get("homeofficemoeglich") else "",
            skills=sorted(skills, key=str.casefold),
            beschreibung=" ".join(teil for teil in beschreibungs_teile if teil),
        )
        if angebot["id"] and angebot["titel"] and _ort_passt(angebot, ort):
            angebote.append(angebot)
    return angebote


def _bw_karriere(
    portal: PortalProfil,
    payload: object,
    query: str,
    ort: str | None,
) -> list[dict[str, Any]]:
    if not isinstance(payload, dict) or not isinstance(payload.get("listings"), list):
        raise JobFeedFehler("BW-Karriere-Antwort enthaelt keine listings-Liste.")
    angebote: list[dict[str, Any]] = []
    for roh in payload["listings"]:
        if not isinstance(roh, dict):
            continue
        scopes = _liste(roh.get("employment_scopes"))
        arten = _liste(roh.get("employment_type"))
        dauer = _liste(roh.get("employment_duration"))
        beschreibungs_teile = [
            str(roh.get("department") or ""),
            str(roh.get("field_of_activity") or ""),
            str(roh.get("compensation_short") or ""),
            str(roh.get("application_deadline") or ""),
            *arten,
            *dauer,
            *scopes,
        ]
        angebot = _basis_angebot(
            portal=portal,
            link=roh.get("url"),
            titel=roh.get("title"),
            firma=roh.get("department"),
            ort=roh.get("location"),
            arbeitsmodell="",
            skills=[],
            beschreibung=", ".join(teil for teil in beschreibungs_teile if teil),
        )
        if angebot["id"] and angebot["titel"] and _passt(angebot, query, ort):
            angebote.append(angebot)
    return angebote


def _jobriver_meta(meta: str) -> tuple[str, str]:
    teile = [teil.strip() for teil in meta.split("·") if teil.strip()]
    ort = teile[0] if teile else ""
    arbeitsmodell = ""
    for wert in teile[1:]:
        niedrig = wert.casefold()
        if niedrig in {"remote", "hybrid", "vor ort"}:
            arbeitsmodell = niedrig
            break
    return ort, arbeitsmodell


def _jobriver(
    portal: PortalProfil,
    payload: object,
    query: str,
    ort: str | None,
) -> list[dict[str, Any]]:
    if not isinstance(payload, str):
        raise JobFeedFehler("Jobriver lieferte keinen HTML-Text.")
    angebote: list[dict[str, Any]] = []
    for m in re.finditer(
        r'<a\s+href="(/jobs/[a-z0-9-]+-\d+)"[^>]*class="alle-jobs-card[^"]*"[^>]*>',
        payload,
        re.S,
    ):
        karte_ende = payload.find("</a>", m.end())
        if karte_ende < 0:
            continue
        parser = _JobriverKarte()
        parser.feed(payload[m.end() : karte_ende])
        ort_jobriver, arbeitsmodell = _jobriver_meta(parser.wert("alle-jobs-card-meta"))
        angebot = _basis_angebot(
            portal=portal,
            link=f"https://jobriver.de{m.group(1)}",
            titel=parser.wert("alle-jobs-card-title"),
            firma=parser.wert("alle-jobs-card-company"),
            ort=ort_jobriver,
            arbeitsmodell=arbeitsmodell,
            skills=[],
            beschreibung="",
        )
        if angebot["id"] and angebot["titel"] and _passt(angebot, query, ort):
            angebote.append(angebot)
    return angebote


_VERTRAGSARTEN = {
    "contracting": "Freiberuflicher Auftrag",
    "permanent_position": "Festanstellung",
    "employee_leasing": "Arbeitnehmerüberlassung",
}


def _freelancermap_json(text: str) -> dict[str, Any]:
    marker = 'data-component-name="ProjectSearch"'
    start = text.find(marker)
    if start < 0:
        raise JobFeedFehler(
            "Freelancermap-Seite enthaelt kein ProjectSearch-JSON."
        )
    start = text.find(">", start) + 1
    ende = text.find("</script>", start)
    if ende < 0:
        raise JobFeedFehler("Freelancermap-ProjectSearch-JSON ist nicht geschlossen.")
    try:
        roh = json.loads(text[start:ende])
    except ValueError as exc:
        raise JobFeedFehler(
            "Freelancermap-ProjectSearch-JSON ist kein gueltiges JSON."
        ) from exc
    if not isinstance(roh, dict):
        raise JobFeedFehler("Freelancermap-ProjectSearch-JSON ist kein Mapping.")
    return roh


def _freelancermap_link(projekt: dict[str, Any]) -> str:
    slug = str(projekt.get("slug") or "").strip()
    if not slug:
        return ""
    return f"https://www.freelancermap.de/projekt/{slug}"


def _freelancermap_firma(projekt: dict[str, Any]) -> str:
    links = projekt.get("links")
    if isinstance(links, dict):
        company = links.get("company")
        if isinstance(company, dict):
            name = str(company.get("name") or "").strip()
            if name:
                return name
    poster = projekt.get("poster")
    if isinstance(poster, dict):
        return str(poster.get("company") or "").strip()
    return ""


def _freelancermap_vertragsart(projekt: dict[str, Any]) -> str:
    pct = projekt.get("projectContractType")
    typ = ""
    if isinstance(pct, dict):
        typ = str(pct.get("type") or "").strip()
    return f"Auftragsart: {_VERTRAGSARTEN.get(typ, typ)}" if typ else ""


def _freelancermap_ist_festanstellung(projekt: dict[str, Any]) -> bool:
    pct = projekt.get("projectContractType")
    return isinstance(pct, dict) and pct.get("type") == "permanent_position"


def _freelancermap_ort(projekt: dict[str, Any]) -> tuple[str, str]:
    ort = str(projekt.get("city") or "").strip()
    remote_prozent = 0
    pct = projekt.get("projectContractType")
    if isinstance(pct, dict):
        try:
            remote_prozent = int(pct.get("remoteInPercent") or 0)
        except (TypeError, ValueError):
            remote_prozent = 0
    if remote_prozent >= 100:
        arbeitsmodell = "remote"
    elif remote_prozent > 0:
        arbeitsmodell = "hybrid"
    else:
        arbeitsmodell = ""
    return ort, arbeitsmodell


def _freelancermap(
    portal: PortalProfil,
    payload: object,
    query: str,
    ort: str | None,
) -> list[dict[str, Any]]:
    if not isinstance(payload, str):
        raise JobFeedFehler("Freelancermap lieferte keinen HTML-Text.")
    data = _freelancermap_json(payload)
    roh = data.get("initialResults")
    if not isinstance(roh, list):
        raise JobFeedFehler("Freelancermap-JSON enthaelt keine initialResults-Liste.")
    angebote: list[dict[str, Any]] = []
    for projekt in roh:
        if not isinstance(projekt, dict):
            continue
        if _freelancermap_ist_festanstellung(projekt):
            continue
        link = _freelancermap_link(projekt)
        if not link:
            continue
        ort_flm, arbeitsmodell = _freelancermap_ort(projekt)
        skills = sorted(
            {
                str(skill.get("de") or "").strip()
                for skill in (projekt.get("skills") or [])
                if isinstance(skill, dict)
            }
        )
        beschreibungs_teile = [
            _freelancermap_vertragsart(projekt),
            str(projekt.get("beginningText") or ""),
            str(projekt.get("durationText") or ""),
            _html_zu_text(projekt.get("description")),
        ]
        angebot = _basis_angebot(
            portal=portal,
            link=link,
            titel=projekt.get("title"),
            firma=_freelancermap_firma(projekt),
            ort=ort_flm,
            arbeitsmodell=arbeitsmodell,
            skills=skills,
            beschreibung=", ".join(teil for teil in beschreibungs_teile if teil),
        )
        if angebot["id"] and angebot["titel"] and _passt(angebot, query, ort):
            angebote.append(angebot)
    return angebote


_ADAPTER: dict[
    str,
    Callable[[PortalProfil, object, str, str | None], list[dict[str, Any]]],
] = {
    "arbeitnow": _arbeitnow,
    "remotive": _remotive,
    "weworkremotely": _weworkremotely,
    "arbeitsagentur": _arbeitsagentur,
    "bw_karriere": _bw_karriere,
    "jobriver": _jobriver,
    "freelancermap": _freelancermap,
}


def _feed_params(
    adapter: str,
    feed: PortalFeed,
    query: str,
    ort: str | None,
    seite: int,
) -> dict[str, str | int]:
    if adapter == "remotive":
        return {"search": query, "limit": feed.max_treffer}
    if adapter == "arbeitsagentur":
        size = max(min(feed.max_treffer, 100), 5)
        params: dict[str, str | int] = {"was": query, "size": size, "page": seite}
        if ort:
            params["wo"] = ort
            params["umkreis"] = 50
        return params
    if adapter == "bw_karriere":
        return {"page": seite}
    if adapter == "freelancermap":
        flm_params: dict[str, str | int] = {}
        if query:
            flm_params["query"] = query
        if ort and ort.casefold().strip() not in {"", "remote"}:
            flm_params["city"] = ort
        return flm_params
    return {}


def _seiten_url(feed: PortalFeed, seite: int) -> str:
    if feed.adapter == "jobriver" and seite > 1:
        return f"{feed.endpoint.rstrip('/')}/seite/{seite}"
    return feed.endpoint


def _seite_fertig(adapter: str, payload: object, params: dict[str, str | int]) -> bool:
    if adapter == "arbeitsagentur":
        if not isinstance(payload, dict):
            return True
        ergebnisliste = payload.get("ergebnisliste")
        if not isinstance(ergebnisliste, list) or not ergebnisliste:
            return True
        seite = int(params.get("page", 1))
        groesse = int(params.get("size", 5))
        max_ergebnisse = payload.get("maxErgebnisse")
        if isinstance(max_ergebnisse, int) and seite * groesse >= max_ergebnisse:
            return True
        return len(ergebnisliste) < groesse
    if adapter == "bw_karriere":
        if not isinstance(payload, dict):
            return True
        pagination = payload.get("pagination")
        if isinstance(pagination, dict):
            return not pagination.get("has_next")
    if adapter == "jobriver":
        return not isinstance(payload, str) or 'rel="next"' not in payload
    return True


def _hole_feed(
    client: httpx.Client,
    portal: PortalProfil,
    params: dict[str, str | int],
    seite: int = 1,
) -> object:
    feed = portal.feed
    if feed is None:
        raise ValueError(f"Portal hat keinen Feed: {portal.portal_id}")
    headers = {"accept": "application/json, application/rss+xml, application/xml"}
    headers.update(feed.headers)
    url = _seiten_url(feed, seite)
    assert_replay_allowed(
        ReplayRequest(method="GET", url=url, headers=headers, json_body={}),
        portal.policy,
    )
    response = client.get(url, params=params, headers=headers)
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise JobFeedFehler(
            f"{portal.portal_id} antwortete mit HTTP {response.status_code}."
        ) from exc
    if feed.adapter in ("jobriver", "freelancermap"):
        return response.content.decode("utf-8", errors="replace")
    if feed.adapter == "weworkremotely":
        return response.text
    try:
        return response.json()
    except ValueError as exc:
        raise JobFeedFehler(
            f"{portal.portal_id} lieferte kein gueltiges JSON."
        ) from exc


def _feed_anfragen(
    client: httpx.Client,
    portal: PortalProfil,
    query: str,
    ort: str | None,
) -> list[object]:
    feed = portal.feed
    if feed is None:
        raise ValueError(f"Portal hat keinen Feed: {portal.portal_id}")
    payloads: list[object] = []
    if feed.adapter not in ("arbeitsagentur", "bw_karriere", "jobriver"):
        return [
            _hole_feed(
                client, portal, _feed_params(feed.adapter, feed, query, ort, 1)
            )
        ]
    for seite in range(1, MAX_SEITEN + 1):
        params = _feed_params(feed.adapter, feed, query, ort, seite)
        payload = _hole_feed(client, portal, params, seite)
        payloads.append(payload)
        if _seite_fertig(feed.adapter, payload, params):
            break
    return payloads


def suche_feed(
    portal: PortalProfil,
    query: str,
    ort: str | None = None,
    client: httpx.Client | None = None,
) -> list[dict[str, Any]]:
    """Fragt einen konfigurierten Feed ab und normalisiert seine Treffer."""
    feed = portal.feed
    if feed is None:
        raise ValueError(f"Portal hat keinen Feed: {portal.portal_id}")
    adapter = _ADAPTER[feed.adapter]
    if client is None:
        with httpx.Client(timeout=15, follow_redirects=True) as eigener_client:
            payloads = _feed_anfragen(eigener_client, portal, query, ort)
    else:
        payloads = _feed_anfragen(client, portal, query, ort)
    angebote: list[dict[str, Any]] = []
    for payload in payloads:
        for angebot in adapter(portal, payload, query, ort):
            if angebot["id"] not in {bestehend["id"] for bestehend in angebote}:
                angebote.append(angebot)
        if len(angebote) >= feed.max_treffer:
            break
    return angebote[: feed.max_treffer]

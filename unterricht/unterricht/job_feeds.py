"""Adapter fuer offiziell angebotene Job-APIs und RSS-Feeds.

Die Adapter liefern denselben Rohvertrag wie die Browser-Suche. Transport,
Anbieterformat und HTML-Bereinigung bleiben damit ausserhalb der Domaenenmodelle.
"""

from __future__ import annotations

from collections.abc import Callable
from html.parser import HTMLParser
from typing import Any
from xml.etree import ElementTree

import httpx

from unterricht.job_portal import PortalProfil
from unterricht.models import ReplayRequest
from unterricht.policy import assert_replay_allowed

MAX_BESCHREIBUNG_ZEICHEN = 2000


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


def _html_zu_text(wert: object) -> str:
    parser = _HtmlText()
    parser.feed(str(wert or ""))
    return " ".join(parser.teile)[:MAX_BESCHREIBUNG_ZEICHEN]


def _liste(wert: object) -> list[str]:
    if not isinstance(wert, list):
        return []
    return sorted({str(eintrag).strip() for eintrag in wert if str(eintrag).strip()})


def _passt(angebot: dict[str, Any], query: str, ort: str | None) -> bool:
    suchtext = " ".join(
        str(angebot.get(feld, ""))
        for feld in ("titel", "firma", "beschreibung", "skills")
    ).casefold()
    begriffe = [begriff for begriff in query.casefold().split() if begriff]
    if begriffe and not all(begriff in suchtext for begriff in begriffe):
        return False
    if not ort:
        return True
    angebot_ort = str(angebot.get("ort", "")).casefold()
    if ort.casefold().strip() in angebot_ort:
        return True
    weltweite_marker = ("anywhere", "worldwide", "anywhere in the world", "global")
    return angebot.get("arbeitsmodell") == "remote" and any(
        marker in angebot_ort for marker in weltweite_marker
    )


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


_ADAPTER: dict[
    str,
    Callable[[PortalProfil, object, str, str | None], list[dict[str, Any]]],
] = {
    "arbeitnow": _arbeitnow,
    "remotive": _remotive,
    "weworkremotely": _weworkremotely,
}


def _feed_anfragen(
    client: httpx.Client,
    portal: PortalProfil,
    query: str,
) -> object:
    feed = portal.feed
    if feed is None:
        raise ValueError(f"Portal hat keinen Feed: {portal.portal_id}")
    assert_replay_allowed(
        ReplayRequest(
            method="GET",
            url=feed.endpoint,
            headers={
                "accept": "application/json, application/rss+xml, application/xml"
            },
            json_body={},
        ),
        portal.policy,
    )
    params: dict[str, str | int] = {}
    if feed.adapter == "remotive":
        params = {"search": query, "limit": feed.max_treffer}
    response = client.get(feed.endpoint, params=params)
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise JobFeedFehler(
            f"{portal.portal_id} antwortete mit HTTP {response.status_code}."
        ) from exc
    if feed.adapter == "weworkremotely":
        return response.text
    try:
        return response.json()
    except ValueError as exc:
        raise JobFeedFehler(
            f"{portal.portal_id} lieferte kein gueltiges JSON."
        ) from exc


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
            payload = _feed_anfragen(eigener_client, portal, query)
    else:
        payload = _feed_anfragen(client, portal, query)
    return adapter(portal, payload, query, ort)[: feed.max_treffer]

"""Deterministische Bewertung von Stellenangeboten gegen ein JobProfil.

Die Regeln sind bewusst von Transport und Berichtsformat getrennt, damit sie
rein als Domänenlogik getestet werden koennen.
"""

from typing import Any

from job_search_mcp.domain.models import (
    JobAngebot,
    JobMatch,
    JobProfil,
    normalisiere_menge,
)


def angebot_aus_dict(rohdaten: dict[str, Any]) -> JobAngebot:
    """Baut ein normalisiertes JobAngebot aus einer Portalantwort."""
    gehalt_min = rohdaten.get("gehalt_min")
    gehalt_max = rohdaten.get("gehalt_max")
    erfahrung = rohdaten.get("erfahrungsjahre")
    return JobAngebot(
        id=str(rohdaten["id"]),
        portal=str(rohdaten.get("portal", "")),
        firma=str(rohdaten["firma"]),
        titel=str(rohdaten["titel"]),
        ort=str(rohdaten.get("ort", "")),
        arbeitsmodell=str(rohdaten.get("arbeitsmodell", "")),
        skills=normalisiere_menge(*rohdaten.get("skills", [])),
        gehalt_min=gehalt_min if isinstance(gehalt_min, int) else None,
        gehalt_max=gehalt_max if isinstance(gehalt_max, int) else None,
        sprachen=normalisiere_menge(*rohdaten.get("sprachen", [])),
        erfahrungsjahre=erfahrung if isinstance(erfahrung, int) else None,
        beschreibung=str(rohdaten.get("beschreibung", "")),
    )


def _skill_abgedeckt(skills: frozenset[str], gewuenscht: str) -> bool:
    """True wenn ein Angebots-Skill gleich ist oder als Wortpraefix passt.

    ``spring`` deckt ``spring boot`` ab, aber nicht ``springboot`` und nicht
    das Teilwort ``qa`` in ``quality``.
    """
    return any(
        skill == gewuenscht or skill.startswith(gewuenscht + " ") for skill in skills
    )


def _skill_anteil(menge: frozenset[str], vorhanden: frozenset[str]) -> float:
    if not menge:
        return 1.0
    gedeckt = sum(1 for skill in menge if _skill_abgedeckt(vorhanden, skill))
    return gedeckt / len(menge)


def _ort_passt(profil: JobProfil, angebot: JobAngebot) -> bool:
    if not profil.orte:
        return True
    ort = angebot.ort.casefold()
    for gewuenscht in profil.orte:
        if gewuenscht in ort or ort in gewuenscht:
            return True
    return "remote" in angebot.arbeitsmodell.casefold() and any(
        "remote" in ort for ort in profil.orte
    )


def _modell_passt(profil: JobProfil, angebot: JobAngebot) -> bool:
    if not profil.arbeitsmodelle:
        return True
    modell = angebot.arbeitsmodell.casefold()
    return any(gewuenscht == modell for gewuenscht in profil.arbeitsmodelle)


def _gehalt_score(profil: JobProfil, angebot: JobAngebot) -> int:
    if profil.gehalt_min is None and profil.gehalt_max is None:
        return 15
    if angebot.gehalt_min is None and angebot.gehalt_max is None:
        return 15
    p_lo = profil.gehalt_min if profil.gehalt_min is not None else 0
    p_hi = profil.gehalt_max if profil.gehalt_max is not None else 10**9
    a_lo = angebot.gehalt_min if angebot.gehalt_min is not None else 0
    a_hi = angebot.gehalt_max if angebot.gehalt_max is not None else 10**9
    ueberlappung = max(0, min(p_hi, a_hi) - max(p_lo, a_lo))
    spanne = max(p_hi, a_hi) - min(p_lo, a_lo)
    if spanne <= 0:
        return 15
    return round((ueberlappung / spanne) * 15)


def _bewerte_einzel(profil: JobProfil, angebot: JobAngebot) -> JobMatch:
    gruende: list[str] = []
    vorhandene_pflicht = frozenset(
        skill
        for skill in profil.skills_pflicht
        if _skill_abgedeckt(angebot.skills, skill)
    )
    fehlende_pflicht = tuple(
        sorted(skill for skill in profil.skills_pflicht - vorhandene_pflicht)
    )
    benoetigte_pflicht = (
        len(profil.skills_pflicht)
        if profil.min_pflicht_skills is None
        else min(profil.min_pflicht_skills, len(profil.skills_pflicht))
    )
    passt = True

    if len(vorhandene_pflicht) < benoetigte_pflicht:
        passt = False
        gruende.append("Pflicht-Skills fehlen: " + ", ".join(fehlende_pflicht))
    elif fehlende_pflicht:
        gruende.append(
            f"Pflicht-Skills vorhanden ({len(vorhandene_pflicht)}"
            f"/{len(profil.skills_pflicht)}): " + ", ".join(sorted(vorhandene_pflicht))
        )
    else:
        gruende.append("Alle Pflicht-Skills vorhanden")

    if (
        angebot.sprachen
        and profil.sprachen
        and not (angebot.sprachen & profil.sprachen)
    ):
        passt = False
        gruende.append("Sprachanforderung nicht erfuellt")

    if (
        angebot.erfahrungsjahre is not None
        and profil.min_erfahrung_jahre > angebot.erfahrungsjahre
    ):
        passt = False
        gruende.append(
            f"Nur {angebot.erfahrungsjahre} Jahre Erfahrung statt "
            f"{profil.min_erfahrung_jahre}"
        )

    gefundene_wunsch = tuple(
        sorted(
            skill
            for skill in angebot.skills
            if any(
                skill == wunsch or skill.startswith(wunsch + " ")
                for wunsch in profil.skills_wunsch
            )
        )
    )
    pflicht_anteil = _skill_anteil(profil.skills_pflicht, angebot.skills)
    wunsch_anteil = _skill_anteil(profil.skills_wunsch, angebot.skills)

    ort_score = 15 if _ort_passt(profil, angebot) else 0
    if not ort_score:
        gruende.append("Ort passt nicht")
    else:
        gruende.append("Ort passt")

    modell_score = 10 if _modell_passt(profil, angebot) else 0
    if not modell_score:
        gruende.append("Arbeitsmodell passt nicht")

    gehalt_score = _gehalt_score(profil, angebot)
    if gehalt_score == 0:
        gruende.append("Gehalt ueberlappt nicht")
    elif gehalt_score < 15:
        gruende.append("Gehalt ueberlappt teilweise")

    if gefundene_wunsch:
        gruende.append("Wunsch-Skills: " + ", ".join(gefundene_wunsch))

    score = round(
        pflicht_anteil * 40
        + wunsch_anteil * 20
        + ort_score
        + modell_score
        + gehalt_score
    )
    score = min(100, score)
    if passt:
        gruende.append(f"Score {score}/100")
    return JobMatch(
        angebot=angebot,
        score=score,
        passt=passt,
        gefundene_skills=gefundene_wunsch,
        fehlende_pflicht_skills=fehlende_pflicht,
        gruende=tuple(gruende),
    )


def bewerte_angebote(profil: JobProfil, angebote: list[JobAngebot]) -> list[JobMatch]:
    """Bewertet alle Angebote und sortiert passende nach Score absteigend."""
    matches = [_bewerte_einzel(profil, angebot) for angebot in angebote]
    return sorted(matches, key=lambda match: (match.passt, match.score), reverse=True)

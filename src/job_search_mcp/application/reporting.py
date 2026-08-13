"""Markdown-Bericht fuer den JOB-Agenten."""

from pathlib import Path

from job_search_mcp.domain.models import JobMatch, JobProfil


def _zeile(wert: object) -> str:
    return str(wert)


def _angebotszeile(match: JobMatch) -> list[str]:
    angebot = match.angebot
    gehalt = "k. A."
    if angebot.gehalt_min is not None or angebot.gehalt_max is not None:
        gehalt = f"{angebot.gehalt_min or 0} - {angebot.gehalt_max or 'unbegrenzt'} EUR"
    zeilen = [
        f"### {angebot.titel} bei {angebot.firma} (Score {match.score}/100)",
        f"- Portal: `{angebot.portal}`",
        f"- Ort: {angebot.ort} | Arbeitsmodell: {angebot.arbeitsmodell} | Gehalt: {gehalt}",
        f"- Skills: {', '.join(sorted(angebot.skills))}",
    ]
    if angebot.id.startswith(("https://", "http://")):
        zeilen.append(f"- Link: [Stellenanzeige]({angebot.id})")
    if angebot.sprachen:
        zeilen.append(f"- Sprachen: {', '.join(sorted(angebot.sprachen))}")
    if match.gruende:
        zeilen.append("- Begruendung: " + "; ".join(match.gruende))
    return zeilen


def schreibe_bericht(
    pfad: Path,
    profil: JobProfil,
    matches: list[JobMatch],
    quellen: list[str],
) -> Path:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    passende = [match for match in matches if match.passt]
    ausgeschlossen = [match for match in matches if not match.passt]

    zeilen = [
        "# Job-Bericht",
        "",
        f"_Erstellt: {profil.name}_",
        "",
        "## Profil",
        "",
        f"- Suchbegriffe: {', '.join(profil.suchbegriffe)}",
        f"- Pflicht-Skills: {', '.join(sorted(profil.skills_pflicht))}",
        f"- Wunsch-Skills: {', '.join(sorted(profil.skills_wunsch))}",
        f"- Orte: {', '.join(profil.orte)}",
        f"- Arbeitsmodelle: {', '.join(profil.arbeitsmodelle)}",
        f"- Gehaltsspanne: {profil.gehalt_min or 0} - {profil.gehalt_max or 'unbegrenzt'} EUR",
        f"- Sprachen: {', '.join(sorted(profil.sprachen))}",
        (
            f"- Mindest-Pflicht-Skills: {profil.min_pflicht_skills}"
            if profil.min_pflicht_skills is not None
            else f"- Mindest-Pflicht-Skills: alle ({len(profil.skills_pflicht)})"
        ),
        "",
        "## Zusammenfassung",
        "",
        f"- Passende Angebote: {len(passende)}",
        f"- Ausgeschlossen: {len(ausgeschlossen)}",
        f"- Quellen: {', '.join(quellen)}",
        "",
    ]

    if passende:
        zeilen.append("## Passende Angebote")
        zeilen.append("")
        for match in passende:
            zeilen.extend(_angebotszeile(match))
            zeilen.append("")

    if ausgeschlossen:
        zeilen.append("## Ausgeschlossen")
        zeilen.append("")
        for match in ausgeschlossen:
            zeilen.extend(_angebotszeile(match))
            zeilen.append("")

    zeilen.append("_Erzeugt durch den JOB-Agenten des Unterrichtslabors._")
    pfad.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    return pfad

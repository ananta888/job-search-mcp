"""Laden und Validieren des vorgegebenen Jobsuchprofils."""

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from unterricht.job_models import JobProfil, normalisiere_menge, normalisiere_tuple


ROOT = Path(__file__).resolve().parent
PROFIL_SCHEMA = ROOT / "schemas" / "job-profil.schema.json"
STANDARD_PROFIL = ROOT / "profiles" / "job-suchprofil.json"


def _lese_json(pfad: Path) -> dict[str, Any]:
    try:
        text = pfad.read_text(encoding="utf-8")
    except OSError as error:
        raise ValueError(f"Profil nicht lesbar: {pfad} ({error})") from error
    raw: Any = json.loads(text)
    if not isinstance(raw, dict):
        raise ValueError(f"Das Profil muss ein JSON-Objekt sein: {pfad}")
    return raw


def validiere_profil_dict(rohdaten: dict[str, Any], schema_pfad: Path = PROFIL_SCHEMA) -> dict[str, Any]:
    schema: Any = json.loads(schema_pfad.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(rohdaten)
    return rohdaten


def profil_aus_dict(rohdaten: dict[str, Any]) -> JobProfil:
    """Baut ein normalisiertes JobProfil aus einem bereits validierten Dict."""
    gehalt_min = rohdaten.get("gehalt_min")
    gehalt_max = rohdaten.get("gehalt_max")
    if (
        isinstance(gehalt_min, int)
        and isinstance(gehalt_max, int)
        and gehalt_min > gehalt_max
    ):
        raise ValueError(f"gehalt_min darf nicht groesser als gehalt_max sein: {gehalt_min} > {gehalt_max}")
    return JobProfil(
        name=str(rohdaten["name"]),
        suchbegriffe=normalisiere_tuple(*rohdaten.get("suchbegriffe", [])),
        skills_pflicht=normalisiere_menge(*rohdaten.get("skills_pflicht", [])),
        skills_wunsch=normalisiere_menge(*rohdaten.get("skills_wunsch", [])),
        orte=normalisiere_tuple(*rohdaten.get("orte", [])),
        arbeitsmodelle=normalisiere_tuple(*rohdaten.get("arbeitsmodelle", [])),
        gehalt_min=gehalt_min,
        gehalt_max=gehalt_max,
        sprachen=normalisiere_menge(*rohdaten.get("sprachen", [])),
        min_erfahrung_jahre=int(rohdaten.get("min_erfahrung_jahre", 0)),
    )


def lade_profil(pfad: Path = STANDARD_PROFIL) -> JobProfil:
    """Liest, validiert und normalisiert das Jobsuchprofil."""
    rohdaten = validiere_profil_dict(_lese_json(pfad))
    return profil_aus_dict(rohdaten)

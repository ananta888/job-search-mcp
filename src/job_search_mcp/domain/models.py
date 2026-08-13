"""Immutable Domänenmodelle fuer den JOB-Agenten.

Profil, Angebot und Match sind bewusst getrennt von Transport, Persistenz und
Berichtsformat, damit die Matching-Regeln rein und deterministisch testbar sind.
"""

from dataclasses import dataclass


def normalisiere_menge(*werte: object) -> frozenset[str]:
    """Kleinbuchstaben-normalisierte Menge ohne leere Eintraege."""
    return frozenset(
        str(wert).strip().casefold() for wert in werte if str(wert).strip()
    )


def normalisiere_tuple(*werte: object) -> tuple[str, ...]:
    return tuple(str(wert).strip().casefold() for wert in werte if str(wert).strip())


@dataclass(frozen=True)
class JobProfil:
    name: str
    suchbegriffe: tuple[str, ...]
    skills_pflicht: frozenset[str]
    skills_wunsch: frozenset[str] = frozenset()
    orte: tuple[str, ...] = ()
    arbeitsmodelle: tuple[str, ...] = ()
    gehalt_min: int | None = None
    gehalt_max: int | None = None
    sprachen: frozenset[str] = frozenset()
    min_erfahrung_jahre: int = 0
    min_pflicht_skills: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "suchbegriffe", normalisiere_tuple(*self.suchbegriffe))
        object.__setattr__(
            self, "skills_pflicht", normalisiere_menge(*self.skills_pflicht)
        )
        object.__setattr__(
            self, "skills_wunsch", normalisiere_menge(*self.skills_wunsch)
        )
        object.__setattr__(self, "orte", normalisiere_tuple(*self.orte))
        object.__setattr__(
            self, "arbeitsmodelle", normalisiere_tuple(*self.arbeitsmodelle)
        )
        object.__setattr__(self, "sprachen", normalisiere_menge(*self.sprachen))


@dataclass(frozen=True)
class JobAngebot:
    id: str
    portal: str
    firma: str
    titel: str
    ort: str
    arbeitsmodell: str
    skills: frozenset[str]
    gehalt_min: int | None = None
    gehalt_max: int | None = None
    sprachen: frozenset[str] = frozenset()
    erfahrungsjahre: int | None = None
    beschreibung: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "skills", normalisiere_menge(*self.skills))
        object.__setattr__(self, "sprachen", normalisiere_menge(*self.sprachen))


@dataclass(frozen=True)
class JobMatch:
    angebot: JobAngebot
    score: int
    passt: bool
    gefundene_skills: tuple[str, ...]
    fehlende_pflicht_skills: tuple[str, ...]
    gruende: tuple[str, ...]

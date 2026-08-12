"""Job-Matching-MVP: ein Mini-Profil gegen drei Beispielangebote bewerten."""

from unterricht.job_match import bewerte_angebote
from unterricht.job_models import JobAngebot, JobProfil


def run() -> None:
    profil = JobProfil(
        name="Python-Data-Analyst",
        suchbegriffe=("python", "daten"),
        skills_pflicht={"python", "sql"},
        skills_wunsch={"pandas", "docker"},
        orte=("Berlin", "remote"),
        arbeitsmodelle=("remote", "hybrid"),
        gehalt_min=60000,
        gehalt_max=85000,
        sprachen={"deutsch", "englisch"},
    )
    angebote = [
        JobAngebot(
            id="p1", portal="acme", firma="Acme GmbH", titel="Data Analyst",
            ort="Berlin", arbeitsmodell="remote",
            skills={"python", "sql", "pandas"},
            gehalt_min=65000, gehalt_max=80000, sprachen={"englisch"},
        ),
        JobAngebot(
            id="p2", portal="jobvermittlung", firma="Dataworks",
            titel="Python Developer", ort="Hamburg", arbeitsmodell="onsite",
            skills={"python"},
            gehalt_min=55000, gehalt_max=65000, sprachen={"deutsch"},
        ),
        JobAngebot(
            id="p3", portal="jobvermittlung", firma="Cloudfy",
            titel="Data Engineer", ort="Remote", arbeitsmodell="remote",
            skills={"python", "sql", "docker", "pandas"},
            gehalt_min=70000, gehalt_max=95000, sprachen={"englisch"},
        ),
    ]
    matches = bewerte_angebote(profil, angebote)
    for match in matches:
        status = "PASST" if match.passt else "AUSGESCHLOSSEN"
        print(f"{status:14} Score {match.score:3} | {match.angebot.firma} - {match.angebot.titel}")
        print(f"    {'; '.join(match.gruende)}")


if __name__ == "__main__":
    run()

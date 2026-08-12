"""Tests fuer die deterministische Matching-Logik."""

import unittest

from job_search_mcp.domain.matching import angebot_aus_dict, bewerte_angebote
from job_search_mcp.domain.models import JobAngebot, JobProfil


def _profil(**overrides) -> JobProfil:
    basis = {
        "name": "Dev",
        "suchbegriffe": ("backend",),
        "skills_pflicht": {"java", "spring", "sql"},
        "skills_wunsch": {"docker", "kubernetes"},
        "orte": ("Berlin", "remote"),
        "arbeitsmodelle": ("remote", "hybrid"),
        "gehalt_min": 65000,
        "gehalt_max": 95000,
        "sprachen": {"deutsch", "englisch"},
        "min_erfahrung_jahre": 0,
    }
    basis.update(overrides)
    return JobProfil(**basis)


def _angebot(**overrides) -> JobAngebot:
    basis = {
        "id": "a1",
        "portal": "acme",
        "firma": "Acme GmbH",
        "titel": "Backend Developer",
        "ort": "Berlin",
        "arbeitsmodell": "remote",
        "skills": {"java", "spring", "sql", "docker"},
        "gehalt_min": 70000,
        "gehalt_max": 90000,
        "sprachen": {"englisch"},
        "erfahrungsjahre": None,
    }
    basis.update(overrides)
    return JobAngebot(**basis)


class PflichtSkillGateTest(unittest.TestCase):
    def test_fehlender_pflicht_skill_schliesst_aus(self):
        angebot = _angebot(skills={"java", "sql"})
        match = bewerte_angebote(_profil(), [angebot])[0]
        self.assertFalse(match.passt)
        self.assertIn("spring", match.fehlende_pflicht_skills)
        self.assertTrue(
            any("Pflicht-Skills fehlen" in grund for grund in match.gruende)
        )

    def test_vollstaendige_pflicht_skills_passen(self):
        match = bewerte_angebote(_profil(), [_angebot()])[0]
        self.assertTrue(match.passt)


class SprachenUndErfahrungTest(unittest.TestCase):
    def test_sprachkonflikt_schliesst_aus(self):
        angebot = _angebot(sprachen={"franzoesisch"})
        match = bewerte_angebote(_profil(), [angebot])[0]
        self.assertFalse(match.passt)
        self.assertTrue(any("Sprachanforderung" in grund for grund in match.gruende))

    def test_keine_sprachangabe_kein_ausschluss(self):
        angebot = _angebot(sprachen=set())
        self.assertTrue(bewerte_angebote(_profil(), [angebot])[0].passt)

    def test_erfahrung_zu_gering_schliesst_aus(self):
        profil = _profil(min_erfahrung_jahre=5)
        angebot = _angebot(erfahrungsjahre=2)
        match = bewerte_angebote(profil, [angebot])[0]
        self.assertFalse(match.passt)
        self.assertTrue(any("Erfahrung" in grund for grund in match.gruende))


class ScoreTest(unittest.TestCase):
    def test_hoeherer_wunschskill_anteil_gewinnt(self):
        profil = _profil()
        mit_docker = _angebot(id="mit", skills={"java", "spring", "sql", "docker"})
        ohne = _angebot(id="ohne", skills={"java", "spring", "sql"})
        matches = bewerte_angebote(profil, [ohne, mit_docker])
        self.assertEqual(matches[0].angebot.id, "mit")
        self.assertGreater(matches[0].score, matches[1].score)

    def test_sortierung_passende_vor_ausgeschlossene(self):
        passt = _angebot(id="passt", skills={"java", "spring", "sql"})
        failt = _angebot(id="failt", skills={"java"})
        matches = bewerte_angebote(_profil(), [failt, passt])
        self.assertEqual([m.angebot.id for m in matches], ["passt", "failt"])

    def test_ort_ohne_treffer_verliert_gegen_ort_mit_treffer(self):
        profil = _profil(orte=("Muenchen",), arbeitsmodelle=())
        in_muenchen = _angebot(id="muc", ort="Muenchen")
        in_hamburg = _angebot(id="hamburg", ort="Hamburg")
        matches = bewerte_angebote(profil, [in_hamburg, in_muenchen])
        self.assertEqual(matches[0].angebot.id, "muc")

    def test_gehalt_ohne_ueberlappung_verliert(self):
        profil = _profil(orte=(), arbeitsmodelle=())
        zu_teuer = _angebot(id="teuer", gehalt_min=150000, gehalt_max=200000)
        passend = _angebot(id="passend", gehalt_min=70000, gehalt_max=90000)
        matches = bewerte_angebote(profil, [zu_teuer, passend])
        self.assertEqual(matches[0].angebot.id, "passend")

    def test_leeres_profil_bewertet_neutral_mit_vollpunkt(self):
        profil = _profil(
            skills_pflicht=set(),
            skills_wunsch=set(),
            orte=(),
            arbeitsmodelle=(),
            gehalt_min=None,
            gehalt_max=None,
            sprachen=set(),
        )
        match = bewerte_angebote(profil, [_angebot()])[0]
        self.assertTrue(match.passt)
        self.assertEqual(match.score, 100)

    def test_score_ist_gekappt_bei_100(self):
        self.assertLessEqual(bewerte_angebote(_profil(), [_angebot()])[0].score, 100)


class TeilskillMatchingTest(unittest.TestCase):
    def test_pflicht_skill_matcht_als_wortpraefix(self):
        angebot = _angebot(skills={"spring boot", "java", "sql"})
        match = bewerte_angebote(_profil(), [angebot])[0]
        self.assertTrue(match.passt)

    def test_teilwort_matcht_nicht(self):
        angebot = _angebot(skills={"springboot", "java", "sql"})
        match = bewerte_angebote(_profil(), [angebot])[0]
        self.assertFalse(match.passt)

    def test_wunsch_skill_als_wortpraefix_zaehlt(self):
        angebot = _angebot(skills={"java", "spring", "sql", "docker compose"})
        match = bewerte_angebote(_profil(), [angebot])[0]
        self.assertTrue(any("docker" in skill for skill in match.gefundene_skills))


class AngebotParsingTest(unittest.TestCase):
    def test_angebot_aus_dict_normalisiert_skills(self):
        angebot = angebot_aus_dict(
            {
                "id": 1,
                "firma": "Acme",
                "titel": "Dev",
                "ort": "Berlin",
                "arbeitsmodell": "REMOTE",
                "skills": ["Java", "SQL"],
            }
        )
        self.assertIn("java", angebot.skills)
        self.assertIn("sql", angebot.skills)


if __name__ == "__main__":
    unittest.main()

"""Tests fuer Jobprofil-Laden und JSON-Schema-Validierung."""

import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import ValidationError

from job_search_mcp.infrastructure.profile_repository import (
    PROFIL_SCHEMA,
    lade_profil,
    profil_aus_dict,
    validiere_profil_dict,
)


def _schreibe(tmp: str, daten: dict) -> Path:
    pfad = Path(tmp) / "profil.json"
    pfad.write_text(json.dumps(daten), encoding="utf-8")
    return pfad


class JobProfilLadenTest(unittest.TestCase):
    def test_beispielprofil_wird_geladen_und_normalisiert(self):
        profil = lade_profil()
        self.assertEqual(profil.name, "KI-Automatisierung & Digitalisierungsmanager")
        self.assertIn("ki", profil.suchbegriffe)
        self.assertIn("llm", profil.skills_pflicht)
        self.assertEqual(profil.min_pflicht_skills, 1)
        self.assertIn("karlsruhe", profil.orte)
        self.assertIn("remote", profil.arbeitsmodelle)

    def test_gueltiges_profil_aus_dict(self):
        daten = {
            "name": "Dev",
            "suchbegriffe": ["backend"],
            "skills_pflicht": ["Java", "Spring"],
        }
        profil = profil_aus_dict(validiere_profil_dict(daten))
        self.assertIn("java", profil.skills_pflicht)
        self.assertIn("spring", profil.skills_pflicht)

    def test_ungueltiges_profil_fehlendes_pflichtfeld(self):
        with self.assertRaises(ValidationError):
            validiere_profil_dict({"name": "ohne skills"})

    def test_kein_mapping_wird_abgelehnt(self):
        with self.assertRaises(ValueError):
            lade_profil(Path("existiert-nicht.json"))

    def test_gehalt_min_groesser_gehalt_max_wird_abgelehnt(self):
        daten = {
            "name": "Dev",
            "suchbegriffe": ["backend"],
            "skills_pflicht": ["java"],
            "gehalt_min": 100000,
            "gehalt_max": 50000,
        }
        with self.assertRaises(ValueError):
            profil_aus_dict(validiere_profil_dict(daten))

    def test_schema_datei_ist_selbst_gueltig(self):
        schema = json.loads(PROFIL_SCHEMA.read_text(encoding="utf-8"))
        import jsonschema

        jsonschema.Draft202012Validator.check_schema(schema)

    def test_laden_aus_tempdatei(self):
        with tempfile.TemporaryDirectory() as tmp:
            pfad = _schreibe(
                tmp,
                {
                    "name": "Tester",
                    "suchbegriffe": ["test"],
                    "skills_pflicht": ["python"],
                },
            )
            profil = lade_profil(pfad)
            self.assertEqual(profil.name, "Tester")


if __name__ == "__main__":
    unittest.main()

"""Tests fuer den verschluesselten Anmeldedaten-Speicher (credential_store)."""

import tempfile
import unittest
from pathlib import Path

from unterricht.credential_store import (
    CredentialError,
    CredentialStore,
    PortalCredential,
)


class CredentialStoreTest(unittest.TestCase):
    def test_round_trip_hinterlege_und_lese(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = CredentialStore(Path(tmp))
            store.hinterlege("stepstone", "max@beispiel.de", "geheim")
            gelesen = store.lese("stepstone")
            self.assertEqual(
                gelesen, PortalCredential("stepstone", "max@beispiel.de", "geheim")
            )

    def test_kein_klartext_auf_der_platte(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = CredentialStore(Path(tmp))
            store.hinterlege("stepstone", "max@beispiel.de", "geheim")
            token = (Path(tmp) / "stepstone.cred").read_bytes()
            self.assertNotIn(b"geheim", token)
            self.assertNotIn(b"max@beispiel.de", token)

    def test_token_datei_und_key_haben_0600(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = CredentialStore(Path(tmp))
            store.hinterlege("stepstone", "u", "w")
            for name in ("key", "stepstone.cred"):
                modus = (Path(tmp) / name).stat().st_mode & 0o777
                self.assertEqual(modus, 0o600, f"{name} hat Modus {oct(modus)}")

    def test_schluessel_bleibt_ueber_instanzen_stabil(self):
        with tempfile.TemporaryDirectory() as tmp:
            CredentialStore(Path(tmp)).hinterlege("p", "u", "w")
            gelesen = CredentialStore(Path(tmp)).lese("p")
            self.assertEqual(gelesen, PortalCredential("p", "u", "w"))

    def test_entferne_loescht_daten(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = CredentialStore(Path(tmp))
            store.hinterlege("stepstone", "u", "w")
            self.assertTrue(store.entferne("stepstone"))
            self.assertFalse(store.entferne("stepstone"))
            self.assertIsNone(store.lese("stepstone"))

    def test_ohne_daten_liefert_lese_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(CredentialStore(Path(tmp)).lese("gibts-nicht"))

    def test_korruptes_token_wirft_credential_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = CredentialStore(Path(tmp))
            (Path(tmp) / "stepstone.cred").write_bytes(b"kein fernet-token")
            with self.assertRaises(CredentialError):
                store.lese("stepstone")

    def test_leere_pflichtfelder_werden_abgelehnt(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = CredentialStore(Path(tmp))
            with self.assertRaises(CredentialError):
                store.hinterlege("  ", "u", "w")
            with self.assertRaises(CredentialError):
                store.hinterlege("p", "", "w")

    def test_portal_id_darf_speicherverzeichnis_nicht_verlassen(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = CredentialStore(Path(tmp))
            for portal_id in ("../fremd", "a/b", "a\\b", "."):
                with (
                    self.subTest(portal_id=portal_id),
                    self.assertRaises(CredentialError),
                ):
                    store.hinterlege(portal_id, "u", "w")

    def test_speicherverzeichnis_hat_restriktive_rechte(self):
        with tempfile.TemporaryDirectory() as tmp:
            speicher_dir = Path(tmp) / "credentials"
            CredentialStore(speicher_dir).hinterlege("stepstone", "u", "w")
            self.assertEqual(speicher_dir.stat().st_mode & 0o777, 0o700)

    def test_bestehendes_speicherverzeichnis_wird_abgesichert(self):
        with tempfile.TemporaryDirectory() as tmp:
            speicher_dir = Path(tmp) / "credentials"
            speicher_dir.mkdir(mode=0o755)
            CredentialStore(speicher_dir).hinterlege("stepstone", "u", "w")
            self.assertEqual(speicher_dir.stat().st_mode & 0o777, 0o700)


if __name__ == "__main__":
    unittest.main()

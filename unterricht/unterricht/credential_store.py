"""Verschluesselte Ablage von Portal-Anmeldedaten (Fernet).

Klartext-Anmeldedaten existieren nur im Arbeitsspeicher des laufenden Prozesses
und werden niemals protokolliert oder exportiert. Auf der Platte liegt
ausschliesslich ein Fernet-Token in einer Datei mit 0600-Rechten.

Der Schluessel kommt aus der Umgebungsvariable ``JOB_MCP_FERNET_KEY`` oder wird
beim ersten Lauf generiert und 0600-geschuetzt im State-Verzeichnis abgelegt.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken


@dataclass(frozen=True)
class PortalCredential:
    portal_id: str
    benutzername: str
    passwort: str


class CredentialError(ValueError):
    """Kennzeichnet Probleme mit dem Credential-Speicher."""


_PORTAL_ID = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}", re.IGNORECASE)


def validiere_portal_id(portal_id: str) -> str:
    """Validiert eine Portal-ID, bevor sie Bestandteil eines Dateinamens wird."""
    if not isinstance(portal_id, str) or not _PORTAL_ID.fullmatch(portal_id):
        raise CredentialError(
            "portal_id darf nur Buchstaben, Ziffern, Bindestrich und Unterstrich enthalten"
        )
    return portal_id


class CredentialStore:
    """Fernet-verschluesselter Speicher: ein Token pro Portal."""

    def __init__(self, speicher_dir: Path, key: bytes | None = None) -> None:
        self.speicher_dir = Path(speicher_dir)
        try:
            self._fernet = Fernet(key if key is not None else self._key_laden())
        except (TypeError, ValueError) as error:
            raise CredentialError("Ungueltiger Fernet-Schluessel") from error

    def _speicher_dir_anlegen(self) -> None:
        self.speicher_dir.mkdir(parents=True, exist_ok=True)
        self.speicher_dir.chmod(0o700)

    def _key_laden(self) -> bytes:
        env_key = os.getenv("JOB_MCP_FERNET_KEY")
        if env_key:
            return env_key.encode("utf-8")
        key_pfad = self.speicher_dir / "key"
        if key_pfad.exists():
            self._speicher_dir_anlegen()
            key_pfad.chmod(0o600)
            return key_pfad.read_bytes()
        key = Fernet.generate_key()
        self._speicher_dir_anlegen()
        key_pfad.write_bytes(key)
        key_pfad.chmod(0o600)
        return key

    def _pfad(self, portal_id: str) -> Path:
        return self.speicher_dir / f"{validiere_portal_id(portal_id)}.cred"

    def hinterlege(self, portal_id: str, benutzername: str, passwort: str) -> None:
        """Verschluesselt und speichert die Anmeldedaten eines Portals."""
        validiere_portal_id(portal_id)
        if not benutzername.strip() or not passwort:
            raise CredentialError(
                "portal_id, benutzername und passwort sind erforderlich"
            )
        klartext = json.dumps(
            {"benutzername": benutzername, "passwort": passwort},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        token = self._fernet.encrypt(klartext.encode("utf-8"))
        pfad = self._pfad(portal_id)
        self._speicher_dir_anlegen()
        pfad.write_bytes(token)
        pfad.chmod(0o600)

    def lese(self, portal_id: str) -> PortalCredential | None:
        """Entschluesselt die Anmeldedaten oder liefert None, wenn keine hinterlegt sind."""
        pfad = self._pfad(portal_id)
        if not pfad.exists():
            return None
        try:
            text = self._fernet.decrypt(pfad.read_bytes()).decode("utf-8")
        except (InvalidToken, OSError, UnicodeDecodeError) as error:
            raise CredentialError(
                f"Anmeldedaten fuer {portal_id!r} sind nicht entschluesselbar "
                "(falscher Schluessel oder beschädigtes Token)"
            ) from error
        try:
            rohdaten = json.loads(text)
            benutzername = rohdaten["benutzername"]
            passwort = rohdaten["passwort"]
            if not isinstance(benutzername, str) or not isinstance(passwort, str):
                raise TypeError
        except (json.JSONDecodeError, KeyError, TypeError):
            # Abwaertskompatibel zu Tokens aus der ersten Implementierung.
            benutzername, trenner, passwort = text.partition("\n")
            if not trenner:
                raise CredentialError(
                    f"Anmeldedaten fuer {portal_id!r} haben ein ungueltiges Format"
                )
        return PortalCredential(
            portal_id=portal_id, benutzername=benutzername, passwort=passwort
        )

    def entferne(self, portal_id: str) -> bool:
        """Loescht gespeicherte Anmeldedaten; True wenn etwas geloescht wurde."""
        pfad = self._pfad(portal_id)
        if pfad.exists():
            pfad.unlink()
            return True
        return False

    def vorhanden(self, portal_id: str) -> bool:
        return self._pfad(portal_id).exists()

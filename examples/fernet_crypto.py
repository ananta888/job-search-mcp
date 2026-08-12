"""Cryptography-MVP: ein Secret nur im Speicher ver- und entschluesseln."""

from cryptography.fernet import Fernet


def run() -> None:
    cipher = Fernet(Fernet.generate_key())
    token = cipher.encrypt(b"job-search-demo-secret")
    plaintext = cipher.decrypt(token).decode("utf-8")
    print(
        f"Fernet: verschlüsselt ({len(token)} Bytes) und entschlüsselt -> {plaintext}"
    )


if __name__ == "__main__":
    run()

"""PyYAML-MVP: eine lesbare Konfiguration laden."""

from unterricht.profile import PROFILE_PATH, read_profile_yaml


def run() -> None:
    raw = read_profile_yaml()
    print(f"PyYAML: {PROFILE_PATH.name} -> Profil {raw['name']!r}")


if __name__ == "__main__":
    run()

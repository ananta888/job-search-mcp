"""Zentrale Pfadauflösung für Paketressourcen und veränderliche Ausgaben."""

from __future__ import annotations

import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
RESOURCES_DIR = PACKAGE_DIR / "resources"
PROFILES_DIR = RESOURCES_DIR / "profiles"
PORTALS_DIR = PROFILES_DIR / "portals"
SCHEMAS_DIR = RESOURCES_DIR / "schemas"
DEFAULT_JOB_PROFILE = PROFILES_DIR / "job-profile.json"
LOCAL_DEMO_PROFILE = PROFILES_DIR / "local-demo.yaml"
PORTAL_CATALOG_FILE = PROFILES_DIR / "portal-catalog.yaml"


def resolve_profile_path(path: str | Path) -> Path:
    """Löst Nutzerpfade zuerst lokal und danach gegen gebündelte Profile auf."""
    requested = Path(path).expanduser()
    if requested.is_absolute() or requested.exists():
        return requested.resolve()
    resource_name = requested.name
    packaged = PROFILES_DIR / resource_name
    if packaged.exists():
        return packaged
    return requested.resolve()


def resolve_schema_path(path: str | Path) -> Path:
    """Löst einen Schemanamen unabhängig vom aktuellen Arbeitsverzeichnis auf."""
    requested = Path(path).expanduser()
    if requested.is_absolute() or requested.exists():
        return requested.resolve()
    packaged = SCHEMAS_DIR / requested.name
    if packaged.exists():
        return packaged
    return requested.resolve()


def report_dir() -> Path:
    """Berichte sind veränderliche Nutzerdaten und liegen außerhalb des Pakets."""
    configured = os.getenv("JOB_MCP_REPORT_DIR")
    return (
        Path(configured).expanduser().resolve()
        if configured
        else Path.cwd() / "reports"
    )

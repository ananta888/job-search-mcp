"""Kleine Allowlist-Policy vor jedem direkten Replay."""

from urllib.parse import urlsplit

from job_search_mcp.domain.crawler_models import ReplayRequest
from job_search_mcp.infrastructure.crawler_config import PolicyProfile


class PolicyViolation(ValueError):
    pass


def _pfad_erlaubt(pfad: str, erlaubt: list[str]) -> bool:
    """Erlaubt exakte Treffer sowie alle Unterseiten eines erlaubten Pfads."""
    return any(pfad == teil or pfad.startswith(teil + "/") for teil in erlaubt)


def assert_replay_allowed(request: ReplayRequest, policy: PolicyProfile) -> None:
    target = urlsplit(request.url)
    if target.scheme not in {"http", "https"}:
        raise PolicyViolation(f"Nicht erlaubtes URL-Schema: {target.scheme}")
    if target.hostname not in policy.allowed_hosts:
        raise PolicyViolation(f"Host nicht in Allowlist: {target.hostname}")
    if not _pfad_erlaubt(target.path, policy.allowed_paths):
        raise PolicyViolation(f"Pfad nicht in Allowlist: {target.path}")

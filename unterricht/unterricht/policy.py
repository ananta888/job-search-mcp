"""Kleine Allowlist-Policy vor jedem direkten Replay."""

from urllib.parse import urlsplit

from unterricht.models import ReplayRequest
from unterricht.profile import PolicyProfile


class PolicyViolation(ValueError):
    pass


def assert_replay_allowed(request: ReplayRequest, policy: PolicyProfile) -> None:
    target = urlsplit(request.url)
    if target.scheme not in {"http", "https"}:
        raise PolicyViolation(f"Nicht erlaubtes URL-Schema: {target.scheme}")
    if target.hostname not in policy.allowed_hosts:
        raise PolicyViolation(f"Host nicht in Allowlist: {target.hostname}")
    if target.path not in policy.allowed_paths:
        raise PolicyViolation(f"Pfad nicht in Allowlist: {target.path}")

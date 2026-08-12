"""Reduziert Browser-Requests auf bewusst replaybare Daten."""

from unterricht.models import CapturedHttpRequest, ReplayRequest


ALLOWED_CAPTURED_HEADERS = frozenset({"accept", "content-type"})


def normalize_request(captured: CapturedHttpRequest) -> ReplayRequest:
    headers = {
        name.lower(): value
        for name, value in captured.headers.items()
        if name.lower() in ALLOWED_CAPTURED_HEADERS
    }
    headers.setdefault("accept", "application/json")
    headers.setdefault("content-type", "application/json")
    return ReplayRequest(
        method=captured.method,
        url=captured.url,
        headers=headers,
        json_body=dict(captured.json_body),
    )

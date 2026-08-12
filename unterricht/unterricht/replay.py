"""Direkter HTTP-Replay ohne Browser."""

from typing import Any

import httpx

from unterricht.models import ReplayRequest, ReplayResult


def replay_request(request: ReplayRequest) -> ReplayResult:
    with httpx.Client(timeout=5, follow_redirects=False) as client:
        response = client.request(
            method=request.method,
            url=request.url,
            headers=request.headers,
            json=request.json_body,
        )
    response.raise_for_status()
    response_json: Any = response.json()
    if not isinstance(response_json, dict):
        raise TypeError("Die Replay-Antwort muss ein JSON-Objekt sein")
    return ReplayResult(status_code=response.status_code, response_json=response_json)

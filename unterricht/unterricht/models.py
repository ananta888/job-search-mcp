"""Kleine explizite Datenmodelle fuer Discovery und Replay."""

from dataclasses import dataclass
from typing import Any


JsonObject = dict[str, Any]


@dataclass(frozen=True)
class CapturedHttpRequest:
    method: str
    url: str
    headers: dict[str, str]
    json_body: JsonObject


@dataclass(frozen=True)
class DiscoveryResult:
    request: CapturedHttpRequest
    response_json: JsonObject
    ui_output: str


@dataclass(frozen=True)
class ReplayRequest:
    method: str
    url: str
    headers: dict[str, str]
    json_body: JsonObject


@dataclass(frozen=True)
class ReplayResult:
    status_code: int
    response_json: JsonObject

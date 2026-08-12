"""Durchgaengiges MVP: UI -> Capture -> Policy -> Replay -> Validation."""

from job_search_mcp.domain.normalization import normalize_request
from job_search_mcp.infrastructure.crawler_config import load_profile
from job_search_mcp.infrastructure.discovery import discover_search
from job_search_mcp.infrastructure.http_replay import replay_request
from job_search_mcp.infrastructure.policy import assert_replay_allowed
from job_search_mcp.infrastructure.validation import assert_equivalent, validate_schema
from job_search_mcp.interfaces.demo_server import DemoServer


def run() -> None:
    profile = load_profile()
    with DemoServer() as server:
        discovery = discover_search(server.base_url, "OCR", profile)
        print(f"1 UI-Discovery: {discovery.ui_output}")
        print(f"2 Capture: {discovery.request.method} {discovery.request.url}")

        replay_request_model = normalize_request(discovery.request)
        print(f"3 Normalisierung: Header={sorted(replay_request_model.headers)}")

        assert_replay_allowed(replay_request_model, profile.policy)
        print("4 Policy: lokales Ziel erlaubt")

        replay = replay_request(replay_request_model)
        validate_schema(replay.response_json, profile.validation.schema_file)
        assert_equivalent(
            discovery.response_json,
            replay.response_json,
            profile.validation.ignore_paths,
        )
        print(f"5 Replay + Validierung: HTTP {replay.status_code}, gleichwertig")


if __name__ == "__main__":
    run()

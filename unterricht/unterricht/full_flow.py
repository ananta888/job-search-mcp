"""Durchgaengiges MVP: UI -> Capture -> Policy -> Replay -> Validation."""

from unterricht.discovery import discover_search
from unterricht.normalization import normalize_request
from unterricht.policy import assert_replay_allowed
from unterricht.profile import load_profile
from unterricht.replay import replay_request
from unterricht.server import DemoServer
from unterricht.validation import assert_equivalent, validate_schema


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

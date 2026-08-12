"""JSON-Schema-MVP: eine echte lokale API-Antwort pruefen."""

import httpx

from job_search_mcp.infrastructure.crawler_config import load_profile
from job_search_mcp.infrastructure.validation import validate_schema
from job_search_mcp.interfaces.demo_server import DemoServer


def run() -> None:
    profile = load_profile()
    with DemoServer() as server:
        response = httpx.post(
            f"{server.base_url}/api/search",
            json={"query": "Replay", "limit": 1},
            timeout=5,
        )
        response.raise_for_status()
    validate_schema(response.json(), profile.validation.schema_file)
    print("JSON Schema: Antwort ist strukturell gültig")


if __name__ == "__main__":
    run()

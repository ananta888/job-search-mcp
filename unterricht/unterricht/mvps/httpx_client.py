"""HTTPX-MVP: die lokale API direkt aufrufen."""

import httpx

from unterricht.server import DemoServer


def run() -> None:
    with DemoServer() as server:
        response = httpx.post(
            f"{server.base_url}/api/search",
            json={"query": "OCR", "limit": 1},
            timeout=5,
        )
        response.raise_for_status()
        payload = response.json()
        print(f"HTTPX: HTTP {response.status_code} -> {payload['results'][0]['title']}")


if __name__ == "__main__":
    run()

"""python-multipart-MVP: klassische Formulardaten verarbeiten."""

import httpx

from unterricht.server import DemoServer


def run() -> None:
    with DemoServer() as server:
        response = httpx.post(
            f"{server.base_url}/api/form",
            data={"topic": "OCR"},
            timeout=5,
        )
        response.raise_for_status()
    print(f"python-multipart: {response.json()}")


if __name__ == "__main__":
    run()

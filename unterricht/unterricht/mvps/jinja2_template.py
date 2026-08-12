"""Jinja2-MVP: serverseitig HTML aus Daten rendern."""

import httpx

from unterricht.server import DemoServer


def run() -> None:
    with DemoServer() as server:
        response = httpx.get(
            f"{server.base_url}/result",
            params={"topic": "Jinja2 im Unterricht"},
            timeout=5,
        )
        response.raise_for_status()
    marker = "<h1>Jinja2 im Unterricht</h1>"
    if marker not in response.text:
        raise AssertionError("Template wurde nicht wie erwartet gerendert")
    print(f"Jinja2: HTML gerendert -> {marker}")


if __name__ == "__main__":
    run()

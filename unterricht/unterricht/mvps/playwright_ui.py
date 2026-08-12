"""Playwright-MVP: fill, click, read in isoliertem BrowserContext."""

from unterricht.discovery import discover_search
from unterricht.profile import load_profile
from unterricht.server import DemoServer


def run() -> None:
    with DemoServer() as server:
        result = discover_search(server.base_url, "OCR", load_profile())
    print(f"Playwright: {result.ui_output}")


if __name__ == "__main__":
    run()

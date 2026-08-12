"""Playwright-MVP: fill, click, read in isoliertem BrowserContext."""

from job_search_mcp.infrastructure.crawler_config import load_profile
from job_search_mcp.infrastructure.discovery import discover_search
from job_search_mcp.interfaces.demo_server import DemoServer


def run() -> None:
    with DemoServer() as server:
        result = discover_search(server.base_url, "OCR", load_profile())
    print(f"Playwright: {result.ui_output}")


if __name__ == "__main__":
    run()

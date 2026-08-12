"""Session-MVP: Cookie-Zustand explizit exportieren und wiederverwenden."""

from playwright.sync_api import sync_playwright

from unterricht.server import DemoServer


def run() -> None:
    with DemoServer() as server, sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        first_context = browser.new_context()
        try:
            page = first_context.new_page()
            response = page.request.post(f"{server.base_url}/api/session/start")
            if not response.ok:
                raise RuntimeError("Sitzung konnte nicht erstellt werden")
            state = first_context.storage_state()
        finally:
            first_context.close()

        second_context = browser.new_context(storage_state=state)
        try:
            response = second_context.request.get(f"{server.base_url}/api/session/private")
            response_json = response.json()
            if not response.ok:
                raise RuntimeError(f"Sitzung konnte nicht wiederverwendet werden: {response_json}")
        finally:
            second_context.close()
            browser.close()
    print(f"Session State: {response_json['session']}")


if __name__ == "__main__":
    run()

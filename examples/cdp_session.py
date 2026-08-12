"""CDP-MVP: einen Chrome-DevTools-Befehl ueber Playwright senden."""

from playwright.sync_api import sync_playwright


def run() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        try:
            page = context.new_page()
            cdp = context.new_cdp_session(page)
            reply = cdp.send(
                "Runtime.evaluate",
                {"expression": "6 * 7", "returnByValue": True},
            )
            value = reply["result"]["value"]
            print(f"Chrome DevTools Protocol: 6 * 7 = {value}")
        finally:
            context.close()
            browser.close()


if __name__ == "__main__":
    run()

"""UI-Discovery mit Playwright und gezieltem Netzwerk-Capture."""

from typing import Any

from playwright.sync_api import expect, sync_playwright

from job_search_mcp.domain.crawler_models import CapturedHttpRequest, DiscoveryResult
from job_search_mcp.infrastructure.crawler_config import TeachingProfile


def discover_search(
    base_url: str,
    query: str,
    profile: TeachingProfile,
) -> DiscoveryResult:
    """Perform fill-click-read and return the request caused by that action."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        try:
            page = context.new_page()
            page.goto(base_url, wait_until="domcontentloaded")
            page.get_by_label(profile.selectors.input_label).fill(query)

            with page.expect_response(
                lambda response: (
                    response.url.endswith("/api/search")
                    and response.request.method == "POST"
                )
            ) as response_info:
                page.get_by_role(
                    profile.selectors.submit_role,
                    name=profile.selectors.submit_name,
                ).click()

            response = response_info.value
            response_json: Any = response.json()
            request_json: Any = response.request.post_data_json
            if not isinstance(response_json, dict) or not isinstance(
                request_json, dict
            ):
                raise TypeError(
                    "Die Unterrichts-API muss JSON-Objekte senden und empfangen"
                )

            output = page.locator(profile.selectors.output_css)
            expect(output).not_to_have_text("")
            ui_output = output.inner_text()

            request = CapturedHttpRequest(
                method=response.request.method,
                url=response.request.url,
                headers=dict(response.request.headers),
                json_body=request_json,
            )
            return DiscoveryResult(
                request=request,
                response_json=response_json,
                ui_output=ui_output,
            )
        finally:
            context.close()
            browser.close()

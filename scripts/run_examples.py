"""Fuehrt alle lokalen Kern-MVPs nacheinander aus."""

import subprocess
import sys

CORE_MVPS = (
    "examples.yaml_config",
    "examples.pydantic_validation",
    "examples.httpx_client",
    "examples.jinja2_template",
    "examples.multipart_form",
    "examples.jsonschema_validation",
    "examples.fernet_crypto",
    "examples.structlog_logging",
    "examples.playwright_ui",
    "examples.cdp_session",
    "examples.session_state",
    "examples.job_matching",
    "job_search_mcp.application.job_flow",
    "job_search_mcp.application.crawler_flow",
)


def run() -> None:
    for index, module in enumerate(CORE_MVPS, start=1):
        print(f"\n[{index}/{len(CORE_MVPS)}] {module}", flush=True)
        subprocess.run([sys.executable, "-m", module], check=True)
    print("\nAlle lokalen Kern-MVPs sind erfolgreich.")


if __name__ == "__main__":
    run()

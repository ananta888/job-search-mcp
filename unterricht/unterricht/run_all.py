"""Fuehrt alle lokalen Kern-MVPs nacheinander aus."""

import subprocess
import sys


CORE_MVPS = (
    "unterricht.mvps.yaml_config",
    "unterricht.mvps.pydantic_validation",
    "unterricht.mvps.httpx_client",
    "unterricht.mvps.jinja2_template",
    "unterricht.mvps.multipart_form",
    "unterricht.mvps.jsonschema_validation",
    "unterricht.mvps.fernet_crypto",
    "unterricht.mvps.structlog_logging",
    "unterricht.mvps.playwright_ui",
    "unterricht.mvps.cdp_session",
    "unterricht.mvps.session_state",
    "unterricht.mvps.job_matching",
    "unterricht.job_flow",
    "unterricht.full_flow",
)


def run() -> None:
    for index, module in enumerate(CORE_MVPS, start=1):
        print(f"\n[{index}/{len(CORE_MVPS)}] {module}", flush=True)
        subprocess.run([sys.executable, "-m", module], check=True)
    print("\nAlle lokalen Kern-MVPs sind erfolgreich.")


if __name__ == "__main__":
    run()

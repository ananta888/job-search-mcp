"""Optionales Browser-Use-MVP mit sicherem Dry-Run als Standard."""

import argparse
import asyncio
import os
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from job_search_mcp.interfaces.demo_server import DemoServer


def task_for(base_url: str) -> str:
    return (
        f"Öffne {base_url}, suche nach OCR und gib ausschließlich den Text "
        "des Suchergebnisses zurück. Verlasse diese lokale Website nicht."
    )


async def execute(base_url: str) -> str:
    from browser_use import Agent, Browser, ChatBrowserUse

    if not os.getenv("BROWSER_USE_API_KEY"):
        raise RuntimeError("Für --run muss BROWSER_USE_API_KEY gesetzt sein")
    browser = Browser(headless=True, allowed_domains=["127.0.0.1"])
    try:
        agent: Any = Agent(
            task=task_for(base_url),
            llm=ChatBrowserUse(),
            browser=browser,
            use_vision=False,
            max_actions_per_step=2,
        )
        history = await agent.run(max_steps=8)
        return history.final_result() or "kein Ergebnis"
    finally:
        await browser.stop()


def run(run_agent: bool = False) -> None:
    try:
        installed_version = version("browser-use")
    except PackageNotFoundError as error:
        raise RuntimeError(
            "Installieren mit: pip install -e '.[browser-use]'"
        ) from error

    with DemoServer() as server:
        task = task_for(server.base_url)
        print(f"Browser Use {installed_version}: Aufgabe vorbereitet -> {task}")
        if run_agent:
            print(f"Agent-Ergebnis: {asyncio.run(execute(server.base_url))}")
        else:
            print("Dry-Run; echter Agent optional mit --run und BROWSER_USE_API_KEY")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--run", action="store_true", help="Agent mit Browser-Use-LLM starten"
    )
    run(parser.parse_args().run)

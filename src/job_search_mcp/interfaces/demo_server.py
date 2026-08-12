"""Startet die Unterrichts-Sandbox kontrolliert fuer ein MVP."""

from __future__ import annotations

import socket
from contextlib import AbstractContextManager
from threading import Event, Thread

import uvicorn

from job_search_mcp.interfaces.demo_app import app


class DemoServer(AbstractContextManager["DemoServer"]):
    """Uvicorn in einem Thread, mit explizitem Ready- und Shutdown-Zustand."""

    def __init__(self) -> None:
        self.host = "127.0.0.1"
        self.port = self._free_port()
        self.base_url = f"http://{self.host}:{self.port}"
        self._server = uvicorn.Server(
            uvicorn.Config(app, host=self.host, port=self.port, log_level="error")
        )
        self._thread = Thread(
            target=self._server.run, name="job-search-demo", daemon=True
        )

    @staticmethod
    def _free_port() -> int:
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            return int(listener.getsockname()[1])

    def __enter__(self) -> DemoServer:
        self._thread.start()
        wakeup = Event()
        while not self._server.started:
            if not self._thread.is_alive():
                raise RuntimeError("Der lokale Demo-Server konnte nicht starten")
            wakeup.wait(0.01)
        return self

    def __exit__(self, *args: object) -> None:
        self._server.should_exit = True
        self._thread.join(timeout=5)
        if self._thread.is_alive():
            raise RuntimeError("Der lokale Demo-Server konnte nicht sauber stoppen")

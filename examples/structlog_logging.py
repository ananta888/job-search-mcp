"""Structlog-MVP: maschinenlesbares Ereignis statt Print-Log."""

import structlog


def run() -> None:
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(sort_keys=True),
        ]
    )
    logger = structlog.get_logger()
    logger.info("replay_allowed", target="local-demo", status=200)


if __name__ == "__main__":
    run()

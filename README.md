# Job Search MCP

Installierbarer MCP-Server für eine regelkonforme Mehrportal-Jobsuche mit
OpenCode. Er verbindet die öffentliche StepStone-Suche mit den offiziellen
APIs beziehungsweise Feeds von Arbeitnow, Remotive und We Work Remotely.
Weitere Portale werden mit transparentem Zugangsstatus katalogisiert, ohne
gesperrte Dienste zu scrapen.

## Funktionen

- kombinierte Mehrportal-Suche mit isolierten Quellenausfällen
- öffentliche Suche ohne unnötigen Login
- sichtbarer Camoufox-Browser für optionale Konto-Funktionen und 2FA
- deterministisches Matching gegen ein JSON-Jobprofil
- Markdown-Berichte mit Original-Links
- Portal-Allowlist und verschlüsselte lokale Credentials
- OpenCode-Konfiguration und stdio-MCP-CLI

## Installation

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -m camoufox fetch
```

Tests und Qualitätsprüfungen:

```bash
.venv/bin/python -m unittest discover -s tests -t .
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m mypy
```

## Verwendung

Der MCP-Server ist über den installierten Einstiegspunkt verfügbar:

```bash
export ALLOW_EXTERNAL_PORTALS=1
.venv/bin/job-search-mcp
```

OpenCode verwendet denselben Einstieg über `.opencode/opencode.json`. Nach der
Installation genügt daher:

```bash
export ALLOW_EXTERNAL_PORTALS=1
opencode
```

Das zentrale Werkzeug lautet:

```text
mehrportal_suche(query="backend", ort="nürnberg")
```

Ohne `portal_ids` werden StepStone, Arbeitnow, Remotive und We Work Remotely
abgefragt. Ein Fehler einer Quelle verwirft die übrigen Ergebnisse nicht.

## Repository-Struktur

```text
src/job_search_mcp/
├── domain/          # Jobmodelle und reine Matching-Regeln
├── application/     # Such-, Bewertungs- und Berichtsabläufe
├── infrastructure/  # Browser, Feeds, Credentials und Konfiguration
├── interfaces/      # MCP-Server, CLI und lokale Demo-API
└── resources/       # Profile, Portalkatalog und JSON-Schemas
tests/               # Unit-, Vertrags- und Integrationstests
examples/            # einzeln ausführbare Lernbeispiele
scripts/             # Repository-Hilfsskripte
docs/                # Architektur, Portale und ausführlicher Leitfaden
todos/               # versionierte Planung und Umsetzungsevidenz
reports/             # lokal erzeugte Berichte
```

Mehr Details stehen im [Leitfaden](docs/guide.md), in der
[Architekturbeschreibung](docs/architecture.md) und in der
[Portalübersicht](docs/portals.md). UML- und BPMN-Sichten liegen unter
[architecture/](architecture/README.md).

## Sicherheitsgrenzen

- Externe Läufe benötigen `ALLOW_EXTERNAL_PORTALS=1`.
- Indeed bleibt ohne eigene Autorisierung gesperrt.
- LinkedIn wird nur mit ausdrücklicher Crawling-Erlaubnis automatisiert.
- Instaffo bleibt ein interaktiver Matching-Workflow.
- Captchas, 2FA und Bot-Schutz werden nicht umgangen.
- Credentials und Browserzustände liegen außerhalb des Repositories im lokalen
  State-Verzeichnis.

## Lizenz

Dieses Projekt steht unter der [BSD-3-Clause-Lizenz](LICENSE). Abhängigkeiten
und übernommene Fremdkomponenten behalten ihre jeweiligen Lizenzen.

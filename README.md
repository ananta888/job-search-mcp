# Job Search MCP

Lokaler MCP-Server für eine regelkonforme Jobsuche mit OpenCode. Er verbindet
eine öffentliche StepStone-Browsersuche mit den offiziellen APIs beziehungsweise
Feeds von Arbeitnow, Remotive und We Work Remotely. Weitere Portale werden mit
transparentem Zugangsstatus katalogisiert, ohne gesperrte Dienste heimlich zu
scrapen.

## Funktionen

- Mehrportal-Suche mit isolierten Quellenausfällen
- öffentliche Suche ohne unnötigen Login
- sichtbarer, interaktiver Browser für optionale Konto-Funktionen
- deterministisches Matching gegen ein JSON-Jobprofil
- Markdown-Berichte mit Original-Links
- Portal-Allowlist, verschlüsselte lokale Credentials und externer Zugriff nur
  nach expliziter Freigabe

## Schnellstart

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r unterricht/unterricht/requirements-dev.txt
.venv/bin/python -m camoufox fetch
cd unterricht
export ALLOW_EXTERNAL_PORTALS=1
../.venv/bin/python -m unittest discover -s unterricht/tests -t .
../.venv/bin/python unterricht/job_search_mcp.py
```

Die vollständige Dokumentation, Architekturhinweise und Sicherheitsgrenzen
stehen in [unterricht/unterricht/README.md](unterricht/unterricht/README.md).

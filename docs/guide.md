# Leitfaden

## Lokaler Start

Das Projekt benötigt Python 3.12 oder neuer, aber kein Docker.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -m camoufox fetch
```

Die lokale Demo-API startet über den installierten CLI-Einstieg:

```bash
.venv/bin/job-search-demo
```

Danach sind die Oberfläche unter <http://127.0.0.1:8765> und die API-Doku
unter <http://127.0.0.1:8765/docs> erreichbar.

## MCP mit OpenCode

Die Root-Konfiguration `.opencode/opencode.json` startet bevorzugt den
installierten Einstieg `.venv/bin/job-search-mcp`. Als Fallback kann sie das
Paket mit `PYTHONPATH=src` direkt aus dem Checkout starten.

```bash
export ALLOW_EXTERNAL_PORTALS=1
opencode mcp list
opencode
```

Empfohlener Ablauf im Job-Agenten:

1. `liste_portale` zeigt Zugangsart, Aktivierungs- und Erlaubnisstatus.
2. `mehrportal_suche(query=..., ort=...)` fragt alle aktiven Quellen ab.
3. `bewerte_angebote` bewertet Rohangebote gegen das Profil.
4. `erstelle_bericht` schreibt einen Markdown-Bericht nach `reports/`.

Für eine einzelne Quelle dient `portal_suche(portal_id=...)`. Eine
profilbasierte Suche mit Bericht ist über `portal_recherche` möglich.

## Aktive Quellen

| Quelle | Zugriff | Login für öffentliche Suche |
|---|---|---|
| StepStone | sichtbarer/headless Camoufox-Browser | nein |
| Arbeitnow | öffentliche JSON-API | nein |
| Remotive | öffentliche JSON-API | nein |
| We Work Remotely | öffentlicher RSS-Feed | nein |

Remotive und We Work Remotely verlangen Attribution und unveränderte
Original-Links. Indeed wird ohne eigene Autorisierung nicht automatisiert;
LinkedIn benötigt eine ausdrückliche Crawl-Erlaubnis. Instaffo wird als
interaktiver Matching-Workflow katalogisiert.

## Optionaler sichtbarer Login

Ein Login ist nur für kontogebundene Portal-Funktionen erforderlich:

```text
browser_status(portal_id="stepstone")
portal_login(portal_id="stepstone", sichtbar=true, auto=false)
```

Unter WSL verwendet Camoufox WSLg. Nach Login und möglicher 2FA bestätigt der
Nutzer im grünen Browserpanel **„Anmeldung abgeschlossen – Sitzung
speichern“**. Zugangsdaten werden nicht im Chat abgefragt und nicht geloggt.
Mit `portal_sitzung_loeschen` und `anmeldedaten_entfernen` lassen sich lokale
Daten wieder entfernen.

## Profile und Ressourcen

Gebündelte Standardressourcen liegen unter
`src/job_search_mcp/resources/`:

- `profiles/job-profile.json`: Standard-Jobsuchprofil
- `profiles/portal-catalog.yaml`: fachlicher Katalog mit 20 Portalen
- `profiles/portals/*.yaml`: ausführbare Portaladapter und Allowlisten
- `schemas/*.json`: Antwort- und Profilverträge

Ein eigenes Profil kann als absoluter oder relativer Pfad an die MCP-Werkzeuge
übergeben werden. Der Name `job-profile.json` löst auf das gebündelte
Standardprofil auf.

## Berichte und lokaler Zustand

Berichte werden standardmäßig in `reports/` relativ zum aktuellen
Arbeitsverzeichnis geschrieben. `JOB_MCP_REPORT_DIR` überschreibt das Ziel.

Credentials und Browserzustände liegen außerhalb des Repositories unter dem
XDG-State-Verzeichnis beziehungsweise `~/.local/state/job-search-mcp`.
`JOB_MCP_STATE_DIR` erlaubt ein anderes Verzeichnis. Credentials werden mit
Fernet verschlüsselt und Dateien restriktiv berechtigt.

## Beispiele

Die kleinen, einzeln ausführbaren Beispiele liegen in `examples/`:

```bash
.venv/bin/python -m examples.yaml_config
.venv/bin/python -m examples.job_matching
.venv/bin/python -m examples.playwright_ui
.venv/bin/python -m examples.stepstone_calib
```

Alle lokalen Kernbeispiele laufen nacheinander über:

```bash
.venv/bin/python scripts/run_examples.py
```

Der StepStone-Kalibrierer bleibt standardmäßig ein Dry-Run. Nur mit `--run`
öffnet er die öffentliche Seite; er loggt sich nicht ein und umgeht keinen
Bot-Schutz.

## Qualitätssicherung

```bash
.venv/bin/python -m unittest discover -s tests -t .
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m mypy
.venv/bin/python -m build
.venv/bin/python -m pip check
```

Die GitHub-Actions-Workflowdatei `.github/workflows/ci.yml` führt Tests,
Ruff, Mypy und Paket-Build bei Pull Requests aus.

## Sicherheitsmodell

- Externe Netzwerkzugriffe benötigen `ALLOW_EXTERNAL_PORTALS=1`.
- Jeder Feed-Endpunkt und Browserpfad wird gegen eine Portal-Allowlist geprüft.
- Browser Use erhält niemals Portalpasswörter.
- Browserkontexte werden isoliert geöffnet und deterministisch geschlossen.
- Captchas, 2FA und technische Zugriffssperren werden nicht umgangen.
- Öffentliche APIs und Feeds werden gegenüber volatilen Seitenselektoren
  bevorzugt.

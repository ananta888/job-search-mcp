# Ananta Webcrawler – Unterrichtslabor

Dieses Verzeichnis ist der kompakte Einstieg für den Unterricht. Die Kernbeispiele laufen gegen
eine lokale FastAPI-Sandbox. Als externe Vertiefung stehen StepStone sowie ausdrücklich angebotene
Job-APIs und RSS-Feeds bereit; alle externen Zugriffe bleiben separat freizugeben. Docker ist nicht
erforderlich. Die große Implementierung unter `src/` bleibt nur als weiterführende Referenz.

Die Arbeits- und Architekturregeln stehen in [`AGENTS.md`](AGENTS.md). Planung und Fortschritt
werden über die versionierten Artefakte unter [`todos/`](todos/) geführt: neue Vorhaben liegen in
`feature/`, begonnene Arbeiten in `active/` und verifizierte Abschlüsse in `archiv/`.

## Schnellstart

Im äußeren Arbeitsordner (dort, wo `.opencode/` und `.venv/` liegen):

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r unterricht/unterricht/requirements-dev.txt
.venv/bin/python -m camoufox fetch
cd unterricht
../.venv/bin/python -m unterricht.run_all
```

Der letzte Befehl führt vierzehn lokale Kern-MVPs aus. Alternativ kann die Sandbox sichtbar
gestartet werden:

```bash
.venv/bin/python -m unterricht.demo_app
```

Danach sind die Demo-Oberfläche unter <http://127.0.0.1:8765> und die automatisch erzeugte
API-Dokumentation unter <http://127.0.0.1:8765/docs> erreichbar.

## Werkzeugübersicht

| Werkzeug | Wofür es im Projekt dient | Kleinstes ausführbares MVP |
|---|---|---|
| Python 3.11+ | gemeinsame Laufzeit | `python -m unterricht.run_all` |
| PyYAML | lesbare Website- und Policy-Konfiguration | `python -m unterricht.mvps.yaml_config` |
| Pydantic | Eingaben und Konfiguration typisiert validieren | `python -m unterricht.mvps.pydantic_validation` |
| FastAPI | lokale JSON-API und Lehr-Oberfläche | `python -m unterricht.demo_app` |
| Uvicorn | ASGI-Server für FastAPI | `python -m unterricht.demo_app` |
| Watchfiles | automatischer Neustart beim Entwickeln | `python -m uvicorn unterricht.demo_app:app --reload --port 8765` |
| HTTPX | entdeckte API-Anfrage direkt ausführen | `python -m unterricht.mvps.httpx_client` |
| Playwright | Browser mit `fill → click → read` steuern | `python -m unterricht.mvps.playwright_ui` |
| Chrome DevTools Protocol | Browser intern per CDP ansprechen | `python -m unterricht.mvps.cdp_session` |
| Jinja2 | serverseitiges HTML rendern | `python -m unterricht.mvps.jinja2_template` |
| python-multipart | Formulardaten in FastAPI verarbeiten | `python -m unterricht.mvps.multipart_form` |
| JSON Schema | Replay-Antwort strukturell prüfen | `python -m unterricht.mvps.jsonschema_validation` |
| Cryptography/Fernet | Secrets verschlüsseln, ohne sie zu protokollieren | `python -m unterricht.mvps.fernet_crypto` |
| Structlog | auditierbare strukturierte Ereignisse schreiben | `python -m unterricht.mvps.structlog_logging` |
| Browser Use (optional) | natürlichsprachige Browser-Aufgabe durch einen Agenten | `python -m unterricht.mvps.browser_use_agent` |
| Selenium (optional) | Vergleich einer zweiten Browser-Automation | `python -m unterricht.mvps.selenium_browser` |
| Camoufox (optional) | Anti-Detect-Firefox als Playwright-Drop-in für echte Portal-Läufe | `python -m unterricht.mvps.camoufox_browser` |
| Unittest | Verhalten automatisch prüfen | `python -m unittest discover -s unterricht/tests -t .` |
| Ruff | Stil- und Fehlerprüfung | `python -m ruff check unterricht` |
| Mypy + types-PyYAML | statische Typprüfung einschließlich YAML-Stubs | `python -m mypy unterricht` |
| MCP (Python SDK) | Login, Sitzung und Jobsuche für OpenCode bereitstellen | `python unterricht/job_search_mcp.py` |
| Job-Matching | Angebote deterministisch gegen ein Profil bewerten | `python -m unterricht.mvps.job_matching` |
| GitHub Actions | dieselben MVPs in CI ausführen | [`.github/workflows/teaching-mvps.yml`](../.github/workflows/teaching-mvps.yml) |

Alle Modulbefehle in der Tabelle werden aus dem inneren Projektordner
`unterricht/` mit aktivierter virtueller Umgebung ausgeführt. Ohne Aktivierung
einfach `../.venv/bin/` vor `python` setzen.

## Möglichkeiten als kleine Lernkette

| Schritt | Beobachtbare Möglichkeit | Datei/MVP |
|---:|---|---|
| 1 | Website-Verhalten über Selektoren konfigurieren | [`profiles/local-demo.yaml`](profiles/local-demo.yaml) |
| 2 | UI öffnen, Eingabe setzen, Aktion auslösen, Ausgabe lesen | `mvps/playwright_ui.py` |
| 3 | genau die durch den Klick ausgelöste Anfrage erfassen | `discovery.py` |
| 4 | volatile Browser-Header verwerfen | `normalization.py` |
| 5 | Host und Pfad gegen eine Allowlist prüfen | `policy.py` |
| 6 | Anfrage ohne Browser per HTTPX wiederholen | `replay.py` |
| 7 | Antwort per Schema und Smart Diff validieren | `validation.py` |
| 8 | Cookie-Zustand explizit exportieren und wiederverwenden | `mvps/session_state.py` |
| 9 | alle Schritte zu einem sicheren Ablauf verbinden | `python -m unterricht.full_flow` |

Der Gesamtfluss zeigt absichtlich nicht „beliebige Requests automatisch ausführen“. Vor dem
Replay stehen Normalisierung und Policy-Prüfung; anschließend werden Struktur und funktionale
Gleichwertigkeit geprüft. Die volatilen Felder `request_id` und `meta.server_time` sind dafür im
Profil als Ignore-Pfade dokumentiert.

```text
lokale UI → Netzwerk-Capture → Normalisierung → Allowlist → HTTP-Replay → Validierung
```

## Optionale Vertiefungen

Browser Use ist in `requirements-job-search.txt` enthalten und dient nur als
experimenteller Fallback, wenn Camoufox scheitert. Es wird erst mit einer
expliziten LLM-Konfiguration aktiv:

```bash
export BROWSER_USE_API_KEY='...'
# alternativ: BROWSER_USE_BASE_URL + BROWSER_USE_MODEL oder OLLAMA_HOST + OLLAMA_MODEL
```

Der Fallback erhält den gespeicherten Browserzustand und die Portal-Allowlist,
aber keine Portalpasswörter. Ohne diese Variablen bleibt er deaktiviert.

Selenium dient nur als Vergleich zu Playwright und benötigt weder Grid noch Docker:

```bash
../.venv/bin/python -m unterricht.mvps.selenium_browser
```

Für den roten Faden ist Selenium nicht erforderlich. Playwright eignet sich hier besser, weil
UI-Automation und Netzwerkbeobachtung in einem Werkzeug zusammenkommen.

Camoufox ist ein Anti-Detect-Firefox, der im JOB-Agenten als austauschbare
Browser-Engine für echte Portal-Läufe dient (`job_browser.BrowserEngine`):

```bash
../.venv/bin/python -m camoufox fetch
../.venv/bin/python -m unterricht.mvps.camoufox_browser          # Dry-Run
../.venv/bin/python -m unterricht.mvps.camoufox_browser --run    # gegen 127.0.0.1
```

Der Dry-Run ist Standard. Der echte Lauf des MVPs findet ausschließlich gegen
die lokale Sandbox statt.

## JOB-Agent (Skills + MCP)

Ein JOB-Agent analysiert Firmen- und Vermittlungsportale und bewertet
Stellenangebote gegen ein vorgegebenes Bewerberprofil. Er kombiniert drei
Bestandteile:

| Bestandteil | Pfad | Rolle |
|---|---|---|
| opencode-Subagent | `.opencode/agent/job-agent.md` | JOB-Analyst, orchestriert die Analyse |
| Skill | `.opencode/skills/job-crawler/SKILL.md` | Workflow und Sicherheitsgrenzen |
| MCP-Server | `unterricht/job_search_mcp.py` | exponiert Login, Sitzung, Suche, Matching und Bericht |

Ablauf für echte Quellen: Portalstatus prüfen → eine einzelne Quelle mit
`portal_suche` oder alle aktiven Quellen mit `mehrportal_suche` abfragen →
Angebote gegen das Profil bewerten → Markdown-Bericht mit Original-Links
schreiben. Ein Konto-Login ist für die öffentliche StepStone-Trefferliste und
die offiziellen Feeds nicht nötig.

```bash
# kleines Matching-Beispiel ohne Netzwerk
python -m unterricht.mvps.job_matching

# vollständiger lokaler Flow gegen die Sandbox, schreibt berichte/job-report.md
python -m unterricht.job_flow

# MCP-Server als lokaler stdio-Server (wird von OpenCode automatisch gestartet)
python unterricht/job_search_mcp.py

# Tests des JOB-Agenten
python -m unittest discover -s unterricht/tests -t .
```

Der MCP-Server ist in der äußeren und inneren `.opencode/opencode.json`
registriert. Dadurch funktioniert der Start aus beiden Arbeitsordnern mit der
gemeinsamen virtuellen Umgebung und ohne Docker:

```json
{
  "mcp": {
    "job-crawler": {
      "type": "local",
      "command": [
        "bash",
        "-lc",
        "if [ -x .venv/bin/python ]; then exec .venv/bin/python unterricht/unterricht/job_search_mcp.py; else exec ../../.venv/bin/python job_search_mcp.py; fi"
      ],
      "enabled": true
    }
  }
}
```

Prüfen und starten:

```bash
opencode mcp list
export ALLOW_EXTERNAL_PORTALS=1
opencode
```

Im Agenten zuerst `liste_portale` aufrufen. Der Katalog trennt aktive Adapter
von manuellen, partnergebundenen, gesperrten und noch nicht angebundenen
Portalen. Eine gemeinsame Suche startet zum Beispiel so:

```text
mehrportal_suche(query="backend", ort="nürnberg")
```

Standardmäßig werden StepStone, Arbeitnow, Remotive und We Work Remotely
abgefragt; Fehler einer Quelle blockieren die übrigen Quellen nicht. Für eine
einzelne Quelle `portal_suche(portal_id="arbeitnow", query="backend")` oder
`portal_suche(portal_id="stepstone", query="informatiker", ort="nürnberg")`
verwenden. Nur vor einem optionalen StepStone-Login zusätzlich
`browser_status` prüfen. `portal_login` ist nur für kontogebundene Funktionen
nötig; ein optionaler Auto-Fill ist über `anmeldedaten_hinterlegen` möglich. Mit
`portal_sitzung_loeschen` und `anmeldedaten_entfernen` werden lokale Daten
wieder entfernt. Das Profil `profiles/job-suchprofil.json` wird gegen
`schemas/job-profil.schema.json` validiert.

Für kontogebundene Funktionen öffnet
`portal_login(portal_id="stepstone", sichtbar=true, auto=false)` Camoufox über
die lokale Desktop-Anzeige. Unter WSL wird WSLg verwendet; `browser_status`
meldet den erkannten Anzeigeweg. Nach dem Login im Browser den grünen Button
**„Anmeldung abgeschlossen – Sitzung speichern“** anklicken. Erst dann wird
der Browserzustand übernommen und das Fenster geschlossen. Fehlen
`DISPLAY`/Wayland, bricht das Tool vor dem Browserstart mit einer konkreten
WSLg-Anweisung ab.

Echte externe Portale benötigen weiterhin `ALLOW_EXTERNAL_PORTALS=1` und die
Freigabe im Portalprofil; der ältere Toolpfad `analysiere_echtes_portal` bleibt
standardmäßig ein Dry-Run. StepStone ist für Camoufox freigeschaltet. Login-URL,
Formularfelder, öffentliche Such-URL und Trefferkarten wurden am 2026-08-12
zugangsdatenfrei live kalibriert; ein echter Login wurde bewusst nicht ohne
Nutzerkonto ausgeführt. Der Kalibrierer
`python -m unterricht.mvps.stepstone_calib --run` gibt nur Selektormetadaten
und höchstens fünf Titel aus. Er umgeht keinen Bot-Schutz. Indeed bleibt ohne
eigene Autorisierung technisch deaktiviert; Details stehen in
`profiles/portals/README.md`.

Die Feed-Adapter nutzen nur offiziell veröffentlichte Lesewege:

- Arbeitnow: öffentliche JSON-API ohne API-Schlüssel
- Remotive: öffentliche JSON-API; Original-Link und Quellenname bleiben erhalten
- We Work Remotely: öffentlicher RSS-Feed; Original-Link und Quellenname bleiben erhalten

API/RSS-Antworten werden in `job_feeds.py` auf den vorhandenen
`JobAngebot`-Vertrag normalisiert. Suchbegriff und Ort werden zusätzlich lokal
gefiltert; Beschreibungen sind auf 2.000 Zeichen begrenzt, damit MCP-Antworten
beherrschbar bleiben. Remotive- und We-Work-Remotely-Ergebnisse müssen bei
Weiterverwendung weiterhin als solche attribuiert werden.

## Verzeichnisaufbau

```text
unterricht/
├── AGENTS.md         # Senior-Architekt: SOLID, TDD, DDD und Todo-Workflow
├── demo_app.py       # lokale FastAPI-Sandbox (inkl. Job-Portale unter /portal)
├── profiles/         # YAML: Selektoren, Policy, Validierung; JSON-Jobprofil; profiles/portals/
├── schemas/          # JSON-Schemas: Suchantwort, Portalantwort, Jobprofil
├── templates/        # kleinstes Jinja2-Beispiel
├── todos/            # Feature-, Aktiv- und Archiv-Planung mit JSON-Schemas
├── berichte/         # erzeugte Job-Berichte (Markdown)
├── .opencode/        # JOB-Agent: opencode.json, agent/, skills/
├── mvps/             # ein direkt startbares Beispiel je Werkzeug
├── discovery.py      # UI-Interaktion und gezielter Capture
├── normalization.py  # sichere Header-Auswahl
├── policy.py         # Replay-Allowlist
├── replay.py         # direkter HTTPX-Aufruf
├── validation.py     # Schema und Smart Diff
├── job_models.py     # Domänenmodelle: JobProfil, JobAngebot, JobMatch
├── job_profile.py    # Jobprofil laden und per JSON-Schema validieren
├── job_match.py      # deterministische Angebotsbewertung
├── job_portal.py     # Portal-Profile (Pydantic) laden
├── job_feeds.py      # offizielle JSON-/RSS-Quellen normalisieren
├── job_report.py     # Markdown-Bericht erzeugen
├── job_browser.py    # schmale Browser-Port: Playwright- und Camoufox-Engine
├── browser_session.py # Login, storage_state, Suche und browser-use-Fallback
├── credential_store.py # Fernet-verschlüsselte Portal-Anmeldedaten
├── job_flow.py       # Job-Flow: Suche → Policy → Validierung → Match → Report
├── job_agent_mcp.py  # MCP-Server mit Tools für den JOB-Agenten
├── job_search_mcp.py # OpenCode-MCP für Status, Login, Suche und Recherche
├── requirements-job-search.txt # reproduzierbare MCP-/Browser-Laufzeit
├── requirements-dev.txt # Laufzeit plus Ruff, Mypy und YAML-Typen
├── full_flow.py      # die vollständige Lernkette
└── run_all.py        # automatischer lokaler Rundgang
```

## Sicherheitsrahmen für den Unterricht

- Die Sandbox bindet ausschließlich an `127.0.0.1`.
- Portal-Anmeldedaten werden nur nach explizitem Tool-Aufruf angenommen, nie
  ausgegeben oder geloggt und als Fernet-Token mit Dateimodus `0600` abgelegt.
- State liegt standardmäßig außerhalb des Projekts unter
  `~/.local/state/unterricht-job-search` (Verzeichnis `0700`). Mit
  `JOB_MCP_STATE_DIR` kann der Ort geändert werden; mit
  `JOB_MCP_FERNET_KEY` kann der Schlüssel getrennt verwaltet werden. Ein lokal
  daneben gespeicherter Schlüssel schützt vor versehentlicher Einsicht, nicht
  vor einem bereits kompromittierten Benutzerkonto.
- Jeder Playwright-Lauf erzeugt und schließt einen isolierten `BrowserContext`.
- Der Replay-Guard erlaubt im MVP nur `localhost`/`127.0.0.1` und `/api/search`.
- StepStone verlangt zusätzlich `ALLOW_EXTERNAL_PORTALS=1`; seine öffentliche
  Suche funktioniert ohne Session. Gespeicherte Cookies werden nur an die
  Host-Allowlist des Portals weitergegeben.
- Feed-Endpunkte werden vor jeder Anfrage gegen dieselbe Host-/Pfad-Allowlist
  geprüft. Indeed und LinkedIn werden ohne eigene Autorisierung nicht
  gecrawlt; Instaffo bleibt ein interaktiver Matching-Workflow.
- Browser Use bekommt keine Portalpasswörter und ist ohne LLM-Konfiguration aus.
- Browser-Header wie Cookies und `Sec-Fetch-*` werden nicht blind übernommen.
- Docker ist für keinen Unterrichtsbefehl vorgesehen oder erforderlich.

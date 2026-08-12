# Architektur

Das Repository verwendet ein Python-`src`-Layout. Dadurch wird in Entwicklung
und Installation immer dasselbe Paket importiert; versehentliche Importe aus
dem Arbeitsverzeichnis werden vermieden.

```text
OpenCode / CLI
      │
      ▼
interfaces ─────► application ─────► domain
      │                 ▲
      └────► infrastructure ────────┘
```

- `domain`: unveränderliche Jobmodelle, Matching und reine Normalisierung
- `application`: Such-, Bewertungs- und Berichtsabläufe
- `infrastructure`: Browser, Feeds, Credentials, Policies und Konfiguration
- `interfaces`: MCP-Server, CLI und lokale Demo-API
- `resources`: gebündelte Standardprofile, Portalkatalog und JSON-Schemas

Veränderliche Daten gehören nicht in das installierte Paket. Sitzungen und
Credentials liegen im XDG-State-Verzeichnis; Berichte werden nach `reports/`
oder in `JOB_MCP_REPORT_DIR` geschrieben.

## Entscheidung

Die frühere doppelte Verzeichnisstruktur `unterricht/unterricht` wurde nicht
abgeflacht, sondern durch ein installierbares Paket ersetzt. Eine vollständig
flache Modulsammlung wäre beim aktuellen Umfang schwer navigierbar; noch mehr
Schichten oder abstrakte Repositories hätten dagegen keinen zusätzlichen
fachlichen Nutzen.

Ausführliche Komponenten-, Klassen-, Sequenz- und BPMN-Diagramme stehen in der
[Diagrammübersicht](../architecture/README.md).

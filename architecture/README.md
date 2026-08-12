# Architekturdiagramme

Dieser Ordner beschreibt die aktuelle Architektur des Job-Search-MCP. Die
Diagramme sind bewusst nah an den vorhandenen Modulen, Klassen und
MCP-Werkzeugen gehalten.

| Sicht | Format | Datei |
|---|---|---|
| Komponenten und Abhängigkeiten | UML-orientiertes Mermaid-Flowchart | [01-komponenten.md](01-komponenten.md) |
| Domänen-, Konfigurations- und Browserklassen | Mermaid `classDiagram` | [02-klassenmodell.md](02-klassenmodell.md) |
| Ablauf von `mehrportal_suche` | Mermaid `sequenceDiagram` | [03-sequenz-mehrportal-suche.md](03-sequenz-mehrportal-suche.md) |
| Fachlicher End-to-End-Prozess | BPMN-orientiertes Mermaid-Flowchart | [04-bpmn-job-recherche.md](04-bpmn-job-recherche.md) |
| Austauschbares BPMN-2.0-Modell | BPMN XML | [job-recherche.bpmn](job-recherche.bpmn) |

GitHub rendert die Mermaid-Blöcke direkt in den Markdown-Dateien. Das
`job-recherche.bpmn`-Modell kann beispielsweise mit bpmn.io, Camunda Modeler
oder einem anderen BPMN-2.0-kompatiblen Werkzeug geöffnet werden.

## Systemgrenzen

- OpenCode kommuniziert per stdio/MCP mit dem lokalen Server.
- Externe Portale liegen hinter Allowlist, Portalprofil und expliziter
  Freigabe durch `ALLOW_EXTERNAL_PORTALS=1`.
- Öffentliche APIs und RSS-Feeds benötigen keinen Login.
- Ein sichtbarer Login bleibt eine Nutzeraufgabe; 2FA, Captchas und andere
  Schutzmechanismen werden nicht automatisiert umgangen.
- Credentials und Browserzustände liegen außerhalb des Repositories.
- Generierte Berichte liegen unter `reports/` oder in `JOB_MCP_REPORT_DIR`.

## Pflege

Bei Änderungen an MCP-Werkzeugen, Schichtgrenzen, Portalzugriffen oder dem
Login-Ablauf müssen die betroffenen Diagramme gemeinsam mit Code und Tests
aktualisiert werden.

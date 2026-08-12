# UML-Komponentendiagramm

Die Komponentensicht zeigt Laufzeitgrenzen und die beabsichtigte
Abhängigkeitsrichtung. Pfeile bedeuten „verwendet“; gestrichelte Pfeile stehen
für Datei- beziehungsweise Ressourcenzugriffe.

```mermaid
flowchart LR
    User["Nutzer"] --> OpenCode["OpenCode<br/>Job-Agent"]

    subgraph Local["Lokaler Prozess"]
        MCP["«component»<br/>MCP-Interface<br/>interfaces/mcp_server.py"]

        subgraph App["Application"]
            Search["«component»<br/>Job- und Portal-Flows"]
            Report["«component»<br/>Reporting"]
        end

        subgraph Domain["Domain"]
            Models["«component»<br/>Job- und Crawler-Modelle"]
            Match["«component»<br/>Matching"]
            Normalize["«component»<br/>Normalisierung"]
        end

        subgraph Infra["Infrastructure"]
            Config["«component»<br/>Profil- und Portal-Konfiguration"]
            Feed["«adapter»<br/>API- und RSS-Feeds"]
            Browser["«adapter»<br/>Browser Session Manager"]
            Credentials["«adapter»<br/>Credential Store"]
            Guard["«component»<br/>Policy und Validierung"]
        end
    end

    subgraph LocalData["Lokale Daten"]
        Resources[("Paketressourcen<br/>Profile, YAML, Schemas")]
        State[("XDG State<br/>Credentials, Sessions")]
        Reports[("reports/<br/>Markdown-Berichte")]
    end

    subgraph External["Externe Systeme"]
        PublicFeeds["Arbeitnow API<br/>Remotive API<br/>WWR RSS"]
        BrowserPortals["StepStone<br/>weitere erlaubte Portale"]
    end

    OpenCode -->|"stdio / MCP"| MCP
    MCP --> Search
    MCP --> Match
    MCP --> Report
    MCP --> Config
    MCP --> Feed
    MCP --> Browser

    Search --> Models
    Search --> Match
    Search --> Guard
    Report --> Models
    Match --> Models
    Normalize --> Models

    Feed --> Guard
    Browser --> Guard
    Browser --> Credentials
    Config -.-> Resources
    Credentials -.-> State
    Browser -.-> State
    Report -.-> Reports

    Feed -->|"HTTPS"| PublicFeeds
    Browser -->|"Playwright / Camoufox"| BrowserPortals

    classDef boundary fill:#eef4ff,stroke:#315a9e,color:#10233f;
    classDef core fill:#eefaf1,stroke:#2f7d4a,color:#12351f;
    classDef adapter fill:#fff6e6,stroke:#a76700,color:#4d3000;
    classDef data fill:#f6efff,stroke:#7447a8,color:#2f174c;
    class MCP,OpenCode boundary;
    class Search,Report,Models,Match,Normalize core;
    class Config,Feed,Browser,Credentials,Guard adapter;
    class Resources,State,Reports data;
```

## Zentrale Regeln

- Die Domäne importiert keine Browser-, HTTP-, FastAPI- oder MCP-Frameworks.
- Interfaces orchestrieren Anwendungsfälle und Infrastrukturadapter.
- Portalzugriffe werden über Konfiguration und Policy begrenzt.
- Veränderlicher Zustand wird nicht in Paketressourcen geschrieben.

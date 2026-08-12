# UML-Klassendiagramm

Das Diagramm konzentriert sich auf die tatsächlich vorhandenen Domänenmodelle,
Portalprofile und austauschbaren Browserimplementierungen. Funktionale
Anwendungsfälle wie `mehrportal_suche` bleiben Funktionen und werden nicht als
künstliche Klassen dargestellt.

```mermaid
classDiagram
    direction LR

    class JobProfil {
        +str name
        +tuple~str~ suchbegriffe
        +frozenset~str~ skills_pflicht
        +frozenset~str~ skills_wunsch
        +tuple~str~ orte
        +tuple~str~ arbeitsmodelle
        +int gehalt_min
        +int gehalt_max
    }

    class JobAngebot {
        +str id
        +str portal
        +str firma
        +str titel
        +str ort
        +str arbeitsmodell
        +frozenset~str~ skills
        +str beschreibung
    }

    class JobMatch {
        +JobAngebot angebot
        +int score
        +bool passt
        +tuple~str~ gefundene_skills
        +tuple~str~ fehlende_pflicht_skills
        +tuple~str~ gruende
    }

    class PortalProfil {
        +str portal_id
        +str name
        +str kind
        +str base_url
        +bool enabled
        +bool erlaubt
        +str browser
        +str suchart
    }

    class PortalLogin {
        +str url
        +str username_selector
        +str password_selector
        +str success_selector
    }

    class PortalSuche {
        +str url_template
        +bool login_erforderlich
        +str card_selector
    }

    class PortalFeed {
        +str adapter
        +str endpoint
        +str attribution
    }

    class PortalPolicy {
        +list~str~ allowed_hosts
        +list~str~ allowed_path_prefixes
    }

    class PortalValidation {
        +str schema_file
    }

    class BrowserEngine {
        <<abstract>>
        +suche_ui(base_url, selectors, query, headless) str
    }

    class PlaywrightChromiumEngine {
        +suche_ui(base_url, selectors, query, headless) str
    }

    class CamoufoxEngine {
        +suche_ui(base_url, selectors, query, headless) str
    }

    class BrowserSessionManager {
        +anmelden(portal, sichtbar) dict
        +login_interaktiv(portal, sichtbar) dict
        +suche_mit_fallback(portal, query, anmerkung, ort) list
        +sitzung_vorhanden(portal_id) bool
        +sitzung_loeschen(portal_id) bool
    }

    class BrowserUseTreiber {
        +suchen(portal, query, storage_state, anmerkung, ort) list
    }

    class CredentialStore {
        +speichere(portal_id, username, password)
        +lade(portal_id) PortalCredential
        +entferne(portal_id) bool
    }

    class PortalCredential {
        +str username
        +str password
    }

    JobMatch *-- JobAngebot : bewertet
    JobProfil ..> JobAngebot : Auswahlregeln
    JobProfil ..> JobMatch : Matching erzeugt

    PortalProfil *-- PortalLogin : optional
    PortalProfil *-- PortalSuche : optional
    PortalProfil *-- PortalFeed : optional
    PortalProfil *-- PortalPolicy
    PortalProfil *-- PortalValidation

    BrowserEngine <|-- PlaywrightChromiumEngine
    BrowserEngine <|-- CamoufoxEngine
    BrowserSessionManager --> PortalProfil : verwendet
    BrowserSessionManager --> CredentialStore : verwaltet Login
    BrowserSessionManager --> BrowserUseTreiber : optionaler Fallback
    CredentialStore --> PortalCredential : verschlüsselt
```

## Invarianten

- `JobProfil`, `JobAngebot`, `JobMatch` und `PortalCredential` sind immutable
  Dataclasses.
- Ein `PortalProfil` hat entweder eine Feed-Konfiguration oder einen
  Browser-Suchpfad.
- Ein gespeicherter Loginzustand ist optional; die öffentliche Suche darf ihn
  nicht unnötig voraussetzen.
- `BrowserEngine` hält die Anwendung von Playwright beziehungsweise Camoufox
  unabhängig.

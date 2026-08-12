# UML-Sequenzdiagramm: Mehrportal-Suche

Der aktuelle Aggregator verarbeitet die ausgewählten Portale bewusst
nacheinander. Ein Fehler wird je Quelle erfasst und verhindert nicht die
Verarbeitung der folgenden Portale.

```mermaid
sequenceDiagram
    autonumber
    actor User as Nutzer
    participant OC as OpenCode
    participant MCP as MCP-Interface
    participant Profile as Profile Repository
    participant Config as Portal Config
    participant Feed as Feed Adapter
    participant Browser as Browser Session Manager
    participant Portal as Externes Portal

    User->>OC: Mehrportal-Suche anfordern
    OC->>MCP: mehrportal_suche(query, ort, portal_ids?)
    MCP->>Profile: lade_profil(profil_pfad)
    Profile-->>MCP: validiertes JobProfil

    alt keine portal_ids angegeben
        MCP->>Config: lade_portale()
        Config-->>MCP: aktive Browser- und Feed-Profile
    end

    loop für jedes eindeutige Portal
        MCP->>Config: Portalprofil und Freigabe prüfen
        Config-->>MCP: PortalProfil

        alt Feed-Portal
            MCP->>Feed: suche_feed(portal, query, ort)
            Feed->>Portal: HTTPS API/RSS
            Portal-->>Feed: JSON oder XML
            Feed-->>MCP: normalisierte Rohangebote
        else Browser-Portal
            MCP->>Browser: suche_mit_fallback(portal, query, ort)
            Browser->>Portal: Playwright/Camoufox-Suche
            Portal-->>Browser: Trefferkarten
            Browser-->>MCP: normalisierte Rohangebote
        end

        alt Quelle erfolgreich
            MCP->>MCP: in JobAngebot umwandeln
            MCP->>MCP: Treffer und Quellenstatus ergänzen
        else beliebiger Quellenfehler
            MCP->>MCP: Fehler nur für diese Quelle protokollieren
        end
    end

    MCP-->>OC: Angebote plus Status je Quelle
    OC-->>User: Teilergebnis transparent anzeigen

    opt Bewertung und Bericht gewünscht
        OC->>MCP: bewerte_angebote(angebote)
        MCP-->>OC: sortierte JobMatches
        OC->>MCP: erstelle_bericht(angebote, quellen)
        MCP-->>OC: Pfad des Markdown-Berichts
        OC-->>User: Matches und Bericht
    end
```

## Fehlersemantik

- Profil- und Eingabefehler beenden den gesamten Aufruf.
- Ein nicht freigegebenes, unbekanntes oder vorübergehend fehlerhaftes Portal
  wird als Quellenfehler zurückgegeben.
- Bereits erfolgreiche Quellen bleiben im Resultat erhalten.

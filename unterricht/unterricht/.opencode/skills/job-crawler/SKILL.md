---
name: job-crawler
description: >-
  Workflow für den JOB-Agenten: Jobportale und Firmen-Karriereseiten mit dem
  Unterrichts-Webcrawler analysieren, Angebote gegen ein Jobprofil bewerten und
  einen Markdown-Bericht erzeugen. Verwende diesen Skill, wenn es um Job,
  Stellen, Karriere, Bewerbung, Firmenanalyse oder Stellenangebote geht und die
  MCP-Tools job-crawler verfügbar sind. Berücksichtige die AGENTS.md
  Sicherheitsgrenzen (lokal zuerst, echte Portale nur gated).
---

# job-crawler

Workflow für die Analyse von Job- und Vermittlungsportalen mit dem lokalen
Webcrawler des Unterrichtslabors. Die Lernkette des Projekts lautet:

```text
UI → Capture → Normalisierung → Policy → Replay → Validierung → Matching
```

Für lokale JSON-Portale sind Discovery und Capture im `job-crawler`-MCP-Server
zusammengefasst; die Sicherheitsstufen (Policy, Validierung) laufen trotzdem
immer mit.

## Schritt 1 – Profil laden

Lies das Jobprofil mit dem MCP-Tool `lade_profil`. Standarddatei:
`profiles/job-suchprofil.json`. Das Profil wird gegen
`schemas/job-profil.schema.json` validiert. Felder: `suchbegriffe`,
`skills_pflicht`, `skills_wunsch`, `orte`, `arbeitsmodelle`, `gehalt_min`,
`gehalt_max`, `sprachen`, `min_erfahrung_jahre`.

## Schritt 2 – Portale und Browser prüfen

Rufe `liste_portale` auf. Beachte neben `erlaubt` auch `status` und
`zugangsart`: Nur aktive Adapter dürfen automatisiert laufen. Lokale Portale
(`kind: local`) sind standardmäßig erlaubt; echte Portale benötigen
`enabled: true`, `ALLOW_EXTERNAL_PORTALS=1` und die explizite Nutzerfreigabe.
Rufe `browser_status` nur für Browserportale auf. Öffentliche APIs und RSS-Feeds
benötigen weder Browser noch Sitzung.

## Schritt 3 – Angebote sammeln

Rufe `suche_angebote` auf. Der Server crawlt alle erlaubten lokalen Portale
gegen die jeweilige Policy-Allowlist und validiert jede Antwort gegen das
Portal-Schema (`schemas/job-portal-response.schema.json`). Ergebnisse werden
bereits per `suchbegriffe` des Profils gefiltert.

Für echte Quellen rufe bevorzugt `mehrportal_suche(query=..., ort=...)` auf.
Ohne `portal_ids` fragt sie StepStone, Arbeitnow, Remotive und We Work Remotely
ab; ein Quellenausfall blockiert die übrigen Resultate nicht. Nutze
`portal_suche(portal_id=...)` für eine gezielte Einzelabfrage. Arbeitnow,
Remotive und We Work Remotely laufen über offiziell angebotene APIs/Feeds.
Erhalte bei Remotive und We Work Remotely immer Portalname und Original-Link.

## Schritt 4 – Bewerten

Rufe `bewerte_angebote` mit den gesammelten Angeboten auf. Die Bewertung ist
deterministisch:

- Pflicht-Skills sind ein Ausschlusskriterium (Präfix-Worttreffer zählen,
  z. B. `spring` → `spring boot`).
- Sprachen und Erfahrungsjahre sind weitere Ausschlusskriterien.
- Wunsch-Skills, Ort, Arbeitsmodell und Gehalt beeinflussen den Score (0–100).

## Schritt 5 – Bericht erzeugen

Rufe `erstelle_bericht` auf. Er schreibt den Bericht nach
`berichte/job-report.md` und liefert den Pfad zurück. Abschnitte: Profil,
Zusammenfassung, passende Angebote (nach Score sortiert) und ausgeschlossene
Angebote mit Gründen.

## Schritt 6 – Ergebnis fassen

Gib dem Nutzer eine kurze Zusammenfassung: Anzahl passender/ausgeschlossener
Angebote, Top-Treffer mit Score und Begründung, Quellen und Berichtspfad.
Kennzeichne unbelegte Aussagen als Vermutung.

## Verwaltete StepStone-Sitzung

Für StepStone verwende den neueren browserbasierten Pfad:

1. `browser_status(portal_id="stepstone")` prüfen. Für die öffentliche Suche
   ist `sitzung_vorhanden=false` kein Blocker, wenn
   `login_fuer_suche_erforderlich=false` gemeldet wird.
2. Direkt `portal_suche` mit getrenntem Suchbegriff und Ort aufrufen, zum
   Beispiel `query="informatiker", ort="nürnberg"`. Für eine profilbasierte
   Mehrfachsuche `portal_recherche(..., ort="nürnberg")` verwenden.
3. Nur für kontogebundene Funktionen `portal_login` starten. In einer
   headless Umgebung keinen sichtbaren Login erzwingen. Wenn `browser_status`
   den sichtbaren Browser als verfügbar meldet, `sichtbar=true, auto=false`
   verwenden. Der Nutzer loggt sich im tatsächlich verwendeten Camoufox ein
   und klickt danach im grünen Übergabe-Panel auf **„Anmeldung abgeschlossen –
   Sitzung speichern“**. Bei 2FA/Captcha immer diesen interaktiven Weg nutzen.
4. Nur wenn der Nutzer Auto-Fill ausdrücklich wünscht:
   `anmeldedaten_hinterlegen` einmalig aufrufen und danach `portal_login` mit
   `auto=true`. Passwörter niemals wiederholen, zusammenfassen oder in einen
   Bericht übernehmen.
5. Auf Wunsch `portal_sitzung_loeschen` und `anmeldedaten_entfernen` ausführen.

Camoufox ist primär. Der browser-use-Fallback ist nur bei expliziter
LLM-Konfiguration verfügbar und erhält gespeicherten Browserzustand, Suchtext
und Host-Allowlist, niemals Portalpasswörter.

## Echte Portale (optional, gated)

- Nur `kind: real` + `enabled: true` + `ALLOW_EXTERNAL_PORTALS=1` + explizite
  Nutzerfreigabe.
- Standard ist Dry-Run: `analysiere_echtes_portal` beschreibt den geplanten
  Lauf ohne Netzwerkzugriff.
- Die Browser-Engine kommt aus dem Portal-Profil (`browser: playwright|camoufox`);
  Camoufox ist ein Anti-Detect-Firefox als Playwright-Drop-in. Ein echter Lauf
  mit Camoufox verlangt `pip install -U camoufox` + `camoufox fetch`.
- StepStone ist per expliziter Nutzerfreigabe (2026-08-12) auf
  `browser: camoufox` freigeschaltet. Login-Formular, öffentliche Such-URL und
  Ergebniskarten wurden an diesem Tag zugangsdatenfrei live kalibriert. Der
  Login-Erfolgsindikator ist ohne Nutzerkonto noch nicht live bestätigt.
  Indeed bleibt deaktiviert ohne `selectors` und damit technisch blockiert.
  LinkedIn benötigt eine ausdrückliche Crawl-Erlaubnis; Instaffo bleibt wegen
  seines kontobasierten Matchings ein manueller Workflow.
- Respektiere ToS und `robots.txt`; die öffentliche Suche verwendet genau den
  erlaubten Pfad `/jobs/in-deutschland?q=…` ohne weitere Query-Parameter.
- Erwarte nicht-deterministische Seiten und teile das dem Nutzer mit.

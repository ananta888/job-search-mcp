# Portal-Profile

Jede YAML-Datei unter `src/job_search_mcp/resources/profiles/portals/` ist ein
validiertes `PortalProfil`.

- `kind: local` -> Sandbox-Portal (`demo_app.py`), standardmaessig `enabled: true`.
- `kind: real` -> echtes externes Portal, standardmaessig `enabled: false` und nur per
  `ALLOW_EXTERNAL_PORTALS=1` sowie expliziter Freigabe ueberhaupt erreichbar
  (siehe `job_flow.crawl_erlaubt` / `job_flow.crawle_echtes_portal`).

Aktuelle ausführbare externe Profile sind StepStone sowie die drei offiziellen
Feed-Quellen Arbeitnow, Remotive und We Work Remotely. `beispiel-karriere.yaml`
bleibt fiktiv; `indeed.yaml` bleibt als bewusst gesperrter Grenzfall erhalten.

- `indeed.yaml` enthaelt absichtlich keine `selectors`: Indeeds AGB untersagen
  automatisiertes Auslesen; ein echter Lauf bleibt dadurch auch bei voller
  Freigabe technisch blockiert, bis eine eigene Autorisierung (z. B. eine
  offizielle API/Partner-Vereinbarung) vorliegt.
- `stepstone.yaml` wurde per expliziter Nutzerfreigabe (2026-08-12) auf
  `enabled: true` und `browser: camoufox` gestellt (Umkehr von JAP-01, siehe
  `todos/archiv/job-agent-camoufox-stepstone.json`). Login-URL und -Felder,
  öffentliche Such-URL sowie die Trefferkarten wurden am 2026-08-12 mit
  `examples/stepstone_calib.py` zugangsdatenfrei live kalibriert. Der
  Login-Erfolgsindikator bleibt bis zu einem echten Nutzerlogin unbestätigt.
  Die öffentliche Trefferliste ist mit `login_erforderlich: false` headless
  nutzbar. `ort_pfad_template` bildet Suchbegriff und Ort auf StepStones
  kanonischen Pfad `/jobs/{query}/in-{ort}` ab.
  Für einen optionalen Konto-Login öffnet `portal_login(sichtbar=true)` den
  konfigurierten Camoufox über die Desktop-Anzeige. Ein vom MCP injiziertes
  grünes Übergabe-Panel lässt den Nutzer nach Login/2FA die Speicherung des
  Browserzustands ausdrücklich bestätigen.
  Selektoren externer SPAs sind volatil und müssen bei Änderungen neu
  kalibriert werden. Es gelten weiterhin `ALLOW_EXTERNAL_PORTALS=1` und die
  Tool-Freigabe; der ältere Analysepfad bleibt standardmäßig ein Dry-Run.

Jedes Portal kann zusätzlich `browser: playwright|camoufox` setzen; Standard
ist `playwright` (Chromium). `camoufox` nutzt Firefox als Playwright-Drop-in
(`infrastructure/browser.py`, `examples/camoufox_browser.py`). Der
Browser-Session-Manager speichert `storage_state` außerhalb des Projekts;
der optionale browser-use-Fallback bekommt keine Portalpasswörter.

## Offizielle Feed-Quellen

- `arbeitnow.yaml` liest die öffentliche JSON-API ohne API-Schlüssel.
- `remotive.yaml` liest die öffentliche Remote-Jobs-API. Der Quellenname
  Remotive und der Original-Link müssen in Ergebnissen erhalten bleiben.
- `weworkremotely.yaml` liest den öffentlich angebotenen RSS-Feed. Der
  Quellenname und der Original-Link müssen ebenfalls erhalten bleiben.

`infrastructure/feeds.py` kapselt Transport und Anbieterformate hinter einem gemeinsamen
Rohdatenvertrag. Es entfernt HTML, begrenzt Beschreibungstexte und filtert
zusätzlich lokal. Neue offiziell angebotene Feed-Varianten werden als Adapter
ergänzt; Browser- und Feed-Logik werden nicht in einem Anbieter-Scraper
vermischt. Wie StepStone benötigen auch Feeds für einen externen Lauf
`ALLOW_EXTERNAL_PORTALS=1`.

## Portal-Katalog und nicht automatisierte Dienste

`resources/profiles/portal-catalog.yaml` ist der fachliche Katalog. Er ist bewusst vom
ausführbaren Portalprofil getrennt: Ein bekannter Portalname ist noch keine
Freigabe zum automatisierten Zugriff. `liste_portale` führt beide Sichten
zusammen und zeigt `aktiv`, `manuell`, `partnerzugang`, `gesperrt` oder
`nicht_angebunden`.

Instaffo wird als interaktiver Konto-Workflow geführt. Instaffo beschreibt das
Produkt als Matching-Plattform statt als klassische öffentliche Jobbörse; das
vorhandene Modell „Suchseite → Trefferkarten“ passt darauf nicht.

LinkedIn wird nur als Partnerzugang katalogisiert, weil automatisches Crawling
eine ausdrückliche Erlaubnis verlangt. Indeed bleibt gesperrt, weil dessen
Nutzungsbedingungen automatisiertes Auslesen ohne eigene Autorisierung
untersagen. Bundesagentur, XING, Jobware, stellenanzeigen.de, meinestadt.de,
Monster, GermanTechJobs, jobvector, Absolventa, Honeypot, JOIN, Glassdoor und
Google Jobs sind sichtbar, aber bewusst nicht als ungeprüfte Scraper aktiv.

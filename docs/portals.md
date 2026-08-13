# Portal-Profile

Jede YAML-Datei unter `src/job_search_mcp/resources/profiles/portals/` ist ein
validiertes `PortalProfil`.

- `kind: local` -> Sandbox-Portal (`demo_app.py`), standardmaessig `enabled: true`.
- `kind: real` -> echtes externes Portal, standardmaessig `enabled: false` und nur per
  `ALLOW_EXTERNAL_PORTALS=1` sowie expliziter Freigabe ueberhaupt erreichbar
  (siehe `job_flow.crawl_erlaubt` / `job_flow.crawle_echtes_portal`).

Aktuelle ausführbare externe Profile sind StepStone sowie die offiziellen
Feed-Quellen Arbeitnow, Remotive, We Work Remotely, die Jobsuche-API der
Bundesagentur für Arbeit, das Karriereportal des Landes
Baden-Württemberg, die öffentliche Stellenliste von JobRiver
(jobriver.de) und die Projektbörse freelancermap (freelancermap.de).
`beispiel-karriere.yaml` bleibt fiktiv; `indeed.yaml`
bleibt als bewusst gesperrter Grenzfall erhalten.

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
- `bundesagentur-arbeit.yaml` liest die öffentliche Jobsuche-API der
  Bundesagentur für Arbeit (`rest.arbeitsagentur.de`). Die Suche läuft über
  den Fulltext-Parameter `was` (mit optionaler Orts- und Umkreisangabe);
  eine Liste enthält keine Volltext-Beschreibung, der lokale Filter prüft
  daher nur den Ort. Die Referenz `X-API-Key` ist die von der
  Open-Data-Dokumentation veröffentlichte Demo-Authentifizierung.
- `bw-karriere.yaml` liest die JSON-API des öffentlichen Karriereportals des
  Landes Baden-Württemberg (`karriere.baden-wuerttemberg.de/api/job-search`).
  Die Suchbegriff-Länge des Portals ist auf mindestens drei Zeichen begrenzt;
  deshalb wird die Gesamtliste paginiert gelesen und lokal nach Suchbegriff
  und Ort gefiltert.
- `jobriver.yaml` liest die öffentlich zugängliche, servergerenderte
  Trefferliste `/stellenangebote` (jobriver.de), deren `robots.txt` Crawling
  ausdrücklich erlaubt. Es gibt keine öffentliche Such-API: Die Seite wird
  ohne Suchparameter geladen, über `<link rel="next">` bzw.
  `/stellenangebote/seite/{n}` paginiert und die lokale Trefferliste wird
  nach Suchbegriff und Ort gefiltert. Die Stellenkarten tragen die Klassen
  `alle-jobs-card-title`, `alle-jobs-card-company` und
  `alle-jobs-card-meta`; Ort und Arbeitsmodell (Remote/Hybrid) stehen im
  Meta-Bereich der Karte.
- `freelancermap.yaml` liest die servergerenderte Projektbörse
  (`www.freelancermap.de/projekte`), deren `robots.txt` Crawling erlaubt.
  Es gibt keine öffentliche Such-API: Die Seite wird mit den Parametern
  `query` (Suchbegriff) und `city` (Ort) serverseitig gefiltert geladen;
  aus dem eingebetteten `ProjectSearch`-JSON (React-on-Rails) werden die
  `initialResults` entnommen. Die Auftragsart wird aus
  `projectContractType.type` (freiberuflicher Auftrag / Festanstellung /
  Arbeitnehmerüberlassung) in die Beschreibung übernommen, das
  Arbeitsmodell aus `remoteInPercent`. Festanstellungen
  (`permanent_position`) werden gefiltert: Es fließen nur projektbasierte
  Aufträge (freiberuflich/Contracting und Arbeitnehmerüberlassung) ein.
  Die lokale Nachfilterung nach Suchbegriff und Ort bleibt wie bei den
  anderen Feeds bestehen.

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
untersagen. jobs.heise.de wird als `manuell` geführt: Die Next.js-Oberfläche
liefert Daten nur über `/api`-Aufrufe, die in `robots.txt` mit
`Disallow: /api` gesperrt sind (keine Sitemap/RSS). freelance.de ist
`gesperrt`, weil dessen `robots.txt` automatisiertes Crawling ausdrücklich
nur mit schriftlicher Genehmigung erlaubt. jobvector wird ebenfalls
als `manuell` geführt, weil alle Pfade inklusive `/api/*` Cloudflare-403 ohne
Browser-Kalibrierung liefern. XING, Jobware, stellenanzeigen.de, meinestadt.de,
Monster, GermanTechJobs, Absolventa, Honeypot, JOIN, Glassdoor und
Google Jobs sind sichtbar, aber bewusst nicht als ungeprüfte Scraper aktiv.

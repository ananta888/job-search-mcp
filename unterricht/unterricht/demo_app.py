"""Lokale FastAPI-Sandbox fuer alle Unterrichts-MVPs."""

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi import Cookie, FastAPI, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=ROOT / "templates")
app = FastAPI(title="Ananta Unterrichts-Sandbox", version="1.0.0")


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=80)
    limit: int = Field(default=3, ge=1, le=5)


class SearchResult(BaseModel):
    id: int
    title: str
    summary: str


class ResponseMeta(BaseModel):
    server_time: datetime


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    request_id: str
    meta: ResponseMeta


CATALOG = (
    SearchResult(id=1, title="OCR", summary="Text aus Bildern extrahieren"),
    SearchResult(
        id=2, title="Browser-Automation", summary="UI-Abläufe reproduzierbar steuern"
    ),
    SearchResult(
        id=3, title="API-Replay", summary="Entdeckte HTTP-Anfragen direkt wiederholen"
    ),
    SearchResult(
        id=4, title="Validierung", summary="Antwortstruktur und Gleichwertigkeit prüfen"
    ),
    SearchResult(
        id=5, title="Policy", summary="Erlaubte Replay-Ziele explizit begrenzen"
    ),
)

PORTAL_KATALOGE: dict[str, list[dict[str, object]]] = {
    "acme": [
        {
            "id": "acme-backend-1",
            "firma": "Acme GmbH",
            "titel": "Backend-Entwickler Java/Spring",
            "ort": "Berlin",
            "arbeitsmodell": "remote",
            "skills": ["Java", "Spring", "SQL", "Docker", "Kubernetes"],
            "gehalt_min": 70000,
            "gehalt_max": 90000,
            "sprachen": ["deutsch", "englisch"],
            "erfahrungsjahre": 3,
            "beschreibung": "Entwicklung unserer Zahlungsplattform mit Java 21 und Spring Boot.",
        },
        {
            "id": "acme-backend-2",
            "firma": "Acme GmbH",
            "titel": "Senior Java Developer",
            "ort": "Hamburg",
            "arbeitsmodell": "hybrid",
            "skills": ["Java", "Spring", "SQL"],
            "gehalt_min": 80000,
            "gehalt_max": 100000,
            "sprachen": ["englisch"],
            "erfahrungsjahre": 5,
            "beschreibung": "Architektur und Umsetzung neuer Backend-Services.",
        },
        {
            "id": "acme-qa-1",
            "firma": "Acme GmbH",
            "titel": "QA Engineer",
            "ort": "Berlin",
            "arbeitsmodell": "onsite",
            "skills": ["Testautomatisierung", "Python"],
            "gehalt_min": 55000,
            "gehalt_max": 65000,
            "sprachen": ["deutsch"],
            "erfahrungsjahre": 2,
            "beschreibung": "Automatisierte Tests fuer unsere Web-Anwendungen.",
        },
    ],
    "jobvermittlung": [
        {
            "id": "jv-1",
            "firma": "Solaris Systems",
            "titel": "Java Softwareentwickler",
            "ort": "Remote",
            "arbeitsmodell": "remote",
            "skills": ["Java", "Spring Boot", "SQL", "Git"],
            "gehalt_min": 65000,
            "gehalt_max": 85000,
            "sprachen": ["deutsch"],
            "erfahrungsjahre": 3,
            "beschreibung": "Mitarbeit in einem agilen Team fuer Versicherungsprozesse.",
        },
        {
            "id": "jv-2",
            "firma": "Webwerk AG",
            "titel": "Full-Stack Entwickler",
            "ort": "München",
            "arbeitsmodell": "onsite",
            "skills": ["JavaScript", "React", "Java"],
            "gehalt_min": 60000,
            "gehalt_max": 75000,
            "sprachen": ["englisch"],
            "erfahrungsjahre": 1,
            "beschreibung": "Web-Plattform fuer E-Commerce-Kunden.",
        },
        {
            "id": "jv-3",
            "firma": "Cloudfy",
            "titel": "Backend Engineer (Java)",
            "ort": "Berlin",
            "arbeitsmodell": "hybrid",
            "skills": ["Java", "Spring", "SQL", "Docker"],
            "gehalt_min": 72000,
            "gehalt_max": 95000,
            "sprachen": ["englisch"],
            "erfahrungsjahre": 4,
            "beschreibung": "Skalierbare Cloud-Dienste mit Kubernetes.",
        },
    ],
}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return """
<!doctype html>
<html lang="de">
  <head><meta charset="utf-8"><title>Lokale Such-Demo</title></head>
  <body>
    <main>
      <h1>Lokale Such-Demo</h1>
      <form id="search-form">
        <label for="query">Suchbegriff</label>
        <input id="query" name="query" value="OCR">
        <button type="submit">Suchen</button>
      </form>
      <p id="result" aria-live="polite"></p>
    </main>
    <script>
      document.querySelector('#search-form').addEventListener('submit', async (event) => {
        event.preventDefault();
        const query = document.querySelector('#query').value;
        const response = await fetch('/api/search', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({query, limit: 3})
        });
        const data = await response.json();
        const output = document.querySelector('#result');
        output.textContent = `${data.results[0].title}: ${data.results[0].summary}`;
        output.dataset.requestId = data.request_id;
      });
    </script>
  </body>
</html>
"""


@app.post("/api/search", response_model=SearchResponse)
def search(payload: SearchRequest) -> SearchResponse:
    term = payload.query.casefold()
    matches = [
        item
        for item in CATALOG
        if term in item.title.casefold() or term in item.summary.casefold()
    ]
    if not matches:
        matches = list(CATALOG)
    return SearchResponse(
        query=payload.query,
        results=matches[: payload.limit],
        request_id=str(uuid4()),
        meta=ResponseMeta(server_time=datetime.now(UTC)),
    )


@app.get("/portal/{portal_id}/jobs")
def portal_jobs(portal_id: str, q: str | None = None) -> dict[str, object]:
    """Lokale Job-Portal-Sandbox: Firmen- und Vermittlungsportal als JSON."""
    if portal_id not in PORTAL_KATALOGE:
        raise HTTPException(status_code=404, detail=f"Unbekanntes Portal: {portal_id}")
    jobs: list[dict[str, object]] = list(PORTAL_KATALOGE[portal_id])
    if q:
        term = q.casefold()

        def suchwerte(angebot: dict[str, object]) -> list[object]:
            skills = angebot.get("skills")
            skill_liste = skills if isinstance(skills, list) else []
            return [
                angebot.get("titel", ""),
                angebot.get("beschreibung", ""),
                *skill_liste,
            ]

        jobs = [
            angebot
            for angebot in jobs
            if any(term in str(wert).casefold() for wert in suchwerte(angebot))
        ]
    return {"portal": portal_id, "jobs": jobs}


@app.post("/api/form")
def form_data(topic: str = Form(min_length=2)) -> dict[str, str]:
    return {"received": topic, "parser": "python-multipart"}


@app.get("/result", response_class=HTMLResponse)
def rendered_result(request: Request, topic: str = "API-Replay") -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="result.html",
        context={"topic": topic, "items": CATALOG[:3]},
    )


@app.post("/api/session/start")
def start_session(response: Response) -> dict[str, str]:
    response.set_cookie(
        key="teaching_session",
        value="local-demo",
        httponly=True,
        samesite="strict",
    )
    return {"session": "created"}


@app.get("/api/session/private")
def private_session(
    teaching_session: str | None = Cookie(default=None),
) -> dict[str, str]:
    if teaching_session != "local-demo":
        raise HTTPException(status_code=401, detail="Keine Unterrichtssitzung")
    return {"session": "reused", "secret": "nur-lokale-demo"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("unterricht.demo_app:app", host="127.0.0.1", port=8765, reload=False)

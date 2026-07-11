"""End-to-end HTTP tests via FastAPI TestClient (offline)."""
from fastapi.testclient import TestClient

from app.main import app


def test_full_http_flow():
    with TestClient(app) as c:
        # create
        r = c.post("/projects", json={"idea": "A hotel booking platform with rooms, bookings and payments."})
        assert r.status_code == 200
        pid = r.json()["project"]["id"]

        # list
        assert any(p["id"] == pid for p in c.get("/projects").json()["projects"])

        # analyze
        a = c.post(f"/projects/{pid}/analyze")
        assert a.status_code == 200
        assert a.json()["classification"]["domain_key"] == "hotel"

        # questions
        qs = c.get(f"/projects/{pid}/questions").json()["questions"]
        assert 5 <= len(qs) <= 20

        # answers
        answers = [{"question_id": q["id"], "value": (q.get("suggested_options") or ["Yes"])[0]} for q in qs[:5]]
        ans = c.post(f"/projects/{pid}/answers", json={"answers": answers})
        assert ans.status_code == 200

        # generate
        gen = c.post(f"/projects/{pid}/generate-srs").json()
        assert gen["summary"]["functional"] >= 3
        assert gen["version"] == "1.0.0"

        # reads
        assert c.get(f"/projects/{pid}/srs-json").json()["srs_document"]["project_name"]
        assert c.get(f"/projects/{pid}/requirements").json()["functional_requirements"]
        assert len(c.get(f"/projects/{pid}/diagrams").json()["diagrams"]) == 7
        assert "ambiguities" in c.get(f"/projects/{pid}/ambiguities").json()
        assert "risk_priority" in c.get(f"/projects/{pid}/risks").json()

        # customize
        cust = c.post(f"/projects/{pid}/customize", json={"prompt": "Add a loyalty programme"})
        assert cust.status_code == 200
        assert cust.json()["version"] == "1.1.0"
        assert cust.json()["diff_summary"]

        # downloads
        dj = c.get(f"/projects/{pid}/download/json")
        assert dj.status_code == 200 and dj.headers["content-type"].startswith("application/json")
        dp = c.get(f"/projects/{pid}/download/pdf")
        assert dp.status_code == 200 and dp.headers["content-type"] == "application/pdf"
        assert len(dp.content) > 2000

        # approve
        assert c.post(f"/projects/{pid}/approve").json()["project"]["status"] == "approved"


def test_health_endpoint():
    with TestClient(app) as c:
        h = c.get("/health").json()
        assert h["status"] == "ok"
        assert "ollama" in h

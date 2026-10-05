"""تست دود: کل جریان با LLM جعلی (بدون اینترنت و بدون API key)."""
import os
import tempfile

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/t.db"

from fastapi.testclient import TestClient  # noqa: E402

from app import agents, llm, services  # noqa: E402
from app.main import app  # noqa: E402
from app.schemas import (InterviewTurn, JobExtract, MatchBatch, MatchItem, ProfileData, RefineDecision,  # noqa: E402
                         ResumeContent, SummaryOut)

PROFILE = ProfileData(name="سارا", city="تهران", level="junior", target_role="Frontend Developer",
                      remote_pref="remote", skills=["React", "JavaScript", "CSS"],
                      projects=[{"name": "TodoApp", "description": "اپ کارها", "tech": ["React"]}])


def fake_chat_json(db, user_id, agent, model, system, messages, schema, retries=1):
    if schema is InterviewTurn:
        return InterviewTurn(reply="آماده‌ایم!", profile=PROFILE, ready=True)
    if schema is SummaryOut:
        return SummaryOut(summary_en="Junior React developer, remote.")
    if schema is MatchBatch:
        import json
        ids = [j["job_id"] for j in json.loads(messages[0]["content"])["jobs"]]
        return MatchBatch(results=[MatchItem(job_id=i, score=90 - n, why_fit=["React بلدی"], gaps=["Jest"]) for n, i in enumerate(ids)])
    if schema is JobExtract:
        return JobExtract(title="Pasted Job", company="X", remote=True, level="junior", skills=["React"], summary_en="React job")
    if schema is ResumeContent:
        return ResumeContent(name="سارا", headline="Frontend", skills=["React", "Kubernetes"], summary="خلاصه")
    if schema is RefineDecision:
        m = messages[0]["content"]
        if "نمی‌خوام" in m:
            return RefineDecision(action="exclude_job", message="حذف شد")
        if "رزومه" in m:
            return RefineDecision(action="revise_resume", instructions="کوتاه‌تر", message="اصلاح شد")
        return RefineDecision(action="update_preferences", patch={"skills": ["Vue"]}, message="به‌روز شد")
    raise AssertionError(schema)


def test_full_flow(monkeypatch):
    for mod in (services, agents):
        monkeypatch.setattr(mod, "chat_json", fake_chat_json)
    monkeypatch.setattr(services, "embed", lambda texts: None)  # fallback کلیدواژه‌ای
    with TestClient(app) as c:
        r = c.post("/api/auth/register", json={"email": "a@b.com", "password": "secret1", "name": "سارا"})
        assert r.status_code == 200
        h = {"Authorization": f"Bearer {r.json()['token']}"}
        assert c.post("/api/auth/login", json={"email": "a@b.com", "password": "bad"}).status_code == 401
        assert c.get("/api/interview").status_code == 401

        st = c.post("/api/interview/message", json={"message": ""}, headers=h).json()
        assert st["ready"] and st["completeness"] == 100

        ms = c.post("/api/matches/run", headers=h).json()["matches"]
        assert ms and all(m["job"]["level"] != "senior" for m in ms)       # فیلتر سخت
        assert all(m["job"]["remote"] for m in ms)                          # ترجیح دورکاری
        assert ms == sorted(ms, key=lambda m: -m["score"])

        jid = ms[0]["job"]["id"]
        rs = c.post("/api/resume", json={"job_id": jid, "lang": "fa"}, headers=h).json()
        assert "Kubernetes" not in rs["content"]["skills"]                  # محافظ ضدجعل
        assert c.get(f"/api/resume?job_id={jid}", headers=h).json()["version"] == 1

        rf = c.post("/api/refine", json={"message": "رزومه رو کوتاه کن", "job_id": jid}, headers=h).json()
        assert rf["action"] == "revise_resume" and "resume" in rf["changed"]
        assert c.get(f"/api/resume?job_id={jid}", headers=h).json()["version"] == 2

        rf = c.post("/api/refine", json={"message": "این آگهی رو نمی‌خوام", "job_id": jid}, headers=h).json()
        assert rf["action"] == "exclude_job"
        assert jid not in [m["job"]["id"] for m in c.get("/api/matches", headers=h).json()["matches"]]

        rf = c.post("/api/refine", json={"message": "Vue هم بلدم"}, headers=h).json()
        assert rf["action"] == "update_preferences" and "matches" in rf["changed"]

        p = c.post("/api/jobs/paste", json={"text": "x" * 50}, headers=h).json()
        assert p["job_id"]

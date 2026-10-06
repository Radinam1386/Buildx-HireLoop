"""No paid calls: real matching/persistence, external search and model responses replaced."""
import json

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import services
from app import jobs as boards
from app.db import Base
from app.models import Job, Profile, User
from app.schemas import MatchBatch, MatchItem, ProfileData, SummaryOut


def test_preferences_do_not_relax_when_few_jobs_remain():
    p = ProfileData(city="تهران", level="intern", remote_pref="remote")
    jobs = [Job(id=1, title="Python intern", level="intern", remote=True),
            Job(id=2, title="Python junior", level="junior", remote=True),
            Job(id=3, title="Python intern", level="intern", remote=False, location="تهران")]
    assert [j.id for j in services.hard_filter(p, jobs)] == [1]
    p.remote_pref = "onsite"
    assert [j.id for j in services.hard_filter(p, jobs)] == [3]


def test_search_replaces_samples_and_upserts_without_duplicates(monkeypatch):
    async def search(p):
        return {"query": "React", "sources": [{"id": "jobvision", "status": "ok", "count": 1}],
                "jobs": [{"source": "jobvision", "url": "https://jobvision.ir/jobs/123", "title": "React developer",
                          "company": "Example", "location": "تهران", "remote": True, "level": "junior",
                          "skills": ["React"], "description": "React frontend development"}]}

    def model(db, uid, agent, name, system, messages, schema):
        if schema is SummaryOut:
            return SummaryOut(summary_en="Junior React developer")
        ids = [j["job_id"] for j in json.loads(messages[0]["content"])["jobs"]]
        return MatchBatch(results=[MatchItem(job_id=i, score=85, why_fit=["React"], gaps=[]) for i in ids])

    monkeypatch.setattr(services, "search_jobs", search, raising=False)
    monkeypatch.setattr(services, "chat_json", model)
    monkeypatch.setattr(services, "embed", lambda _: None)
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        u = User(email="test@example.com", password_hash="unused")
        db.add(u)
        db.flush()
        p = ProfileData(name="Test", target_role="Frontend developer", level="junior", remote_pref="remote", skills=["React", "CSS"])
        db.add(Profile(user_id=u.id, data=p.model_dump(), messages=[]))
        db.add(Job(source="sample", title="Sample React", remote=True, level="junior", skills=["React"]))
        db.commit()
        services.run_match(db, u)
        assert [m["job"]["url"] for m in services.list_matches(db, u)] == ["https://jobvision.ir/jobs/123"]
        services.run_match(db, u)
        assert db.query(Job).filter_by(source="jobvision").count() == 1


def test_run_match_scores_all_filtered_jobs(monkeypatch):
    async def search(p):
        return {"query": "React", "sources": [{"id": "jobvision", "status": "ok", "count": 25}],
                "jobs": [{"source": "jobvision", "url": f"https://jobvision.ir/jobs/{1000 + i}", "title": f"React developer {i}",
                          "company": "Example", "location": "تهران", "remote": True, "level": "junior",
                          "skills": ["React"], "description": "React frontend development"}
                         for i in range(25)]}

    def model(db, uid, agent, name, system, messages, schema):
        if schema is SummaryOut:
            return SummaryOut(summary_en="Junior React developer")
        ids = [j["job_id"] for j in json.loads(messages[0]["content"])["jobs"]]
        return MatchBatch(results=[MatchItem(job_id=i, score=80, why_fit=["React"], gaps=[]) for i in ids])

    monkeypatch.setattr(services, "search_jobs", search, raising=False)
    monkeypatch.setattr(services, "chat_json", model)
    monkeypatch.setattr(services, "embed", lambda _: None)
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        u = User(email="many@example.com", password_hash="unused")
        db.add(u)
        db.flush()
        p = ProfileData(name="Test", target_role="Frontend developer", level="junior", remote_pref="remote", skills=["React", "CSS"])
        db.add(Profile(user_id=u.id, data=p.model_dump(), messages=[]))
        db.commit()
        assert len(services.run_match(db, u)["matches"]) == 25


def test_score_jobs_keeps_candidates_when_model_omits_ids(monkeypatch):
    def model(db, uid, agent, name, system, messages, schema):
        ids = [j["job_id"] for j in json.loads(messages[0]["content"])["jobs"]]
        return MatchBatch(results=[MatchItem(job_id=ids[0], score=88, why_fit=["React"], gaps=[])])

    monkeypatch.setattr(services, "chat_json", model)
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        u = User(email="omitted@example.com", password_hash="unused")
        db.add(u)
        db.flush()
        prof = Profile(user_id=u.id, data=ProfileData(skills=["React"]).model_dump(), messages=[])
        jobs = [Job(title="React developer", source="jobvision", url=f"https://jobvision.ir/jobs/{i}",
                    remote=True, level="junior", skills=["React"], description="React frontend")
                for i in (1, 2)]
        db.add(prof)
        db.add_all(jobs)
        db.commit()
        services.score_jobs(db, u, prof, jobs)
        matches = services.list_matches(db, u)
        assert len(matches) == 2
        assert sorted(m["score"] for m in matches) == [0, 88]


def test_original_page_expiry_overrides_search_cards():
    card = {"url": "https://jobinja.ir/companies/example/jobs/Ab12/title", "title": "Python intern"}
    posting = '<script type="application/ld+json">' + json.dumps({"@type": "JobPosting", "title": "Python intern", "description": "Python and FastAPI", "validThrough": "2099-01-01", "jobLocationType": "TELECOMMUTE"}) + '</script>'
    job = boards.detail("jobinja", posting, card, ["Python", "FastAPI"])
    assert job["level"] == "intern" and job["remote"] and job["skills"] == ["Python", "FastAPI"]
    assert boards.detail("jobinja", posting + '<div class="c-alert">این آگهی منقضی شده است</div>', card, []) is None
    assert boards.detail("jobinja", posting.replace("2099-01-01", "2020-01-01"), card, []) is None
    for url in ["https://evil.example/jobs/123", "https://jobvision.ir:bad/jobs/123", "https://user@jobvision.ir/jobs/123", "https://jobvision.ir/jobs"]:
        assert not boards.job_key("jobvision", url)


def test_experience_conflict_is_not_silently_rounded_down():
    assert boards.level({"title": "Front-End Developer", "min_years": 2, "text": "We seek over 2 years of hands-on experience."}) == "mid"
    assert boards.level({"title": "Full Stack Developer", "text": "Minimum of 5 years of professional experience."}) == "senior"


def test_python_intern_and_hybrid_are_not_lost_to_title_and_remote_guards():
    p = ProfileData(city="تهران", target_role="Python developer", level="intern", remote_pref="hybrid")
    j = Job(id=1, title="Python Intern", description="Build Python backend APIs. Hybrid: two office days and three remote days.", level="intern", remote=True, location="تهران")
    assert services.hard_filter(p, [j]) == [j]


def test_ranking_does_not_buy_embeddings_without_job_vectors(monkeypatch):
    calls = []
    monkeypatch.setattr(services, "embed", lambda texts: calls.append(texts))
    j = Job(id=1, title="React developer", skills=["React"], summary_en="", embedding=None)
    assert services.rank(None, ProfileData(skills=["React"]), "React candidate", [j], 8) == [j]
    assert calls == []


def test_search_uses_the_target_profession_before_incidental_tech_skills():
    assert boards.queries(ProfileData(target_role="کارشناس فروش", skills=["Python", "Excel"])) == ["کارشناس فروش"]
    assert boards.queries(ProfileData(target_role="JavaScript developer", skills=["JavaScript"])) == ["JavaScript developer"]
    assert boards.queries(ProfileData(target_role="Backend developer", skills=["Python"])) == ["Python"]


def test_experienced_profiles_are_not_forced_into_entry_level_jobs():
    jobs = [Job(id=1, title="Accountant", level="junior", description="1 year of experience"),
            Job(id=2, title="Accountant", level="", description="3 years of experience"),
            Job(id=3, title="Senior Accountant", level="senior", description="5 years of experience")]
    p = ProfileData(target_role="حسابدار", level="mid")
    assert [j.id for j in services.hard_filter(p, jobs)] == [2]
    p.level = "senior"
    assert [j.id for j in services.hard_filter(p, jobs)] == [3]
    p.level = "junior"
    assert [j.id for j in services.hard_filter(p, jobs)] == [1]


def test_saved_resumes_remain_accessible_without_matches_and_are_private():
    from fastapi.testclient import TestClient
    from app.main import app
    from app.db import SessionLocal
    from app.models import Resume
    with TestClient(app) as client:
        first = client.post("/api/auth/register", json={"email": "resume-owner@example.test", "password": "test-only"}).json()
        other = client.post("/api/auth/register", json={"email": "resume-other@example.test", "password": "test-only"}).json()
        with SessionLocal() as db:
            job = Job(title="Accountant", source="pasted", owner_id=first["user"]["id"])
            db.add(job)
            db.flush()
            jid = job.id
            db.add(Resume(user_id=first["user"]["id"], job_id=jid, lang="en", version=2, content={"name": "Test"}))
            db.commit()
        h = {"Authorization": "Bearer " + first["token"]}
        response = client.get("/api/resumes", headers=h)
        assert response.status_code == 200
        saved = response.json()["resumes"]
        assert [(r["job"]["id"], r["lang"], r["version"]) for r in saved] == [(jid, "en", 2)]
        assert client.get("/api/resume", params={"job_id": jid, "lang": "en"}, headers=h).json()["content"]["name"] == "Test"
        assert client.get("/api/resumes", headers={"Authorization": "Bearer " + other["token"]}).json()["resumes"] == []
        assert client.get("/api/resumes").status_code == 401


def test_all_engineering_stacks_query_generation_and_hard_filtering():
    # 1. AI / ML
    p_ai = ProfileData(target_role="مهندس هوش مصنوعی", skills=["PyTorch", "Python"])
    assert boards.queries(p_ai) == ["هوش مصنوعی"]
    p_ai_intern = ProfileData(target_role="AI Engineer", skills=["PyTorch"], level="intern")
    assert boards.queries(p_ai_intern) == ["هوش مصنوعی", "کارآموز هوش مصنوعی"]

    j_ai = Job(id=10, title="AI Engineer (LLM & RAG)", description="Building AI models with PyTorch", level="mid")
    j_fe = Job(id=11, title="Frontend React Developer", description="Building UI with React and CSS", level="mid")
    assert [j.id for j in services.hard_filter(p_ai, [j_ai, j_fe])] == [10]

    # 2. DevOps
    p_devops = ProfileData(target_role="مهندس دوآپس", skills=["Docker", "Kubernetes"])
    assert boards.queries(p_devops) == ["DevOps"]
    j_devops = Job(id=20, title="DevOps Engineer", description="Managing Kubernetes clusters and CI/CD", level="mid")
    assert [j.id for j in services.hard_filter(p_devops, [j_devops, j_fe])] == [20]

    # 3. Mobile
    p_mobile = ProfileData(target_role="توسعه دهنده موبایل", skills=["Flutter", "Dart"])
    assert boards.queries(p_mobile) == ["Flutter"]
    j_mobile = Job(id=30, title="Flutter Developer", description="Mobile cross-platform development", level="mid")
    assert [j.id for j in services.hard_filter(p_mobile, [j_mobile, j_fe])] == [30]

    # 4. Backend (Go)
    p_go = ProfileData(target_role="توسعه دهنده بک اند", skills=["Golang", "PostgreSQL"])
    assert boards.queries(p_go) == ["Golang"]
    j_go = Job(id=40, title="Golang Backend Developer", description="Microservices with Go and gRPC", level="mid")
    assert [j.id for j in services.hard_filter(p_go, [j_go, j_fe])] == [40]

    # 5. Full-Stack
    p_fullstack = ProfileData(target_role="Full Stack Developer", skills=["React", "Node.js"])
    assert boards.queries(p_fullstack) == ["Full Stack"]
    j_fs = Job(id=50, title="Full Stack Engineer", description="React frontend and Node backend", level="mid")
    assert [j.id for j in services.hard_filter(p_fullstack, [j_fs])] == [50]


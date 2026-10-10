"""Comprehensive tests for adaptive interview and resume generation.

Validates:
1. Simulation with Radin Almasi reference data (AI Olympiad Bronze, SAMPAD, 4 Projects, Skills & Tools, Languages).
2. is_resume_ready and completeness metrics.
3. Adaptive interview targeting empty/weak sections without static repetition.
4. Anti-forgery engine: stripping invented skills, fake degrees, hallucinated projects, and unsupported numeric claims.
5. Backward compatibility with legacy string lists for skills and contacts.
"""
import json
from fastapi.testclient import TestClient

from app import agents, services
from app.db import SessionLocal
from app.main import app
from app.models import Job, Profile, Resume, User
from app.schemas import (
    CertItem,
    ContactData,
    Edu,
    Exp,
    HonorItem,
    InterviewTurn,
    LanguageItem,
    ProfileData,
    Proj,
    ResumeContent,
    ResumeEvidence,
    ResumeExp,
    ResumeProj,
    SkillItem,
    skill_names,
)
from app.services import (
    _guard_skills,
    completeness,
    coverage_report,
    is_resume_ready,
    merge_profile,
    resume_evidence,
    resume_sources,
    soft_match,
)


def make_radin_profile() -> ProfileData:
    return ProfileData(
        name="رادین الماسی",
        name_en="Radin Almasi",
        headline="توسعه‌دهنده هوش مصنوعی و پایتون | برنده مدال برنز المپیاد هوش مصنوعی",
        contact=ContactData(
            email="radinam1386@gmail.com",
            phone="09180000000",
            city="تهران",
            country="ایران",
            linkedin="https://linkedin.com/in/radin-almasi",
            github="https://github.com/radinam1386",
            website="https://radinam1386.github.io/resume/",
        ),
        city="تهران",
        level="junior",
        target_role="مهندس هوش مصنوعی و توسعه‌دهنده بک‌اند",
        remote_pref="city_or_remote",
        goals="توسعه سیستم‌های مبتنی بر هوش مصنوعی، مدل‌های یادگیری عمیق و میکروسرویس‌های مقیاس‌پذیر با تمرکز بر پردازش تصویر و متن.",
        honors=[
            HonorItem(
                title="مدال برنز المپیاد هوش مصنوعی",
                issuer="کمیته ملی المپیاد هوش مصنوعی",
                year="۱۴۰۳",
                location="تهران",
                description="کسب رتبه برتر و مدال برنز در رقابت‌های تئوری و عملی الگوریتم‌های یادگیری ماشین و یادگیری عمیق.",
            )
        ],
        education=[
            Edu(
                degree="دیپلم",
                field="ریاضی و فیزیک",
                school="دبیرستان استعدادهای درخشان سمپاد (شهید بهشتی)",
                period="۱۳۹۹-۱۴۰۳",
                gpa="۱۹.۸۰",
                notes="عضو فعال تیم المپیاد کامپیوتر و هوش مصنوعی",
            )
        ],
        projects=[
            Proj(
                name="Mentora",
                role="توسعه‌دهنده اصلی و طراح سیستم",
                link="https://github.com/radinam1386/mentora",
                period="۱۴۰۳",
                tech=["Python", "FastAPI", "PostgreSQL", "Docker", "React"],
                description="پلتفرم هوشمند راهنمایی و منتورینگ با معماری میکروسرویس و الگوریتم‌های مچینگ هوشمند برای تطبیق منتور و دانشجو.",
            ),
            Proj(
                name="Language School Portal",
                role="برنامه‌نویس فول‌استک",
                link="https://github.com/radinam1386/language-school-portal",
                period="۱۴۰۲",
                tech=["Python", "Django", "PostgreSQL", "TailwindCSS"],
                description="سامانه جامع مدیریت آموزشی، ثبت‌نام، تقویم کلاسی و پنل اساتید و زبان‌آموزان با سیستم آزمون‌ساز آنلاین.",
            ),
            Proj(
                name="National ID OCR",
                role="توسعه‌دهنده یادگیری عمیق",
                link="https://github.com/radinam1386/national-id-ocr",
                period="۱۴۰۲",
                tech=["Python", "PyTorch", "OpenCV", "YOLO"],
                description="خط لوله پیشرفته استخراج خودکار متون و مشخصات از کارت ملی هوشمند با ترکیب YOLOv8 برای تشخیص ناحیه و مدل CRNN برای خواندن حروف فارسی.",
            ),
            Proj(
                name="Face Recognition Pipeline",
                role="مهندس بینایی ماشین",
                link="https://github.com/radinam1386/face-recognition",
                period="۱۴۰۱",
                tech=["Python", "OpenCV", "TensorFlow", "scikit-learn"],
                description="سیستم احراز هویت تصویری بلادرنگ با شناسایی چهره و تشخیص زنده‌بودن (Liveness Detection) با نرخ دقت ۹۸.۵ درصد.",
            ),
        ],
        skills=[
            SkillItem(name="Python", level="مسلط", tools=["FastAPI", "Django", "PyTorch", "NumPy"]),
            SkillItem(name="Machine Learning & Deep Learning", level="مسلط", tools=["PyTorch", "TensorFlow", "YOLO", "OpenCV", "scikit-learn"]),
            SkillItem(name="SQL & Databases", level="پیشرفته", tools=["PostgreSQL", "SQLite", "Redis"]),
            SkillItem(name="DevOps & Tools", level="متوسط", tools=["Docker", "Git", "Linux", "CI/CD"]),
            SkillItem(name="Frontend Basics", level="متوسط", tools=["React", "JavaScript", "HTML", "TailwindCSS"]),
        ],
        languages=[
            LanguageItem(name="فارسی", level="زبان مادری"),
            LanguageItem(name="انگلیسی", level="پیشرفته (C1)"),
        ],
        links=[
            "https://github.com/radinam1386",
            "https://linkedin.com/in/radin-almasi",
            "https://radinam1386.github.io/resume/",
        ],
    )


def test_radin_almasi_reference_profile_is_ready_and_complete():
    profile = make_radin_profile()
    cov = coverage_report(profile)

    assert cov["identity"] == "ok"
    assert cov["target_role_and_level"] == "ok"
    assert cov["skills"] == "ok"
    assert cov["projects"] == "ok"
    assert cov["education"] == "ok"
    assert cov["honors"] == "ok"
    assert cov["languages"] == "ok"
    assert cov["links"] == "ok"

    ready = is_resume_ready(profile)
    assert ready is True

    pct, missing = completeness(profile)
    assert pct == 100
    assert missing == []


def test_coverage_report_and_declined_sections():
    # Empty profile
    empty_p = ProfileData()
    assert is_resume_ready(empty_p) is False
    cov_empty = coverage_report(empty_p)
    assert cov_empty["identity"] == "empty"
    assert cov_empty["skills"] == "empty"

    # Profile with declined experience and honors
    p = ProfileData(
        name="علی رضایی",
        target_role="Frontend Developer",
        level="junior",
        contact=ContactData(email="ali@example.com", city="تهران"),
        skills=[SkillItem(name="React", level="مسلط"), SkillItem(name="JavaScript", level="متوسط")],
        projects=[Proj(name="Portfolio", tech=["React"], description="ساخت سایت شخصی و پورتفولیو با ریکت و استایل‌های واکنش‌گرا.")],
        education=[Edu(degree="کارشناسی", school="دانشگاه شریف")],
        languages=[LanguageItem(name="فارسی", level="زبان مادری")],
        declined_sections=["experience", "honors", "certifications"],
    )
    cov = coverage_report(p)
    assert cov["experience"] == "declined"
    assert cov["honors"] == "declined"
    assert cov["certifications"] == "declined"
    assert is_resume_ready(p) is True


def test_soft_match_and_anti_forgery_guard_skills():
    profile = make_radin_profile()

    # Content with both valid claims and forged/hallucinated items
    forged_content = ResumeContent(
        name="رادین الماسی",
        name_en="Radin Almasi",
        headline="AI Engineer",
        skills=[
            SkillItem(name="Python", level="مسلط", tools=["FastAPI", "PyTorch", "Rust"]),  # Rust is forged
            SkillItem(name="Machine Learning & Deep Learning", level="مسلط", tools=["YOLO", "QuantumComputing"]),  # Quantum is forged
            SkillItem(name="Solidity & Smart Contracts", level="ارشد"),  # Completely forged skill
        ],
        education=[
            Edu(degree="دیپلم", field="ریاضی و فیزیک", school="دبیرستان استعدادهای درخشان سمپاد (شهید بهشتی)"),
            Edu(degree="دکتری", field="فیزیک هسته‌ای", school="دانشگاه استنفورد"),  # Forged education
        ],
        honors=[
            HonorItem(title="مدال برنز المپیاد هوش مصنوعی", issuer="کمیته ملی"),
            HonorItem(title="جایزه نوبل هوش مصنوعی"),  # Forged honor
        ],
        projects=[
            ResumeProj(
                name="Mentora",
                role="Lead Developer",
                tech=["Python", "FastAPI", "Blockchain", "Docker"],  # Blockchain is forged
                bullets=["توسعه پلتفرم هوشمند منتورینگ با معماری میکروسرویس."],
            ),
            ResumeProj(
                name="Fabricated Drone Project",  # Forged project
                role="Founder",
                tech=["C++", "ROS"],
                bullets=["طراحی پهپاد خودران."],
            ),
        ],
        experience=[
            ResumeExp(title="مدیر ارشد فنی", org="Google Inc.", bullets=["مدیریت ۱۰۰ مهندس نرم‌افزار."]),  # Forged experience
        ],
        certifications=[
            CertItem(name="AWS Certified Solutions Architect"),  # Forged cert
        ],
    )

    guarded = _guard_skills(forged_content, profile)

    # 1. Skills guarded
    guarded_skills = skill_names(guarded.skills)
    assert "Python" in guarded_skills
    assert "Machine Learning & Deep Learning" in guarded_skills
    assert "Solidity & Smart Contracts" not in guarded_skills

    # Tools guarded inside valid skills
    py_skill = next(s for s in guarded.skills if s.name == "Python")
    assert "FastAPI" in py_skill.tools
    assert "Rust" not in py_skill.tools

    ml_skill = next(s for s in guarded.skills if s.name == "Machine Learning & Deep Learning")
    assert "YOLO" in ml_skill.tools
    assert "QuantumComputing" not in ml_skill.tools

    # 2. Education guarded
    assert len(guarded.education) == 1
    assert "سمپاد" in guarded.education[0].school
    assert not any("استنفورد" in ed.school for ed in guarded.education)

    # 3. Honors guarded
    assert len(guarded.honors) == 1
    assert "المپیاد" in guarded.honors[0].title
    assert not any("نوبل" in h.title for h in guarded.honors)

    # 4. Projects guarded
    assert len(guarded.projects) == 1
    assert guarded.projects[0].name == "Mentora"
    assert "Blockchain" not in guarded.projects[0].tech
    assert not any(p.name == "Fabricated Drone Project" for p in guarded.projects)

    # 5. Experience guarded (since profile has no experience)
    assert len(guarded.experience) == 0


def test_resume_evidence_numeric_omission():
    profile = make_radin_profile()
    sources = resume_sources(profile, [])

    content = {
        "name": "رادین الماسی",
        "headline": "AI Engineer",
        "summary": "توسعه‌دهنده هوش مصنوعی با تجربه پیاده‌سازی ۴ پروژه واقعی و کسب مدال در سال ۱۴۰۳.",
        "projects": [
            {
                "name": "Face Recognition Pipeline",
                "tech": ["Python", "OpenCV"],
                "bullets": [
                    "شناسایی چهره با دقت ۹۸.۵ درصد در شرایط نوری مختلف.",
                    "افزایش سرعت پردازش به میزان ۹۹۹ درصد در ثانیه.",  # 999 is unsupported number
                ],
            }
        ],
    }

    refs = [
        ResumeEvidence(path="projects.0.bullets.0", source_ids=["project:3"]),
        ResumeEvidence(path="projects.0.bullets.1", source_ids=["project:3"]),
    ]

    res = resume_evidence(content, refs, sources)

    # The supported bullet (98.5) should be kept
    assert len(content["projects"][0]["bullets"]) == 1
    assert "۹۸.۵" in content["projects"][0]["bullets"][0]

    # The unsupported claim (999) must be placed in omitted list
    assert any("۹۹۹" in o["text"] for o in res["omitted"])


def test_backward_compatibility_string_coercion():
    # 1. SkillItem coercion from plain strings
    p_dict = {
        "name": "تست کاربر",
        "target_role": "Backend",
        "skills": ["Python", "Django", "PostgreSQL"],
        "contact": ["test@example.com", "09121234567", "https://github.com/testuser"],
        "languages": ["فارسی", "انگلیسی"],
    }
    p = ProfileData.model_validate(p_dict)

    assert len(p.skills) == 3
    assert all(isinstance(s, SkillItem) for s in p.skills)
    assert p.skills[0].name == "Python"
    assert p.skills[1].name == "Django"

    assert p.contact.email == "test@example.com"
    assert p.contact.phone == "09121234567"
    assert p.contact.github == "https://github.com/testuser"

    assert len(p.languages) == 2
    assert p.languages[0].name == "فارسی"

    # skill_names helper with various input types
    assert skill_names(p) == ["Python", "Django", "PostgreSQL"]
    assert skill_names(["React", "TypeScript"]) == ["React", "TypeScript"]
    assert skill_names({"skills": [{"name": "Go"}, {"name": "Docker"}]}) == ["Go", "Docker"]
    assert skill_names(None) == []


def test_full_resume_generation_and_roundtrip(monkeypatch):
    profile = make_radin_profile()

    def fake_writer(db, uid, agent, model, system, messages, schema):
        payload = json.loads(messages[0]["content"])
        assert payload["profile"]["name"] == "رادین الماسی"
        assert len(payload["profile"]["projects"]) == 4
        return ResumeContent(
            name="رادین الماسی",
            name_en="Radin Almasi",
            headline="AI & Backend Developer",
            contact=ContactData(
                email="radinam1386@gmail.com",
                github="https://github.com/radinam1386",
                city="تهران",
            ),
            summary="مهندس هوش مصنوعی برنده مدال برنز المپیاد با تمرکز بر پردازش تصویر و یادگیری عمیق.",
            skills=[
                SkillItem(name="Python", level="مسلط", tools=["FastAPI", "PyTorch"]),
                SkillItem(name="Machine Learning & Deep Learning", level="مسلط", tools=["PyTorch", "YOLO"]),
                SkillItem(name="SQL & Databases", level="پیشرفته", tools=["PostgreSQL"]),
            ],
            honors=[
                HonorItem(title="مدال برنز المپیاد هوش مصنوعی", issuer="کمیته ملی", year="۱۴۰۳"),
            ],
            education=[
                Edu(degree="دیپلم", field="ریاضی و فیزیک", school="دبیرستان استعدادهای درخشان سمپاد (شهید بهشتی)", period="۱۳۹۹-۱۴۰۳"),
            ],
            projects=[
                ResumeProj(
                    name="Mentora",
                    role="Lead Developer",
                    link="https://github.com/radinam1386/mentora",
                    tech=["Python", "FastAPI", "Docker"],
                    bullets=["طراحی و پیاده‌سازی سرویس تطبیق منتور و دانشجو با فست‌ای‌پی‌آی."],
                ),
                ResumeProj(
                    name="National ID OCR",
                    role="AI Engineer",
                    link="https://github.com/radinam1386/national-id-ocr",
                    tech=["Python", "PyTorch", "OpenCV", "YOLO"],
                    bullets=["استخراج خودکار اطلاعات کارت ملی با دقت بالا."],
                ),
            ],
            languages=[
                LanguageItem(name="فارسی", level="زبان مادری"),
                LanguageItem(name="انگلیسی", level="پیشرفته (C1)"),
            ],
            evidence=[
                ResumeEvidence(path="honors.0.title", source_ids=["honors:0"]),
                ResumeEvidence(path="projects.0.bullets.0", source_ids=["project:0"]),
                ResumeEvidence(path="projects.1.bullets.0", source_ids=["project:2"]),
            ],
        )

    monkeypatch.setattr(services, "chat_json", fake_writer)

    with TestClient(app) as c:
        token = c.post("/api/auth/register", json={"email": "radin-test@example.com", "password": "pass1234password"}).json()["token"]
        h = {"Authorization": f"Bearer {token}"}

        # Save profile
        patch_res = c.patch("/api/profile", headers=h, json=profile.model_dump())
        assert patch_res.status_code == 200

        # Verify interview state
        st = c.get("/api/interview", headers=h).json()
        assert st["resume_ready"] is True
        assert st["completeness"] == 100

        # Create job & generate resume
        with SessionLocal() as db:
            job = Job(
                title="Python & AI Engineer",
                company="TechCorp",
                source="jobvision",
                description="Python, FastAPI, PyTorch, Deep Learning",
                skills=["Python", "PyTorch", "FastAPI"],
            )
            db.add(job)
            db.commit()
            jid = job.id

        res = c.post("/api/resume", headers=h, json={"job_id": jid, "lang": "fa"}).json()
        assert res["content"]["name"] == "رادین الماسی"
        assert res["content"]["name_en"] == "Radin Almasi"
        assert len(res["content"]["honors"]) == 1
        assert res["content"]["honors"][0]["title"] == "مدال برنز المپیاد هوش مصنوعی"
        assert len(res["content"]["projects"]) == 2
        assert res["content"]["projects"][0]["name"] == "Mentora"
        assert res["content"]["projects"][0]["link"] == "https://github.com/radinam1386/mentora"
        assert "FastAPI" in res["content"]["projects"][0]["tech"]
        assert len(res["content"]["education"]) == 1
        assert res["content"]["education"][0]["field"] == "ریاضی و فیزیک"

        # Direct edit via PATCH /api/resume
        content_to_edit = dict(res["content"])
        content_to_edit["headline"] = "Senior AI Engineer & Python Architect"
        edit_res = c.patch("/api/resume", headers=h, json={
            "job_id": jid,
            "lang": "fa",
            "version": res["version"],
            "content": content_to_edit,
        })
        assert edit_res.status_code == 200
        assert edit_res.json()["version"] == 2
        assert edit_res.json()["content"]["headline"] == "Senior AI Engineer & Python Architect"


def test_interview_completion_announcement_and_post_additions(monkeypatch):
    """Test that when interview reaches completion, reply explicitly announces it and invites additions,
    and post-completion additions are seamlessly merged while keeping resume_ready True."""
    complete_profile = make_radin_profile()

    turns_mock = [
        # Turn 1: user provides complete info
        InterviewTurn(
            reply="اطلاعات رزومهٔ شما کامل شد! 🎉 تمام بخش‌های اصلی با موفقیت ثبت شده‌اند. اگر نکته، مهارت یا سابقهٔ دیگری هست که می‌خواهید به رزومه اضافه یا ویرایش شود بفرمایید تا به رزومه اضافه کنم.",
            profile=complete_profile,
            resume_ready=True,
            ready=True,
        ),
        # Turn 2: user adds a new skill "Docker & Kubernetes"
        InterviewTurn(
            reply="مهارت Docker & Kubernetes به رزومه اضافه شد! آیا مورد دیگری هست که بخواهید اضافه شود؟",
            profile=ProfileData(skills=[SkillItem(name="Docker & Kubernetes", level="مسلط")]),
            resume_ready=True,
            ready=True,
        ),
    ]

    call_count = 0

    def fake_interviewer(db, uid, agent, model, system, messages, schema):
        nonlocal call_count
        turn = turns_mock[min(call_count, len(turns_mock) - 1)]
        call_count += 1
        return turn

    monkeypatch.setattr(agents, "chat_json", fake_interviewer)

    with TestClient(app) as c:
        token = c.post("/api/auth/register", json={"email": "completion-test@example.com", "password": "pass1234password"}).json()["token"]
        h = {"Authorization": f"Bearer {token}"}

        # 1. First message leading to completion
        r1 = c.post("/api/interview/message", headers=h, json={"message": "تمام اطلاعات من ثبت شده است."}).json()
        assert r1["resume_ready"] is True
        last_msg = r1["messages"][-1]["content"]
        assert "کامل شد" in last_msg or "کامل شده" in last_msg
        assert "اضافه" in last_msg

        # 2. User adds additional skill after completion
        r2 = c.post("/api/interview/message", headers=h, json={"message": "مهارت Docker & Kubernetes رو هم به رزومه‌ام اضافه کن."}).json()
        assert r2["resume_ready"] is True
        assert any(s["name"] == "Docker & Kubernetes" for s in r2["profile"]["skills"])
        last_msg2 = r2["messages"][-1]["content"]
        assert "اضافه شد" in last_msg2 or "اضافه" in last_msg2


def test_resume_tailoring_to_job_requirements(monkeypatch):
    """Test that resume tailoring highlights matching skills, prioritizes matching projects,
    and tailors the headline and summary to the specific job."""
    profile = make_radin_profile()

    def job_tailored_writer(db, uid, agent, model, system, messages, schema):
        payload = json.loads(messages[0]["content"])
        job = payload["job"]
        assert "FastAPI" in job["skills"]
        assert "Python" in job["skills"]

        # The writer creates a resume tailored to the job
        return ResumeContent(
            name="رادین الماسی",
            name_en="Radin Almasi",
            headline=f"توسعه‌دهنده بک‌اند و هوش مصنوعی ({job['title']})",
            contact=ContactData(email="radin@example.com", city="تهران"),
            summary=f"توسعه‌دهنده با سابقه ساخت سیستم‌های مبتنی بر {job['skills'][0]} و {job['skills'][1]}.",
            skills=[
                SkillItem(name="Python", level="مسلط", tools=["FastAPI"]),
                SkillItem(name="FastAPI", level="مسلط", tools=["REST API"]),
                SkillItem(name="Machine Learning & Deep Learning", level="مسلط", tools=["PyTorch"]),
            ],
            projects=[
                ResumeProj(
                    name="Mentora",
                    role="طراح سیستم و توسعه‌دهنده بک‌اند",
                    tech=["Python", "FastAPI"],
                    bullets=["طراحی میکروسرویس با فست‌ای‌پی‌آی."],
                ),
            ],
            education=[
                Edu(degree="دیپلم", school="دبیرستان سمپاد"),
            ],
            languages=[
                LanguageItem(name="فارسی", level="زبان مادری"),
            ],
            evidence=[
                ResumeEvidence(path="projects.0.bullets.0", source_ids=["project:0"]),
            ],
        )

    monkeypatch.setattr(services, "chat_json", job_tailored_writer)

    with TestClient(app) as c:
        token = c.post("/api/auth/register", json={"email": "tailor-test@example.com", "password": "pass1234password"}).json()["token"]
        h = {"Authorization": f"Bearer {token}"}
        c.patch("/api/profile", headers=h, json=profile.model_dump())

        with SessionLocal() as db:
            target_job = Job(
                title="توسعه‌دهنده ارشد پایتون (FastAPI)",
                company="ابر دیجی",
                source="jobvision",
                description="تسلط بر پایتون و FastAPI و معماری میکروسرویس",
                skills=["Python", "FastAPI"],
            )
            db.add(target_job)
            db.commit()
            jid = target_job.id

        res = c.post("/api/resume", headers=h, json={"job_id": jid, "lang": "fa"}).json()
        assert "FastAPI" in res["content"]["headline"]
        assert "FastAPI" in res["tailoring"]["highlighted_skills"]
        assert "Python" in res["tailoring"]["highlighted_skills"]
        assert res["tailoring"]["projects"] == ["Mentora"]


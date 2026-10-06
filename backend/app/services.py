"""منطق اصلی: پروفایل، matching سه‌لایه، رزومه. (ایجنت‌ها از اینجا ابزار می‌گیرند.)"""
import asyncio
import json
import re
from datetime import datetime
from threading import Lock

from sqlalchemy import or_
from sqlalchemy.orm import Session

from . import prompts
from .config import S
from .llm import chat_json, cosine, embed
from .jobs import job_key, level as job_level, norm, search_jobs
from .models import Job, Match, Profile, Resume, User
from .schemas import (JobExtract, MatchBatch, ProfileData, ResumeContent, SummaryOut)

# ponytail: one-process upsert lock; a unique canonical-key column is needed before using multiple workers.
_jobs_lock = Lock()


# ---------- پروفایل ----------
def get_profile(db: Session, user: User) -> Profile:
    p = db.query(Profile).filter_by(user_id=user.id).first()
    if not p:
        p = Profile(user_id=user.id, data=ProfileData().model_dump(), messages=[], summary_en="", ready=False)
        db.add(p)
        db.commit()
    return p


def merge_profile(old: ProfileData, patch: dict, union: bool = False) -> ProfileData:
    """ادغام امن: مقدار خالی چیزی را پاک نمی‌کند. union=True برای لیست‌ها اضافه‌کردن است (مثل مهارت جدید)."""
    d = old.model_dump()
    for k, v in patch.items():
        if k == "excluded_job_ids" or v in ("", None, [], {}):
            continue
        if union and isinstance(v, list) and isinstance(d.get(k), list):
            d[k] += [i for i in v if i not in d[k]]
        else:
            d[k] = v
    return ProfileData.model_validate(d)


def meets_minimum(p: ProfileData) -> bool:
    return bool(p.name and p.target_role and len(p.skills) >= 2)


def completeness(p: ProfileData) -> tuple[int, list[str]]:
    checks = [
        ("نام", bool(p.name)), ("شهر", bool(p.city)), ("سطح تجربه", bool(p.level)),
        ("نقش هدف", bool(p.target_role)), ("ترجیح دورکاری", bool(p.remote_pref)),
        ("مهارت‌ها (حداقل ۲)", len(p.skills) >= 2),
        ("پروژه، سابقه یا تحصیلات", bool(p.projects or p.experience or p.education)),
    ]
    missing = [n for n, ok in checks if not ok]
    return round(100 * (len(checks) - len(missing)) / len(checks)), missing


# ---------- آگهی‌ها ----------
def job_dict(j: Job) -> dict:
    return {"id": j.id, "title": j.title, "company": j.company, "location": j.location, "remote": j.remote,
            "level": j.level, "skills": j.skills or [], "description": j.description, "url": j.url,
            "source": j.source, "needs_review": not j.level or not j.location}


def visible_jobs(db: Session, user: User) -> list[Job]:
    return db.query(Job).filter(Job.source != "sample", or_(Job.owner_id.is_(None), Job.owner_id == user.id)).all()


def ensure_embeddings(db: Session, jobs: list[Job]) -> None:
    todo = [j for j in jobs if not j.embedding and j.summary_en]
    if not todo:
        return
    vecs = embed([j.summary_en for j in todo])
    if vecs:
        for j, v in zip(todo, vecs):
            j.embedding = v
        db.commit()


def hard_filter(p: ProfileData, jobs: list[Job]) -> list[Job]:
    """لایهٔ ۱: فیلتر سخت بدون مدل (سطح، دورکاری/شهر، انطباق استک/حوزه و آگهی‌های ردشده)."""
    levels = {j: job_level({"title": j.title, "level": j.level, "text": j.description}) for j in jobs}
    allowed = {"intern": {"intern"}, "junior": {"intern", "junior", ""}, "mid": {"mid", ""}, "senior": {"senior", ""}}.get(p.level)
    ok = [j for j in jobs if (allowed is None or levels[j] in allowed) and j.id not in p.excluded_job_ids]

    role = norm(p.target_role)
    if role:
        is_ai = bool(re.search(r"هوش مصنوعی|یادگیری ماشین|machine learning|deep learning|\bai\b|data scien|علم داده|پردازش تصویر|پردازش زبان|computer vision|\bnlp\b|\bllm\b", role))
        is_devops = bool(re.search(r"دواپس|دوآپس|devops|زیرساخت|infrastructure|sysadmin|ادمین لینوکس|\bsre\b|cloud", role))
        is_mobile = bool(re.search(r"موبایل|mobile|فلاتر|flutter|اندروید|android|\bios\b|swift|سویفت|react native", role))
        is_frontend = bool(re.search(r"فرانت|front.?end|ui developer", role))
        is_backend = bool(re.search(r"بک اند|back.?end", role))

        if is_ai:
            ok = [j for j in ok if re.search(r"هوش مصنوعی|یادگیری ماشین|machine learning|deep learning|\bai\b|data|علم داده|پردازش|computer vision|\bnlp\b|\bllm\b|پایتون|python|الگوریتم", norm(j.title + " " + j.description))]
        elif is_devops:
            ok = [j for j in ok if re.search(r"devops|دوآپس|دواپس|زیرساخت|infrastructure|sysadmin|لینوکس|linux|cloud|docker|داکر|kubernetes|کوبرنتیز|\bsre\b", norm(j.title + " " + j.description))]
        elif is_mobile:
            ok = [j for j in ok if re.search(r"موبایل|mobile|flutter|فلاتر|android|اندروید|ios|swift|سویفت|react native|کاتلین|kotlin", norm(j.title + " " + j.description))]
        elif is_frontend:
            ok = [j for j in ok if re.search(r"front.?end|فرانت|ui|web|وب|react|ریکت|vue|ویو|angular|next|javascript|typescript", norm(j.title + " " + j.description))]
        elif is_backend:
            ok = [j for j in ok if re.search(r"back.?end|بک اند|سرور|سرویس|python|پایتون|django|fastapi|golang|go|node|java|جاوا|spring|php|laravel|لاراول|\.net|c#|سی شارپ|پایگاه داده|دیتابیس", norm(j.title + " " + j.description))]
        elif re.search(r"developer|programmer|software|برنامه نویس|توسعه دهنده|مهندس نرم افزار", role):
            ok = [j for j in ok if re.search(r"developer|programmer|software (?:engineer|intern)?|برنامه نویس|توسعه دهنده|مهندس نرم افزار|front.?end|back.?end|full.?stack|کارآموز|\bintern\b", norm(j.title))]
            if "python" in role or "پایتون" in role:
                ok = [j for j in ok if re.search(r"\bpython\b|پایتون", norm(j.description))]

    if p.remote_pref == "remote":
        ok = [j for j in ok if j.remote]
    elif p.remote_pref in ("onsite", "hybrid") and p.city:
        ok = [j for j in ok if norm(p.city) in norm(j.location) and (p.remote_pref == "hybrid" or not j.remote)]
        if p.remote_pref == "hybrid":
            ok = [j for j in ok if re.search(r"\bhybrid\b|هیبرید|ترکیبی", norm(j.description))]
    elif p.remote_pref == "city_or_remote" and p.city:
        ok = [j for j in ok if j.remote or norm(p.city) in norm(j.location)]
    return ok


def rank(db: Session, p: ProfileData, summary_en: str, jobs: list[Job], k: int) -> list[Job]:
    """لایهٔ ۲: embedding روی خلاصه‌های انگلیسی؛ اگر در دسترس نبود، هم‌پوشانی مهارت‌ها."""
    ensure_embeddings(db, jobs)
    vec = embed([summary_en]) if summary_en and all(j.embedding for j in jobs) else None
    if vec and all(j.embedding for j in jobs):
        scored = sorted(jobs, key=lambda j: cosine(vec[0], j.embedding), reverse=True)
    else:
        mine = {s.lower() for s in p.skills}
        scored = sorted(jobs, key=lambda j: len(mine & {s.lower() for s in (j.skills or [])}), reverse=True)
    return scored[:k]


def profile_summary_en(db: Session, user: User, prof: Profile) -> str:
    if not prof.summary_en:
        out = chat_json(db, user.id, "utility", S.model_utility, prompts.PROFILE_SUMMARY,
                        [{"role": "user", "content": json.dumps(prof.data, ensure_ascii=False)}], SummaryOut)
        prof.summary_en = out.summary_en
        db.commit()
    return prof.summary_en


def score_jobs(db: Session, user: User, prof: Profile, jobs: list[Job]) -> list[Match]:
    """لایهٔ ۳: امتیاز و توضیح تناسب با LLM (یک فراخوانی برای همهٔ کاندیدها)."""
    payload = {"profile": prof.data,
               "jobs": [{"job_id": j.id, "title": j.title, "company": j.company, "location": j.location,
                         "remote": j.remote, "level": j.level, "skills": j.skills, "description": j.description}
                        for j in jobs]}
    out = chat_json(db, user.id, "matcher", S.model_matcher, prompts.MATCH,
                    [{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}], MatchBatch)
    valid = {j.id for j in jobs}
    saved = []
    received = set()
    for r in out.results:
        if r.job_id not in valid:
            continue
        received.add(r.job_id)
        m = db.query(Match).filter_by(user_id=user.id, job_id=r.job_id).first() or Match(user_id=user.id, job_id=r.job_id)
        m.score, m.why_fit, m.gaps = max(0, min(100, r.score)), r.why_fit[:3], r.gaps[:3]
        db.add(m)
        saved.append(m)
    for j in jobs:
        if j.id in received:
            continue
        m = db.query(Match).filter_by(user_id=user.id, job_id=j.id).first() or Match(user_id=user.id, job_id=j.id)
        m.score, m.why_fit, m.gaps = 0, [], ["مدل برای این آگهی امتیاز برنگرداند؛ متن منبع را بررسی کن."]
        db.add(m)
        saved.append(m)
    db.commit()
    return saved


def run_match(db: Session, user: User) -> dict:
    prof = get_profile(db, user)
    p = ProfileData.model_validate(prof.data)
    found = asyncio.run(search_jobs(p))
    search = {k: v for k, v in found.items() if k != "jobs"}
    if all(s["status"] == "error" for s in found["sources"]):
        return {"matches": list_matches(db, user), "search": dict(search, stale=True)}
    current = []
    with _jobs_lock:
        existing = {job_key(j.source, j.url): j for j in visible_jobs(db, user) if j.owner_id is None}
        for data in found["jobs"]:
            key = data.get("key") or job_key(data["source"], data["url"])
            j = existing.get(key) or Job(source=data["source"], title=data["title"])
            changed = j.description != data["description"]
            for field in ("source", "url", "title", "company", "location", "remote", "level", "skills", "description"):
                setattr(j, field, data[field])
            if changed:
                j.summary_en, j.embedding = "", None
            db.add(j)
            existing[key] = j
            current.append(j)
        db.commit()
    current.extend(db.query(Job).filter_by(owner_id=user.id, source="pasted").all())
    filtered = hard_filter(p, current)
    summary = profile_summary_en(db, user, prof) if S.embedding_model and filtered and all(j.embedding or j.summary_en for j in filtered) else ""
    candidates = rank(db, p, summary, filtered, len(filtered)) if filtered else []
    if candidates:
        score_jobs(db, user, prof, candidates)
    keep = {j.id for j in candidates}
    for m in db.query(Match).filter_by(user_id=user.id).all():  # نتایج قبلی که دیگر کاندید نیستند
        if m.job_id not in keep:
            db.delete(m)
    db.commit()
    return {"matches": list_matches(db, user), "search": search}


def list_matches(db: Session, user: User) -> list[dict]:
    prof = get_profile(db, user)
    profile = ProfileData.model_validate(prof.data)
    rows = (db.query(Match, Job).join(Job, Job.id == Match.job_id)
            .filter(Match.user_id == user.id).order_by(Match.score.desc()).all())
    allowed = {j.id for j in hard_filter(profile, [j for _, j in rows])}
    return [{"job": job_dict(j), "score": m.score, "why_fit": m.why_fit, "gaps": m.gaps}
            for m, j in rows if j.id in allowed and j.source != "sample"]


def add_pasted_job(db: Session, user: User, text: str) -> Job:
    ex = chat_json(db, user.id, "utility", S.model_utility, prompts.JOB_EXTRACT,
                   [{"role": "user", "content": text[:6000]}], JobExtract)
    j = Job(owner_id=user.id, source="pasted", title=ex.title, company=ex.company, location=ex.location,
            remote=ex.remote, level=ex.level, skills=ex.skills, description=ex.description or text[:400],
            summary_en=ex.summary_en)
    db.add(j)
    db.commit()
    return j


# ---------- رزومه ----------
def _guard_skills(content: ResumeContent, p: ProfileData) -> ResumeContent:
    """محافظ ضدجعل: مهارتی که در پروفایل نیست از رزومه حذف می‌شود."""
    known = [s.lower() for s in p.skills] + [t.lower() for pr in p.projects for t in pr.tech]
    content.skills = [s for s in content.skills if any(s.lower() in k or k in s.lower() for k in known)]
    return content


def generate_resume(db: Session, user: User, job: Job, lang: str = "fa", instructions: str = "") -> Resume:
    prof = get_profile(db, user)
    p = ProfileData.model_validate(prof.data)
    lang = "en" if lang == "en" else "fa"
    system = prompts.RESUME.format(lang_name="فارسی" if lang == "fa" else "English")
    payload = {"profile": {k: v for k, v in prof.data.items() if k != "excluded_job_ids"},
               "job": job_dict(job), "revision_instructions": instructions}
    out = chat_json(db, user.id, "writer", S.model_writer, system,
                    [{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}], ResumeContent)
    out = _guard_skills(out, p)
    r = db.query(Resume).filter_by(user_id=user.id, job_id=job.id, lang=lang).first()
    if r:
        r.content, r.version, r.updated_at = out.model_dump(), r.version + 1, datetime.utcnow()
    else:
        r = Resume(user_id=user.id, job_id=job.id, lang=lang, content=out.model_dump())
        db.add(r)
    db.commit()
    return r

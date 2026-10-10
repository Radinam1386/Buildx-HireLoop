"""منطق اصلی: پروفایل، matching سه‌لایه، رزومه. (ایجنت‌ها از اینجا ابزار می‌گیرند.)"""
import asyncio
import hashlib
import json
import re
from datetime import datetime
from threading import Lock

from sqlalchemy import or_, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import prompts
from .config import RESUME_SECTION_ORDER, S
from .llm import chat_json, cosine, embed
from .jobs import job_key, level as job_level, norm, search_jobs
from .models import Job, Match, Profile, Resume, User
from .schemas import (
    ContactData,
    Edu,
    Exp,
    HonorItem,
    JobExtract,
    MatchBatch,
    ProfileData,
    Proj,
    ResumeContent,
    ResumeExp,
    ResumeProj,
    SkillItem,
    SummaryOut,
    skill_names,
)

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
        elif isinstance(v, dict) and isinstance(d.get(k), dict):
            # Nested merge for dicts like contact
            merged_dict = dict(d[k])
            for sub_k, sub_v in v.items():
                if sub_v not in ("", None, [], {}):
                    merged_dict[sub_k] = sub_v
            d[k] = merged_dict
        else:
            d[k] = v
    return ProfileData.model_validate(d)


def meets_minimum(p: ProfileData) -> bool:
    names = skill_names(p)
    return bool(p.target_role.strip() and len({norm(s) for s in names if s.strip()}) >= 2)


def coverage_report(p: ProfileData) -> dict[str, str]:
    """گزارش وضعیت بخش‌های رزومه: empty / weak / ok / declined."""
    declined = set(p.declined_sections or [])

    # ۱. هویت و اطلاعات تماس
    has_contact = bool(
        p.contact.email.strip()
        or p.contact.phone.strip()
        or p.contact.city.strip()
        or p.city.strip()
        or p.contact.linkedin.strip()
        or p.contact.github.strip()
    )
    if p.name.strip():
        id_status = "ok" if (has_contact and (p.headline.strip() or p.target_role.strip())) else "weak"
    else:
        id_status = "empty"

    # ۲. نقش هدف و سطح تجربه
    if p.target_role.strip() and p.level.strip():
        role_status = "ok"
    elif p.target_role.strip() or p.level.strip():
        role_status = "weak"
    else:
        role_status = "empty"

    # ۳. خلاصهٔ حرفه‌ای / اهداف شغلی
    if "summary" in declined:
        sum_status = "declined"
    elif p.goals.strip() and len(p.goals.strip()) >= 25:
        sum_status = "ok"
    elif p.goals.strip():
        sum_status = "weak"
    else:
        sum_status = "empty"

    # ۴. مهارت‌ها (با سطح و ابزارها)
    names = skill_names(p)
    has_levels_or_tools = any(bool(s.level.strip() or s.tools) for s in p.skills)
    if not names:
        skill_status = "empty"
    elif len(names) >= 2 and has_levels_or_tools:
        skill_status = "ok"
    else:
        skill_status = "weak"

    # ۵. پروژه‌ها
    if "projects" in declined:
        proj_status = "declined"
    elif not p.projects:
        proj_status = "empty"
    else:
        weak_projs = [
            pr for pr in p.projects
            if not pr.name.strip() or not pr.tech or len(pr.description.strip()) < 25
        ]
        proj_status = "weak" if weak_projs else "ok"

    # ۶. سابقهٔ کاری
    if "experience" in declined:
        exp_status = "declined"
    elif not p.experience:
        exp_status = "empty"
    else:
        weak_exp = [
            ex for ex in p.experience
            if not ex.title.strip() or not ex.org.strip() or len(ex.details.strip()) < 25
        ]
        exp_status = "weak" if weak_exp else "ok"

    # ۷. تحصیلات
    if "education" in declined:
        edu_status = "declined"
    elif not p.education:
        edu_status = "empty"
    else:
        weak_edu = [ed for ed in p.education if not (ed.degree.strip() or ed.school.strip())]
        edu_status = "weak" if weak_edu else "ok"

    # ۸. افتخارات و دستاوردها
    if "honors" in declined:
        hon_status = "declined"
    elif not p.honors:
        hon_status = "empty"
    else:
        weak_hon = [h for h in p.honors if not h.title.strip()]
        hon_status = "weak" if weak_hon else "ok"

    # ۹. زبان‌ها
    if "languages" in declined:
        lang_status = "declined"
    elif not p.languages:
        lang_status = "empty"
    else:
        weak_lang = [l for l in p.languages if not l.name.strip() or not l.level.strip()]
        lang_status = "weak" if weak_lang else "ok"

    # ۱۰. گواهینامه‌ها
    if "certifications" in declined:
        cert_status = "declined"
    elif not p.certifications:
        cert_status = "empty"
    else:
        cert_status = "ok"

    # ۱۱. لینک‌ها
    has_links = bool(p.links or p.contact.github or p.contact.linkedin or p.contact.website)
    if "links" in declined:
        links_status = "declined"
    elif has_links:
        links_status = "ok"
    else:
        links_status = "empty"

    return {
        "identity": id_status,
        "target_role_and_level": role_status,
        "summary": sum_status,
        "skills": skill_status,
        "projects": proj_status,
        "experience": exp_status,
        "education": edu_status,
        "honors": hon_status,
        "languages": lang_status,
        "certifications": cert_status,
        "links": links_status,
    }


def is_resume_ready(p: ProfileData) -> bool:
    """آیا پوشش اطلاعات برای ساخت رزومهٔ کامل و حرفه‌ای کافی است؟"""
    cov = coverage_report(p)
    # شرایط پایه برای آمادگی کامل رزومه
    has_proj_or_exp = bool(p.projects or p.experience)
    proj_ok = cov["projects"] in ("ok", "declined")
    exp_ok = cov["experience"] in ("ok", "declined")
    core_ready = (
        cov["identity"] == "ok"
        and cov["target_role_and_level"] in ("ok", "weak")
        and cov["skills"] in ("ok", "weak")
        and (len(skill_names(p)) >= 2)
        and (proj_ok or exp_ok)
        and has_proj_or_exp
        and cov["education"] in ("ok", "declined")
        and cov["languages"] in ("ok", "declined")
    )
    return core_ready


def completeness(p: ProfileData) -> tuple[int, list[str]]:
    """محاسبهٔ جامع درصد تکمیل و فهرست بخش‌های نیازمند بهبود."""
    cov = coverage_report(p)
    checks = [
        ("نام و اطلاعات تماس", cov["identity"] == "ok"),
        ("نقش هدف و سطح تجربه", cov["target_role_and_level"] == "ok"),
        ("مهارت‌ها با سطوح و ابزارها", cov["skills"] == "ok"),
        ("پروژه‌ها یا سابقهٔ کار با جزئیات", (cov["projects"] == "ok" or cov["experience"] == "ok" or ("projects" in p.declined_sections and "experience" in p.declined_sections))),
        ("تحصیلات و رشته", cov["education"] in ("ok", "declined")),
        ("زبان‌ها با سطح تسلط", cov["languages"] in ("ok", "declined")),
        ("افتخارات و دستاوردها", cov["honors"] in ("ok", "declined")),
        ("لینک‌های گیت‌هاب و لینکدین", cov["links"] in ("ok", "declined")),
    ]
    missing = [label for label, ok in checks if not ok]
    pct = round(100 * (len(checks) - len(missing)) / len(checks))
    return pct, missing


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
        mine = {s.lower() for s in skill_names(p)}
        scored = sorted(jobs, key=lambda j: len(mine & {s.lower() for s in (j.skills or [])}), reverse=True)
    return scored[:k]


def profile_summary_en(db: Session, user: User, prof: Profile) -> str:
    if not prof.summary_en:
        out = chat_json(db, user.id, "utility", S.model_utility, prompts.PROFILE_SUMMARY,
                        [{"role": "user", "content": ProfileData.model_validate(prof.data).model_dump_json()}], SummaryOut)
        prof.summary_en = out.summary_en
        db.commit()
    return prof.summary_en


def score_jobs(db: Session, user: User, prof: Profile, jobs: list[Job]) -> list[Match]:
    """لایهٔ ۳: امتیاز و توضیح تناسب با LLM (یک فراخوانی برای همهٔ کاندیدها)."""
    payload = {"profile": ProfileData.model_validate(prof.data).model_dump(exclude={"excluded_job_ids"}),
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
            remote=ex.remote, level=ex.level, skills=ex.skills, description=text,
            summary_en=ex.summary_en)
    db.add(j)
    db.commit()
    return j


# ---------- رزومه ----------
def resume_preparation(prof: Profile, job: Job) -> dict:
    p = ProfileData.model_validate(prof.data)
    fingerprint = hashlib.sha256(json.dumps([p.model_dump(), job_dict(job)], sort_keys=True,
                                            ensure_ascii=False).encode()).hexdigest()
    known = {norm(s) for s in skill_names(p)} | {norm(t) for pr in p.projects for t in pr.tech}
    questions = []
    seen = set()
    # ponytail: use the source's skill list, not another model call; add extraction only if sources lack useful skills.
    for skill in job.skills or []:
        key = norm(skill)
        if not key or key in known or key in seen:
            continue
        seen.add(key)
        questions.append({"id": f"skill:{key}", "skill": skill,
                          "question": f"در این آگهی «{skill}» خواسته شده. با آن کار کرده‌ای؟ اگر بله، در چه پروژه‌ای و چه کاری انجام داده‌ای؟"})
        if len(questions) == 2:
            break
    # ponytail: short descriptions need evidence; explicit evidence fields can replace this heuristic later.
    unfinished = [(i, pr) for i, pr in enumerate(p.projects) if len(pr.description.strip()) < 60]
    if unfinished:
        i, pr = max(unfinished, key=lambda row: len({norm(t) for t in row[1].tech} & {norm(t) for t in job.skills or []}))
        questions.append({"id": f"project:{i}", "skill": "",
                          "question": f"در پروژهٔ «{pr.name}» کدام بخش را خودت ساختی و چه مسئله‌ای حل کردی؟ اگر نتیجه یا لینک واقعی داری، اضافه کن."})
    elif not p.projects and p.experience and len(p.experience[0].details.strip()) < 60:
        ex = p.experience[0]
        questions.append({"id": "experience:0", "skill": "",
                          "question": f"در سابقهٔ «{ex.title or ex.org}» چه مسئولیتی داشتی که به این آگهی مرتبط است؟ نتیجهٔ واقعی کارت را توضیح بده."})
    elif not p.projects and not p.experience:
        questions.append({"id": "evidence", "skill": "",
                          "question": "چه پروژه یا تمرین مرتبطی انجام داده‌ای؟ نام پروژه، سهم خودت، ابزارها و نتیجه را بگو؛ اگر تجربه‌ای نداری این سؤال را رد کن."})
    saved = (prof.data.get('_resume_prep') or {}).get(str(job.id), {})
    answers = {a['id']: a for a in saved.get('answers', [])} if saved.get('fingerprint') == fingerprint else {}
    for q in questions:
        a = answers.get(q['id'], {})
        q.update(status=a.get('status', 'skip'), answer=a.get('answer', ''))
    pct, missing = completeness(p)
    return {
        "job": job_dict(job),
        "profile": p.model_dump(exclude={"excluded_job_ids"}),
        "questions": questions,
        "fingerprint": fingerprint,
        "saved": saved.get('fingerprint') == fingerprint,
        "completeness": pct,
        "missing": missing,
        "coverage": coverage_report(p),
        "resume_ready": is_resume_ready(p),
    }


def save_preparation(db: Session, prof: Profile, job: Job, answers: list, fingerprint: str) -> dict:
    from fastapi import HTTPException
    prep = resume_preparation(prof, job)
    if fingerprint != prep['fingerprint']:
        raise HTTPException(409, "پروفایل یا آگهی تغییر کرده؛ صفحه را تازه کن و پاسخ‌ها را بررسی کن.")
    ids = [a.id for a in answers]
    if len(set(ids)) != len(ids) or not set(ids) <= {q['id'] for q in prep['questions']}:
        raise HTTPException(422, "سؤال‌ها تغییر کرده‌اند یا پاسخ تکراری است؛ صفحه را تازه کن.")
    saved = dict(prof.data.get('_resume_prep') or {})
    saved[str(job.id)] = {'fingerprint': prep['fingerprint'], 'answers': [a.model_dump() for a in answers]}
    prof.data = {**prof.data, '_resume_prep': saved}
    db.commit()
    return resume_preparation(prof, job)


def soft_match(claim: str, candidates: list[str]) -> bool:
    """تطبیق نرم برای جلوگیری از جعل: تطابق کامل، زیررشته یا تشابه واژگانی بالا."""
    if not claim or not candidates:
        return False
    nc = norm(claim).strip()
    if not nc:
        return False
    for cand in candidates:
        if not cand:
            continue
        n_cand = norm(cand).strip()
        if not n_cand:
            continue
        if nc == n_cand or nc in n_cand or n_cand in nc:
            return True
        w_claim = set(re.findall(r"\w+", nc.lower()))
        w_cand = set(re.findall(r"\w+", n_cand.lower()))
        if not w_claim or not w_cand:
            continue
        claim_coverage = len(w_claim & w_cand) / len(w_claim)
        if len(w_claim) <= 2:
            if claim_coverage >= 1.0:
                return True
        elif claim_coverage >= 0.6:
            return True
    return False


def _guard_skills(content: ResumeContent, p: ProfileData) -> ResumeContent:
    """محافظ ضدجعل تعمیم‌یافته: هر مهارت، افتخار، مدرک، پروژه، سابقه و شرکت باید با آیتم‌های پروفایل منطبق باشد."""
    known_skills = {norm(s) for s in skill_names(p)} | {norm(t) for pr in p.projects for t in pr.tech}
    allowed_skills_list = skill_names(p) + [t for pr in p.projects for t in pr.tech]

    # ۱. مهارت‌ها
    before_skills = list(content.skills)
    skill_indices = {}
    filtered_skills = []
    for old_idx, s in enumerate(before_skills):
        s_name = s.name if hasattr(s, "name") else str(s)
        if norm(s_name) in known_skills or soft_match(s_name, allowed_skills_list):
            new_idx = len(filtered_skills)
            skill_indices[old_idx] = new_idx
            if hasattr(s, "tools") and s.tools:
                s.tools = [t for t in s.tools if norm(t) in known_skills or soft_match(t, allowed_skills_list)]
            filtered_skills.append(s)
    content.skills = filtered_skills

    # ۲. پروژه‌ها
    raw_projects = [pr.model_copy(deep=True) for pr in content.projects]
    project_indices = {}
    tech_indices = {}
    filtered_projects = []
    proj_names = [pr.name for pr in p.projects]
    for old_idx, raw_pr in enumerate(raw_projects):
        if soft_match(raw_pr.name, proj_names):
            new_idx = len(filtered_projects)
            project_indices[old_idx] = new_idx
            orig = next((orig for orig in p.projects if soft_match(orig.name, [raw_pr.name])), None)
            allowed_tech = {norm(t) for t in orig.tech} if orig else known_skills
            allowed_tech_list = (orig.tech if orig else []) + allowed_skills_list
            before_tech = list(raw_pr.tech)
            filtered_tech = []
            for old_t_idx, t in enumerate(before_tech):
                if norm(t) in allowed_tech or soft_match(t, allowed_tech_list):
                    new_t_idx = len(filtered_tech)
                    tech_indices[(old_idx, old_t_idx)] = (new_idx, new_t_idx)
                    filtered_tech.append(t)
            new_pr = raw_pr.model_copy(deep=True)
            new_pr.tech = filtered_tech
            filtered_projects.append(new_pr)
    content.projects = filtered_projects

    # ۳. سابقهٔ کاری
    exp_candidates = (
        [f"{ex.title} {ex.org}" for ex in p.experience]
        + [ex.org for ex in p.experience if ex.org]
        + [ex.title for ex in p.experience if ex.title]
    )
    if not p.experience:
        content.experience = []
    else:
        content.experience = [
            ex for ex in content.experience
            if soft_match(f"{ex.title} {ex.org}", exp_candidates)
        ]

    # ۴. تحصیلات
    edu_candidates = (
        [f"{ed.degree} {ed.field} {ed.school}" for ed in p.education]
        + [ed.school for ed in p.education if ed.school]
        + [ed.degree for ed in p.education if ed.degree]
    )
    if not p.education:
        content.education = []
    else:
        content.education = [
            ed for ed in content.education
            if soft_match(f"{ed.degree} {ed.field} {ed.school}", edu_candidates)
        ]

    # ۵. افتخارات
    honor_candidates = [h.title for h in p.honors]
    if not p.honors:
        content.honors = []
    else:
        content.honors = [h for h in content.honors if soft_match(h.title, honor_candidates)]

    # ۶. گواهینامه‌ها
    cert_candidates = [c.name for c in p.certifications]
    if not p.certifications:
        content.certifications = []
    else:
        content.certifications = [c for c in content.certifications if soft_match(c.name, cert_candidates)]

    # ۷. زبان‌ها
    lang_candidates = [l.name for l in p.languages]
    if not p.languages:
        content.languages = []
    else:
        content.languages = [l for l in content.languages if soft_match(l.name, lang_candidates)]

    # ۸. بخش‌های تکمیلی
    extra_candidates = [es.title for es in p.extra_sections]
    if not p.extra_sections:
        content.extra_sections = []
    else:
        content.extra_sections = [es for es in content.extra_sections if soft_match(es.title, extra_candidates)]

    # به‌روزرسانی مسیرهای evidence برای پروژه‌ها و مهارت‌ها
    paths = {}
    for i in range(len(before_skills)):
        paths[f'skills.{i}'] = f'skills.{skill_indices[i]}' if i in skill_indices else None
    for i, orig_pr in enumerate(raw_projects):
        new_index = project_indices.get(i)
        if new_index is None:
            continue
        pr_dict = orig_pr.model_dump() if hasattr(orig_pr, 'model_dump') else orig_pr
        for old_path in resume_texts({'projects': [pr_dict]}):
            suffix = old_path.removeprefix('projects.0.')
            if suffix.startswith('tech.'):
                old_t_idx = int(suffix.split('.')[1])
                target_tech = tech_indices.get((i, old_t_idx))
                if target_tech:
                    paths[f'projects.{i}.{suffix}'] = f'projects.{target_tech[0]}.tech.{target_tech[1]}'
                else:
                    paths[f'projects.{i}.{suffix}'] = None
            else:
                target = f'projects.{new_index}.{suffix}'
                paths[f'projects.{i}.{suffix}'] = target

    refs = []
    for ref in content.evidence:
        if ref.path.startswith(('projects.', 'skills.')):
            target = paths.get(ref.path)
            if not target:
                continue
            ref.path = target
        refs.append(ref)
    content.evidence = refs
    return content


def resume_sources(p: ProfileData, answers: list) -> list[dict]:
    contact_parts = [
        p.name, p.name_en, p.headline, p.city, p.contact.city, p.contact.country,
        p.contact.email, p.contact.phone, p.contact.linkedin, p.contact.github, p.contact.website,
        *p.links
    ]
    sources = [
        {'id': 'profile:identity', 'label': 'نام و هویت و ارتباط', 'text': '\n'.join(filter(None, contact_parts))},
        {'id': 'profile:role', 'label': 'نقش و هدف شغلی', 'text': '\n'.join(filter(None, [p.target_role, p.level, p.goals]))},
        {'id': 'profile:skills', 'label': 'مهارت‌های ثبت‌شده',
         'text': ', '.join(f"{s.name} ({s.level}): {', '.join(s.tools)}" if (s.level or s.tools) else s.name for s in p.skills)},
        {'id': 'profile:languages', 'label': 'زبان‌های ثبت‌شده',
         'text': ', '.join(f"{l.name} ({l.level})" if l.level else l.name for l in p.languages)}
    ]
    for i, item in enumerate(p.education):
        sources.append({'id': f'education:{i}', 'label': f'تحصیلات: {item.degree} {item.school}',
                        'text': json.dumps(item.model_dump(), ensure_ascii=False)})
    for i, item in enumerate(p.honors):
        sources.append({'id': f'honors:{i}', 'label': f'افتخار: {item.title}',
                        'text': json.dumps(item.model_dump(), ensure_ascii=False)})
    for i, item in enumerate(p.projects):
        sources.append({'id': f'project:{i}', 'label': f'پروژه: {item.name}',
                        'text': json.dumps(item.model_dump(), ensure_ascii=False)})
    for i, item in enumerate(p.experience):
        sources.append({'id': f'experience:{i}', 'label': f'سابقه: {item.title or item.org}',
                        'text': json.dumps(item.model_dump(), ensure_ascii=False)})
    for i, item in enumerate(p.certifications):
        sources.append({'id': f'certifications:{i}', 'label': f'گواهی: {item.name}',
                        'text': json.dumps(item.model_dump(), ensure_ascii=False)})
    for i, item in enumerate(p.extra_sections):
        sources.append({'id': f'extra:{i}', 'label': f'بخش اضافه: {item.title}',
                        'text': json.dumps(item.model_dump(), ensure_ascii=False)})
    sources.extend({'id': f'answer:{a["id"]}', 'label': 'پاسخ تأییدشده برای این آگهی', 'text': a['answer']} for a in answers)
    return sources


def resume_texts(content: dict) -> dict[str, str]:
    texts = {k: str(content.get(k, '')) for k in ('name', 'name_en', 'headline', 'summary')}
    contact = content.get('contact')
    if isinstance(contact, dict):
        for k, v in contact.items():
            if v and str(v).strip():
                texts[f'contact.{k}'] = str(v).strip()
    elif isinstance(contact, list):
        for i, v in enumerate(contact):
            if v and str(v).strip():
                texts[f'contact.{i}'] = str(v).strip()

    skills = content.get('skills', [])
    for i, s in enumerate(skills):
        if isinstance(s, dict):
            if s.get('name'):
                texts[f'skills.{i}'] = str(s['name'])
            for j, t in enumerate(s.get('tools', [])):
                if t:
                    texts[f'skills.{i}.tools.{j}'] = str(t)
        elif isinstance(s, str) and s.strip():
            texts[f'skills.{i}'] = s.strip()

    languages = content.get('languages', [])
    for i, l in enumerate(languages):
        if isinstance(l, dict):
            if l.get('name'):
                texts[f'languages.{i}'] = str(l['name'])
        elif isinstance(l, str) and l.strip():
            texts[f'languages.{i}'] = l.strip()

    for key in ('experience', 'projects', 'education', 'honors', 'certifications'):
        for i, item in enumerate(content.get(key, [])):
            if not isinstance(item, dict):
                continue
            for field, value in item.items():
                if isinstance(value, list):
                    for j, v in enumerate(value):
                        if v and str(v).strip():
                            texts[f'{key}.{i}.{field}.{j}'] = str(v).strip()
                elif isinstance(value, str) and value.strip():
                    texts[f'{key}.{i}.{field}'] = value.strip()
    return {path: text for path, text in texts.items() if text.strip()}


def resume_evidence(content: dict, refs: list, sources: list) -> dict:
    known = {s['id']: s for s in sources}
    pointers = {r.path: list(dict.fromkeys(s for s in r.source_ids if s in known)) for r in refs}
    digits = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')
    numbers = lambda text: set(re.findall(r'\d+(?:[.٫]\d+)?', text.translate(digits)))
    all_numbers = numbers(' '.join(s['text'] for s in sources))
    claims, omitted = [], []
    for path, text in resume_texts(content).items():
        ids = pointers.get(path, [])
        if not ids:
            ids = [s['id'] for s in sources if text.casefold() in s['text'].casefold()]
        supported_numbers = numbers(' '.join(known[s]['text'] for s in ids)) if ids else all_numbers
        if (path == 'summary' or '.bullets.' in path or '.description' in path) and numbers(text) - supported_numbers:
            omitted.append({'path': path, 'text': text, 'reason': 'عدد این ادعا در منابع انتخاب‌شده پیدا نشد.'})
            continue
        claims.append({'path': path, 'text': text, 'source_ids': ids, 'review_required': not bool(ids), 'user_confirmed': False})
    for key in ('experience', 'projects'):
        for i, item in enumerate(content.get(key, [])):
            kept = []
            for j, text in enumerate(item.get('bullets', [])):
                old_path = f'{key}.{i}.bullets.{j}'
                claim = next((c for c in claims if c['path'] == old_path), None)
                if claim:
                    claim['path'] = f'{key}.{i}.bullets.{len(kept)}'
                    kept.append(text)
            item['bullets'] = kept
    if any(x['path'] == 'summary' for x in omitted):
        content['summary'] = ''
    return {'sources': sources, 'claims': claims, 'omitted': omitted}


def edit_resume(db: Session, user: User, body) -> Resume:
    from fastapi import HTTPException
    r = db.query(Resume).filter_by(user_id=user.id, job_id=body.job_id, lang=body.lang).first()
    if not r:
        raise HTTPException(404, 'رزومه پیدا نشد.')
    if r.version != body.version:
        raise HTTPException(409, 'رزومه تغییر کرده؛ نسخهٔ ذخیره‌شده را دوباره باز کن.')
    content = body.content.model_dump(exclude={'evidence'})
    if len(json.dumps(content, ensure_ascii=False)) > 50000:
        raise HTTPException(422, 'حجم رزومه بیش از حد مجاز است.')
    evidence = r.content.get('_evidence') or {'sources': [], 'claims': [], 'omitted': []}
    sources, claims = list(evidence['sources']), []
    old = resume_texts(r.content)
    old_claims = {c['path']: c for c in evidence['claims']}
    for path, text in resume_texts(content).items():
        if old.get(path) == text:
            claims.append(old_claims.get(path, {'path': path, 'text': text, 'source_ids': [], 'review_required': True, 'user_confirmed': False}))
        else:
            sid = f'user_edit:{r.version + 1}:{path}'
            sources.append({'id': sid, 'label': 'ویرایش و تأیید مستقیم کاربر', 'text': text})
            claims.append({'path': path, 'text': text, 'source_ids': [sid], 'review_required': False, 'user_confirmed': True})
    content['_evidence'] = {'sources': sources, 'claims': claims, 'omitted': evidence.get('omitted', [])}
    job = db.get(Job, body.job_id)
    required = {norm(s) for s in job.skills or []}
    included = {norm(s) for s in skill_names(content)} | {norm(t) for pr in content.get('projects', []) for t in (pr.get('tech') or [])}
    content['_tailoring'] = {'highlighted_skills': [s for s in skill_names(content) if norm(s) in required],
                            'projects': [pr.get('name', '') for pr in content.get('projects', []) if pr.get('name')],
                            'unconfirmed': [s for s in job.skills or [] if norm(s) not in included]}
    changed = db.execute(update(Resume).where(Resume.id == r.id, Resume.user_id == user.id, Resume.version == body.version)
                         .values(content=content, version=body.version + 1, updated_at=datetime.utcnow()),
                         execution_options={'synchronize_session': False})
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, 'رزومه در صفحهٔ دیگری تغییر کرده؛ دوباره باز کن.')
    db.commit(); db.refresh(r)
    return r


def generate_resume(db: Session, user: User, job: Job, lang: str = "fa", instructions: str = "") -> Resume:
    if job.owner_id not in (None, user.id):
        from fastapi import HTTPException
        raise HTTPException(404, "آگهی پیدا نشد.")
    prof = get_profile(db, user)
    p = ProfileData.model_validate(prof.data)
    prep = resume_preparation(prof, job)
    confirmed = [q for q in prep['questions'] if q['status'] == 'yes' and q['answer']]
    for q in confirmed:
        if q['skill'] and norm(q['skill']) not in {norm(s) for s in skill_names(p)}:
            p.skills.append(SkillItem(name=q['skill']))
    lang = "en" if lang == "en" else "fa"
    existing = db.query(Resume).filter_by(user_id=user.id, job_id=job.id, lang=lang).first()
    expected_version = existing.version if existing else None
    system = prompts.RESUME.format(lang_name="فارسی" if lang == "fa" else "English")
    from .analysis import cached_analysis
    sources = resume_sources(p, confirmed)
    analysis = cached_analysis(db, user, job)
    target = job_dict(job)
    if analysis:
        target['description'] = analysis['source_text']
        analysis = {k: v for k, v in analysis.items() if k not in ('source_text', 'scope_notice')}
    payload = {"profile": p.model_dump(exclude={"excluded_job_ids"}),
               "job": target, "analysis": analysis, "sources": sources,
               "confirmed_answers": confirmed, "revision_instructions": instructions}
    out = chat_json(db, user.id, "writer", S.model_writer, system,
                    [{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}], ResumeContent)
    out = _guard_skills(out, p)
    known = {norm(s) for s in skill_names(p)} | {norm(t) for pr in p.projects for t in pr.tech}
    tailoring = {"highlighted_skills": [s.name for s in out.skills if norm(s.name) in {norm(t) for t in job.skills or []}],
                 "projects": [pr.name for pr in out.projects],
                 "unconfirmed": [s for s in job.skills or [] if norm(s) not in known]}
    content = out.model_dump(exclude={'evidence'})
    evidence = resume_evidence(content, out.evidence, sources)
    content.update(_tailoring=tailoring, _evidence=evidence)
    r = existing
    if existing:
        changed = db.execute(update(Resume).where(Resume.id == existing.id, Resume.user_id == user.id,
                                                 Resume.version == expected_version)
                             .values(content=content, version=expected_version + 1, updated_at=datetime.utcnow()),
                             execution_options={'synchronize_session': False})
        if changed.rowcount != 1:
            db.rollback()
            from fastapi import HTTPException
            raise HTTPException(409, 'رزومه هنگام ساخت تغییر کرده؛ نسخهٔ ذخیره‌شده را دوباره باز کن.')
    else:
        r = Resume(user_id=user.id, job_id=job.id, lang=lang, content=content)
        db.add(r)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        from fastapi import HTTPException
        raise HTTPException(409, 'نسخهٔ دیگری ساخته شده؛ رزومهٔ ذخیره‌شده را دوباره باز کن.')
    db.refresh(r)
    return r

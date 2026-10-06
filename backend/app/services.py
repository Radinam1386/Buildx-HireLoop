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
    return bool(p.target_role.strip() and len({norm(s) for s in p.skills if s.strip()}) >= 2)


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
    known = {norm(s) for s in p.skills} | {norm(t) for pr in p.projects for t in pr.tech}
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
    return {"job": job_dict(job), "profile": p.model_dump(exclude={"excluded_job_ids"}),
            "questions": questions, "fingerprint": fingerprint,
            "saved": saved.get('fingerprint') == fingerprint}


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


def _guard_skills(content: ResumeContent, p: ProfileData) -> ResumeContent:
    """محافظ ضدجعل: مهارتی که در پروفایل نیست از رزومه حذف می‌شود."""
    known = {norm(s) for s in p.skills} | {norm(t) for pr in p.projects for t in pr.tech}
    before = content.model_dump(exclude={'evidence'})
    skill_indices = {old: new for new, old in enumerate(i for i, s in enumerate(content.skills) if norm(s) in known)}
    content.skills = [s for s in content.skills if norm(s) in known]
    projects = {norm(pr.name): pr for pr in p.projects}
    project_indices = {old: new for new, old in enumerate(i for i, pr in enumerate(content.projects) if norm(pr.name) in projects)}
    content.projects = [pr for pr in content.projects if norm(pr.name) in projects]
    for pr in content.projects:
        original = projects.get(norm(pr.name))
        allowed = {norm(t) for t in original.tech} if original else known
        pr.tech = [t for t in pr.tech if norm(t) in allowed]
    paths = {}
    for i, skill in enumerate(before['skills']):
        paths[f'skills.{i}'] = f'skills.{skill_indices[i]}' if i in skill_indices else None
    for i, pr in enumerate(before['projects']):
        new_index = project_indices.get(i)
        if new_index is None:
            continue
        for old_path in resume_texts({'projects': [pr]}):
            suffix = old_path.removeprefix('projects.0.')
            target = f'projects.{new_index}.{suffix}'
            if suffix.startswith('tech.'):
                allowed = {norm(t) for t in projects[norm(pr['name'])].tech}
                tech_indices = {old: new for new, old in enumerate(n for n, t in enumerate(pr['tech']) if norm(t) in allowed)}
                old_tech_index = int(suffix.split('.')[1])
                target = f'projects.{new_index}.tech.{tech_indices[old_tech_index]}' if old_tech_index in tech_indices else None
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
    sources = [{'id': 'profile:identity', 'label': 'نام و ارتباط', 'text': '\n'.join([p.name, p.city, *p.links])},
               {'id': 'profile:role', 'label': 'نقش و هدف شغلی', 'text': '\n'.join([p.target_role, p.level, p.goals])},
               {'id': 'profile:skills', 'label': 'مهارت‌های ثبت‌شده', 'text': ', '.join(p.skills)},
               {'id': 'profile:languages', 'label': 'زبان‌های ثبت‌شده', 'text': ', '.join(p.languages)}]
    for group, label in [('projects', 'پروژه'), ('experience', 'سابقه'), ('education', 'تحصیلات')]:
        for i, item in enumerate(getattr(p, group)):
            singular = {'projects': 'project', 'experience': 'experience', 'education': 'education'}[group]
            sources.append({'id': f'{singular}:{i}', 'label': f'{label}: {getattr(item, "name", None) or getattr(item, "org", None) or getattr(item, "school", "")}',
                            'text': json.dumps(item.model_dump(), ensure_ascii=False)})
    sources.extend({'id': f'answer:{a["id"]}', 'label': 'پاسخ تأییدشده برای این آگهی', 'text': a['answer']} for a in answers)
    return sources


def resume_texts(content: dict) -> dict[str, str]:
    texts = {k: content.get(k, '') for k in ('name', 'headline', 'summary')}
    for key in ('contact', 'skills', 'languages'):
        texts.update({f'{key}.{i}': v for i, v in enumerate(content.get(key, []))})
    for key in ('experience', 'projects', 'education'):
        for i, item in enumerate(content.get(key, [])):
            for field, value in item.items():
                if isinstance(value, list):
                    texts.update({f'{key}.{i}.{field}.{j}': v for j, v in enumerate(value)})
                elif isinstance(value, str):
                    texts[f'{key}.{i}.{field}'] = value
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
        if (path == 'summary' or '.bullets.' in path) and numbers(text) - supported_numbers:
            omitted.append({'path': path, 'text': text, 'reason': 'عدد این ادعا در منابع انتخاب‌شده پیدا نشد.'})
            continue
        claims.append({'path': path, 'text': text, 'source_ids': ids, 'review_required': not bool(ids), 'user_confirmed': False})
    # ponytail: source IDs and numbers are checked, not semantic truth; user review remains necessary.
    for key in ('experience', 'projects'):
        for i, item in enumerate(content.get(key, [])):
            kept = []
            for j, text in enumerate(item['bullets']):
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
    included = {norm(s) for s in content['skills']} | {norm(t) for pr in content['projects'] for t in pr['tech']}
    content['_tailoring'] = {'highlighted_skills': [s for s in content['skills'] if norm(s) in required],
                            'projects': [pr['name'] for pr in content['projects']],
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
    p.skills += [q['skill'] for q in confirmed if q['skill'] and q['skill'] not in p.skills]
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
    known = {norm(s) for s in p.skills} | {norm(t) for pr in p.projects for t in pr.tech}
    tailoring = {"highlighted_skills": [s for s in out.skills if norm(s) in {norm(t) for t in job.skills or []}],
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

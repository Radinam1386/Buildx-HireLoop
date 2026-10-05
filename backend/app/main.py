import re
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from . import agents, services as svc
from .auth import check_pw, current_user, hash_pw, make_token
from .config import S
from .db import Base, SessionLocal, engine, get_db
from .llm import LLMError
from .models import Job, Resume, Usage, User
from .schemas import (LoginIn, MessageIn, PasteIn, ProfileData, RefineIn, RegisterIn, ResumeIn)


@asynccontextmanager
async def lifespan(_):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="HireLoop API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=S.cors, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(LLMError)
async def llm_error(_, exc: LLMError):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=502, content={"detail": f"ارتباط با مدل ناموفق بود. {exc}"})


def _state(db: Session, user: User) -> dict:
    prof = svc.get_profile(db, user)
    p = ProfileData.model_validate(prof.data or {})
    pct, missing = svc.completeness(p)
    return {"messages": prof.messages or [], "profile": p.model_dump(exclude={"excluded_job_ids"}),
            "ready": prof.ready, "completeness": pct, "missing": missing}


def _resume_out(r: Resume, db: Session) -> dict:
    return {"content": r.content, "version": r.version, "lang": r.lang, "job": svc.job_dict(db.get(Job, r.job_id))}


def _own_job(db: Session, user: User, job_id: int) -> Job:
    j = db.get(Job, job_id)
    if not j or (j.owner_id not in (None, user.id)):
        raise HTTPException(404, "آگهی پیدا نشد.")
    return j


# ---------- Auth ----------
@app.get("/api/health")
def health():
    return {"ok": True}


@app.post("/api/auth/register")
def register(body: RegisterIn, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise HTTPException(400, "ایمیل معتبر نیست.")
    if len(body.password) < 6:
        raise HTTPException(400, "رمز عبور باید حداقل ۶ کاراکتر باشد.")
    if db.query(User).filter_by(email=email).first():
        raise HTTPException(409, "این ایمیل قبلاً ثبت‌نام کرده است.")
    u = User(email=email, name=body.name.strip(), password_hash=hash_pw(body.password))
    db.add(u)
    db.commit()
    return {"token": make_token(u.id), "user": {"id": u.id, "email": u.email, "name": u.name}}


@app.post("/api/auth/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    u = db.query(User).filter_by(email=body.email.strip().lower()).first()
    if not u or not check_pw(body.password, u.password_hash):
        raise HTTPException(401, "ایمیل یا رمز عبور درست نیست.")
    return {"token": make_token(u.id), "user": {"id": u.id, "email": u.email, "name": u.name}}


@app.get("/api/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "email": user.email, "name": user.name}


# ---------- Interview ----------
@app.get("/api/interview")
def interview_state(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _state(db, user)


@app.post("/api/interview/message")
def interview_message(body: MessageIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    agents.interview_turn(db, user, body.message)
    return _state(db, user)


@app.post("/api/interview/reset")
def interview_reset(user: User = Depends(current_user), db: Session = Depends(get_db)):
    prof = svc.get_profile(db, user)
    prof.data, prof.messages, prof.ready, prof.summary_en = ProfileData().model_dump(), [], False, ""
    db.commit()
    return _state(db, user)


# ---------- Matches ----------
@app.post("/api/matches/run")
def matches_run(user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = ProfileData.model_validate(svc.get_profile(db, user).data)
    if not svc.meets_minimum(p):
        raise HTTPException(400, "پروفایل هنوز کامل نیست؛ مصاحبه را ادامه دهید.")
    return svc.run_match(db, user)


@app.get("/api/matches")
def matches_list(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return {"matches": svc.list_matches(db, user)}


@app.post("/api/jobs/paste")
def jobs_paste(body: PasteIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if len(body.text.strip()) < 30:
        raise HTTPException(400, "متن آگهی خیلی کوتاه است.")
    prof = svc.get_profile(db, user)
    job = svc.add_pasted_job(db, user, body.text)
    svc.score_jobs(db, user, prof, [job])
    return {"matches": svc.list_matches(db, user), "job_id": job.id}


# ---------- Resume ----------
@app.get("/api/resumes")
def resume_list(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = (db.query(Resume, Job).join(Job, Job.id == Resume.job_id)
            .filter(Resume.user_id == user.id, or_(Job.owner_id.is_(None), Job.owner_id == user.id))
            .order_by(Resume.updated_at.desc(), Resume.id.desc()).all())
    return {"resumes": [{"job": svc.job_dict(j), "lang": r.lang, "version": r.version,
                         "updated_at": r.updated_at.isoformat()} for r, j in rows]}


@app.get("/api/resume")
def resume_get(job_id: int, lang: str = "fa", user: User = Depends(current_user), db: Session = Depends(get_db)):
    _own_job(db, user, job_id)
    r = db.query(Resume).filter_by(user_id=user.id, job_id=job_id, lang="en" if lang == "en" else "fa").first()
    return _resume_out(r, db) if r else None


@app.post("/api/resume")
def resume_make(body: ResumeIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    job = _own_job(db, user, body.job_id)
    return _resume_out(svc.generate_resume(db, user, job, body.lang, body.instructions), db)


# ---------- Refine ----------
@app.post("/api/refine")
def refine(body: RefineIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not body.message.strip():
        raise HTTPException(400, "بازخورد خالی است.")
    return agents.refine(db, user, body.message.strip(), body.job_id, body.lang)


# ---------- Usage (برای محاسبهٔ هزینه) ----------
@app.get("/api/usage")
def usage(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = (db.query(Usage.agent, func.sum(Usage.tokens_in), func.sum(Usage.tokens_out), func.count())
            .filter(Usage.user_id == user.id).group_by(Usage.agent).all())
    return {"by_agent": [{"agent": a, "tokens_in": int(i or 0), "tokens_out": int(o or 0), "calls": c} for a, i, o, c in rows]}

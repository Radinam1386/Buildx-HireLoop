"""ایجنت‌ها: Interviewer (چرخهٔ مصاحبه) و Refiner (گراف LangGraph که اقدام را انتخاب و اجرا می‌کند)."""
import json
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from . import prompts, services as svc
from .config import S
from .llm import chat_json
from .models import Job, Match, User
from .schemas import InterviewTurn, ProfileData, RefineDecision


# ---------- Interviewer ----------
def interview_turn(db: Session, user: User, message: str) -> dict:
    prof = svc.get_profile(db, user)
    history = list(prof.messages or [])
    if not message.strip() and not history:
        reply = "سلام! دنبال چه نقش یا حوزه‌ای از برنامه‌نویسی هستی و با چه ابزارهایی کار می‌کنی؟"
        prof.messages = [{"role": "assistant", "content": reply}]
        db.commit()
        return {"reply": reply, "profile": ProfileData.model_validate(prof.data).model_dump(), "ready": prof.ready}
    if message.strip():
        history.append({"role": "user", "content": message.strip()})
    llm_msgs = history[-12:] or [{"role": "user", "content": "یک سؤال کوتاه دربارهٔ نقش هدف یا مهارت‌های ثبت‌نشده بپرس."}]
    old = ProfileData.model_validate(prof.data or {})
    system = prompts.INTERVIEWER.format(profile=json.dumps(old.model_dump(exclude={"excluded_job_ids"}), ensure_ascii=False))
    turn = chat_json(db, user.id, "interviewer", S.model_interviewer, system, llm_msgs, InterviewTurn)
    new = svc.merge_profile(old, turn.profile.model_dump()) if turn.profile else old
    ready = svc.meets_minimum(new)
    history.append({"role": "assistant", "content": turn.reply})
    prof.data, prof.messages, prof.ready, prof.summary_en = {**prof.data, **new.model_dump()}, history, ready, ""
    db.commit()
    return {"reply": turn.reply, "profile": new.model_dump(), "ready": ready}


# ---------- Refiner (LangGraph) ----------
class RState(TypedDict, total=False):
    message: str
    job_id: int | None
    lang: str
    decision: RefineDecision
    changed: list[str]
    reply: str


def build_refine_graph(db: Session, user: User):
    prof = svc.get_profile(db, user)

    def decide(s: RState):
        p = ProfileData.model_validate(prof.data)
        system = prompts.REFINER.format(job_id=s.get("job_id"),
                                        profile=json.dumps(p.model_dump(exclude={"excluded_job_ids"}), ensure_ascii=False))
        d = chat_json(db, user.id, "refiner", S.model_refiner, system,
                      [{"role": "user", "content": s["message"]}], RefineDecision)
        if d.job_id is None:
            d.job_id = s.get("job_id")
        return {"decision": d, "reply": d.message}

    def route(s: RState):
        d = s["decision"]
        needs_job = d.action in ("exclude_job", "revise_resume")
        if d.action not in ("update_preferences", "exclude_job", "revise_resume") or (needs_job and not d.job_id):
            return "reply"
        return d.action

    def prefs(s: RState):
        p = ProfileData.model_validate(prof.data)
        patch = ProfileData.model_validate(s["decision"].patch).model_dump(exclude_unset=True)
        prof.data = {**prof.data, **svc.merge_profile(p, patch, union=True).model_dump()}
        prof.summary_en = ""
        db.commit()
        svc.run_match(db, user)
        return {"changed": ["profile", "matches"]}

    def exclude(s: RState):
        p = ProfileData.model_validate(prof.data)
        jid = s["decision"].job_id
        if jid not in p.excluded_job_ids:
            p.excluded_job_ids.append(jid)
        prof.data = {**prof.data, **p.model_dump()}
        for m in db.query(Match).filter_by(user_id=user.id, job_id=jid).all():
            db.delete(m)
        db.commit()
        return {"changed": ["matches"]}

    def revise(s: RState):
        job = db.get(Job, s["decision"].job_id)
        if not job:
            return {"reply": "آگهی پیدا نشد."}
        svc.generate_resume(db, user, job, s.get("lang", "fa"), s["decision"].instructions or s["message"])
        return {"changed": ["resume"]}

    g = StateGraph(RState)
    for name, fn in [("decide", decide), ("prefs", prefs), ("exclude", exclude), ("revise", revise),
                     ("reply", lambda s: {})]:
        g.add_node(name, fn)
    g.add_edge(START, "decide")
    g.add_conditional_edges("decide", route, {"update_preferences": "prefs", "exclude_job": "exclude",
                                              "revise_resume": "revise", "reply": "reply"})
    for n in ("prefs", "exclude", "revise", "reply"):
        g.add_edge(n, END)
    return g.compile()


def refine(db: Session, user: User, message: str, job_id: int | None, lang: str) -> dict:
    out = build_refine_graph(db, user).invoke({"message": message, "job_id": job_id, "lang": lang, "changed": []})
    return {"action": out["decision"].action, "reply": out.get("reply") or "انجام شد.",
            "changed": out.get("changed", []), "job_id": out["decision"].job_id}

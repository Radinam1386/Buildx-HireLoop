from typing import Any
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Lenient(BaseModel):
    """خروجی LLM گاهی null یا فیلد اضافه دارد؛ اینجا تحمل می‌شود."""
    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def _drop_none(cls, v: Any):
        return {k: x for k, x in v.items() if x is not None} if isinstance(v, dict) else v


class Edu(Lenient):
    degree: str = ""
    school: str = ""
    period: str = ""


class Exp(Lenient):
    title: str = ""
    org: str = ""
    period: str = ""
    details: str = ""


class Proj(Lenient):
    name: str = ""
    description: str = ""
    tech: list[str] = Field(default_factory=list)


class ProfileData(Lenient):
    name: str = ""
    city: str = ""
    level: str = ""            # intern | junior
    target_role: str = ""
    remote_pref: str = ""      # remote | hybrid | onsite | any
    skills: list[str] = Field(default_factory=list)
    education: list[Edu] = Field(default_factory=list)
    experience: list[Exp] = Field(default_factory=list)
    projects: list[Proj] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)
    goals: str = ""
    excluded_job_ids: list[int] = Field(default_factory=list)


class InterviewTurn(Lenient):
    reply: str
    profile: ProfileData | None = None
    ready: bool = False


class MatchItem(Lenient):
    job_id: int
    score: int = 0
    why_fit: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)


class MatchBatch(Lenient):
    results: list[MatchItem] = Field(default_factory=list)


class SummaryOut(Lenient):
    summary_en: str = ""


class JobExtract(Lenient):
    title: str = "آگهی بدون عنوان"
    company: str = ""
    location: str = ""
    remote: bool = False
    level: str = "junior"
    skills: list[str] = Field(default_factory=list)
    description: str = ""
    summary_en: str = ""


class ResumeExp(Lenient):
    title: str = ""
    org: str = ""
    period: str = ""
    bullets: list[str] = Field(default_factory=list)


class ResumeProj(Lenient):
    name: str = ""
    tech: list[str] = Field(default_factory=list)
    bullets: list[str] = Field(default_factory=list)


class ResumeContent(Lenient):
    name: str = ""
    headline: str = ""
    contact: list[str] = Field(default_factory=list)
    summary: str = ""
    skills: list[str] = Field(default_factory=list)
    experience: list[ResumeExp] = Field(default_factory=list)
    projects: list[ResumeProj] = Field(default_factory=list)
    education: list[Edu] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)


class RefineDecision(Lenient):
    action: str = "reply_only"   # update_preferences | exclude_job | revise_resume | reply_only
    patch: dict = Field(default_factory=dict)
    job_id: int | None = None
    instructions: str = ""
    message: str = ""


# ---- ورودی‌های API ----
class RegisterIn(BaseModel):
    email: str
    password: str
    name: str = ""


class LoginIn(BaseModel):
    email: str
    password: str


class MessageIn(BaseModel):
    message: str = ""


class PasteIn(BaseModel):
    text: str


class ResumeIn(BaseModel):
    job_id: int
    lang: str = "fa"
    instructions: str = ""


class RefineIn(BaseModel):
    message: str
    job_id: int | None = None
    lang: str = "fa"

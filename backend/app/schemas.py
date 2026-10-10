from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Lenient(BaseModel):
    """خروجی LLM گاهی null یا فیلد اضافه دارد؛ اینجا تحمل می‌شود."""
    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def _drop_none(cls, v: Any):
        return {k: x for k, x in v.items() if x is not None} if isinstance(v, dict) else v


class ContactData(Lenient):
    email: str = ""
    phone: str = ""
    city: str = ""
    country: str = ""
    linkedin: str = ""
    github: str = ""
    website: str = ""


class Edu(Lenient):
    degree: str = ""
    field: str = ""
    school: str = ""
    period: str = ""
    gpa: str = ""
    notes: str = ""


class Exp(Lenient):
    title: str = ""
    org: str = ""
    period: str = ""
    location: str = ""
    details: str = ""


class Proj(Lenient):
    name: str = ""
    role: str = ""
    link: str = ""
    period: str = ""
    tech: list[str] = Field(default_factory=list)
    description: str = ""


class SkillItem(Lenient):
    name: str = ""
    level: str = ""            # مقدماتی | متوسط | مسلط | پیشرفته
    tools: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _coerce_str(cls, v: Any):
        if isinstance(v, str):
            return {"name": v.strip()}
        return v


class LanguageItem(Lenient):
    name: str = ""
    level: str = ""

    @model_validator(mode="before")
    @classmethod
    def _coerce_str(cls, v: Any):
        if isinstance(v, str):
            return {"name": v.strip()}
        return v


class HonorItem(Lenient):
    title: str = ""
    issuer: str = ""
    year: str = ""
    location: str = ""
    description: str = ""

    @model_validator(mode="before")
    @classmethod
    def _coerce_str(cls, v: Any):
        if isinstance(v, str):
            return {"title": v.strip()}
        return v


class CertItem(Lenient):
    name: str = ""
    issuer: str = ""
    year: str = ""

    @model_validator(mode="before")
    @classmethod
    def _coerce_str(cls, v: Any):
        if isinstance(v, str):
            return {"name": v.strip()}
        return v


class ExtraSection(Lenient):
    title: str = ""
    items: list[str] = Field(default_factory=list)


def parse_contact_list_or_dict(c: Any, fallback_city: str = "") -> Any:
    if isinstance(c, ContactData):
        if fallback_city and not c.city:
            c.city = fallback_city
        return c
    if hasattr(c, "model_dump"):
        d = c.model_dump()
        if fallback_city and not d.get("city"):
            d["city"] = fallback_city
        return d
    if isinstance(c, dict):
        d = dict(c)
        if fallback_city and not d.get("city"):
            d["city"] = fallback_city
        return d
    if isinstance(c, list):
        contact_obj: dict[str, str] = {}
        for item in c:
            if not isinstance(item, str):
                continue
            item_str = item.strip()
            if "@" in item_str:
                contact_obj["email"] = item_str
            elif "linkedin.com" in item_str:
                contact_obj["linkedin"] = item_str
            elif "github.com" in item_str:
                contact_obj["github"] = item_str
            elif item_str.startswith("http"):
                contact_obj["website"] = item_str
            elif any(ch.isdigit() for ch in item_str) and len(item_str) >= 7:
                contact_obj["phone"] = item_str
            elif not contact_obj.get("city"):
                contact_obj["city"] = item_str
        if fallback_city and not contact_obj.get("city"):
            contact_obj["city"] = fallback_city
        return contact_obj
    return {"city": fallback_city} if fallback_city else {}


def skill_names(p: Any) -> list[str]:
    """استخراج اسامی مهارت‌ها به صورت لیست رشته از ProfileData، ResumeContent، dict یا list."""
    if p is None:
        return []
    if isinstance(p, list):
        items = p
    elif hasattr(p, "skills"):
        items = p.skills
    elif isinstance(p, dict):
        items = p.get("skills", [])
    else:
        return []

    names: list[str] = []
    for item in items:
        if isinstance(item, str):
            if item.strip():
                names.append(item.strip())
        elif hasattr(item, "name"):
            if getattr(item, "name", None) and str(item.name).strip():
                names.append(str(item.name).strip())
        elif isinstance(item, dict):
            n = item.get("name")
            if n and str(n).strip():
                names.append(str(n).strip())
    return list(dict.fromkeys(names))


class ProfileData(Lenient):
    name: str = ""
    name_en: str = ""
    headline: str = ""
    contact: ContactData = Field(default_factory=ContactData)
    city: str = ""
    level: str = ""            # intern | junior | mid | senior
    target_role: str = ""
    remote_pref: str = ""      # remote | hybrid | onsite | any | city_or_remote
    skills: list[SkillItem] = Field(default_factory=list)
    education: list[Edu] = Field(default_factory=list)
    experience: list[Exp] = Field(default_factory=list)
    projects: list[Proj] = Field(default_factory=list)
    languages: list[LanguageItem] = Field(default_factory=list)
    honors: list[HonorItem] = Field(default_factory=list)
    certifications: list[CertItem] = Field(default_factory=list)
    extra_sections: list[ExtraSection] = Field(default_factory=list)
    declined_sections: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)
    goals: str = ""
    excluded_job_ids: list[int] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _sync_contact(cls, v: Any):
        if isinstance(v, dict):
            c = v.get("contact")
            city = v.get("city", "")
            if c is not None or city:
                v["contact"] = parse_contact_list_or_dict(c, city)
        return v


class InterviewTurn(Lenient):
    reply: str
    profile: ProfileData | None = None
    ready: bool = False
    resume_ready: bool = False
    focus: str = ""


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
    level: str = ""
    skills: list[str] = Field(default_factory=list)
    description: str = ""
    summary_en: str = ""


class ResumeExp(Lenient):
    title: str = ""
    org: str = ""
    period: str = ""
    location: str = ""
    bullets: list[str] = Field(default_factory=list)


class ResumeProj(Lenient):
    name: str = ""
    role: str = ""
    link: str = ""
    period: str = ""
    tech: list[str] = Field(default_factory=list)
    bullets: list[str] = Field(default_factory=list)


class ResumeEvidence(Lenient):
    path: str = Field(max_length=160)
    source_ids: list[str] = Field(default_factory=list, max_length=20)


class ResumeContent(Lenient):
    name: str = ""
    name_en: str = ""
    headline: str = ""
    contact: ContactData = Field(default_factory=ContactData)
    summary: str = ""
    skills: list[SkillItem] = Field(default_factory=list)
    languages: list[LanguageItem] = Field(default_factory=list)
    education: list[Edu] = Field(default_factory=list)
    honors: list[HonorItem] = Field(default_factory=list)
    experience: list[ResumeExp] = Field(default_factory=list)
    projects: list[ResumeProj] = Field(default_factory=list)
    certifications: list[CertItem] = Field(default_factory=list)
    extra_sections: list[ExtraSection] = Field(default_factory=list)
    evidence: list[ResumeEvidence] = Field(default_factory=list, max_length=150)

    @model_validator(mode="before")
    @classmethod
    def _coerce_contact(cls, v: Any):
        if isinstance(v, dict):
            c = v.get("contact")
            if isinstance(c, list):
                contact_obj: dict[str, str] = {}
                for item in c:
                    if not isinstance(item, str):
                        continue
                    if "@" in item:
                        contact_obj["email"] = item
                    elif "linkedin.com" in item:
                        contact_obj["linkedin"] = item
                    elif "github.com" in item:
                        contact_obj["github"] = item
                    elif item.startswith("http"):
                        contact_obj["website"] = item
                    elif any(ch.isdigit() for ch in item) and len(item) >= 7:
                        contact_obj["phone"] = item
                    else:
                        contact_obj["city"] = item
                v["contact"] = contact_obj
        return v


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
    text: str = Field(min_length=30, max_length=12000)


class ResumeIn(BaseModel):
    job_id: int
    lang: str = "fa"
    instructions: str = ""


class ResumeEditIn(BaseModel):
    job_id: int = Field(gt=0)
    lang: Literal['fa', 'en'] = 'fa'
    version: int = Field(ge=1)
    content: ResumeContent


class PreparationAnswer(BaseModel):
    id: str = Field(max_length=180)
    status: Literal["yes", "no", "skip"] = "skip"
    answer: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def confirmed_detail(self):
        self.answer = self.answer.strip()
        if self.status == "yes" and not self.answer:
            raise ValueError("برای تأیید تجربه، توضیح کوتاهی بنویس.")
        return self


class PreparationIn(BaseModel):
    job_id: int = Field(gt=0)
    fingerprint: str = Field(min_length=64, max_length=64)
    answers: list[PreparationAnswer] = Field(default_factory=list, max_length=3)


class RefineIn(BaseModel):
    message: str
    job_id: int | None = None
    lang: str = "fa"

from typing import Annotated
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator

Short = Annotated[str, Field(max_length=200)]
Text = Annotated[str, Field(max_length=3000)]


class Project(BaseModel):
    name: Short = ''
    description: Text = ''
    url: Short = ''

    @field_validator('url')
    @classmethod
    def safe_url(cls, value):
        if value and (urlparse(value).scheme not in ('https','http') or not urlparse(value).netloc):
            raise ValueError('لینک پروژه باید با https:// یا http:// شروع شود.')
        return value


class Experience(BaseModel):
    company: Short = ''
    role: Short = ''
    description: Text = ''


class Profile(BaseModel):
    model_config = ConfigDict(extra='ignore')
    full_name: Short = ''
    email: Short = ''
    phone: Short = ''
    city: Short = ''
    remote: bool = False
    skills: list[Short] = Field(default_factory=list,max_length=40)
    projects: list[Project] = Field(default_factory=list,max_length=12)
    experience: list[Experience] = Field(default_factory=list,max_length=12)
    education: list[Short] = Field(default_factory=list,max_length=10)
    languages: list[Short] = Field(default_factory=list,max_length=10)
    summary: Text = ''
    confirmed: bool = False


class AuthInput(BaseModel):
    name: str = Field(default='',max_length=100)
    email: str = Field(min_length=5,max_length=200)
    password: str = Field(min_length=8,max_length=128)

    @field_validator('email')
    @classmethod
    def email_shape(cls, value):
        value = value.strip().lower()
        if '@' not in value or any(c.isspace() for c in value) or '.' not in value.rsplit('@',1)[1]:
            raise ValueError('ایمیل معتبر وارد کنید.')
        return value


class MessageInput(BaseModel):
    message: str = Field(min_length=1,max_length=4000)


class Job(BaseModel):
    id: Short = ''
    title: str = Field(default='',max_length=300)
    company: Short = ''
    location: Short = ''
    url: str = Field(default='',max_length=2000)
    source: Short = ''
    description: str = Field(default='',max_length=12000)
    skills: list[Short] = Field(default_factory=list,max_length=40)
    verified: bool = False
    evidence_type: Short = 'user_text'
    checked_at: Short = ''

    @field_validator('url')
    @classmethod
    def safe_url(cls, value):
        if value and (urlparse(value).scheme not in ('https','http') or not urlparse(value).netloc):
            raise ValueError('لینک آگهی معتبر نیست.')
        return value


class SearchInput(BaseModel):
    query: str = Field(default='فرانت اند',min_length=1,max_length=120)
    city: Short = ''
    remote: bool = False
    sources: list[Short] | None = Field(default=None,max_length=4)


class MatchInput(BaseModel):
    jobs: list[Job] = Field(min_length=1,max_length=12)


class ResumeInput(BaseModel):
    job: Job = Field(default_factory=Job)
    job_text: str = Field(default='',max_length=12000)


class FeedbackInput(BaseModel):
    feedback: str = Field(min_length=1,max_length=3000)

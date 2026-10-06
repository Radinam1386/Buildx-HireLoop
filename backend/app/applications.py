from copy import deepcopy
from datetime import date as Date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import JSON, ForeignKey, String, Text, UniqueConstraint, or_, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from .auth import current_user
from .db import Base, get_db
from .models import Job, Resume, User, now
from .services import job_dict

router = APIRouter(prefix='/api/applications')
Status = Literal['saved', 'sent', 'interview', 'rejected', 'offer']


class Application(Base):
    __tablename__ = 'applications'
    __table_args__ = (UniqueConstraint('user_id', 'job_id'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey('jobs.id'))
    status: Mapped[str] = mapped_column(String(20), default='saved')
    date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default='')
    resume_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    version: Mapped[int] = mapped_column(default=1)


class Changes(BaseModel):
    status: Status = 'saved'
    date: str | None = None
    notes: str = Field(default='', max_length=5000)
    resume_lang: Literal['fa', 'en'] | None = None
    resume_version: int | None = Field(default=None, ge=1)

    @model_validator(mode='after')
    def valid(self):
        if self.date is not None and Date.fromisoformat(self.date).isoformat() != self.date:
            raise ValueError('Use YYYY-MM-DD')
        if (self.resume_lang is None) != (self.resume_version is None):
            raise ValueError('Select resume language and version together')
        return self


class Create(Changes):
    job_id: int = Field(gt=0)


class Edit(Changes):
    version: int = Field(ge=1)


def own_job(db, user, job_id):
    job = db.get(Job, job_id)
    if not job or job.owner_id not in (None, user.id):
        raise HTTPException(404, 'آگهی پیدا نشد.')
    return job


def own_application(db, user, application_id):
    row = db.query(Application).filter_by(id=application_id, user_id=user.id).first()
    if not row:
        raise HTTPException(404, 'درخواست پیدا نشد.')
    own_job(db, user, row.job_id)
    return row


def output(db, row):
    return {key: getattr(row, key) for key in ('id', 'status', 'date', 'notes', 'version', 'resume_snapshot')} | {'job': job_dict(db.get(Job, row.job_id))}


def snapshot(db, user, job_id, body):
    resume = db.query(Resume).filter_by(user_id=user.id, job_id=job_id, lang=body.resume_lang).first()
    if not resume or resume.version != body.resume_version:
        raise HTTPException(409, 'نسخهٔ رزومه تغییر کرده است؛ دوباره آن را انتخاب کن.')
    return {'lang': resume.lang, 'version': resume.version, 'updated_at': resume.updated_at.isoformat(),
            'captured_at': now().isoformat(), 'content': deepcopy(resume.content)}


@router.get('')
def listing(job_id: int | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(Application).join(Job).filter(Application.user_id == user.id, or_(Job.owner_id.is_(None), Job.owner_id == user.id))
    if job_id is not None:
        own_job(db, user, job_id)
        rows = rows.filter(Application.job_id == job_id)
    return {'applications': [output(db, row) for row in rows.order_by(Application.id.desc()).all()]}


@router.post('')
def create(body: Create, user: User = Depends(current_user), db: Session = Depends(get_db)):
    own_job(db, user, body.job_id)
    row = db.query(Application).filter_by(user_id=user.id, job_id=body.job_id).first()
    if row:
        return output(db, row)
    row = Application(user_id=user.id, job_id=body.job_id, status=body.status, date=body.date, notes=body.notes,
                      resume_snapshot=snapshot(db, user, body.job_id, body) if body.resume_lang else None)
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        row = db.query(Application).filter_by(user_id=user.id, job_id=body.job_id).one()
    return output(db, row)


@router.patch('/{application_id}')
def edit(application_id: int, body: Edit, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = own_application(db, user, application_id)
    changes = body.model_dump(exclude_unset=True, exclude={'version', 'resume_lang', 'resume_version'})
    if body.resume_lang:
        changes['resume_snapshot'] = snapshot(db, user, row.job_id, body)
    changed = db.execute(update(Application).where(Application.id == row.id, Application.version == body.version)
                         .values(**changes, version=Application.version + 1))
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, 'درخواست تغییر کرده است؛ صفحه را تازه کن و دوباره ذخیره کن.')
    db.commit()
    db.refresh(row)
    return output(db, row)


@router.get('/{application_id}/resume')
def saved_resume(application_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return own_application(db, user, application_id).resume_snapshot

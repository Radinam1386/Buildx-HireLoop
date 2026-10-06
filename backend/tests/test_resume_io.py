from io import BytesIO
from zipfile import ZipFile
from xml.etree import ElementTree as ET

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import resume_io
from app.auth import current_user
from app.db import Base, get_db
from app.main import profile_edit
from app.models import Job, Profile, Resume, User


def test_import_review_and_export(monkeypatch):
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(email='io@test.local', password_hash='unused')
        db.add(user); db.flush()
        profile = Profile(user_id=user.id, data={'name': 'قبلی', 'skills': ['Python'], 'excluded_job_ids': [8], '_private': 'secret'}, messages=[{'role': 'user', 'content': 'history'}])
        job = Job(title='Public')
        private = Job(title='Private', owner_id=user.id + 99)
        db.add_all([profile, job, private]); db.flush()
        resume = Resume(user_id=user.id, job_id=job.id, lang='fa', version=3, content={'name': 'سارا & <نام>', 'skills': ['Python'], '_tailoring': {'secret': 'internal'}, 'experience': [{'title': 'توسعه', 'bullets': ['واقعی & <نتیجه>']} ]})
        db.add(resume); db.commit()
        app = FastAPI(); app.include_router(resume_io.router)
        app.add_api_route('/api/profile', profile_edit, methods=['PATCH'])
        app.dependency_overrides[current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: db
        calls = []
        def fake(*args, **kwargs):
            calls.append(args)
            return kwargs['schema'].model_validate({'profile': {'skills': ['React'], 'excluded_job_ids': [999]}})
        monkeypatch.setattr(resume_io, 'chat_json', fake)
        with TestClient(app) as client:
            assert client.post('/api/profile/import', json={'text': 'short'}).status_code == 422
            assert client.post('/api/profile/import', json={'text': ' ' * 70}).status_code == 422
            result = client.post('/api/profile/import', json={'text': 'Existing resume with React projects and actual experience. ' * 2 + 'Contact: candidate@example.test; Portfolio: https://example.test/work.'})
            assert result.status_code == 200, result.text
            proposal = result.json()['profile']
            assert proposal['name'] == 'قبلی' and proposal['skills'] == ['Python', 'React']
            assert 'candidate@example.test' in proposal['links'] and 'https://example.test/work' in proposal['links']
            assert 'excluded_job_ids' not in proposal
            assert len(calls) == 1
            db.refresh(profile)
            assert profile.data['skills'] == ['Python'] and profile.messages[0]['content'] == 'history'
            assert client.patch('/api/profile', json=proposal).status_code == 200
            db.refresh(profile)
            assert profile.data['_private'] == 'secret' and profile.data['excluded_job_ids'] == [8]
            assert profile.messages[0]['content'] == 'history'
            out = client.get(f'/api/resume/export?job_id={job.id}&lang=fa')
            assert out.status_code == 200
            assert 'HireLoop-fa-v3.docx' in out.headers['content-disposition']
            with ZipFile(BytesIO(out.content)) as doc:
                assert {'[Content_Types].xml', '_rels/.rels', 'word/document.xml'} <= set(doc.namelist())
                raw = doc.read('word/document.xml').decode()
                ET.fromstring(raw)
                assert 'سارا &amp; &lt;نام&gt;' in raw and '<w:bidi w:val="1"' in raw
                assert 'internal' not in raw and '_tailoring' not in raw
            resume.lang = 'en'; db.commit()
            english = client.get(f'/api/resume/export?job_id={job.id}&lang=en')
            with ZipFile(BytesIO(english.content)) as doc:
                assert '<w:bidi w:val="0"' in doc.read('word/document.xml').decode()
            assert client.get(f'/api/resume/export?job_id={job.id}&lang=de').status_code == 422
            assert client.get(f'/api/resume/export?job_id={private.id}&lang=fa').status_code == 404
            assert client.get('/api/resume/export?job_id=999999&lang=fa').status_code == 404
            assert len(calls) == 1

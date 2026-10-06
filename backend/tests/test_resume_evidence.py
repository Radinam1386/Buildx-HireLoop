"""Evidence and manual edits stay attached to the saved version, without provider calls."""
import json

from fastapi.testclient import TestClient

from app import services
from app.db import SessionLocal
from app.main import app
from app.models import Job, Resume, User
from app.schemas import ResumeContent


def test_resume_sources_edits_and_numeric_claims(monkeypatch):
    def writer(db, uid, agent, model, system, messages, schema):
        payload = json.loads(messages[0]['content'])
        assert payload['sources'][0]['id'] == 'profile:identity'
        assert any(s['id'] == 'project:0' for s in payload['sources'])
        return ResumeContent.model_validate({'name': 'سارا', 'headline': 'Backend developer',
            'skills': ['Python'], 'summary': 'Built a cart API.',
            'projects': [{'name': 'Shop', 'tech': ['Python'], 'bullets': ['Implemented cart validation.', 'Reduced latency by 90%.']}],
            'evidence': [{'path': 'summary', 'source_ids': ['project:0']},
                         {'path': 'projects.0.bullets.0', 'source_ids': ['project:0', 'invented:0']},
                         {'path': 'projects.0.bullets.1', 'source_ids': ['project:0']}]})
    monkeypatch.setattr(services, 'chat_json', writer)
    with TestClient(app) as c:
        token = c.post('/api/auth/register', json={'email': 'evidence-edit@example.test', 'password': 'secret1'}).json()['token']
        h = {'Authorization': f'Bearer {token}'}
        c.patch('/api/profile', headers=h, json={'name': 'سارا', 'target_role': 'Backend', 'skills': ['Python', 'FastAPI'],
            'projects': [{'name': 'Shop', 'tech': ['Python'], 'description': 'Implemented cart validation in my local shop API project.'}]})
        with SessionLocal() as db:
            job = Job(title='Backend developer', source='jobvision', description='Python API development', skills=['Python'])
            db.add(job); db.commit(); jid = job.id
        made = c.post('/api/resume', headers=h, json={'job_id': jid}).json()
        assert made['content']['projects'][0]['bullets'] == ['Implemented cart validation.']
        assert next(x for x in made['evidence']['claims'] if x['path'] == 'projects.0.bullets.0')['source_ids'] == ['project:0']
        assert made['evidence']['omitted'][0]['text'] == 'Reduced latency by 90%.'
        assert 'evidence' not in made['content'] and all(not k.startswith('_') for k in made['content'])
        original_source = made['evidence']['sources']
        def no_ai(*a, **kw):
            raise AssertionError('Manual edits and GET must not use a model')
        monkeypatch.setattr(services, 'chat_json', no_ai)
        content = made['content']
        content['summary'] = 'I built and tested shopping-cart input validation.'
        body = {'job_id': jid, 'lang': 'fa', 'version': 1, 'content': content}
        edit = c.patch('/api/resume', headers=h, json=body)
        assert edit.status_code == 200, edit.text
        edited = edit.json()
        assert edited['version'] == 2
        claim = next(x for x in edited['evidence']['claims'] if x['path'] == 'summary')
        assert claim['user_confirmed'] and not claim['review_required']
        assert next(s for s in edited['evidence']['sources'] if s['id'] == claim['source_ids'][0])['text'] == content['summary']
        assert c.patch('/api/resume', headers=h, json=body).status_code == 409
        c.patch('/api/profile', headers=h, json={'projects': []})
        saved = c.get(f'/api/resume?job_id={jid}', headers=h).json()
        assert saved['version'] == 2 and saved['evidence']['sources'][:len(original_source)] == original_source
        token2 = c.post('/api/auth/register', json={'email': 'evidence-other@example.test', 'password': 'secret1'}).json()['token']
        assert c.patch('/api/resume', headers={'Authorization': f'Bearer {token2}'}, json={**body, 'version': 2}).status_code == 404


def test_filtering_preserves_the_correct_project_source(monkeypatch):
    monkeypatch.setattr(services, 'chat_json', lambda *a, **k: ResumeContent.model_validate({
        'skills': ['Docker', 'Python'], 'projects': [{'name': 'Invented', 'tech': ['Docker'], 'bullets': ['False claim.']},
            {'name': 'Shop', 'tech': ['Docker', 'Python'], 'bullets': ['Created 2 validation endpoints.']}],
        'evidence': [{'path': 'projects.1.bullets.0', 'source_ids': ['project:0']},
                     {'path': 'projects.1.tech.1', 'source_ids': ['project:0']},
                     {'path': 'skills.1', 'source_ids': ['profile:skills']}] }))
    with TestClient(app) as c:
        token = c.post('/api/auth/register', json={'email': 'evidence-filter@example.test', 'password': 'secret1'}).json()['token']
        h = {'Authorization': f'Bearer {token}'}
        c.patch('/api/profile', headers=h, json={'skills': ['Python'], 'projects': [{'name': 'Shop', 'tech': ['Python'], 'description': 'I implemented 2 cart API endpoints with input checks.'}]})
        with SessionLocal() as db:
            job = Job(title='Backend', source='jobvision', skills=['Python'])
            db.add(job); db.commit(); jid = job.id
        made = c.post('/api/resume', headers=h, json={'job_id': jid}).json()
        assert [p['name'] for p in made['content']['projects']] == ['Shop']
        claim = next(x for x in made['evidence']['claims'] if x['path'] == 'projects.0.bullets.0')
        assert claim['source_ids'] == ['project:0'] and not claim['review_required']


def test_slow_generation_cannot_replace_a_manual_save(monkeypatch):
    with TestClient(app) as c:
        token = c.post('/api/auth/register', json={'email': 'evidence-race@example.test', 'password': 'secret1'}).json()['token']
        h = {'Authorization': f'Bearer {token}'}
        uid = c.get('/api/me', headers=h).json()['id']
        with SessionLocal() as db:
            job = Job(title='Backend', source='jobvision')
            db.add(job); db.commit(); jid = job.id
            db.add(Resume(user_id=uid, job_id=jid, lang='fa', version=1, content=ResumeContent(summary='Original').model_dump()))
            db.commit()
        def concurrent_save(*a, **k):
            with SessionLocal() as other:
                r = other.query(Resume).filter_by(user_id=uid, job_id=jid).one()
                r.content = ResumeContent(summary='Confirmed manual edit').model_dump()
                r.version = 2
                other.commit()
            return ResumeContent(summary='Late model output')
        monkeypatch.setattr(services, 'chat_json', concurrent_save)
        assert c.post('/api/resume', headers=h, json={'job_id': jid}).status_code == 409
        assert c.get(f'/api/resume?job_id={jid}', headers=h).json()['content']['summary'] == 'Confirmed manual edit'


def test_duplicate_names_and_values_keep_positional_sources():
    from app.schemas import ProfileData
    content = ResumeContent.model_validate({'skills': ['Unknown', 'Python', 'Python'],
        'projects': [{'name': 'Shop', 'tech': ['Unknown', 'Python', 'Python'], 'bullets': ['First']},
                     {'name': 'Shop', 'tech': ['Python'], 'bullets': ['Second']}],
        'evidence': [{'path': 'projects.0.bullets.0', 'source_ids': ['project:0']},
                     {'path': 'projects.1.bullets.0', 'source_ids': ['answer:second']},
                     {'path': 'skills.2', 'source_ids': ['profile:skills']},
                     {'path': 'projects.0.tech.2', 'source_ids': ['project:0']}]})
    guarded = services._guard_skills(content, ProfileData(skills=['Python'], projects=[{'name': 'Shop', 'tech': ['Python']}]))
    paths = {r.path: r.source_ids for r in guarded.evidence}
    assert paths['projects.0.bullets.0'] == ['project:0']
    assert paths['projects.1.bullets.0'] == ['answer:second']
    assert paths['skills.1'] == ['profile:skills'] and paths['projects.0.tech.1'] == ['project:0']

"""Preparation must keep unconfirmed requirements out of the candidate's resume."""
import json

from fastapi.testclient import TestClient

from app import agents, services
from app.db import SessionLocal
from app.main import app
from app.llm import LLMError
from app.models import Job
from app.schemas import InterviewTurn, ProfileData, ResumeContent


def account(c, email):
    token = c.post('/api/auth/register', json={'email': email, 'password': 'secret1'}).json()['token']
    return {'Authorization': f'Bearer {token}'}


def test_profile_can_clear_fields_without_erasing_history(monkeypatch):
    monkeypatch.setattr(agents, 'chat_json', lambda *a, **k: InterviewTurn(
        reply='ثبت شد', profile=ProfileData(target_role='Backend', skills=['Python', 'FastAPI']), ready=False))
    with TestClient(app) as c:
        h = account(c, 'profile-edit@example.test')
        state = c.post('/api/interview/message', json={'message': 'Python و FastAPI'}, headers=h).json()
        assert state['ready']  # Optional name and model readiness must not block search.
        saved = c.patch('/api/profile', json={'skills': [], 'city': ''}, headers=h)
        assert saved.status_code == 200
        assert saved.json()['profile']['skills'] == []
        assert not saved.json()['ready']
        assert saved.json()['messages'] == state['messages']
        assert saved.json()['profile']['target_role'] == 'Backend'
        assert c.patch('/api/profile', headers=h, json={'level': 'expert'}).status_code == 422


def test_job_answers_are_private_persistent_and_used_only_when_confirmed(monkeypatch):
    def writer(db, uid, agent, model, system, messages, schema):
        payload = json.loads(messages[0]['content'])
        assert payload['confirmed_answers'][0]['skill'] == 'PostgreSQL'
        assert payload['confirmed_answers'][0]['answer'] == 'طراحی جداول و کوئری در پروژه فروشگاه'
        assert all(a['skill'] != 'Docker' for a in payload['confirmed_answers'])
        return ResumeContent(name='سارا', skills=['Python', 'PostgreSQL', 'Docker', 'Java'],
                             projects=[{'name': 'Shop', 'tech': ['Python', 'Docker']}])

    monkeypatch.setattr(services, 'chat_json', writer)
    with TestClient(app) as c:
        h = account(c, 'prep-owner@example.test')
        other = account(c, 'prep-other@example.test')
        assert c.patch('/api/profile', headers=h, json={'name': 'سارا', 'target_role': 'Backend',
            'skills': ['Python', 'FastAPI'], 'projects': [{'name': 'Shop', 'tech': ['Python']}]}).status_code == 200
        with SessionLocal() as db:
            job = Job(title='Backend', skills=['Python', 'PostgreSQL', 'Docker'], description='PostgreSQL Docker', source='jobvision')
            db.add(job); db.commit(); jid = job.id
        url = f'/api/resume/preparation?job_id={jid}'
        assert c.get(url).status_code == 401
        prep = c.get(url, headers=h).json()
        questions = prep['questions']
        assert len(questions) <= 3
        assert [q['skill'] for q in questions[:2]] == ['PostgreSQL', 'Docker']
        answers = [{'id': q['id'], 'status': 'skip', 'answer': ''} for q in questions]
        answers[0].update(status='yes', answer='طراحی جداول و کوئری در پروژه فروشگاه')
        answers[1].update(status='no', answer='تجربه ندارم')
        body = {'job_id': jid, 'fingerprint': prep['fingerprint'], 'answers': answers}
        saved = c.post('/api/resume/preparation', headers=h, json=body)
        assert saved.status_code == 200
        assert c.get(url, headers=h).json()['questions'][0]['answer'] == answers[0]['answer']
        assert c.get(url, headers=other).json()['questions'][0]['status'] == 'skip'
        assert [s['name'] if isinstance(s, dict) else s for s in c.get('/api/interview', headers=h).json()['profile']['skills']] == ['Python', 'FastAPI']
        bad = [{'id': questions[0]['id'], 'status': 'yes', 'answer': ''}]
        assert c.post('/api/resume/preparation', headers=h, json={**body, 'answers': bad}).status_code == 422
        assert c.post('/api/resume/preparation', headers=h, json={**body, 'answers': [answers[0], answers[0]]}).status_code == 422
        made = c.post('/api/resume', headers=h, json={'job_id': jid}).json()
        assert [s['name'] if isinstance(s, dict) else s for s in made['content']['skills']] == ['Python', 'PostgreSQL']
        assert made['content']['projects'][0]['tech'] == ['Python']
        assert 'Docker' in made['tailoring']['unconfirmed']
        assert 'PostgreSQL' in made['tailoring']['highlighted_skills']
        assert c.get(f'/api/resume?job_id={jid}', headers=h).json()['version'] == 1

        def failed_writer(*args, **kwargs):
            raise LLMError('provider unavailable')

        monkeypatch.setattr(services, 'chat_json', failed_writer)
        assert c.post('/api/resume', headers=h, json={'job_id': jid}).status_code == 502
        assert c.get(f'/api/resume?job_id={jid}', headers=h).json()['content'] == made['content']
        c.patch('/api/profile', headers=h, json={'skills': ['Python'], 'projects': [{'name': 'Shop', 'tech': ['Python'],
            'description': 'I implemented the cart API, database tables and checkout validation myself. The app is a local practice project.'}]})
        assert c.get(url, headers=h).json()['questions'][0]['status'] == 'skip'  # Profile changed: re-confirm.
        assert len(c.get(url, headers=h).json()['questions']) == 2  # Do not repeat a filled project question.
        assert c.post('/api/resume/preparation', headers=h, json=body).status_code == 409


def test_private_job_cannot_be_prepared_by_another_user():
    with TestClient(app) as c:
        owner = account(c, 'private-prep-owner@example.test')
        other = account(c, 'private-prep-other@example.test')
        uid = c.get('/api/me', headers=owner).json()['id']
        with SessionLocal() as db:
            j = Job(title='Private', source='pasted', owner_id=uid)
            db.add(j); db.commit(); jid = j.id
        assert c.get(f'/api/resume/preparation?job_id={jid}', headers=other).status_code == 404
        assert c.post('/api/resume/preparation', headers=other, json={'job_id': jid, 'fingerprint': '0' * 64, 'answers': []}).status_code == 404

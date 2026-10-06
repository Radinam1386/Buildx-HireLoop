from fastapi.testclient import TestClient

from app import practice
from app.db import SessionLocal
from app.main import app
from app.llm import LLMError
from app.models import Job


def account(client, email):
    token = client.post('/api/auth/register', json={'email': email, 'password': 'secret1'}).json()['token']
    return {'Authorization': f'Bearer {token}'}


def test_practice_persists_caps_followups_and_preserves_failed_answers(monkeypatch):
    calls = []
    def model(*args, **kwargs):
        schema = args[6]
        calls.append(schema)
        if schema is practice.Questions:
            return schema(questions=[{'text': f'Question {i}', 'kind': 'technical' if i < 3 else 'behavioral'} for i in range(5)])
        return schema(scores={k: 3 for k in practice.SCORE_KEYS}, feedback='Your example needs a concrete result.',
                      example_answer='Describe your actual result; do not invent numbers.', followup='What was your result?')
    monkeypatch.setattr(practice, 'chat_json', model)
    with TestClient(app) as c:
        h = account(c, 'practice-owner@example.test')
        other = account(c, 'practice-other@example.test')
        with SessionLocal() as db:
            j = Job(title='Backend', description='Full job description with Python and collaboration.', level='junior')
            db.add(j); db.commit(); jid = j.id
        url = f'/api/practice?job_id={jid}'
        assert c.get(url, headers=h).json()['session'] is None
        state = c.post('/api/practice/start', headers=h, json={'job_id': jid}).json()['session']
        assert c.post('/api/practice/start', headers=h, json={'job_id': jid}).json()['session'] == state
        assert len(calls) == 1
        assert c.get(url, headers=h).json()['session'] == state
        assert 'questions' not in state and 'example_answer' not in str(state)
        answer_url = f"/api/practice/{state['id']}/answer"
        body = {'version': state['version'], 'question_id': state['current_question']['id'], 'answer': 'I built a Python API.'}
        assert c.post(answer_url, headers=other, json=body).status_code == 404
        assert c.post(answer_url, headers=h, json={**body, 'answer': '  '}).status_code == 422
        def fail(*a, **k):
            raise LLMError('offline')
        monkeypatch.setattr(practice, 'chat_json', fail)
        assert c.post(answer_url, headers=h, json=body).status_code == 502
        assert c.get(url, headers=h).json()['session'] == state
        monkeypatch.setattr(practice, 'chat_json', lambda *a, **k: {'scores': {}})
        assert c.post(answer_url, headers=h, json=body).status_code == 502
        assert c.get(url, headers=h).json()['session'] == state
        monkeypatch.setattr(practice, 'chat_json', model)
        for i in range(10):
            previous = state
            body = {'version': state['version'], 'question_id': state['current_question']['id'], 'answer': 'I built a Python API.'}
            response = c.post(answer_url, headers=h, json=body)
            assert response.status_code == 200, response.text
            state = response.json()['session']
            assert c.post(answer_url, headers=h, json=body).status_code == 409
            assert state['version'] == previous['version'] + 1
        assert state['completed'] and state['total_answered'] == 10 and state['primary_answered'] == 5
        assert state['current_question'] is None and state['report']['scores']['clarity'] == 3
        assert len(calls) == 11  # Report and reads require no model call.
        assert c.get(url, headers=other).json()['session'] is None
        assert c.get('/api/interview', headers=h).json()['profile']['skills'] == []
        assert c.post('/api/practice/start', headers=h, json={'job_id': jid, 'restart': True}).status_code == 409
        assert len(calls) == 11
        restarted = c.post('/api/practice/start', headers=h, json={'job_id': jid, 'restart': True, 'version': state['version']}).json()['session']
        assert restarted['id'] == state['id'] and restarted['history'] == []
        assert restarted['version'] == state['version'] + 1


def test_practice_invalid_questions_and_private_job(monkeypatch):
    monkeypatch.setattr(practice, 'chat_json', lambda *a, **k: {'questions': [{'text': ' ', 'kind': 'technical'}] * 5})
    with TestClient(app) as c:
        h = account(c, 'practice-private-owner@example.test')
        other = account(c, 'practice-private-other@example.test')
        uid = c.get('/api/me', headers=h).json()['id']
        with SessionLocal() as db:
            j = Job(title='Private', owner_id=uid)
            db.add(j); db.commit(); jid = j.id
        assert c.post('/api/practice/start', headers=other, json={'job_id': jid}).status_code == 404
        assert c.get(f'/api/practice?job_id={jid}', headers=other).status_code == 404
        assert c.post('/api/practice/start', headers=h, json={'job_id': jid}).status_code == 502
        assert c.get(f'/api/practice?job_id={jid}', headers=h).json()['session'] is None


def test_practice_without_followups_and_competing_write(monkeypatch):
    def model(*args, **kwargs):
        schema = args[6]
        if schema is practice.Questions:
            return schema(questions=[{'text': f'Question {i}', 'kind': 'technical' if i < 3 else 'behavioral'} for i in range(5)])
        return schema(scores={k: 4 for k in practice.SCORE_KEYS}, feedback='Concrete answer.', example_answer='Actual example.', followup=None)
    monkeypatch.setattr(practice, 'chat_json', model)
    with TestClient(app) as c:
        h = account(c, 'practice-short@example.test')
        with SessionLocal() as db:
            job = Job(title='Backend')
            db.add(job); db.commit(); jid = job.id
        state = c.post('/api/practice/start', headers=h, json={'job_id': jid}).json()['session']
        url = f"/api/practice/{state['id']}/answer"
        def competing_model(*args, **kwargs):
            with SessionLocal() as db:
                row = db.get(practice.PracticeSession, state['id'])
                row.version += 1
                db.commit()
            return model(*args, **kwargs)
        monkeypatch.setattr(practice, 'chat_json', competing_model)
        body = {'version': state['version'], 'question_id': state['current_question']['id'], 'answer': 'I wrote an API.'}
        assert c.post(url, headers=h, json=body).status_code == 409
        state = c.get(f'/api/practice?job_id={jid}', headers=h).json()['session']
        assert state['history'] == [] and state['version'] == 2
        monkeypatch.setattr(practice, 'chat_json', model)
        for _ in range(5):
            state = c.post(url, headers=h, json={'version': state['version'], 'question_id': state['current_question']['id'], 'answer': 'I wrote an API.'}).json()['session']
        assert state['completed'] and state['total_answered'] == 5

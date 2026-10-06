from importlib.util import find_spec


def test_applications_module_exists():
    assert find_spec('app.applications') is not None, 'Private application tracking is missing'


def test_tracking_is_private_versioned_and_preserves_sent_content(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from app import agents, services
    from app.applications import router
    from app.auth import current_user
    from app.db import Base, get_db
    from app.models import Job, Resume, User

    def forbidden(*args, **kwargs):
        raise AssertionError('Tracker must never call AI')
    for module in (agents, services):
        monkeypatch.setattr(module, 'chat_json', forbidden)
    monkeypatch.setattr(services, 'embed', forbidden)
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as db:
        users = [User(email=f'tracker{i}@test.example', password_hash='unused') for i in range(2)]
        db.add_all(users); db.flush()
        public = Job(title='Public')
        private = Job(title='Private', owner_id=users[1].id)
        db.add_all([public, private]); db.flush()
        resume = Resume(user_id=users[0].id, job_id=public.id, lang='fa', content={'name': 'Original'}, version=1)
        db.add(resume); db.commit()
        job_id, private_id, resume_id = public.id, private.id, resume.id
    active_user = [users[0]]
    def database():
        with Session() as db:
            yield db
    app = FastAPI(); app.include_router(router)
    app.dependency_overrides[get_db] = database
    app.dependency_overrides[current_user] = lambda: active_user[0]
    with TestClient(app) as client:
        created = client.post('/api/applications', json={'job_id': job_id, 'status': 'sent', 'resume_lang': 'fa', 'resume_version': 1})
        assert created.status_code == 200
        row = created.json(); ident = row['id']
        assert row['resume_snapshot']['content'] == {'name': 'Original'}
        duplicate = client.post('/api/applications', json={'job_id': job_id})
        assert duplicate.json() == row
        with Session() as db:
            resume = db.get(Resume, resume_id)
            resume.content = {'name': 'Regenerated'}; resume.version = 2; db.commit()
        edited = client.patch(f'/api/applications/{ident}', json={'version': 1, 'status': 'interview', 'date': '2026-10-06', 'notes': 'Meeting'})
        assert edited.status_code == 200
        assert edited.json()['version'] == 2
        assert client.get(f'/api/applications/{ident}/resume').json()['content'] == {'name': 'Original'}
        assert client.patch(f'/api/applications/{ident}', json={'version': 1, 'notes': 'Stale'}).status_code == 409
        assert client.patch(f'/api/applications/{ident}', json={'version': 2, 'resume_lang': 'fa', 'resume_version': 1}).status_code == 409
        for invalid in ({'date': '2026-02-30'}, {'date': '20261006'}, {'notes': 'x' * 5001}, {'status': 'unknown'}, {'resume_lang': 'en'}):
            assert client.patch(f'/api/applications/{ident}', json={'version': 2, **invalid}).status_code == 422
        assert client.post('/api/applications', json={'job_id': private_id}).status_code == 404
        assert client.get(f'/api/applications?job_id={private_id}').status_code == 404
        active_user[0] = users[1]
        assert client.get('/api/applications').json() == {'applications': []}
        assert client.get(f'/api/applications/{ident}/resume').status_code == 404
        assert client.patch(f'/api/applications/{ident}', json={'version': 2, 'status': 'offer'}).status_code == 404
        active_user[0] = users[0]
        attached = client.patch(f'/api/applications/{ident}', json={'version': 2, 'resume_lang': 'fa', 'resume_version': 2})
        assert attached.json()['resume_snapshot']['content'] == {'name': 'Regenerated'}

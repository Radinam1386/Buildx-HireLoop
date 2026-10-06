import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app import analysis
from app.db import Base
from app.models import User, Job, Profile


def test_grounding_cache_profile_and_failure(monkeypatch):
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(email='a', password_hash='x')
        other = User(email='b', password_hash='x')
        db.add_all([user, other]); db.commit()
        text = 'Python is required. Remote only. Docker is preferred. React.js is required.'
        job = Job(title='Dev', description=text, owner_id=user.id)
        db.add(job); db.commit()
        def model(*args):
            return analysis.AnalysisOutput(requirements=[
                {'label':'Python', 'kind':'skill', 'quote':'Python is required.', 'value':'Python'},
                {'label':'Remote', 'kind':'work_mode', 'quote':'Remote only.', 'value':'remote'},
                {'label':'Docker', 'priority':'preferred', 'kind':'skill', 'quote':'Docker is preferred.', 'value':'Docker'},
                {'label':'Java', 'kind':'skill', 'quote':'Java required', 'value':'Java'},
                {'label':'React.js', 'kind':'skill', 'quote':'React.js is required.', 'value':'React.js'},
            ])
        monkeypatch.setattr(analysis, 'chat_json', model)
        assert analysis.read_analysis(job.id, user, db)['analysis'] is None
        result = analysis.analyze_job(job.id, analysis.AnalysisIn(), user, db)
        assert len(result['analysis']['requirements']) == 4
        assert result['analysis']['unknowns']
        assert all(r['status'] in ('ask', 'unknown') for r in result['analysis']['requirements'])
        db.add(Profile(user_id=user.id, data={'skills':['Python', 'React']})); db.commit()
        monkeypatch.setattr(analysis, 'chat_json', lambda *a: (_ for _ in ()).throw(RuntimeError('provider failed')))
        cached = analysis.analyze_job(job.id, analysis.AnalysisIn(), user, db)
        assert cached['analysis']['requirements'][0]['status'] == 'evidenced'
        assert cached['analysis']['requirements'][3]['status'] == 'evidenced'
        assert cached['analysis']['source_text'] == text
        with pytest.raises(RuntimeError):
            analysis.analyze_job(job.id, analysis.AnalysisIn(text=text+' Changed text.'), user, db)
        assert analysis.read_analysis(job.id, user, db)['analysis'] == cached['analysis']
        with pytest.raises(HTTPException) as exc:
            analysis.read_analysis(job.id, other, db)
        assert exc.value.status_code == 404
        job.owner_id = None; db.commit()
        assert analysis.read_analysis(job.id, other, db)['analysis'] is None

def test_quote_whitespace_and_skill_boundaries():
    assert analysis.exact_quote('Python  is\nrequired.', 'Python is required.') == 'Python  is\nrequired.'
    assert analysis.skill_in_quote('JavaScript is required', 'Java') is False
    assert analysis.skill_in_quote('C++ is required', 'C++') is True

def test_definite_conditions():
    p = analysis.ProfileData(level='junior', remote_pref='remote', city='Tehran')
    req = {'kind':'work_mode', 'value':'onsite', 'quote':'Onsite only.', 'priority':'required'}
    assert analysis.condition_status(req, p) == ('conflict', ['ترجیح پروفایل: remote'])
    assert analysis.condition_status({**req, 'priority':'preferred'}, p)[0] == 'ask'
    assert analysis.condition_status({**req, 'quote':'Work arrangement flexible.'}, p)[0] == 'unknown'
    assert analysis.condition_status({'kind':'level', 'value':'senior', 'quote':'Senior required', 'priority':'required'}, p)[0] == 'ask'
    assert analysis.condition_status({'kind':'level', 'value':'junior', 'quote':'Junior required', 'priority':'required'}, p)[0] == 'evidenced'
    assert analysis.condition_status({'kind':'experience','value':'3','quote':'3 years required','priority':'required'}, p)[0] == 'unknown'

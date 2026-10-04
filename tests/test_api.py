import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
from fastapi.testclient import TestClient

from app import main
from app.store import Store


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.patch = patch.object(main,'store',Store(Path(self.directory.name)/'api.db'))
        self.patch.start()
        self.client = TestClient(main.app)
        self.client.post('/api/auth/register',json={'name':'First','email':'first@example.com','password':'test password'})

    def tearDown(self):
        self.client.close()
        self.patch.stop()
        self.directory.cleanup()

    def test_registration_persistence_and_resume_ownership(self):
        saved = self.client.put('/api/profile',json={'full_name':'First','skills':['HTML'],'confirmed':True})
        self.assertEqual(saved.status_code,200)
        self.assertEqual(self.client.get('/api/me').json()['profile']['skills'],['HTML'])
        owner = self.client.get('/api/me').json()['user']['id']
        resume = main.store.save_resume(owner,'Frontend',{'profile':{'full_name':'<script>x</script>','skills':['HTML']},'summary':'','job':{}})
        self.assertNotIn('<script>x</script>',self.client.get(f'/api/resumes/{resume["id"]}/print').text)
        second = TestClient(main.app)
        second.post('/api/auth/register',json={'name':'Second','email':'second@example.com','password':'test password'})
        self.assertEqual(second.get(f'/api/resumes/{resume["id"]}').status_code,404)
        second.close()
        self.client.post('/api/auth/logout')
        self.assertEqual(self.client.get('/api/me').status_code,401)

    def test_invalid_source_is_rejected_without_network(self):
        response = self.client.post('/api/jobs/search',json={'query':'React','sources':['malicious.example']})
        self.assertEqual(response.status_code,400)

    def test_chat_search_metadata_survives_reload(self):
        search = {'query':'Python','city':'زنجان','remote':True,'jobs':[],
                  'sources':[{'id':'jobinja','status':'empty','count':0}]}
        with patch.object(main,'interview',AsyncMock(return_value={'reply':'نتیجه‌ای دریافت نشد.',
              'jobs':[],'source_status':search['sources'],'search':search})):
            response = self.client.post('/api/chat',json={'message':'آگهی پیدا کن'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(self.client.get('/api/me').json()['search'],search)

    def test_missing_provider_and_cross_origin_are_explicit(self):
        with patch.dict('os.environ',{'HORMOUZ_API_KEY':'','HORMOUZ_BASE_URL':''}):
            response = self.client.post('/api/chat',json={'message':'سلام'})
        self.assertEqual(response.status_code,503)
        self.assertEqual(self.client.get('/api/me').json()['usage']['calls'],0)
        response = self.client.put('/api/profile',json={},headers={'Origin':'https://other.example'})
        self.assertEqual(response.status_code,403)

    def test_match_resume_and_refine_use_confirmed_facts(self):
        self.client.put('/api/profile',json={'full_name':'First','skills':['HTML','CSS'],
            'projects':[{'name':'Real project','description':'Built by me'}],'summary':'My actual summary','confirmed':True})
        job = {'id':'real-id','title':'Frontend','description':'HTML required'}
        client_class = httpx.AsyncClient
        def handler(request):
            payload = json.loads(request.content)
            result = {'skills':['Invented skill','HTML'],'project_indices':[0,999],'summary':'Invented seniority'}
            if 'Assess the supplied jobs' in payload['messages'][0]['content']:
                result = {'matches':[{'id':'real-id','score':80,'reason':'HTML documented','gaps':['CSS evidence limited']}]}
            return httpx.Response(200,json={'choices':[{'message':{'role':'assistant','content':json.dumps(result)}}],
                'usage':{'prompt_tokens':10,'completion_tokens':5}})
        with patch.dict('os.environ',{'HORMOUZ_API_KEY':'offline-key','HORMOUZ_BASE_URL':'https://api.example.test/v1'}), \
             patch('app.agent.httpx.AsyncClient',side_effect=lambda **kwargs:client_class(transport=httpx.MockTransport(handler),**kwargs)):
            response = self.client.post('/api/jobs/match',json={'jobs':[job]})
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json()['matches'][0]['score'],80)
            response = self.client.post('/api/resumes',json={'job':job})
            self.assertEqual(response.status_code,200)
            resume = response.json()['resume']
            self.assertEqual(resume['content']['profile']['skills'],['HTML'])
            self.assertEqual(resume['content']['summary'],'My actual summary')
            self.assertEqual(len(resume['content']['profile']['projects']),1)
            response = self.client.post(f'/api/resumes/{resume["id"]}/refine',json={'feedback':'Add imaginary expertise'})
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json()['usage']['calls'],3)
        self.assertEqual(self.client.get(f'/api/resumes/{resume["id"]}').status_code,200)
        self.assertIn('My actual summary',self.client.get(f'/api/resumes/{resume["id"]}/print').text)


if __name__=='__main__':
    unittest.main()

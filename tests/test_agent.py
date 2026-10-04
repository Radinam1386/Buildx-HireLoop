import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx

from app import agent
from app.store import Store


class AgentTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.directory.name)/'agent.db')
        self.user = self.store.register('User','user@example.com','unused')['id']
        self.env = patch.dict('os.environ',{'HORMOUZ_API_KEY':'offline-test-key',
            'HORMOUZ_BASE_URL':'https://api.example.test/v1','HORMOUZ_MODEL':'gpt-6-luna',
            'MAX_AI_CALLS_PER_DAY':'10','MAX_AI_OUTPUT_TOKENS':'1200'})
        self.env.start()
        self.client_class = httpx.AsyncClient

    def tearDown(self):
        self.env.stop()
        self.directory.cleanup()

    def transport(self, handler):
        return patch.object(agent.httpx,'AsyncClient',side_effect=lambda **kwargs:
            self.client_class(transport=httpx.MockTransport(handler),**kwargs))

    async def test_tool_round_requires_confirmation_and_records_bounded_usage(self):
        requests = []
        def handler(request):
            payload = json.loads(request.content)
            requests.append(payload)
            self.assertEqual(str(request.url),'https://api.example.test/v1/chat/completions')
            self.assertEqual(payload['reasoning_effort'],'none')
            self.assertEqual(payload['max_completion_tokens'],1200)
            message = {'role':'assistant','content':'اطلاعات را بررسی و تأیید کن.'}
            if len(requests)==1:
                message = {'role':'assistant','content':None,'tool_calls':[{'id':'call_1','type':'function',
                    'function':{'name':'update_profile','arguments':json.dumps({'profile':{'skills':['HTML'],'confirmed':True}})}}]}
            return httpx.Response(200,json={'choices':[{'message':message}],
                'usage':{'prompt_tokens':10,'completion_tokens':4}})
        with self.transport(handler):
            result = await agent.interview(self.store,self.user,'HTML بلدم.',[])
        self.assertFalse(result['profile']['confirmed'])
        self.assertEqual(result['profile']['skills'],['HTML'])
        self.assertEqual(result['usage'],{'calls':2,'input_tokens':20,'output_tokens':8})
        self.assertEqual(len(self.store.messages(self.user)),2)
        self.assertEqual(requests[1]['messages'][-1]['tool_call_id'],'call_1')

    async def test_bad_match_shapes_return_clean_error(self):
        for matches in ({'id':'job'},[{'id':[]}],None):
            with self.subTest(matches=matches):
                def handler(request):
                    return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps({'matches':matches})}}]})
                with self.transport(handler),self.assertRaises(agent.AgentError):
                    await agent.match_jobs(self.store,self.user,{},[{'id':'job','title':'Frontend'}])

    async def test_malformed_tool_calls_do_not_mutate_profile(self):
        for calls in ([{'function':{'name':'update_profile','arguments':'{}'}}],{'bad':'shape'},True):
            with self.subTest(calls=calls):
                def handler(request):
                    return httpx.Response(200,json={'choices':[{'message':{'role':'assistant','tool_calls':calls}}]})
                with self.transport(handler),self.assertRaises(agent.AgentError):
                    await agent.interview(self.store,self.user,'سلام',[])
        self.assertFalse(self.store.profile(self.user)['confirmed'])
        self.assertEqual(self.store.messages(self.user),[])

    async def test_provider_errors_are_explicit_and_count_attempt(self):
        for response in (httpx.Response(401,json={'secret':'never expose'}),httpx.Response(200,json=[]),
                         httpx.Response(200,json={'choices':[{'message':{'content':[]}}],'usage':None})):
            with self.subTest(response=response):
                with self.transport(lambda request:response),self.assertRaises(agent.AgentError) as error:
                    await agent.interview(self.store,self.user,'سلام',[])
                self.assertNotIn('never expose',str(error.exception))
        self.assertEqual(self.store.usage(self.user)['calls'],3)

    async def test_failed_final_answer_does_not_commit_tool_changes(self):
        original = self.store.profile(self.user)
        self.store.save_jobs(self.user,{'jobs':[{'id':'job','title':'Frontend','description':'HTML'}],'sources':[]})
        original['confirmed'] = True
        self.store.save_profile(self.user,original)
        for name, arguments in (('update_profile',{'profile':{'skills':['React']}}),('prepare_resume',{'job_id':'job'})):
            requests = []
            def handler(request):
                requests.append(request)
                if len(requests)>1:
                    raise httpx.ReadTimeout('offline timeout',request=request)
                return httpx.Response(200,json={'choices':[{'message':{'role':'assistant','tool_calls':[
                    {'id':'call_1','function':{'name':name,'arguments':json.dumps(arguments)}}]}}]})
            with self.subTest(name=name),self.transport(handler),self.assertRaises(agent.AgentError):
                await agent.interview(self.store,self.user,'سلام',self.store.jobs(self.user)['jobs'])
            self.assertEqual(self.store.profile(self.user),original)
            self.assertEqual(self.store.resumes(self.user),[])
            self.assertEqual(self.store.messages(self.user),[])

    async def test_empty_preferred_search_offers_labeled_broader_results(self):
        profile = self.store.profile(self.user)
        profile.update(skills=['Python','OpenCV'],city='زنجان',remote=True,confirmed=False)
        self.store.save_profile(self.user,profile)
        requested = {'query':'machine learning internship','city':'زنجان','remote':True}
        calls = [{'id':'search_1','function':{'name':'search_jobs','arguments':json.dumps(requested)}}]
        model = AsyncMock(side_effect=[{'role':'assistant','tool_calls':calls},
                                      {'role':'assistant','content':'فرصت‌های گسترده‌تر را ببین.'}])
        source = AsyncMock(side_effect=[{'query':requested['query'],'jobs':[],'sources':[]},
            {'query':'Python','jobs':[{'id':'python-job','title':'Python developer'}],'sources':[]}])
        with patch.object(agent,'completion',model),patch('app.jobs.search_jobs',source):
            result = await agent.interview(self.store,self.user,'آگهی پیدا کن',[])
        self.assertEqual(source.await_count,2)
        self.assertEqual(source.await_args_list[1].args,('Python','',False))
        self.assertTrue(result['search']['broadened'])
        self.assertEqual(result['search']['requested'],requested)
        self.assertFalse(result['profile']['confirmed'])
        prompt = model.call_args_list[0].args[2][0]['content']
        self.assertIn('ذخیره و تأیید پروفایل',prompt)
        self.assertIn('برای جست‌وجو تأیید پروفایل لازم نیست',prompt)


if __name__=='__main__':
    unittest.main()

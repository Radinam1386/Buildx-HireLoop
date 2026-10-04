import unittest
from unittest.mock import patch
from app import jobs


JOBINJA = '''<li class="c-jobListView__item"><h2><a class="c-jobListView__titleLink" href="https://jobinja.ir/companies/acme/jobs/Ab12/python?tracking=1">Python developer</a></h2><ul><li class="c-jobListView__metaItem"><span>Acme</span></li><li class="c-jobListView__metaItem"><span>تهران</span></li></ul></li><a href="https://jobinja.ir/jobs/applied">My applications</a><a class="c-jobListView__titleLink" href="https://jobinja.ir.evil.test/companies/acme/jobs/Ab12/python">Python fake</a>'''
IRANTALENT = '''<new-position-card><a href="/en/job/python-developer/123"><p class="position-title">Python developer</p><p class="brand-name">Acme</p><span class="location">Tehran</span></a></new-position-card>'''
QUERA = '''<article><h2><a href="/magnet/jobs/a1b2c">Python developer</a></h2><img alt="لوگوی شرکت Acme"><div class="css-yfucoh"><span>تهران</span></div><div class="chakra-tag__root"><span>Python</span></div></article>'''
RSS = '''<rss><channel><item><title>Python developer</title><link>https://jobvision.ir/jobs/123/python-developer</link><description>Python opening, تهران</description></item><item><title>Python article</title><link>https://jobvision.ir/blog/python</link><description>Guide</description></item><item><title>Python fake</title><link>https://jobvision.ir.evil.test/jobs/123</link><description>Fake</description></item></channel></rss>'''


class JobsTests(unittest.IsolatedAsyncioTestCase):
    def test_board_cards_preserve_evidence_and_exclude_non_job_urls(self):
        found = jobs.parse_listings('jobinja', JOBINJA, 'python')
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]['company'], 'Acme')
        self.assertEqual(found[0]['location'], 'تهران')
        self.assertEqual(found[0]['url'], 'https://jobinja.ir/companies/acme/jobs/Ab12/python')
        self.assertEqual(found[0]['evidence_type'], 'listing')
        self.assertEqual(found[0]['id'], jobs.parse_listings('jobinja', JOBINJA.replace('tracking=1', 'tracking=2'), 'python')[0]['id'])
        self.assertFalse(jobs.parse_listings('jobinja', JOBINJA, 'accountant'))
        self.assertFalse(jobs.parse_listings('jobinja', JOBINJA, 'python', remote=True))
        self.assertEqual(jobs.parse_listings('irantalent', IRANTALENT, 'python')[0]['company'], 'Acme')
        self.assertEqual(jobs.parse_listings('quera', QUERA, 'python')[0]['skills'], ['Python'])

    def test_city_or_remote_filter_keeps_local_and_remote_options(self):
        for text, city, remote, wanted in (
            ('Python remote Tehran', 'Zanjan', True, True),
            ('Python onsite Zanjan', 'Zanjan', True, True),
            ('Python onsite زنجان', 'Zanjan', True, True),
            ('Python onsite Tehran', 'Zanjan', True, False),
            ('Python remote Tehran', '', True, True),
            ('Python onsite Zanjan', '', True, False),
            ('Python remote Tehran', 'Zanjan', False, False),
            ('Python onsite زنجان', 'Zanjan', False, True),
            ('Python onsite Tehran', '', False, True),
        ):
            with self.subTest(text=text, city=city, remote=remote):
                self.assertEqual(jobs._matches(text, 'python', city, remote), wanted)

    async def test_indexed_location_query_accepts_city_or_remote(self):
        def respond(request):
            if request.url.host == 'jobvision.ir':
                return jobs.httpx.Response(200, text='<html>Public search shell</html>')
            self.assertEqual(request.url.params['q'], 'site:jobvision.ir python ("Zanjan" OR دورکاری OR remote)')
            return jobs.httpx.Response(200, text=RSS.replace('Python opening, تهران', 'Python remote opening, Tehran'))
        async with jobs.httpx.AsyncClient(transport=jobs.httpx.MockTransport(respond)) as client:
            found, status = await jobs._search_source(client, jobs.SOURCES[1], 'python', 'Zanjan', True)
        self.assertEqual(len(found), 1)
        self.assertFalse(found[0]['verified'])
        self.assertEqual(status['status'], 'ok')

    async def test_public_result_preserves_query_and_location_filters(self):
        result = await jobs.search_jobs('Python', city='Zanjan', remote=True, sources=[])
        self.assertEqual(result['query'], 'Python')
        self.assertEqual(result['city'], 'Zanjan')
        self.assertIs(result['remote'], True)

    def test_frontend_spellings_match_persian_role_across_sources(self):
        fixtures = {'jobinja': JOBINJA, 'quera': QUERA, 'irantalent': IRANTALENT,
                    'jobvision': '<job-card><a href="/jobs/123/frontend">Python developer</a></job-card>'}
        for source, fixture in fixtures.items():
            for spelling in ('Frontend', 'Front-end', 'Front End', 'فرانت‌اند'):
                with self.subTest(source=source, spelling=spelling):
                    html = fixture.replace('Python developer', spelling + ' developer')
                    self.assertEqual(len(jobs.parse_listings(source, html, 'فرانت اند')), 1)
        self.assertEqual(len(jobs.parse_snippets('jobvision', RSS.replace('Python', 'Front-end'), 'فرانت اند')), 1)

    async def test_persian_frontend_role_uses_board_search_keyword(self):
        def respond(request):
            self.assertEqual(request.url.params['filters[keywords][0]'], 'frontend')
            return jobs.httpx.Response(200, text=JOBINJA.replace('Python developer', 'Frontend developer'))
        async with jobs.httpx.AsyncClient(transport=jobs.httpx.MockTransport(respond)) as client:
            found, status = await jobs._search_source(client, jobs.SOURCES[0], 'فرانت اند', '', False)
        self.assertEqual(found[0]['title'], 'Frontend developer')
        self.assertEqual(status['status'], 'ok')

    def test_city_filter_matches_persian_city_on_english_board(self):
        self.assertEqual(len(jobs.parse_listings('irantalent', IRANTALENT, 'python', city='تهران')), 1)
        self.assertFalse(jobs.parse_listings('irantalent', IRANTALENT, 'python', city='مشهد'))

    def test_indexed_snippets_are_unverified_and_domain_checked(self):
        found = jobs.parse_snippets('jobvision', RSS, 'python', city='تهران')
        self.assertEqual(len(found), 1)
        self.assertFalse(found[0]['verified'])
        self.assertEqual(found[0]['evidence_type'], 'search_snippet')
        self.assertEqual(found[0]['company'], '')

    async def test_invalid_query_and_source_rejected_before_network(self):
        with self.assertRaises(ValueError):
            await jobs.search_jobs('  ')
        with self.assertRaises(ValueError):
            await jobs.search_jobs('python', sources=['evil'])

    async def test_timeout_is_reported_per_source_and_cached_result_is_isolated(self):
        async def unavailable(*args, **kwargs):
            raise TimeoutError('public source timeout')
        jobs._cache.clear()
        with patch.object(jobs, '_fetch', unavailable):
            result = await jobs.search_jobs('python', sources=['jobvision'])
            self.assertEqual(result['jobs'], [])
            self.assertEqual(result['sources'][0]['status'], 'error')
            self.assertIn('مهلت', result['sources'][0]['error'])
            result['sources'][0]['status'] = 'ok'
            again = await jobs.search_jobs('python', sources=['jobvision'])
            self.assertEqual(again['sources'][0]['status'], 'error')


if __name__ == '__main__':
    unittest.main()

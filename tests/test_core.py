import tempfile
import unittest
from pathlib import Path


class CoreTests(unittest.TestCase):
    def setUp(self):
        from app.store import Store
        self.directory = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.directory.name) / 'test.db')

    def tearDown(self):
        self.directory.cleanup()

    def test_password_and_expired_session(self):
        from app.store import password_hash, password_matches
        encoded = password_hash('correct horse battery')
        self.assertTrue(password_matches('correct horse battery', encoded))
        self.assertFalse(password_matches('wrong password', encoded))
        user = self.store.register('Test', 'test@example.com', encoded)
        token = self.store.create_session(user['id'], lifetime=-1)
        self.assertIsNone(self.store.session_user(token))

    def test_resume_is_private_and_facts_are_not_from_model(self):
        from app.store import password_hash
        from app.agent import resume_document
        a = self.store.register('A', 'a@example.com', password_hash('test password'))
        b = self.store.register('B', 'b@example.com', password_hash('test password'))
        profile = {'full_name':'A','skills':['HTML'], 'projects':[], 'experience':[], 'confirmed':True}
        doc = resume_document(profile, {'title':'Frontend'}, {'summary':'Five years of React', 'skills':['React'], 'experience':[{'company':'Fake'}]})
        self.assertEqual(doc['profile']['skills'], ['HTML'])
        self.assertEqual(doc['profile']['experience'], [])
        self.assertNotIn('Five years', doc['summary'])
        resume = self.store.save_resume(a['id'], 'Frontend', doc)
        self.assertIsNone(self.store.resume(b['id'], resume['id']))

    def test_budget_reservations_are_enforced(self):
        from app.store import password_hash
        user = self.store.register('A', 'a@example.com', password_hash('test password'))
        call = self.store.reserve_call(user['id'], 1)
        self.store.finish_call(call, 100, 20)
        with self.assertRaises(ValueError):
            self.store.reserve_call(user['id'], 1)
        self.assertEqual(self.store.usage(user['id'])['output_tokens'], 20)


if __name__ == '__main__':
    unittest.main()

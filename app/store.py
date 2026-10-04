import hashlib
import hmac
import json
import secrets
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def password_hash(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return f'{salt}:{digest}'


def password_matches(password: str, encoded: str) -> bool:
    salt, digest = encoded.split(':', 1)
    actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return hmac.compare_digest(actual, digest)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT NOT NULL,
                  email TEXT UNIQUE NOT NULL, password TEXT NOT NULL, profile TEXT NOT NULL DEFAULT '{}');
                CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, user_id INTEGER NOT NULL,
                  expires REAL NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id));
                CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL,
                  role TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS resumes (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL,
                  title TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS calls (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL,
                  day TEXT NOT NULL, input_tokens INTEGER DEFAULT 0, output_tokens INTEGER DEFAULT 0);
                CREATE TABLE IF NOT EXISTS job_searches (user_id INTEGER PRIMARY KEY, result TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS messages_user ON messages(user_id, id);
                CREATE INDEX IF NOT EXISTS calls_user_day ON calls(user_id, day);
            ''')

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    def register(self, name, email, password):
        profile = {'full_name':name, 'email':email, 'skills':[], 'projects':[], 'experience':[],
                   'education':[], 'languages':[], 'confirmed':False}
        with self.connection() as db:
            cursor = db.execute('INSERT INTO users(name,email,password,profile) VALUES(?,?,?,?)',
                                (name, email, password, json.dumps(profile, ensure_ascii=False)))
            return {'id':cursor.lastrowid, 'name':name, 'email':email}

    def user_by_email(self, email):
        with self.connection() as db:
            row = db.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
            return dict(row) if row else None

    def create_session(self, user_id, lifetime=604800):
        token = secrets.token_urlsafe(32)
        with self.connection() as db:
            db.execute('DELETE FROM sessions WHERE expires<?', (time.time(),))
            db.execute('INSERT INTO sessions VALUES(?,?,?)',
                       (hashlib.sha256(token.encode()).hexdigest(), user_id, time.time()+lifetime))
        return token

    def session_user(self, token):
        if not token:
            return None
        with self.connection() as db:
            row = db.execute('SELECT u.id,u.name,u.email FROM users u JOIN sessions s ON s.user_id=u.id '
                             'WHERE s.token=? AND s.expires>?',
                             (hashlib.sha256(token.encode()).hexdigest(), time.time())).fetchone()
            return dict(row) if row else None

    def delete_session(self, token):
        with self.connection() as db:
            db.execute('DELETE FROM sessions WHERE token=?', (hashlib.sha256(token.encode()).hexdigest(),))

    def profile(self, user_id):
        with self.connection() as db:
            return json.loads(db.execute('SELECT profile FROM users WHERE id=?', (user_id,)).fetchone()[0])

    def save_profile(self, user_id, profile):
        with self.connection() as db:
            db.execute('UPDATE users SET profile=? WHERE id=?', (json.dumps(profile, ensure_ascii=False),user_id))

    def add_message(self, user_id, role, content):
        with self.connection() as db:
            db.execute('INSERT INTO messages(user_id,role,content,created_at) VALUES(?,?,?,?)',
                       (user_id,role,content,now()))

    def messages(self, user_id, limit=30):
        with self.connection() as db:
            rows = db.execute('SELECT role,content FROM messages WHERE user_id=? ORDER BY id DESC LIMIT ?',
                              (user_id,limit)).fetchall()
            return [dict(row) for row in reversed(rows)]

    def save_resume(self, user_id, title, content, resume_id=None):
        with self.connection() as db:
            if resume_id is None:
                resume_id = db.execute('INSERT INTO resumes(user_id,title,content,created_at) VALUES(?,?,?,?)',
                                      (user_id,title,json.dumps(content,ensure_ascii=False),now())).lastrowid
            else:
                db.execute('UPDATE resumes SET content=? WHERE id=? AND user_id=?',
                           (json.dumps(content,ensure_ascii=False),resume_id,user_id))
        return self.resume(user_id,resume_id)

    def resume(self, user_id, resume_id):
        with self.connection() as db:
            row = db.execute('SELECT id,title,content,created_at FROM resumes WHERE id=? AND user_id=?',
                             (resume_id,user_id)).fetchone()
            if row:
                return {**dict(row), 'content':json.loads(row['content'])}
            return None

    def resumes(self, user_id):
        with self.connection() as db:
            return [dict(row) for row in db.execute('SELECT id,title,created_at FROM resumes '
                    'WHERE user_id=? ORDER BY id DESC LIMIT 50',(user_id,)).fetchall()]

    def reserve_call(self, user_id, maximum):
        day = now()[:10]
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            count = db.execute('SELECT COUNT(*) FROM calls WHERE user_id=? AND day=?',(user_id,day)).fetchone()[0]
            if count >= maximum:
                raise ValueError('سقف روزانهٔ استفاده از مدل رسیده است. فردا دوباره امتحان کنید.')
            return db.execute('INSERT INTO calls(user_id,day) VALUES(?,?)',(user_id,day)).lastrowid

    def save_jobs(self, user_id, result):
        with self.connection() as db:
            db.execute('INSERT INTO job_searches VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET result=excluded.result',
                       (user_id,json.dumps(result,ensure_ascii=False)))

    def jobs(self, user_id):
        with self.connection() as db:
            row = db.execute('SELECT result FROM job_searches WHERE user_id=?',(user_id,)).fetchone()
            return json.loads(row[0]) if row else {'jobs':[], 'sources':[]}

    def finish_call(self, call_id, input_tokens, output_tokens):
        with self.connection() as db:
            db.execute('UPDATE calls SET input_tokens=?,output_tokens=? WHERE id=?',
                       (input_tokens,output_tokens,call_id))

    def usage(self, user_id):
        with self.connection() as db:
            row = db.execute('SELECT COUNT(*) calls, COALESCE(SUM(input_tokens),0) input_tokens, '
                             'COALESCE(SUM(output_tokens),0) output_tokens FROM calls WHERE user_id=? AND day=?',
                             (user_id,now()[:10])).fetchone()
            return dict(row)

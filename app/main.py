import asyncio
import html
import os
import sqlite3
import time
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT/'.env')

from .agent import AgentError, configuration, configured, interview, make_resume, match_jobs
from .jobs import SOURCES, search_jobs
from .models import AuthInput, FeedbackInput, MatchInput, MessageInput, Profile, ResumeInput, SearchInput
from .store import Store, password_hash, password_matches

database = Path(os.getenv('DATABASE_PATH','data/hireloop.db'))
store = Store(database if database.is_absolute() else ROOT/database)
app = FastAPI(title='HireLoop',docs_url=None,redoc_url=None)
user_locks = defaultdict(asyncio.Lock)
# ponytail: two concurrent model calls in this single server; use a shared queue when scaling to multiple workers.
model_slots = asyncio.Semaphore(2)
# ponytail: process-local abuse limits; move to shared storage before running multiple workers.
attempts = defaultdict(list)


@app.middleware('http')
async def request_guard(request: Request, call_next):
    if request.method in ('POST','PUT','DELETE'):
        origin = request.headers.get('origin')
        if origin and urlparse(origin).netloc != request.headers.get('host'):
            return JSONResponse({'detail':'درخواست باید از همین سایت ارسال شود.'},403)
        size = request.headers.get('content-length','0')
        if not size.isdigit() or int(size)>100000:
            return JSONResponse({'detail':'حجم درخواست بیش از حد مجاز است.'},413)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['X-Frame-Options'] = 'DENY'
    if request.url.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store'
    return response


@app.exception_handler(AgentError)
async def agent_error(request,exc):
    return JSONResponse({'detail':exc.message},exc.status)


@app.exception_handler(RequestValidationError)
async def validation_error(request,exc):
    return JSONResponse({'detail':'اطلاعات ورودی معتبر نیست: '+'؛ '.join(e['msg'] for e in exc.errors()[:3])},422)


def current_user(request: Request):
    user = store.session_user(request.cookies.get('hireloop_session'))
    if user is None:
        raise HTTPException(401,'برای ادامه وارد حساب شوید.')
    return user


def auth_limit(request):
    address = request.client.host if request.client else 'unknown'
    now = time.monotonic()
    attempts[address] = [t for t in attempts[address] if t>now-600]
    if len(attempts[address])>=20:
        raise HTTPException(429,'تعداد تلاش‌های ورود زیاد است. ده دقیقه بعد امتحان کنید.')
    attempts[address].append(now)


def set_session(response,user_id):
    response.set_cookie('hireloop_session',store.create_session(user_id),httponly=True,
                        secure=os.getenv('COOKIE_SECURE','false').lower()=='true',
                        samesite='lax',max_age=604800,path='/')


@app.get('/api/config')
def public_config():
    return {'configured':configured(),'model':configuration()['model'],'sources':SOURCES}


@app.get('/api/health')
def health():
    return {'status':'ok','configured':configured()}


@app.post('/api/auth/register')
def register(body: AuthInput,request: Request,response: Response):
    auth_limit(request)
    if not body.name.strip():
        raise HTTPException(400,'نام را وارد کنید.')
    try:
        user = store.register(body.name.strip(),body.email,password_hash(body.password))
    except sqlite3.IntegrityError:
        raise HTTPException(409,'این ایمیل قبلاً ثبت شده است. وارد حساب شوید.')
    set_session(response,user['id'])
    return {'user':user}


@app.post('/api/auth/login')
def login(body: AuthInput,request: Request,response: Response):
    auth_limit(request)
    user = store.user_by_email(body.email)
    if not user or not password_matches(body.password,user['password']):
        raise HTTPException(401,'ایمیل یا رمز عبور درست نیست.')
    set_session(response,user['id'])
    return {'user':{key:user[key] for key in ('id','name','email')}}


@app.post('/api/auth/logout')
def logout(request: Request,response: Response):
    token = request.cookies.get('hireloop_session')
    if token:
        store.delete_session(token)
    response.delete_cookie('hireloop_session',path='/')
    return {'ok':True}


@app.get('/api/me')
def me(user=Depends(current_user)):
    return {'user':user,'profile':Profile.model_validate(store.profile(user['id'])).model_dump(),
            'messages':store.messages(user['id']),'resumes':store.resumes(user['id']),
            'usage':store.usage(user['id']),'configured':configured(),'search':store.jobs(user['id'])}


@app.put('/api/profile')
async def save_profile(body: Profile,user=Depends(current_user)):
    async with user_locks[user['id']]:
        store.save_profile(user['id'],body.model_dump())
    return {'profile':body.model_dump()}


@app.post('/api/chat')
async def chat(body: MessageInput,user=Depends(current_user)):
    if not body.message.strip():
        raise HTTPException(400,'پیام خالی است.')
    async with user_locks[user['id']],model_slots:
        result = await interview(store,user['id'],body.message.strip(),store.jobs(user['id'])['jobs'])
        if 'jobs' in result:
            store.save_jobs(user['id'],result.get('search',{'jobs':result['jobs'],'sources':result.get('source_status',[])}))
        return result


@app.post('/api/jobs/search')
async def search(body: SearchInput,user=Depends(current_user)):
    try:
        result = await search_jobs(body.query,body.city,body.remote,body.sources)
    except ValueError as exc:
        raise HTTPException(400,'منبع یا فیلتر جست‌وجو معتبر نیست.') from exc
    store.save_jobs(user['id'],result)
    return result


@app.post('/api/jobs/match')
async def match(body: MatchInput,user=Depends(current_user)):
    async with user_locks[user['id']],model_slots:
        result = await match_jobs(store,user['id'],store.profile(user['id']),[j.model_dump() for j in body.jobs])
        return {'matches':result,'usage':store.usage(user['id'])}


@app.post('/api/resumes')
async def create_resume(body: ResumeInput,user=Depends(current_user)):
    job = body.job.model_dump()
    if body.job_text.strip():
        job.update(description=body.job_text.strip(),evidence_type='user_text',verified=False)
        job['title'] = job['title'] or 'آگهی واردشده'
    if not job.get('description') and not job.get('title'):
        raise HTTPException(400,'یک آگهی انتخاب کنید یا متن آگهی را وارد کنید.')
    async with user_locks[user['id']],model_slots:
        document = await make_resume(store,user['id'],store.profile(user['id']),job)
        resume = store.save_resume(user['id'],job['title'],document)
        return {'resume':resume,'usage':store.usage(user['id'])}


@app.get('/api/resumes')
def resumes(user=Depends(current_user)):
    return {'resumes':store.resumes(user['id'])}


def own_resume(user,resume_id):
    resume = store.resume(user['id'],resume_id)
    if resume is None:
        raise HTTPException(404,'رزومه پیدا نشد.')
    return resume


@app.get('/api/resumes/{resume_id}')
def get_resume(resume_id: int,user=Depends(current_user)):
    return {'resume':own_resume(user,resume_id)}


@app.post('/api/resumes/{resume_id}/refine')
async def refine(resume_id: int,body: FeedbackInput,user=Depends(current_user)):
    async with user_locks[user['id']],model_slots:
        previous = own_resume(user,resume_id)
        document = await make_resume(store,user['id'],store.profile(user['id']),previous['content']['job'],body.feedback)
        resume = store.save_resume(user['id'],previous['title'],document,resume_id)
        return {'resume':resume,'usage':store.usage(user['id'])}


@app.get('/api/resumes/{resume_id}/print',response_class=HTMLResponse)
def print_resume(resume_id: int,user=Depends(current_user)):
    resume = own_resume(user,resume_id)
    profile = resume['content']['profile']
    escape = lambda value: html.escape(str(value))
    contact = ' · '.join(escape(profile.get(key,'')) for key in ('email','phone','city') if profile.get(key))
    sections = []
    if resume['content'].get('summary'):
        sections.append('<p>'+escape(resume['content']['summary'])+'</p>')
    for label,key in [('مهارت‌ها','skills'),('تحصیلات','education'),('زبان‌ها','languages')]:
        if profile.get(key):
            sections.append('<section><h2>'+label+'</h2><p>'+ '، '.join(escape(x) for x in profile[key])+'</p></section>')
    for label,key in [('پروژه‌ها','projects'),('تجربهٔ کاری','experience')]:
        if profile.get(key):
            items = []
            for item in profile[key]:
                heading = item.get('name') or ' · '.join(filter(None,[item.get('role'),item.get('company')]))
                link = f'<p class="link" dir="ltr">{escape(item.get("url",""))}</p>' if item.get('url') else ''
                items.append('<article><h3>'+escape(heading)+'</h3><p>'+escape(item.get('description',''))+'</p>'+link+'</article>')
            sections.append('<section><h2>'+label+'</h2>'+''.join(items)+'</section>')
    return HTMLResponse('<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"><title>رزومه '+escape(profile.get('full_name',''))+'</title>'
        '<link rel="stylesheet" href="/static/styles.css"><style>'
        'body{background:white;color:#172B4D;font-family:Vazirmatn,Tahoma,sans-serif;margin:0}.cv{max-width:760px;margin:40px auto;padding:32px}'
        '.cv h1{font-size:28px}.cv h2{font-size:17px;border-bottom:1px solid #cdd6e3;padding-bottom:8px;margin-top:28px}'
        '.cv h3{font-size:15px;margin-bottom:4px}.cv p{white-space:pre-wrap;line-height:1.9}.cv .link{font-size:12px;overflow-wrap:anywhere}'
        '.print-toolbar{max-width:760px;margin:20px auto;padding:12px;background:#F4F7FB}.print-toolbar button{cursor:pointer}'
        '@page{size:A4;margin:15mm}@media print{.print-toolbar{display:none}.cv{padding:0;margin:0;max-width:none}article{break-inside:avoid}}'
        '</style></head><body><div class="print-toolbar"><button id="print-button">چاپ / ذخیره به صورت PDF</button>'
        '<p>در پنجرهٔ چاپ، گزینهٔ Save as PDF را انتخاب کنید.</p></div><main class="cv"><h1>'+escape(profile.get('full_name',''))+
        '</h1><p dir="auto">'+contact+'</p>'+''.join(sections)+'</main><script src="/static/print.js"></script></body></html>')


app.mount('/static',StaticFiles(directory=ROOT/'app'/'static'),name='static')


@app.get('/',response_class=HTMLResponse)
def index():
    return HTMLResponse((ROOT/'app'/'static'/'index.html').read_text(encoding='utf-8'))

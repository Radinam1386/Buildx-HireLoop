# HireLoop

همراه کاریابی ایجنتیک برای کارآموز و جونیور فرانت‌اند: **مصاحبه ← پروفایل ← آگهی مناسب با دلیل ← رزومهٔ اختصاصی ← بازخورد و اصلاح**

- **Backend:** FastAPI + Pydantic + SQLAlchemy، JWT، ایجنت‌ها با LangGraph (گراف Refiner)
- **Frontend:** React (Vite) با RTL و فونت Vazirmatn
- **LLM:** هر API سازگار با OpenAI (مثلاً هرموز) — مدل هر ایجنت در `.env`

## تنظیم
۱. فایل `.env` را باز کنید و مقدارهایی که `REPLACE` دارند را پر کنید
   (`LLM_BASE_URL`، `LLM_API_KEY`، نام مدل‌ها، `EMBEDDING_MODEL`، و حتماً `JWT_SECRET`).
۲. آگهی‌های فعلی دادهٔ **نمونه** هستند (`backend/app/seed_jobs.json`)؛ بعداً با آگهی‌های واقعی جایگزین کنید.

## اجرای محلی
```bash
# بک‌اند
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# فرانت‌اند (ترمینال دوم)
cd frontend && npm install && npm run dev      # http://localhost:5173
```

## دیپلوی روی سرور
```bash
docker compose up -d --build     # سایت روی پورت ۸۰
```

## تست
```bash
cd backend && pytest -q          # کل جریان با LLM جعلی؛ بدون API key
```

## معماری کوتاه
| ایجنت | فایل | نقش |
|---|---|---|
| Interviewer | `agents.py` | مصاحبهٔ تطبیقی؛ خودش تصمیم می‌گیرد کی پروفایل کافی است |
| Matcher | `services.py` | فیلتر سخت ← embedding ← امتیاز و توضیح LLM |
| Resume Writer | `services.py` | رزومه فقط از واقعیت‌های پروفایل (+ محافظ ضدجعل برای مهارت‌ها) |
| Refiner | `agents.py` | گراف LangGraph: انتخاب اقدام (تغییر ترجیح / حذف آگهی / اصلاح رزومه / پاسخ) |

مصرف توکن هر فراخوانی در جدول `usage` ذخیره می‌شود؛ `GET /api/usage` جمع‌ها را می‌دهد.

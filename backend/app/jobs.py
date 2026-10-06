"""Bounded direct board search, verified against original vacancy pages. No search API or LLM calls."""
import asyncio
import copy
import html
import json
import re
import time
from datetime import datetime, timezone
from urllib.parse import quote, urlencode, urljoin, urlsplit, urlunsplit

import httpx
from bs4 import BeautifulSoup

SOURCES = {"jobinja": ("جابینجا", "https://jobinja.ir/jobs"),
           "jobvision": ("جاب‌ویژن", "https://jobvision.ir/jobs"),
           "quera": ("کوئرا", "https://quera.org/magnet/jobs"),
           "irantalent": ("ایران‌تلنت", "https://www.irantalent.com/en/jobs"),
           "karboom": ("کاربوم", "https://karboom.io/jobs")}
_cache = {}


def norm(text):
    return " ".join(str(text).casefold().replace("ي", "ی").replace("ك", "ک").replace("\u200c", " ").split())


def job_key(source, url):
    try:
        p = urlsplit(url)
        host = urlsplit(SOURCES[source][1]).hostname.removeprefix("www.")
        if p.scheme != "https" or (p.hostname or "").removeprefix("www.") != host or p.username or p.password or p.port not in (None, 443):
            return ""
        patterns = {"jobinja": r"(/companies/[^/]+/jobs/[A-Za-z0-9]+)(?:/.*)?",
                    "jobvision": r"(/jobs/\d+)(?:/.*)?", "quera": r"(/magnet/jobs/[a-z0-9]{5})/?",
                    "irantalent": r"/(?:en|fa)/job/[^/]+/(\d+)/?", "karboom": r"(/jobs/[a-z0-9]{6})(?:/.*)?"}
        match = re.fullmatch(patterns[source], p.path)
        return source + ":" + match.group(1) if match else ""
    except (KeyError, ValueError):
        return ""


TECH_ALIASES = {
    # AI & ML
    "هوش مصنوعی": "هوش مصنوعی", "یادگیری ماشین": "یادگیری ماشین", "machine learning": "Machine Learning",
    "deep learning": "یادگیری عمیق", "computer vision": "پردازش تصویر", "nlp": "پردازش زبان طبیعی",
    "علم داده": "علم داده", "data science": "علم داده",
    # Fullstack
    "full stack": "Full Stack", "fullstack": "Full Stack", "فول استک": "Full Stack",
    # DevOps
    "devops": "DevOps", "دواپس": "DevOps", "دوآپس": "DevOps", "docker": "Docker", "داکر": "Docker",
    "kubernetes": "Kubernetes", "کوبرنتیز": "Kubernetes",
    # Mobile
    "flutter": "Flutter", "فلاتر": "Flutter", "android": "Android", "اندروید": "Android",
    "ios": "iOS", "react native": "React Native",
    # Backend
    "python": "Python", "پایتون": "Python", "django": "Django", "fastapi": "FastAPI",
    "golang": "Golang", "go": "Golang", "گولنگ": "Golang",
    "node.js": "Node.js", "nodejs": "Node.js", "node": "Node.js", "nest": "NestJS", "nestjs": "NestJS",
    "java": "Java", "جاوا": "Java", "spring": "Spring", "spring boot": "Spring Boot",
    "php": "PHP", "laravel": "Laravel", "لاراول": "Laravel",
    "c#": "C#", ".net": ".NET", "دات نت": ".NET",
    # Frontend
    "react": "React", "ریکت": "React", "ری اکت": "React", "next.js": "Next.js", "next": "Next.js",
    "vue": "Vue", "angular": "Angular",
}


def queries(profile):
    role = norm(profile.target_role)
    if re.search(r"یادگیری ماشین|هوش مصنوعی|machine learning|computer vision|\bai\b", role):
        primary = "هوش مصنوعی"
    else:
        primary = next((value for key, value in TECH_ALIASES.items() if re.search(r"(?<!\w)" + re.escape(key) + r"(?!\w)", role)), "")
        if not primary and re.search(r"developer|programmer|software|برنامه نویس|توسعه دهنده|فرانت|بک اند|full.?stack|devops|دواپس|موبایل", role):
            primary = next((TECH_ALIASES[norm(s)] for s in profile.skills if norm(s) in TECH_ALIASES), "")
        primary = primary or profile.target_role.strip()
    result = [primary[:120]]
    if profile.level == "intern":
        result.append("کارآموز " + ("هوش مصنوعی" if primary in ("هوش مصنوعی", "یادگیری ماشین", "Machine Learning") else primary))
    return list(dict.fromkeys(result))[:2]


def level(job):
    title = norm(job.get("title", "") + " " + (job.get("level") or ""))
    text = norm(job.get("text", ""))
    years = [int(n) for n in re.findall(r"(\d+)\s*\+?\s*(?:years?\s+(?:[\w-]+\s+){0,5}experience|سال\s+(?:سابقه|تجربه))", text)]
    years.extend(int(n) + 1 for n in re.findall(r"(?:over|more than|بیش از)\s+(\d+)\s*(?:years?|سال)", text))
    if job.get("min_years") is not None:
        years.append(int(job["min_years"]))
    # ponytail: experience bands are a search heuristic; the matcher still checks the full requirements.
    if re.search(r"\bsenior\b|\blead\b|ارشد|سرپرست|مدیر|architect", title) or (years and max(years) >= 5):
        return "senior"
    if re.search(r"\bmid(?:[ -]level)?\b|\bmiddle\b|میانی", title) or (years and max(years) > 2):
        return "mid"
    if re.search(r"\bintern(?:ship)?\b|کارآموز", title):
        return "intern"
    if re.search(r"\bjunior\b|جونیور|مبتدی|بدون سابقه|بدون تجربه", title) or (years and max(years) <= 2):
        return "junior"
    return ""


def expired(date):
    if not date:
        return False
    try:
        parsed = datetime.strptime(str(date), "%Y-%m-%d %I:%M:%S%p") if str(date).lower().endswith(("am", "pm")) else datetime.fromisoformat(str(date).replace("Z", "+00:00"))
        if "T" not in str(date):
            return parsed.date() < datetime.now(timezone.utc).date()
        return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc) <= datetime.now(timezone.utc)
    except ValueError:
        return False


def cards(source, raw):
    soup = BeautifulSoup(raw, "html.parser")
    if source == "quera":
        node = soup.select_one("#__NEXT_DATA__")
        if not node:
            raise ValueError("دادهٔ جست‌وجوی کوئرا قابل خواندن نبود.")
        edges = json.loads(node.string)["props"]["pageProps"]["jobs"]["edges"]
        return [{"url": "https://quera.org/magnet/jobs/" + n["pk"], "title": n["title"], "company": n["company"]["name"],
                 "location": (n.get("city") or {}).get("name", ""), "level": n.get("level", ""), "remote": n.get("offers_remote"),
                 "skills": [t["technology"]["name"] for t in n.get("jobtechnology_set", [])], "open": n.get("open")}
                for n in (e["node"] for e in edges)]
    selector = ".c-jobListView__titleLink" if source == "jobinja" else ".js-job-position-card[data-href] h3 a[href]"
    result = []
    for a in soup.select(selector):
        card = a.find_parent("li") if source == "jobinja" else a.find_parent(class_="js-job-position-card")
        card = card or a
        company, location = "", ""
        if source == "jobinja":
            meta = card.select(".c-jobListView__metaItem span")
            company = meta[0].get_text(" ", strip=True) if meta else ""
            location = meta[1].get_text(" ", strip=True) if len(meta) > 1 else ""
        else:
            company_node = card.select_one(".company-name")
            company = company_node.get_text(" ", strip=True) if company_node else ""
            location_node = card.select_one(".company-name ~ span.pull-right")
            location = location_node.get_text(" ", strip=True) if location_node else ""
        result.append({"url": urljoin(SOURCES[source][1], a["href"]), "title": a.get_text(" ", strip=True),
                       "company": company, "location": location, "text": card.get_text(" ", strip=True)})
    if not result and not any(marker in raw for marker in ("c-jobListView", "js-job-position-card", "job-list", "نتیجه‌ای", "یافت نشد")):
        raise ValueError("صفحهٔ جست‌وجوی منبع قابل خواندن نبود.")
    return result


def api_cards(source, data):
    payload = data["data"]
    if source == "jobvision":
        result = []
        for j in payload["jobPosts"]:
            props = j.get("properties") or {}
            result.append({"url": f'https://jobvision.ir/jobs/{j["id"]}', "title": j["title"], "company": (j.get("company") or {}).get("nameFa", ""),
                           "location": ((j.get("location") or {}).get("city") or {}).get("titleFa", ""), "remote": props.get("isRemote"),
                           "level": "intern" if props.get("isInternship") else (j.get("seniorityLevel") or {}).get("titleEn", ""),
                           "min_years": props.get("requiredRelatedExperienceYears"), "open": not (j.get("expireTime") or {}).get("isExpired", False)})
        return result
    if not isinstance(payload, list):
        raise ValueError("ساختار جست‌وجوی ایران‌تلنت تغییر کرده است.")
    return [{"url": f'https://www.irantalent.com/en/job/{j["slug"]}/{j["id"]}', "title": j["title"],
             "company": (j.get("employer") or {}).get("name", ""), "location": j.get("location_text_farsi") or j.get("location_text", ""),
             "remote": j.get("work_type") == "remote", "level": " ".join(s.get("title", "") for s in j.get("seniority", [])),
             "open": (j.get("status") or {}).get("title") == "Live-approved"} for j in payload]


def detail(source, raw, card, skills):
    soup = BeautifulSoup(raw, "html.parser")
    if any("آگهی منقضی شده است" in norm(n.get_text(" ", strip=True)) for n in soup.select(".c-alert, .c-text__danger")):
        return None
    postings = []
    for node in soup.select('script[type="application/ld+json"]'):
        try:
            obj = json.loads(node.string or node.get_text())
            postings.extend(obj if isinstance(obj, list) else obj.get("@graph", [obj]))
        except (ValueError, TypeError, AttributeError):
            continue
    posting = next((p for p in postings if isinstance(p, dict) and "JobPosting" in (p.get("@type") or [])), None)
    if not posting:
        raise ValueError("متن ساختاریافتهٔ آگهی در صفحهٔ اصلی در دسترس نبود.")
    if expired(posting.get("validThrough")):
        return None
    text = BeautifulSoup(html.unescape(posting.get("description") or ""), "html.parser").get_text(" ", strip=True)
    if not text:
        raise ValueError("متن آگهی خالی است.")
    job = dict(card, title=posting.get("title") or card["title"], text=text)
    places = posting.get("jobLocation") or []
    places = [places] if isinstance(places, dict) else places
    locality = " ".join(str((loc.get("address") or {}).get("addressLocality", "")) for loc in places if isinstance(loc, dict))
    location = " ".join(dict.fromkeys(filter(None, [card.get("location"), locality])))
    body = norm(text)
    remote = posting.get("jobLocationType") == "TELECOMMUTE" or card.get("remote") is True
    if not re.search(r"\b(?:not|no) remote\b|عدم امکان دورکاری|دورکاری ندار|دورکاری نیست|امکان دورکاری وجود ندارد", body):
        remote = remote or bool(re.search(r"\bremote\b|دورکاری|دور کاری", body))
    organization = posting.get("hiringOrganization") or {}
    parts = urlsplit(card["url"])
    url = urlunsplit(("https", parts.netloc, parts.path.rstrip("/"), "", ""))
    technology = list(dict.fromkeys([*(card.get("skills") or []), *(s for s in skills if norm(s) in norm(job["title"] + " " + text))]))
    return {"key": job_key(source, url), "source": source, "url": url[:500], "title": str(job["title"])[:255],
            "company": str(organization.get("name") or card.get("company") or "")[:255], "location": location[:255],
            "remote": bool(remote), "level": level(job), "skills": technology[:30], "description": text[:8000]}


async def request(client, semaphore, url, body=None):
    host = urlsplit(url).hostname
    async with semaphore:
        for _ in range(4):
            async with client.stream("POST" if body is not None else "GET", url, json=body) as response:
                if response.is_redirect:
                    target = urljoin(url, response.headers.get("location", ""))
                    p = urlsplit(target)
                    if body is not None or p.scheme != "https" or (p.hostname or "").removeprefix("www.") != host.removeprefix("www.") or p.username or p.password or p.port not in (None, 443):
                        raise ValueError("هدایت منبع به نشانی نامعتبر بود.")
                    url = target
                    continue
                response.raise_for_status()
                chunks, size = [], 0
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > 4_000_000:
                        raise ValueError("حجم پاسخ منبع بیشتر از حد مجاز است.")
                    chunks.append(chunk)
                return b"".join(chunks).decode("utf-8", "replace")
    raise ValueError("تعداد هدایت‌های منبع بیش از حد بود.")


def error_text(exc):
    if isinstance(exc, httpx.HTTPStatusError):
        return f"منبع با کد {exc.response.status_code} پاسخ داد."
    if isinstance(exc, (httpx.TimeoutException, TimeoutError)):
        return "مهلت دریافت از منبع تمام شد."
    if isinstance(exc, httpx.HTTPError):
        return "اتصال به منبع برقرار نشد."
    if isinstance(exc, ValueError) and not isinstance(exc, json.JSONDecodeError):
        return str(exc)[:180]
    return "دادهٔ منبع قابل تأیید نبود."


async def search_source(client, semaphore, source, terms, profile):
    name, base = SOURCES[source]
    errors, found = [], {}
    search_ok = False
    for query in terms:
        try:
            if source == "jobvision":
                raw = await request(client, semaphore, "https://candidateapi.jobvision.ir/api/v1/JobPost/List", {"pageSize": 30, "requestedPage": 1, "keyword": query, "sortBy": 1, "searchId": None})
                candidates = api_cards(source, json.loads(raw))
            elif source == "irantalent":
                raw = await request(client, semaphore, "https://api.irantalent.com/api/v1/employer/position/search", {"keyword": query})
                candidates = api_cards(source, json.loads(raw))
            else:
                params = {"filters[keywords][0]": query} if source == "jobinja" else {"search": query} if source == "quera" else {"q": query}
                raw = await request(client, semaphore, base + "?" + urlencode(params))
                candidates = cards(source, raw)
            search_ok = True
            for candidate in candidates:
                key = job_key(source, candidate["url"])
                if key and candidate.get("open") is not False:
                    found.setdefault(key, candidate)
        except (httpx.HTTPError, ValueError, TypeError, KeyError, AttributeError, TimeoutError) as exc:
            errors.append(error_text(exc))
    def priority(card):
        text = norm(card.get("title", "") + " " + card.get("location", ""))
        return (bool(profile.level) and level(card) not in (profile.level, ""),
                bool(profile.city) and norm(profile.city) not in text and card.get("remote") is not True,
                -sum(norm(s) in text for s in profile.skills))
    # ponytail: first-page search remains bounded by each source and the per-source timeout.
    candidates = sorted(found.values(), key=priority)
    checked, closed = [], 0
    async def check(card):
        nonlocal closed
        try:
            job = detail(source, await request(client, semaphore, card["url"]), card, profile.skills)
            if job:
                checked.append(job)
            else:
                closed += 1
        except (httpx.HTTPError, ValueError, TypeError, KeyError, AttributeError, TimeoutError) as exc:
            errors.append(error_text(exc))
    await asyncio.gather(*(check(card) for card in candidates))
    status = {"id": source, "name": name, "status": "ok" if checked else "error" if errors and (not search_ok or candidates) else "empty",
              "count": len(checked), "expired": closed}
    if errors:
        status["error"] = " ".join(dict.fromkeys(errors))
    return checked, status


async def search_jobs(profile):
    terms = queries(profile)
    if not all(1 <= len(t.strip()) <= 200 for t in terms):
        raise ValueError("نقش هدف برای جست‌وجو معتبر نیست.")
    key = (tuple(terms), profile.city, profile.remote_pref, profile.level, tuple(profile.skills))
    now = time.monotonic()
    if key in _cache and now - _cache[key][0] < 300:
        return dict(copy.deepcopy(_cache[key][1]), cached=True)
    semaphore = asyncio.Semaphore(4)
    async def bounded(source, client):
        try:
            return await asyncio.wait_for(search_source(client, semaphore, source, terms, profile), timeout=35)
        except TimeoutError:
            return [], {"id": source, "name": SOURCES[source][0], "status": "error", "count": 0, "error": "مهلت بررسی منبع تمام شد."}
    async with httpx.AsyncClient(timeout=10, headers={"User-Agent": "Mozilla/5.0", "x-lang": "fa"}, follow_redirects=False) as client:
        results = await asyncio.gather(*(bounded(source, client) for source in SOURCES))
    result = {"query": " / ".join(terms), "jobs": [j for jobs, _ in results for j in jobs], "sources": [status for _, status in results], "cached": False}
    if not any(s.get("error") for s in result["sources"]):
        # ponytail: bounded process-local five-minute cache; use a shared cache if multiple workers need one.
        if len(_cache) >= 128:
            _cache.pop(next(iter(_cache)))
        _cache[key] = (now, copy.deepcopy(result))
    return result

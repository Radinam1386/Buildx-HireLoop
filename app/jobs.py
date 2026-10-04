"""Bounded public job-board search. verified means a board card was observed, not that applications remain open."""
import asyncio
import copy
import hashlib
import re
import time
from datetime import datetime, timezone
from urllib.parse import quote, urlencode, urljoin, urlsplit, urlunsplit
from xml.etree import ElementTree

import httpx
from bs4 import BeautifulSoup

SOURCES = [
    {'id': 'jobinja', 'name': 'جابینجا', 'url': 'https://jobinja.ir/jobs'},
    {'id': 'jobvision', 'name': 'جاب‌ویژن', 'url': 'https://jobvision.ir/jobs'},
    {'id': 'quera', 'name': 'کوئرا', 'url': 'https://quera.org/magnet/jobs'},
    {'id': 'irantalent', 'name': 'ایران‌تلنت', 'url': 'https://www.irantalent.com/en/jobs'},
]
_HOSTS = {'jobinja': 'jobinja.ir', 'jobvision': 'jobvision.ir', 'quera': 'quera.org', 'irantalent': 'irantalent.com'}
_PATHS = {
    'jobinja': r'/companies/[^/]+/jobs/[A-Za-z0-9]+(?:/[^/]+)?/?',
    'jobvision': r'/jobs/\d+(?:/[^/]+)?/?',
    'quera': r'/magnet/jobs/[a-z0-9]{5}/?',
    'irantalent': r'/(?:en|fa)/job/[^/]+/\d+/?',
}
_cache: dict[tuple, tuple[float, dict]] = {}


def _normalized(text):
    text = ' '.join(str(text).casefold().replace('ي', 'ی').replace('ك', 'ک').replace('\u200c', ' ').split())
    return re.sub(r'(?<!\w)(?:front[\s-]*end|فرانت[\s-]*اند)(?!\w)', 'frontend', text)


def _job_url(source, url):
    parts = urlsplit(urljoin(next(s['url'] for s in SOURCES if s['id'] == source), url))
    if (parts.scheme != 'https' or parts.hostname not in (_HOSTS[source], 'www.' + _HOSTS[source])
            or parts.username or parts.password or parts.port not in (None, 443)
            or not re.fullmatch(_PATHS[source], parts.path)):
        return ''
    return urlunsplit(('https', parts.netloc.lower(), parts.path.rstrip('/'), '', ''))


def _matches(text, query, city, remote):
    # Board location languages differ; normalize common city names before filtering.
    aliases = {'tehran': 'تهران', 'mashhad': 'مشهد', 'isfahan': 'اصفهان', 'esfahan': 'اصفهان', 'karaj': 'کرج', 'shiraz': 'شیراز', 'tabriz': 'تبریز', 'qom': 'قم', 'ahvaz': 'اهواز', 'rasht': 'رشت', 'yazd': 'یزد', 'zanjan': 'زنجان'}
    haystack, city = _normalized(text), _normalized(city)
    city_text = haystack
    for english, persian in aliases.items():
        city_text = re.sub(r'(?<!\w)' + english + r'(?!\w)', persian, city_text)
        if city == english:
            city = persian
    location_matches = (bool(city) and city in city_text) or (remote and any(word in haystack for word in ('remote', 'دورکاری', 'دور کاری')))
    return all(word in haystack for word in _normalized(query).split()) and (not (city or remote) or location_matches)


def _record(source, url, title, description, company='', location='', skills=(), snippet=False):
    return {
        'id': hashlib.sha256((source + ':' + url).encode()).hexdigest()[:24],
        'title': title[:300], 'company': company[:200], 'location': location[:200],
        'url': url, 'source': source, 'description': description[:2500], 'skills': list(skills)[:30],
        'verified': not snippet, 'evidence_type': 'search_snippet' if snippet else 'listing',
        'checked_at': datetime.now(timezone.utc).isoformat(),
    }


def parse_listings(source, html, query, city='', remote=False):
    """Parse observed board cards only; never fill missing fields from guesses."""
    soup = BeautifulSoup(html, 'html.parser')
    for noise in soup.select('style, script, svg'):
        noise.decompose()
    selectors = {'jobinja': '.c-jobListView__titleLink', 'quera': 'article h2 a[href]',
                 'irantalent': 'new-position-card a[href]', 'jobvision': 'job-card a[href]'}
    jobs, seen = [], set()
    for link in soup.select(selectors[source]):
        try:
            url = _job_url(source, link.get('href', ''))
        except ValueError:
            continue
        if not url or url in seen:
            continue
        card = link.find_parent('li' if source == 'jobinja' else 'article' if source == 'quera' else 'new-position-card' if source == 'irantalent' else 'job-card') or link
        text = card.get_text(' ', strip=True)
        if not _matches(text, query, city, remote):
            continue
        title_node = link.select_one('.position-title') if source == 'irantalent' else None
        title = (title_node or link).get_text(' ', strip=True)
        company, location, skills = '', '', []
        if source == 'jobinja':
            meta = card.select('.c-jobListView__metaItem span')
            company = meta[0].get_text(' ', strip=True) if meta else ''
            location = meta[1].get_text(' ', strip=True) if len(meta) > 1 else ''
        elif source == 'irantalent':
            company_node, location_node = card.select_one('.brand-name'), card.select_one('.location')
            company = company_node.get_text(' ', strip=True) if company_node else ''
            location = location_node.get_text(' ', strip=True) if location_node else ''
        elif source == 'quera':
            logo, location_node = card.select_one('img[alt]'), card.select_one('.css-yfucoh')
            company = logo['alt'].removeprefix('لوگوی شرکت ').strip() if logo else ''
            location = location_node.get_text(' ', strip=True) if location_node else ''
            skills = [tag.get_text(' ', strip=True) for tag in card.select('.chakra-tag__root')]
        if title:
            jobs.append(_record(source, url, title, text, company, location, skills))
            seen.add(url)
        if len(jobs) == 8:
            break
    return jobs


def parse_snippets(source, xml, query, city='', remote=False):
    jobs, seen = [], set()
    for item in ElementTree.fromstring(xml).findall('./channel/item'):
        try:
            url = _job_url(source, item.findtext('link', ''))
        except ValueError:
            continue
        title = BeautifulSoup(item.findtext('title', ''), 'html.parser').get_text(' ', strip=True)
        description = BeautifulSoup(item.findtext('description', ''), 'html.parser').get_text(' ', strip=True)
        if url and title and url not in seen and _matches(title + ' ' + description, query, city, remote):
            jobs.append(_record(source, url, title, description, snippet=True))
            seen.add(url)
        if len(jobs) == 8:
            break
    return jobs


async def _fetch(client, url):
    # Redirects stay on the requested public host; no user-provided URLs are fetched.
    host = urlsplit(url).hostname
    for _ in range(4):
        async with client.stream('GET', url) as response:
            if response.is_redirect:
                url = urljoin(url, response.headers.get('location', ''))
                target = urlsplit(url)
                if target.scheme != 'https' or target.hostname not in (host, 'www.' + host, host.removeprefix('www.')):
                    raise ValueError('وب‌سایت به نشانی خارج از دامنهٔ منبع هدایت شد.')
                continue
            response.raise_for_status()
            chunks, size = [], 0
            async for chunk in response.aiter_bytes():
                size += len(chunk)
                if size > 2_000_000:
                    raise ValueError('حجم پاسخ وب‌سایت بیشتر از حد مجاز بود.')
                chunks.append(chunk)
            return b''.join(chunks).decode('utf-8', 'replace')
    raise ValueError('وب‌سایت بیش از حد به نشانی دیگری هدایت شد.')


def _error_text(exc):
    if isinstance(exc, (httpx.TimeoutException, TimeoutError)):
        return 'مهلت دریافت پاسخ از وب‌سایت تمام شد؛ کمی بعد دوباره تلاش کنید.'
    if isinstance(exc, httpx.HTTPStatusError):
        return f'وب‌سایت درخواست عمومی را با کد HTTP {exc.response.status_code} پاسخ داد.'
    if isinstance(exc, httpx.HTTPError):
        return 'اتصال به وب‌سایت برقرار نشد؛ شبکه یا دسترسی منبع را بررسی کنید.'
    if isinstance(exc, ElementTree.ParseError):
        return 'پاسخ موتور جست‌وجو قابل خواندن نبود.'
    return str(exc)[:180]


async def _search_source(client, source, query, city, remote):
    query = _normalized(query)
    identifier = source['id']
    if identifier == 'jobinja':
        url = source['url'] + '?' + urlencode({'filters[keywords][0]': query})
    elif identifier == 'jobvision':
        url = source['url'] + '/keyword/' + quote(query, safe='')
    elif identifier == 'irantalent':
        url = source['url'] + '?' + urlencode({'keyword': query})
    else:
        # ponytail: Quera searches visible first-page cards; indexed fallback extends reach until a public search API is documented.
        url = source['url']
    errors, found, direct_ok = [], [], False
    try:
        html = await _fetch(client, url)
        found = parse_listings(identifier, html, query, city, remote)
        direct_ok = bool(found) or (identifier != 'jobvision' and any(marker in html for marker in ('c-jobListView', '<article', 'new-position-card')))
        if not direct_ok:
            errors.append('صفحهٔ عمومی آگهی قابل خواندن ندارد؛ ممکن است بارگذاری جاوااسکریپت یا محدودیت دسترسی داشته باشد.')
    except (httpx.HTTPError, ValueError, TimeoutError) as exc:
        errors.append('جست‌وجوی مستقیم: ' + _error_text(exc))
    if not found:
        location_query = city.replace('"', '')
        if remote:
            location_query = f'("{location_query}" OR دورکاری OR remote)' if city else '(دورکاری OR remote)'
        search_query = ' '.join(filter(None, ['site:' + _HOSTS[identifier], query, location_query]))
        try:
            xml = await _fetch(client, 'https://www.bing.com/search?' + urlencode({'format': 'rss', 'q': search_query}))
            found = parse_snippets(identifier, xml, query, city, remote)
        except (httpx.HTTPError, ValueError, TimeoutError, ElementTree.ParseError) as exc:
            errors.append('نتایج موتور جست‌وجو: ' + _error_text(exc))
    status = {'id': identifier, 'name': source['name'], 'status': 'ok' if found else 'empty' if direct_ok else 'error', 'count': len(found)}
    if errors:
        status['error'] = ' '.join(errors)
    if found and found[0]['evidence_type'] == 'search_snippet':
        status['error'] = ' '.join(errors + ['فقط خلاصهٔ موتور جست‌وجو در دسترس است؛ باز بودن فرصت شغلی و متن کامل آگهی تأیید نشده است.'])
    return found, status


async def search_jobs(query: str, city: str = '', remote: bool = False, sources: list[str] | None = None) -> dict:
    if not isinstance(query, str) or not 1 <= len(query.strip()) <= 200:
        raise ValueError('Search query must contain 1 to 200 characters')
    if not isinstance(city, str) or len(city) > 100 or not isinstance(remote, bool):
        raise ValueError('Invalid city or remote filter')
    if sources is not None and (not isinstance(sources, list) or any(not isinstance(s, str) or s not in _HOSTS for s in sources)):
        raise ValueError('Unknown job source')
    query, city = query.strip(), city.strip()
    chosen = [s for s in SOURCES if sources is None or s['id'] in sources]
    key = (query, city, remote, tuple(s['id'] for s in chosen))
    now = time.monotonic()
    if key in _cache and now - _cache[key][0] < 300:
        return copy.deepcopy(_cache[key][1])
    async with httpx.AsyncClient(timeout=httpx.Timeout(7), headers={'User-Agent': 'Mozilla/5.0'}, follow_redirects=False) as client:
        results = await asyncio.gather(*(_search_source(client, source, query, city, remote) for source in chosen))
    result = {'jobs': [job for found, _ in results for job in found], 'sources': [status for _, status in results], 'query': query, 'city': city, 'remote': remote}
    # ponytail: bounded process-local cache; multiple workers would need a shared cache for traffic coalescing.
    if len(_cache) >= 128:
        _cache.pop(next(iter(_cache)))
    _cache[key] = (now, copy.deepcopy(result))
    return result

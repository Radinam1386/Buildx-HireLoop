# HireLoop MVP Implementation Plan

> **For agentic workers:** Use executing-plans for backend integration and dispatch independent UI and source adapters in parallel. User explicitly authorized immediate execution; no additional design approval is needed.

**Goal:** A real locally testable Persian career assistant with Iranian job search and Hormouz Luna.

**Architecture:** FastAPI serves static UI and JSON endpoints. SQLite persists users, sessions, profiles, chat and usage. One bounded agent runs tools; source adapters cache real public job data.

**Tech Stack:** Python, FastAPI, uvicorn, httpx, BeautifulSoup, SQLite, vanilla browser JavaScript.

**Spec:** docs/superpowers/specs/2026-10-04-hireloop-mvp.md

## Global Constraints
- No fake jobs or provider fallback pretending to be AI.
- No secrets in frontend/logs or Git; no paid bulk testing.
- One server, minimal dependencies; 4 reputable Iranian sources.
- Confirmed facts determine resume; authenticated user ID owns every record.

## Review Focus
- Expired/invalid sessions and another user's resume access.
- Provider missing, timeout, malformed/tool output, bounded tool loops.
- Source inaccessible, empty results, unverified search snippets.
- Profile facts absent and feedback trying to add unsupported experience.
- Mobile/keyboard operation, reload persistence and safe HTML rendering.

## Tasks
- [x] Backend: write a small unittest for authentication, ownership and resume factual integrity; observe failure; implement storage/auth/API; run checks.
- [x] Search agent: build app/jobs.py with async search_jobs(query, city='', remote=False, sources=None) returning jobs and per-source statuses; source tests with hand-written HTML fixtures plus one small live check.
- [x] UI agent: build app/static/index.html, app.js, styles.css against the documented JSON endpoints; inspect responsive UI without model spending.
- [x] Integration: implement app/agent.py, configuration and run instructions. Check tools and error paths with offline provider fixtures; one tiny real smoke call if credentials supplied.
- [x] Verify: run unittest, start server, exercise registration/login/profile/search/resume boundaries and browser flow. Review combined diff and record limitations.

## Execution ledger
- Repository cloned; only README exists. Feature branch feat/hireloop-mvp created.
- Ruling: plain browser UI instead of Next.js keeps a single deployment and no Node dependencies; all required UI behavior remains.
- Missing Hormouz URL/key requested asynchronously; independent work continues.
- User deferred credentials. Model connection uses configuration only, with explicit disabled state; no paid call made. Real provider compatibility remains unverified until credentials exist.
- Live source search returned direct cards from Jobinja, Quera and IranTalent. Jobvision's dynamic page is an explicit per-source limitation; indexed fallback evidence stays unverified.
- Browser smoke covers auth, profile persistence, desktop/mobile and actual search; reusable test saved. Offline provider boundary covers bounded tools, usage, malformed responses, truthful resume/refine and failed-turn staging.
- Independent review found stale-account responses, lossy profile text serialization and hidden tool changes on failed turns. All addressed, with a further disabled-chat-field reset on session cleanup.
- Final fresh verification: 19 offline unittest checks passed; installed-Chrome browser smoke passed authentication, lossless multiline/pipe project editing, stale-response rejection, mobile layout and logout privacy. No model calls.
- Fresh live Persian frontend query returned 12 direct listing cards: Jobinja 8, Quera 1, IranTalent 3; Jobvision explicitly unavailable. No claim of current hiring eligibility or vacancy freshness.
- Server restarted with final backend at http://127.0.0.1:8000. README and run.ps1 supplied; blank ignored .env prepared. Work remains local on feat/hireloop-mvp, without commit/push/deployment.
- Real-user follow-up: clarified actual profile confirmation buttons, made career prompts follow AI/Python as well as frontend, corrected city-or-remote semantics, added a bounded labeled broader search and persisted/displayed query/filter/source evidence in chat. Fresh 24 offline tests and browser smoke pass. The running API returned one real Jobinja Python card for Zanjan-or-remote. No model requests made during this bugfix; existing user profile/history retained.

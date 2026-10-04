# HireLoop MVP

User authorized implementation on 2026-10-04 using the supplied six-day plan, a real working flow, Iranian job search across 3–4 reputable sites, Hormouz and Luna, restrained API spending, and optional parallel agents.

Build a single-server FastAPI application with SQLite, secure cookie sessions, and a polished Persian RTL HTML/CSS/JavaScript interface. A static frontend avoids a second deployment and build toolchain for this first version. No generated job listings or pretend AI responses. Missing provider configuration is reported explicitly. Secrets stay server-side.

Core flow: sign up, sign in, continue an adaptive interview, confirm/edit a factual profile, search real Iranian job sources, see evidence-backed suitability explanations, choose a listing or paste its text, receive a resume based on confirmed facts, revise with feedback, print/save as PDF. User data is isolated by authenticated user ID. Conversation and profile persist.

One Luna agent chooses between asking a question, updating profile, searching jobs, comparing jobs, and preparing a resume. Bounded turns, token output, requests and user budgets prevent runaway spend. Job text is untrusted data. Resume contact details, projects, skills and work history come from confirmed profile fields, not invented LLM claims.

Search sources: Jobinja, Jobvision, Quera and IranTalent. Public access must be checked per source. Return original links, available source evidence, and explicit failure/empty statuses. Search snippets are labeled as snippets; unknown salary, eligibility or freshness stays unknown. Cache search results. No bypassing login or CAPTCHA.

Visual direction: blue-gray workspace (#F4F7FB), white document panels (#FFFFFF), deep navy text (#172B4D), blue actions (#245EDB), muted slate (#60708A), teal status (#137D73). Vazirmatn body, Tahoma heading fallback, Latin monospace for small source/date data. Signature: an editable career dossier next to the interview that becomes the actual resume. No decorative AI gradients or invented metrics. Keyboard focus, mobile layout and accessible labels required.

Acceptance: real sign-up/login, persisted interview, user isolation, actual source search with honest provenance/status, confirmed profile resume, feedback, printable output, error recovery. Small stdlib unittest suite plus browser smoke check. Live model smoke at most one short call once credentials exist. Keep locally runnable for user testing. No remote deployment or push unless requested.

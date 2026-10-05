# Karboom direct-source probe

Observed 2026-10-05, eight anonymous GET requests; no account, paid API, or model calls. All responses were HTTP 200. Karboom is technically compatible with the existing server-rendered HTML workflow, with limited observed keyword coverage and inconsistent structured detail metadata.

## Search and extraction

- Official page: <https://karboom.io/jobs>. Nine job cards appeared in the initial HTML.
- Actual search parameter is `q`: <https://karboom.io/jobs?q=Python> and <https://karboom.io/jobs?q=React>. Each returned one matching card. Confirmed from `input[name="q"]` and official frontend code at <https://karboom.io/js/jobs.dad67375c8e18c9c1050.js> (`Search.QS.q`, `submitSearch`, `fetchJobs`).
- Card selector: `.js-job-position-card[data-href]` or `.job-position-card[data-href]`. Use `data-href` or `h3 a[href]` for the detail URL, `h3 a` for title, `.company-name` for employer, and `.company-name ~ span.pull-right` for city. The city is a separate sibling, not part of the employer text.
- Example card: `<span class="company-name ellipsis-text m-0">پارس پویش فن آور</span><span class="p-x-5">-</span><span class="pull-right">تهران</span>`.
- The `.js-job-item[data-url]` attribute exposes `/jobs/details/{code}` for frontend detail rendering. This endpoint was observed in HTML but was not requested.
- Same search URL with `X-Requested-With: XMLHttpRequest` returns an HTML fragment, not JSON. Saved raw response `karboom-python-ajax.json` has a misleading file extension; its content and Content-Type are HTML.
- Category link `/jobs/programming-and-software` exists in official HTML; it was not requested.

## Detail evidence

Python: <https://karboom.io/jobs/wxlvgo/%D8%A8%D8%B1%D9%86%D8%A7%D9%85%D9%87-%D9%86%D9%88%DB%8C%D8%B3-back-end-python>, employer «پارس پویش فن آور», Tehran. The response contains a real Python backend description and apply CTA. It has BreadcrumbList JSON-LD but no JobPosting JSON-LD or observed absolute expiry. Therefore expiry remains unknown even though the current search page lists it.

React: <https://karboom.io/jobs/rakbvp/%D8%A8%D8%B1%D9%86%D8%A7%D9%85%D9%87-%D9%86%D9%88%DB%8C%D8%B3-reactjs-senior-front-end-developer>, employer «حسابا», Tehran. JobPosting JSON-LD includes description, `datePosted: "2026-09-29 16:34:12"`, and `validThrough: "2026-11-01 05:00:09am"`, which is after the observation date. `jobLocation.address.addressLocality` is «تهران»; `addressRegion` is empty. No remote flag or `jobLocationType` was observed. Missing remote information cannot establish onsite-only work. This is a senior React role, not a junior match.

The React `employmentType` is an HTML-escaped JSON string containing `cooperation_type: FULL_TIME`, rather than a normal schema.org enum; decode carefully or use visible HTML. Prefer absolute dates to relative card ages, which differed from the absolute posting age in this sample. Detail body selectors include `h1`, `.job-detail-info`, `.job-detail-box`, `.js-job-detail-data-group`; `.js-apply-job` is the apply CTA, which was not clicked.

## Access evidence and limits

Official <https://karboom.io/robots.txt> explicitly contains `Disallow: /*?q=`. This is relevant crawler guidance, not evidence of a supported public API or licence. Commercial automated search/republication permission was not established by this probe. No documented supported third-party API was found in the pages examined; that is not proof none exists.

Raw probe artifacts are stored locally under `output/search-benchmark/karboom-*` and are not committed. One keyword result per tested query is too small to establish broader coverage or reliability. No Jobguy requests were needed because Karboom returned usable current HTML and a verified future-expiry detail.

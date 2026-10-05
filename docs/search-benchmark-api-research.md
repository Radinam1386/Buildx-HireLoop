# Job-source API and feed research

Checked 2026-10-05 (Asia/Tehran). Official websites, their public HTML/JavaScript, robots files, and direct anonymous search requests were used. No accounts, paid APIs, model calls, or user credentials were used.

## Supported API versus internal frontend endpoints

No publicly documented, supported third-party API for searching public job listings was found for Jobinja, Jobvision, Quera, IranTalent, or e-estekhdam in this investigation. This is a search finding, not proof that partner APIs do not exist. Employer CV-search products and resume endpoints do not establish availability of a public job-listing API. Successful anonymous JSON responses below establish technical accessibility only; they do not establish an integration agreement or permission to republish.

| Source | Observed public retrieval option | Evidence / confidence |
|---|---|---|
| Jobinja | Server-rendered search HTML. Frontend exposes company-specific `GET /api/v10/companies/{company_id}/jobs` and search metadata, but no global JSON job-search endpoint was identified. | [Official homepage](https://jobinja.ir/), [official frontend bundle](https://jobinja.ir/assets/js/end_user.bundle.js?v=2478898). High confidence in observed paths; unsupported global API remains unavailable in benchmark. |
| Jobvision | Browser-internal `POST https://candidateapi.jobvision.ir/api/v1/JobPost/List`. Official-origin RSS feed is also available. | [Official frontend bundle](https://jobvision.ir/main.598c7e19fea9eec5.js), [official RSS](https://jobvision.ir/feed/). POST and response verified anonymously. |
| Quera | Next.js browser data URL under `/_next/data/{buildId}/fa/magnet/jobs.json?search=...`, mirroring search-page SSR data. This is frontend data transport, not a supported public API. | [Official jobs page](https://quera.org/magnet/jobs). Observed in browser and independently returned JSON 200. Build ID is release-dependent. |
| IranTalent | Browser-internal `POST https://api.irantalent.com/api/v1/employer/position/search`; newer service also defines `search-by-slug`. Despite the `/employer/` path, this particular endpoint searches public positions and worked anonymously. | [Official homepage](https://www.irantalent.com/), [official service bundle](https://www.irantalent.com/chunk-5RC6MANP.js). POST and listings independently verified. |
| e-estekhdam | Browser-internal `POST https://www.e-estekhdam.com/search-api/search?page=1`; official-origin RSS feed. | [Official frontend bundle](https://cdn.e-estekhdam.com/_nuxt/assets/index.XLRSbITT.js), [official RSS](https://www.e-estekhdam.com/feed/). Search returned 201 JSON, feed returned 200 RSS. |

## Working request shapes

Jobvision, observed in Chrome then independently verified:

```json
{"pageSize":30,"requestedPage":1,"keyword":"Python","sortBy":1,"searchId":null}
```

`POST /api/v1/JobPost/List` with JSON content type. Browser's optional `clientId` header may be empty; the independent probe succeeded without it. Results are `response.data.jobPosts`; total is `response.data.jobPostCount`. Fields include `id`, `title`, `company.nameFa`, `location.city.titleFa`, `properties.isRemote`, `properties.isInternship`, `activationTime.date`, and `expireTime.isExpired`.

IranTalent, confirmed by its frontend `positionSearch()` implementation and independent response:

```json
{"keyword":"Python"}
```

`POST /api/v1/employer/position/search` with JSON content type. Pagination is the query parameter `page`. Results are `response.data` (list), with `total`. Fields include `id`, `slug`, `title`, `title_farsi`, `role_description`, `role_description_farsi`, `brand_data`, `location`, `employment_type`, and `expired_at`. Public detail URL uses `/job/{slug}/{id}`. `search-by-slug` is observed in source, not independently benchmarked here.

e-estekhdam, corrected using actual UI network payload:

```json
{"query_text":"Python"}
```

`POST /search-api/search?page=1` with JSON content type, `x-lang: fa`, and `X-Requested-With: XMLHttpRequest`. Results are `response.data` (list); `response.meta` identifies the applied search. Fields include `url`, `title`, `short_title`, `brand_name`, `provinces`, `contract`, `expired`, and `technologies`. Detail `url` is already provided. A body `{"q":"..."}` is ignored: those two exploratory probes are marked `valid_query: false` and must be excluded. The alternative `ct: ["Python"]` is a different custom-text search mode, evidenced by its search metadata; prefer `query_text` for parity with the UI.

Its shared `JobsView()` frontend function uses `GET /search-api/jobs/k{uuid}` (search item `uuid` excludes the leading `k`). One anonymous request for `kql9zq` returned 200 JSON with `data.content` (HTML description), `validThrough`, `date`, `contract`, `position_levels`, and `location.text`. Saved in [`e-estekhdam-detail-probe.json`](../output/search-benchmark/e-estekhdam-detail-probe.json). That listing's expiry is 2026-10-10. No structured remote flag or required-experience field appeared in this particular response; absence of a remote mention is unknown, not proof of onsite work.

The detail exposes a concrete matching hazard: this first result for `کارآموز Python` contains ten roles in separate table rows. Python belongs to an AI role; internship belongs to a marketing/sales role. Combining tokens from the whole posting would falsely count this as a Python internship. Assess each role's row/section or leave the role relationship unverified. The aggregated `contract: ["full", "internship"]` cannot resolve that relationship.

The later Tavily detail checks also found an ATS response shape: `top`, `otherqualifications[]`, and `qualificationParts[].title/text` carry the description instead of `content`. The explicit `expired: true` flag must be honored even when `validThrough` is absent; cached `ka1pgc-json-detail.json` is one such closed vacancy. A successful detail request with an empty parsed body does not validate a search-engine snippet. The benchmark's shared detail parser now handles both shapes.

Quera uses `GET /_next/data/{buildId}/fa/magnet/jobs.json?search=Python`. Obtain `buildId` from the jobs page's `__NEXT_DATA__` rather than hardcoding it. Results are `response.pageProps.jobs.edges[].node`, total `totalCount`; fields include `pk`, `title`, `open`, `level`, `offers_remote`, `publish_time`, `company.name`, `city.name`, and `jobtechnology_set`. Only job/query metadata was retained from the response, excluding unrelated global server state.

## Independent probe results

Saved responses, requests, HTTP status, and measured duration: [`api-probes.json`](../output/search-benchmark/api-probes.json). These are first-page retrieval counts, not relevance scores or verified profile matches. All successful search probes completed in about 0.4–1.3 seconds on this machine; a single observation does not establish reliability under load.

| Query | Jobvision returned / total | IranTalent returned / total | e-estekhdam `query_text` returned | Quera returned / total |
|---|---:|---:|---:|---:|
| Python | 30 / 955 | 30 / 31 | 20 | 13 / 13 |
| React | 30 / 304 | 10 / 10 | 20 | 8 / 8 |
| machine learning | 30 / 157 | 8 / 8 | Not tested in this mode | 1 / 1 |
| یادگیری ماشین | 30 / 157 | 8 / 8 | 20 | 1 / 1 |
| کارآموز Python | 0 / 0 | 0 / 0 | 5 | 2 / 2 |

Both Quera English and Persian ML queries were measured separately and each returned one item; do not silently relabel one trial as the other. Strict multiword queries can return zero even when a broader skill search has suitable results; a fallback broadening strategy needs separate measurement.

## Feeds

[e-estekhdam RSS](https://www.e-estekhdam.com/feed/) independently returned current jobs with `title`, `link`, `description`, and `pubDate`. It declares an hourly update period. The parent benchmark also confirmed 100 items in [Jobvision RSS](https://jobvision.ir/feed/) and 20 items in the e-estekhdam feed. A latest-items feed is not a complete keyword-search index; narrow skill coverage cannot be assumed. Public feed availability does not itself grant unrestricted commercial republication rights.

## Observed access and reuse constraints

- [Jobvision terms](https://jobvision.ir/terms) restrict commercial extraction of substantial machine-readable website data and multi-user storage/transmission without prior written permission. They also restrict copying/distribution except where expressly allowed. This is relevant to retaining an internal frontend endpoint for a commercial aggregator.
- [Jobinja candidate terms](https://jobinja.ir/knowledge/job-seeker-faq/pages/job-seeker-tos) allow unchanged content with attribution for noncommercial information, require written permission for stated commercial uses, and set attribution/republication/conversion conditions. Linking an original listing is different from assuming permission to reproduce or transform its content.
- [Jobvision robots](https://jobvision.ir/robots.txt) disallow query URLs for generic crawlers. [IranTalent robots](https://www.irantalent.com/robots.txt) disallow query URLs and search-result routes for generic crawlers. These are crawler directives, not supported API documentation.
- [Quera robots](https://quera.org/robots.txt) exclude account/dashboard/employer areas; the jobs route is not among the listed exclusions. [Jobinja robots](https://jobinja.ir/robots.txt) excludes its style guide. These observations do not grant a commercial data licence.
- [e-estekhdam robots](https://www.e-estekhdam.com/robots.txt) restrict several posted/sort/filter search variants and specify delays for named crawlers. No third-party search API documentation or commercial reuse agreement was found here. Quera and IranTalent commercial reuse terms were not fully verified in this task.

For the benchmark, keep official API availability separate from internal JSON success, HTML/browser success, and RSS coverage. Select a retrieval method on measured relevance, active-listing verification, latency, failure rate, cost, and permitted product use rather than raw counts alone.

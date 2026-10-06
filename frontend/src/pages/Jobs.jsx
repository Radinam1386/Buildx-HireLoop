import { useCallback, useEffect, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { api, fa } from '../api'
import { useApp } from '../ctx'
import { Chip, Empty, ErrorBox, Meter, Skeleton, Spinner } from '../ui'

const SOURCE_NAMES = { jobinja: 'جابینجا', jobvision: 'جاب‌ویژن', quera: 'کوئرا', irantalent: 'ایران‌تلنت', karboom: 'کاربوم', pasted: 'آگهی واردشده', user_text: 'آگهی واردشده' }
const PAGE_SIZE = 12
const realMatches = (items) => (items || []).filter((m) => m.job?.source !== 'sample')
const sourceName = (id, sources = []) => SOURCE_NAMES[id] || sources.find((s) => s.id === id)?.name || id

function listingUrl(value) {
  try {
    const url = new URL(value)
    return ['http:', 'https:'].includes(url.protocol) ? url.href : null
  } catch { return null }
}

function JobCard({ m, top, onNo, busy, sources }) {
  const j = m.job
  const url = listingUrl(j.url)
  return (
    <article className="card job">
      <div className="job-top">
        <div><h3>{j.title}</h3><div className="co">{j.company} · {j.location}</div></div>
        <div style={{ display: 'flex', gap: '.35rem', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
          {j.remote && <span className="tag tag-remote">دورکاری</span>}
          {j.needs_review && <span className="tag tag-sample">نیازمند بررسی شرایط</span>}
          {j.source && <span className="tag">{sourceName(j.source, sources)}</span>}
        </div>
      </div>
      <Meter value={m.score} />
      <div className="reasons">
        {m.why_fit.length > 0 && <div className="fit"><h4>چرا مناسب است</h4><ul>{m.why_fit.map((x, i) => <li key={i}>{x}</li>)}</ul></div>}
        {m.gaps.length > 0 && <div className="gap"><h4>چه چیزی کم است</h4><ul>{m.gaps.map((x, i) => <li key={i}>{x}</li>)}</ul></div>}
      </div>
      <div style={{ display: 'flex', gap: '.3rem', flexWrap: 'wrap' }}>{(j.skills || []).map((s) => <Chip key={s}>{s}</Chip>)}</div>
      <div className="job-actions">
        <Link to={`/app/resume/${j.id}`} className={'btn ' + (top ? 'btn-primary' : 'btn-blue')}>ساخت رزومه برای این آگهی</Link>
        {url && <a href={url} target="_blank" rel="noopener noreferrer" className="btn-text">مشاهده در سایت منبع ↗</a>}
        <button className="btn-text" onClick={() => onNo(j.id)} disabled={busy}>مناسب من نیست</button>
      </div>
    </article>
  )
}

export default function Jobs() {
  const loc = useLocation()
  const nav = useNavigate()
  const { refreshKey, openRefine } = useApp()
  const [matches, setMatches] = useState(null)
  const [search, setSearch] = useState(null)
  const [running, setRunning] = useState(false)
  const [err, setErr] = useState('')
  const [remoteOnly, setRemoteOnly] = useState(false)
  const [pasteOpen, setPasteOpen] = useState(false)
  const [paste, setPaste] = useState('')
  const [busy, setBusy] = useState(false)
  const [page, setPage] = useState(1)

  const run = useCallback(async () => {
    setRunning(true); setErr('')
    try {
      const result = await api('/api/matches/run', { method: 'POST' })
      setMatches(realMatches(result.matches)); setSearch(result.search || null); setPage(1)
    }
    catch (e) { setErr(e.message); setMatches((m) => m ?? []) } finally { setRunning(false) }
  }, [])

  useEffect(() => {
    if (loc.state?.run) { nav(loc.pathname, { replace: true, state: null }); run(); return }
    api('/api/matches').then((r) => { setMatches(realMatches(r.matches)); setSearch(r.search || null); setPage(1) }).catch((e) => { setErr(e.message); setMatches([]) })
  }, [refreshKey])  // eslint-disable-line

  async function dismiss(id) {
    setBusy(true)
    try { await api('/api/refine', { method: 'POST', body: { message: 'این آگهی را نمی‌خواهم', job_id: id } }); setMatches(realMatches((await api('/api/matches')).matches)) }
    catch (e) { setErr(e.message) } finally { setBusy(false) }
  }
  async function addPasted() {
    setBusy(true); setErr('')
    try { setMatches(realMatches((await api('/api/jobs/paste', { method: 'POST', body: { text: paste } })).matches)); setPage(1); setPaste(''); setPasteOpen(false) }
    catch (e) { setErr(e.message) } finally { setBusy(false) }
  }

  if (running) return (
    <div className="card running" role="status">
      <Spinner /><h2>در حال جست‌وجو و بررسی آگهی‌ها…</h2><p className="muted">آگهی‌های منابع کاریابی دریافت و با پروفایلت مقایسه می‌شوند. این کار ممکن است کمی زمان ببرد.</p>
    </div>
  )
  if (!matches) return <div className="jobs">{[0, 1, 2].map((i) => <div key={i} className="card"><Skeleton lines={4} height={16} /></div>)}</div>

  const list = matches.filter((m) => !remoteOnly || m.job.remote)
  const pageCount = Math.max(1, Math.ceil(list.length / PAGE_SIZE))
  const currentPage = Math.min(page, pageCount)
  const pageItems = list.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE)
  const sourceErrors = search?.sources?.some((s) => s.status === 'error')
  return (
    <>
      <div className="page-head">
        <div><h2>آگهی‌های مناسب تو</h2>{matches.length > 0 && <p>{fa(matches.length)} آگهی، به ترتیب میزان تناسب</p>}</div>
        <div style={{ display: 'flex', gap: '.5rem', flexWrap: 'wrap' }}>
          <button className="btn btn-blue" onClick={run} disabled={busy}>جست‌وجوی دوباره آگهی‌ها</button>
          <button className="btn btn-ghost" onClick={() => setPasteOpen(!pasteOpen)}>افزودن آگهی خودم</button>
          <button className="btn btn-ghost" onClick={openRefine}>اصلاح ترجیحات</button>
        </div>
      </div>
      {err && <div style={{ marginBottom: '1rem' }}><ErrorBox message={err} onRetry={matches.length ? undefined : run} /></div>}
      {search && <div style={{ marginBottom: '1rem' }} aria-live="polite">
        {search.stale && <p className="muted" style={{ marginBottom: '.5rem' }}>جست‌وجوی تازه موفق نبود؛ نتایج قبلی نمایش داده می‌شوند.</p>}
        <p className="muted" style={{ marginBottom: '.5rem' }}>{search.query && `جست‌وجو برای «${search.query}»`}{search.cached && ' · نتایج ذخیره‌شده جست‌وجو'}</p>
        <div style={{ display: 'flex', gap: '.5rem', flexWrap: 'wrap', alignItems: 'flex-start' }}>
          {(search.sources || []).map((s) => {
            const label = `${sourceName(s.id, search.sources)} · ${s.status === 'error' ? 'دسترسی ناموفق' : s.status === 'empty' ? 'بدون نتیجه' : `${fa(s.count)} آگهی دریافت شد`}`
            return s.status === 'error' || s.error ? <details key={s.id}><summary style={{ cursor: 'pointer' }}><span className="tag">{label}</span></summary><p className="muted" style={{ maxWidth: '28rem', marginTop: '.5rem' }}>{s.error || 'این منبع پاسخی قابل استفاده برنگرداند. دوباره جست‌وجو کن یا سایت منبع را بررسی کن.'}</p></details> : <span className="tag" key={s.id}>{label}</span>
          })}
        </div>
      </div>}
      {pasteOpen && (
        <div className="card paste">
          <label htmlFor="paste" className="muted">متن آگهی را اینجا بچسبان؛ تحلیلش می‌کنم و تناسبش را می‌سنجم.</label>
          <textarea id="paste" className="input" value={paste} onChange={(e) => setPaste(e.target.value)} />
          <div><button className="btn btn-blue" onClick={addPasted} disabled={busy || paste.trim().length < 30}>{busy ? <Spinner /> : 'تحلیل آگهی'}</button></div>
        </div>
      )}
      {matches.length === 0 ? (
        <Empty title={sourceErrors ? 'آگهی قابل مقایسه‌ای دریافت نشد' : search ? 'برای این جست‌وجو آگهی‌ای پیدا نشد' : 'هنوز آگهی‌ای پیدا نکرده‌ایم'} text={sourceErrors ? 'دسترسی به بعضی منابع موفق نبود. وضعیت هر منبع را بررسی کن و جست‌وجو را دوباره انجام بده.' : search ? 'عنوان شغل یا ترجیحاتت را در پروفایل تغییر بده و دوباره جست‌وجو کن.' : 'اگر مصاحبه را تمام کرده‌ای، جست‌وجو را شروع کن. وگرنه اول پروفایلت را کامل کن.'}>
          <button className="btn btn-primary" onClick={run}>پیدا کردن آگهی‌ها</button>
          <Link to="/app/interview" className="btn btn-ghost">برگشت به مصاحبه</Link>
        </Empty>
      ) : (
        <>
          <div className="toolbar">
            <Chip active={!remoteOnly} onClick={() => { setRemoteOnly(false); setPage(1) }}>همه</Chip>
            <Chip active={remoteOnly} onClick={() => { setRemoteOnly(true); setPage(1) }}>فقط دورکاری</Chip>
            {list.length > 0 && <span className="muted page-count">نمایش {fa((currentPage - 1) * PAGE_SIZE + 1)} تا {fa(Math.min(currentPage * PAGE_SIZE, list.length))} از {fa(list.length)} آگهی</span>}
          </div>
          {list.length === 0 ? <Empty title="آگهی دورکاری‌ای در این فهرست نیست" text="فیلتر را بردار یا ترجیحات جست‌وجو را اصلاح کن."><button className="btn btn-ghost" onClick={() => { setRemoteOnly(false); setPage(1) }}>نمایش همه</button></Empty> :
            <>
              <div className="jobs">{pageItems.map((m, i) => <JobCard key={m.job.id} m={m} top={currentPage === 1 && i === 0} onNo={dismiss} busy={busy} sources={search?.sources} />)}</div>
              {pageCount > 1 && (
                <nav className="pagination" aria-label="صفحه‌های آگهی">
                  <button className="btn btn-ghost" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={currentPage === 1}>قبلی</button>
                  <span className="muted">صفحه {fa(currentPage)} از {fa(pageCount)}</span>
                  <button className="btn btn-ghost" onClick={() => setPage((p) => Math.min(pageCount, p + 1))} disabled={currentPage === pageCount}>بعدی</button>
                </nav>
              )}
            </>}
        </>
      )}
    </>
  )
}

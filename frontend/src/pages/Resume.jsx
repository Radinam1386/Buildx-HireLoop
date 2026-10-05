import { useEffect, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { api, fa } from '../api'
import { useApp } from '../ctx'
import { Empty, ErrorBox, Skeleton, Spinner } from '../ui'

const L = {
  fa: { summary: 'خلاصه', skills: 'مهارت‌ها', exp: 'سابقهٔ کار', proj: 'پروژه‌ها', edu: 'تحصیلات', lang: 'زبان‌ها' },
  en: { summary: 'Summary', skills: 'Skills', exp: 'Experience', proj: 'Projects', edu: 'Education', lang: 'Languages' },
}

function Sheet({ c, lang }) {
  const t = L[lang]
  return (
    <article className="sheet" dir={lang === 'en' ? 'ltr' : 'rtl'} lang={lang}>
      <h1>{c.name}</h1>
      {c.headline && <div className="head">{c.headline}</div>}
      {c.contact.length > 0 && <div className="contact">{c.contact.map((x) => <span key={x}>{x}</span>)}</div>}
      {c.summary && <section><h2>{t.summary}</h2><p>{c.summary}</p></section>}
      {c.skills.length > 0 && <section><h2>{t.skills}</h2><p>{c.skills.join(lang === 'en' ? ' · ' : '، ')}</p></section>}
      {c.experience.length > 0 && <section><h2>{t.exp}</h2>{c.experience.map((e, i) => (
        <div className="item" key={i}><div className="row"><span>{[e.title, e.org].filter(Boolean).join(' — ')}</span><small>{e.period}</small></div>
          <ul>{e.bullets.map((b, j) => <li key={j}>{b}</li>)}</ul></div>))}</section>}
      {c.projects.length > 0 && <section><h2>{t.proj}</h2>{c.projects.map((p, i) => (
        <div className="item" key={i}><div className="row"><span>{p.name}</span><small>{p.tech.join(' · ')}</small></div>
          <ul>{p.bullets.map((b, j) => <li key={j}>{b}</li>)}</ul></div>))}</section>}
      {c.education.length > 0 && <section><h2>{t.edu}</h2>{c.education.map((e, i) => (
        <div className="item" key={i}><div className="row"><span>{[e.degree, e.school].filter(Boolean).join(' — ')}</span><small>{e.period}</small></div></div>))}</section>}
      {c.languages.length > 0 && <section><h2>{t.lang}</h2><p>{c.languages.join('، ')}</p></section>}
    </article>
  )
}

function ResumeEditor() {
  const { jobId } = useParams()
  const [sp, setSp] = useSearchParams()
  const lang = sp.get('lang') === 'en' ? 'en' : 'fa'
  const { refreshKey, openRefine } = useApp()
  const [r, setR] = useState(null)
  const [err, setErr] = useState('')
  const [making, setMaking] = useState(false)

  async function load() {
    setErr(''); setR(null)
    try {
      let res = await api(`/api/resume?job_id=${jobId}&lang=${lang}`)
      if (!res) { setMaking(true); res = await api('/api/resume', { method: 'POST', body: { job_id: Number(jobId), lang } }) }
      setR(res)
    } catch (e) { setErr(e.message) } finally { setMaking(false) }
  }
  useEffect(() => { load() }, [jobId, lang, refreshKey])  // eslint-disable-line

  return (
    <>
      <div className="page-head no-print">
        <div><h2>رزومهٔ اختصاصی</h2>{r && <p className="muted">برای «{r.job.title}»{r.job.company ? ` · ${r.job.company}` : ''}</p>}</div>
        <Link to="/app/jobs" className="btn btn-ghost">برگشت به آگهی‌ها</Link>
      </div>
      <div className="rsplit">
        <div>
          {err ? <ErrorBox message={err} onRetry={load} />
            : !r ? <div className="card" role="status">{making && <p style={{ marginBottom: '1rem' }}><Spinner label="در حال نوشتن رزومه از اطلاعات واقعی تو…" /></p>}<Skeleton lines={6} height={16} /></div>
            : <Sheet c={r.content} lang={lang} />}
        </div>
        <aside className="side no-print">
          <div className="card" style={{ display: 'grid', gap: '.9rem' }}>
            <Link to="/app/resume" className="btn btn-ghost">رزومه‌های من</Link>
            <div className="seg" role="group" aria-label="زبان رزومه">
              <button className={lang === 'fa' ? 'on' : ''} onClick={() => setSp({})}>فارسی</button>
              <button className={lang === 'en' ? 'on' : ''} onClick={() => setSp({ lang: 'en' })}>English</button>
            </div>
            <button className="btn btn-primary" disabled={!r} onClick={() => window.print()}>دانلود PDF</button>
            <button className="btn btn-blue" onClick={openRefine}>درخواست تغییر</button>
            <p className="muted" style={{ fontSize: '.85rem' }}>در پنجرهٔ چاپ «ذخیره به‌صورت PDF» را انتخاب کن. رزومه فقط از اطلاعاتی ساخته شده که خودت گفته‌ای.</p>
          </div>
        </aside>
      </div>
    </>
  )
}

function SavedResumes() {
  const { refreshKey } = useApp()
  const [items, setItems] = useState(null)
  const [err, setErr] = useState('')
  async function load() {
    setErr('')
    try { setItems((await api('/api/resumes')).resumes) }
    catch (e) { setErr(e.message) }
  }
  useEffect(() => { load() }, [refreshKey]) // eslint-disable-line
  return (
    <>
      <div className="page-head">
        <div><h2>رزومه‌های من</h2><p>نسخه‌های ذخیره‌شده برای آگهی‌ها، آمادهٔ باز کردن و دریافت.</p></div>
        <Link to="/app/jobs" className="btn btn-ghost">دیدن آگهی‌ها</Link>
      </div>
      {err ? <ErrorBox message={err} onRetry={load} /> : !items ? <div className="card"><Skeleton lines={3} /></div>
        : !items.length ? <Empty title="هنوز رزومه‌ای نساخته‌ای" text="یک آگهی را انتخاب کن تا رزومهٔ متناسب با آن ساخته و اینجا ذخیره شود."><Link to="/app/jobs" className="btn btn-primary">انتخاب آگهی</Link></Empty>
        : <div className="jobs">{items.map((r) => (
          <article className="card" key={`${r.job.id}-${r.lang}`}>
            <h3>{r.job.title}</h3>
            {r.job.company && <p className="muted">{r.job.company}</p>}
            <p className="muted">{r.lang === 'en' ? 'انگلیسی' : 'فارسی'} · نسخهٔ {fa(r.version)}</p>
            <Link className="btn btn-blue" to={`/app/resume/${r.job.id}?lang=${r.lang}`}>باز کردن رزومه</Link>
          </article>
        ))}</div>}
    </>
  )
}

export default function Resume() {
  const { jobId } = useParams()
  return jobId ? <ResumeEditor /> : <SavedResumes />
}

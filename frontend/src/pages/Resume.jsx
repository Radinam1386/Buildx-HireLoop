import { useEffect, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { api, fa } from '../api'
import { useApp } from '../ctx'
import { Empty, ErrorBox, Skeleton, Spinner } from '../ui'
import ProfileEditor from '../ProfileEditor'
import TrackJob from '../TrackJob'

const L = {
  fa: { summary: 'خلاصه', skills: 'مهارت‌ها', exp: 'سابقهٔ کار', proj: 'پروژه‌ها', edu: 'تحصیلات', lang: 'زبان‌ها' },
  en: { summary: 'Summary', skills: 'Skills', exp: 'Experience', proj: 'Projects', edu: 'Education', lang: 'Languages' },
}

function EvidenceText({ text, path, evidence }) {
  if (evidence === false) return <span>{text}</span>
  const claim = evidence?.claims.find((c) => c.path === path)
  const sources = evidence?.sources.filter((s) => claim?.source_ids.includes(s.id)) || []
  return <><span>{text}</span><details className="claim-source no-print"><summary>{claim?.user_confirmed ? 'تأیید مستقیم شما' : sources.length ? 'منبع جمله' : 'بررسی منبع لازم است'}</summary>
    {sources.length ? sources.map((s) => <div key={s.id}><strong>{s.label}</strong><p dir="auto">{s.text}</p></div>) : <p>برای این جمله منبع ثبت نشده؛ پیش از ارسال بررسی یا ویرایشش کن.</p>}
    {sources.length > 0 && !claim?.user_confirmed && <p className="muted">این منبع پیشنهادی جمله است؛ معنی و نتیجهٔ ادعا را خودت بررسی کن.</p>}
  </details></>
}

function Sheet({ c, lang, evidence }) {
  const t = L[lang]
  return (
    <article className="sheet" dir={lang === 'en' ? 'ltr' : 'rtl'} lang={lang}>
      <h1>{c.name}</h1>
      {c.headline && <div className="head"><EvidenceText text={c.headline} path="headline" evidence={evidence} /></div>}
      {c.contact.length > 0 && <div className="contact">{c.contact.map((x) => <span key={x}>{x}</span>)}</div>}
      {c.summary && <section><h2>{t.summary}</h2><div><EvidenceText text={c.summary} path="summary" evidence={evidence} /></div></section>}
      {c.skills.length > 0 && <section><h2>{t.skills}</h2><p>{c.skills.join(lang === 'en' ? ' · ' : '، ')}</p></section>}
      {c.experience.length > 0 && <section><h2>{t.exp}</h2>{c.experience.map((e, i) => (
        <div className="item" key={i}><div className="row"><span>{[e.title, e.org].filter(Boolean).join(' — ')}</span><small>{e.period}</small></div>
          <ul>{e.bullets.map((b, j) => <li key={j}><EvidenceText text={b} path={`experience.${i}.bullets.${j}`} evidence={evidence} /></li>)}</ul></div>))}</section>}
      {c.projects.length > 0 && <section><h2>{t.proj}</h2>{c.projects.map((p, i) => (
        <div className="item" key={i}><div className="row"><span>{p.name}</span><small>{p.tech.join(' · ')}</small></div>
          <ul>{p.bullets.map((b, j) => <li key={j}><EvidenceText text={b} path={`projects.${i}.bullets.${j}`} evidence={evidence} /></li>)}</ul></div>))}</section>}
      {c.education.length > 0 && <section><h2>{t.edu}</h2>{c.education.map((e, i) => (
        <div className="item" key={i}><div className="row"><span>{[e.degree, e.school].filter(Boolean).join(' — ')}</span><small>{e.period}</small></div></div>))}</section>}
      {c.languages.length > 0 && <section><h2>{t.lang}</h2><p>{c.languages.join('، ')}</p></section>}
    </article>
  )
}

function ContentEditor({ resume, onSaved, onClose, jobId }) {
  const [draft, setDraft] = useState(() => {
    const c = structuredClone(resume.content)
    for (const key of ['contact', 'skills', 'languages']) c[key] = c[key].join('\n')
    for (const key of ['experience', 'projects']) for (const item of c[key]) {
      item.bullets = item.bullets.join('\n')
      if (key === 'projects') item.tech = item.tech.join('\n')
    }
    return c
  })
  const [review, setReview] = useState(false)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const change = (key, value) => { setDraft((p) => ({ ...p, [key]: value })); setReview(false) }
  const lines = (value) => value.split('\n').map((v) => v.trim()).filter(Boolean)
  function content() {
    const c = structuredClone(draft)
    for (const key of ['contact', 'skills', 'languages']) c[key] = lines(c[key])
    for (const key of ['experience', 'projects']) for (const item of c[key]) {
      item.bullets = lines(item.bullets)
      if (key === 'projects') item.tech = lines(item.tech)
    }
    return c
  }
  function itemChange(key, i, field, value) { change(key, draft[key].map((item, n) => n === i ? { ...item, [field]: value } : item)) }
  async function save(e) {
    e.preventDefault(); setBusy(true); setErr('')
    try { onSaved(await api('/api/resume', { method: 'PATCH', body: { job_id: Number(jobId), lang: resume.lang, version: resume.version, content: content() } })) }
    catch (e) { setErr(e.message) } finally { setBusy(false) }
  }
  return <form className="card content-editor no-print" onSubmit={save} aria-label="ویرایش مستقیم رزومه">
    <div className="review-head"><div><h3>ویرایش مستقیم متن رزومه</h3><p className="muted">این متن فقط برای همین نسخه است. جملهٔ تغییرکرده به عنوان تأیید مستقیم شما ثبت می‌شود.</p></div><button type="button" className="btn-text" onClick={onClose} disabled={busy}>انصراف</button></div>
    <fieldset disabled={busy}>
      {[['name', 'نام'], ['headline', 'عنوان رزومه'], ['summary', 'خلاصه']].map(([key, title]) => <label key={key}>{title}<textarea className="input" rows={key === 'summary' ? 4 : 1} dir="auto" maxLength={4000} value={draft[key]} onChange={(e) => change(key, e.target.value)} /></label>)}
      {[['contact', 'ارتباط'], ['skills', 'مهارت‌ها'], ['languages', 'زبان‌ها']].map(([key, title]) => <label key={key}>{title}، هر مورد در یک خط<textarea className="input" dir="auto" rows={3} value={draft[key]} onChange={(e) => change(key, e.target.value)} /></label>)}
      {[['experience', 'سابقهٔ کار'], ['projects', 'پروژه'], ['education', 'تحصیلات']].map(([key, title]) => <section key={key}><h4>{title}</h4>{draft[key].map((item, i) => <fieldset className="profile-item" key={i}><legend>{title} · {fa(i + 1)}</legend>{Object.entries(item).map(([field, value]) => <label key={field}>{({ title: 'عنوان', org: 'شرکت', period: 'بازه زمانی', name: 'نام پروژه', tech: 'ابزارها', bullets: 'جمله‌ها، هر مورد در یک خط', degree: 'رشته و مدرک', school: 'مؤسسه' })[field]}<textarea className="input" dir="auto" rows={field === 'bullets' ? 5 : 1} value={value} onChange={(e) => itemChange(key, i, field, e.target.value)} /></label>)}<button className="btn-text" type="button" onClick={() => change(key, draft[key].filter((_, n) => n !== i))}>حذف این مورد</button></fieldset>)}</section>)}
      <button className="btn btn-ghost" type="button" onClick={() => setReview(!review)}>مقایسهٔ قبل و بعد</button>
      {review && <div className="edit-comparison"><section><h4>نسخهٔ قبلی</h4><Sheet c={resume.content} lang={resume.lang} evidence={false} /></section><section><h4>پیشنهاد شما</h4><Sheet c={content()} lang={resume.lang} evidence={false} /></section></div>}
      {err && <ErrorBox message={err} />}
      <button className="btn btn-primary" type="submit">{busy ? 'در حال ذخیره…' : 'تأیید متن و ذخیرهٔ نسخه جدید'}</button>
    </fieldset>
  </form>
}

function ResumeEditor() {
  const { jobId } = useParams()
  const [sp, setSp] = useSearchParams()
  const lang = sp.get('lang') === 'en' ? 'en' : 'fa'
  const { refreshKey, openRefine } = useApp()
  const [r, setR] = useState(null)
  const [err, setErr] = useState('')
  const [making, setMaking] = useState(false)
  const [prep, setPrep] = useState(null)
  const [preparing, setPreparing] = useState(false)
  const [editing, setEditing] = useState(false)
  const [contentEditing, setContentEditing] = useState(false)
  const [downloading, setDownloading] = useState(false)

  useEffect(() => {
    let active = true
    setErr(''); setR(null); setPrep(null); setPreparing(false); setEditing(false); setContentEditing(false)
    Promise.all([api(`/api/resume?job_id=${jobId}&lang=${lang}`), api(`/api/resume/preparation?job_id=${jobId}`)])
      .then(([saved, preparation]) => { if (active) { setR(saved); setPrep(preparation); setPreparing(!saved) } })
      .catch((e) => { if (active) setErr(e.message) })
    return () => { active = false }
  }, [jobId, lang, refreshKey])

  function answer(index, patch) {
    setPrep((p) => ({ ...p, questions: p.questions.map((q, i) => i === index ? { ...q, ...patch } : q) }))
  }
  async function make(skip = false) {
    if (making) return
    const answers = prep.questions.map((q) => ({ id: q.id, status: skip ? 'skip' : q.status, answer: skip || q.status !== 'yes' ? '' : q.answer }))
    if (answers.some((a) => a.status === 'yes' && !a.answer.trim())) { setErr('برای مواردی که تجربه داری، یک توضیح کوتاه بنویس یا سؤال را رد کن.'); return }
    setMaking(true); setErr('')
    try {
      setPrep(await api('/api/resume/preparation', { method: 'POST', body: { job_id: Number(jobId), fingerprint: prep.fingerprint, answers } }))
      setR(await api('/api/resume', { method: 'POST', body: { job_id: Number(jobId), lang } }))
      setPreparing(false)
    } catch (e) { setErr(e.message) } finally { setMaking(false) }
  }
  async function profileSaved() {
    setEditing(false); setErr('')
    try { setPrep(await api(`/api/resume/preparation?job_id=${jobId}`)); setPreparing(true) }
    catch (e) { setErr(e.message) }
  }

  async function word() {
    setDownloading(true); setErr('')
    try {
      const blob = await api(`/api/resume/export?job_id=${jobId}&lang=${lang}`, { download: true })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a'); link.href = url; link.download = `HireLoop-${lang}-v${r.version}.docx`
      document.body.appendChild(link); link.click(); link.remove()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (e) { setErr(e.message) } finally { setDownloading(false) }
  }

  return (
    <>
      <div className="page-head no-print">
        <div><h2>رزومهٔ اختصاصی</h2>{(r || prep) && <p className="muted">برای «{(r || prep).job.title}»{(r || prep).job.company ? ` · ${(r || prep).job.company}` : ''}</p>}</div>
        <Link to="/app/jobs" className="btn btn-ghost">برگشت به آگهی‌ها</Link>
      </div>
      {editing && prep && <ProfileEditor profile={prep.profile} onClose={() => setEditing(false)} onSaved={profileSaved} />}
      {contentEditing && r && <ContentEditor key={`${jobId}:${lang}:${r.version}`} resume={r} jobId={jobId} onClose={() => setContentEditing(false)} onSaved={(saved) => { setR(saved); setContentEditing(false) }} />}
      {err && <div className="no-print" style={{ marginBottom: '1rem' }}><ErrorBox message={err} onRetry={!prep ? () => location.reload() : undefined} /></div>}
      <div className="rsplit">
        <div>
          {prep && preparing && <form className="card resume-prep no-print" onSubmit={(e) => { e.preventDefault(); make() }}>
            <h3>چند نکته برای همین آگهی</h3>
            <p className="muted">{prep.questions.length ? 'این موارد در پروفایلت مشخص نیستند. اگر تجربه داری توضیح بده؛ پاسخ‌ها فقط برای رزومهٔ همین آگهی استفاده می‌شوند.' : 'اطلاعات اولیهٔ این آگهی را داریم. می‌توانی اطلاعاتت را مرور کنی و رزومه را بسازی.'}</p>
            <fieldset disabled={making || editing}>
              {prep.questions.map((q, i) => <fieldset className="prep-question" key={q.id}>
                <legend>{q.question}</legend>
                <div className="answer-options">{[['yes', 'تجربه دارم'], ['no', 'تجربه ندارم'], ['skip', 'رد کردن']].map(([value, title]) => <label key={value}><input type="radio" name={`answer-${q.id}`} value={value} checked={q.status === value} onChange={() => answer(i, { status: value })} />{title}</label>)}</div>
                {q.status === 'yes' && <label>توضیح تجربهٔ واقعی<textarea className="input" rows={3} value={q.answer} onChange={(e) => answer(i, { answer: e.target.value })} maxLength={2000} placeholder="خودت چه کاری انجام دادی و نتیجه چه بود؟" required /></label>}
              </fieldset>)}
              <div className="review-actions"><button className="btn btn-primary" type="submit">{making ? <Spinner label="در حال ساخت رزومه…" /> : r ? 'ذخیره و ساخت نسخهٔ جدید' : 'ذخیره و ساخت رزومه'}</button><button className="btn btn-ghost" type="button" onClick={() => make(true)}>ساخت فقط با پروفایل فعلی</button>{r && <button className="btn-text" type="button" onClick={() => setPreparing(false)}>برگشت به نسخهٔ ذخیره‌شده</button>}</div>
            </fieldset>
          </form>}
          {!prep && !err && <div className="card"><Skeleton lines={6} height={16} /></div>}
          {r && <Sheet c={r.content} lang={lang} evidence={r.evidence} />}
        </div>
        <aside className="side no-print">
          <div className="card" style={{ display: 'grid', gap: '.9rem' }}>
            <Link to="/app/resume" className="btn btn-ghost">رزومه‌های من</Link>
            <Link to={`/app/jobs/${jobId}`} className="btn btn-ghost">تحلیل شرایط آگهی</Link>
            <Link to={`/app/practice/${jobId}`} className="btn btn-blue">تمرین مصاحبه برای این شغل</Link>
            <div className="seg" role="group" aria-label="زبان رزومه">
              <button className={lang === 'fa' ? 'on' : ''} disabled={making || contentEditing} onClick={() => setSp({})}>فارسی</button>
              <button className={lang === 'en' ? 'on' : ''} disabled={making || contentEditing} onClick={() => setSp({ lang: 'en' })}>English</button>
            </div>
            <button className="btn btn-ghost" disabled={!prep || making} onClick={() => setEditing(!editing)}>مرور و ویرایش اطلاعات</button>
            {r && !preparing && <button className="btn btn-blue" disabled={!prep || making} onClick={() => setPreparing(true)}>تکمیل اطلاعات این آگهی</button>}
            <button className="btn btn-primary" disabled={!r || making} onClick={() => window.print()}>دانلود PDF</button>
            <button className="btn btn-ghost" disabled={!r || making || downloading} onClick={word}>{downloading ? 'در حال دریافت…' : 'دانلود Word'}</button>
            <button className="btn btn-blue" disabled={!r || making || preparing || editing} onClick={() => setContentEditing(!contentEditing)}>ویرایش مستقیم رزومه</button>
            <button className="btn btn-ghost" disabled={!r || making || contentEditing} onClick={openRefine}>درخواست تغییر با گفت‌وگو</button>
            <TrackJob key={`${jobId}:${lang}`} jobId={jobId} lang={r?.lang} resumeVersion={r?.version} />
            {r && <p className="muted">نسخهٔ {fa(r.version)} · با باز کردن مجدد، همین نسخه نمایش داده می‌شود.</p>}
            <p className="muted" style={{ fontSize: '.85rem' }}>پیش از ارسال، متن رزومه را بررسی کن. برای PDF در پنجرهٔ چاپ «ذخیره به‌صورت PDF» را انتخاب کن.</p>
          </div>
          {!!r?.evidence?.omitted?.length && <div className="card"><h3>ادعاهای کنارگذاشته‌شده</h3><p className="muted">این جمله‌ها عددی داشتند که در منبع پیدا نشد و وارد رزومه نشدند.</p>{r.evidence.omitted.map((item, i) => <details key={i}><summary>مرور ادعای {fa(i + 1)}</summary><p dir="auto">{item.text}</p><p>{item.reason}</p></details>)}</div>}
          {r?.tailoring && <div className="card tailoring"><h3>ارتباط رزومه با آگهی</h3>
            {r.tailoring.highlighted_skills.length > 0 && <div><h4>مهارت‌های مرتبط در رزومه</h4><p>{r.tailoring.highlighted_skills.join('، ')}</p></div>}
            {r.tailoring.projects.length > 0 && <div><h4>ترتیب پروژه‌ها در این نسخه</h4><ol>{r.tailoring.projects.map((name, i) => <li key={i}>{name}</li>)}</ol></div>}
            {r.tailoring.unconfirmed.length > 0 && <div><h4>نیازهای ذکر یا تأییدنشده</h4><p>{r.tailoring.unconfirmed.join('، ')}</p><p className="muted">این موارد در اطلاعات این نسخه پشتوانه ندارند؛ این به معنی بلد نبودن تو نیست.</p></div>}
          </div>}
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

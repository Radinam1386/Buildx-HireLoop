import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, fa } from '../api'
import { ErrorBox, Skeleton } from '../ui'

const SCORE_LABELS = { technical_accuracy: 'درستی فنی', relevance: 'ارتباط با سؤال', specificity: 'جزئیات مشخص', clarity: 'وضوح' }

function Feedback({ item }) {
  return <section className="card practice-feedback" aria-label="بازخورد پاسخ">
    <h3>بازخورد پاسخ تو</h3>
    <p className="prewrap">{item.feedback.feedback}</p>
    <dl>{Object.entries(item.feedback.scores).map(([key, value]) => <div key={key}><dt>{SCORE_LABELS[key]}</dt><dd>{fa(value)} از ۵</dd></div>)}</dl>
    <details><summary>دیدن پاسخ نمونه</summary><p className="muted">این نمونه برای یادگیری است؛ تجربه و عددی که نداشته‌ای به پاسخ خود اضافه نکن.</p><p className="prewrap">{item.feedback.example_answer}</p></details>
  </section>
}

export default function Practice() {
  const { jobId } = useParams()
  const [data, setData] = useState(null)
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [review, setReview] = useState(false)
  const [restartConfirm, setRestartConfirm] = useState(false)

  useEffect(() => {
    let active = true
    setData(null); setErr(''); setText(''); setReview(false); setRestartConfirm(false)
    api(`/api/practice?job_id=${jobId}`).then(result => {
      if (active) { setData(result); setReview(Boolean(result.session?.history?.length)) }
    }).catch(e => { if (active) setErr(e.message) })
    return () => { active = false }
  }, [jobId])

  async function start(restart = false) {
    setBusy(true); setErr('')
    try {
      setData(await api('/api/practice/start', { method: 'POST', body: { job_id: Number(jobId), restart, version: data.session?.version } }))
      setText(''); setReview(false); setRestartConfirm(false)
    } catch (e) { setErr(e.message) } finally { setBusy(false) }
  }

  async function submit(event) {
    event.preventDefault()
    if (!text.trim() || busy) return
    setBusy(true); setErr('')
    const session = data.session
    try {
      setData(await api(`/api/practice/${session.id}/answer`, { method: 'POST', body: {
        version: session.version, question_id: session.current_question.id, answer: text.trim(),
      } }))
      setText(''); setReview(true)
    } catch (e) { setErr(e.message) } finally { setBusy(false) }
  }

  async function reloadSaved() {
    setBusy(true); setErr('')
    try { setData(await api(`/api/practice?job_id=${jobId}`)); setReview(false) }
    catch (e) { setErr(e.message) } finally { setBusy(false) }
  }

  if (!data) return err ? <ErrorBox message={err} onRetry={reloadSaved} /> : <div className="card"><Skeleton lines={4} /></div>
  const session = data.session
  const latest = session?.history.at(-1)
  const question = session?.current_question

  return <div className="practice-page">
    <div className="page-head"><div><h2>تمرین مصاحبه</h2><p>{data.job.title}{data.job.company && ` · ${data.job.company}`}</p></div><Link className="btn btn-ghost" to={`/app/jobs/${jobId}`}>بازگشت به آگهی</Link></div>
    {err && <ErrorBox message={err} />}
    {err && session && <button type="button" className="btn btn-ghost" disabled={busy} onClick={reloadSaved}>باز کردن نسخه ذخیره‌شده، با حفظ متن پاسخ</button>}
    {!session ? <section className="card"><h3>پنج سؤال، متناسب با این شغل</h3><p>سؤال‌های فنی و رفتاری از آگهی و پروفایل تو ساخته می‌شوند. ابتدا خودت پاسخ می‌دهی و سپس بازخورد و نمونه را می‌بینی. هر سؤال ممکن است یک سؤال تکمیلی داشته باشد.</p><p className="muted">شروع و ارسال هر پاسخ از مدل استفاده می‌کند. جلسه و پاسخ‌ها خصوصی ذخیره می‌شوند.</p><button className="btn btn-primary" onClick={() => start()} disabled={busy}>{busy ? 'در حال آماده‌سازی سؤال‌ها…' : 'شروع تمرین'}</button></section> : <>
      <section className="card"><p>پاسخ به {fa(session.primary_answered)} از ۵ سؤال اصلی · {fa(session.total_answered)} پاسخ ثبت‌شده</p><div className="progress" role="progressbar" aria-label="پیشرفت سؤال‌های اصلی" aria-valuemin={0} aria-valuemax={5} aria-valuenow={session.primary_answered}><span style={{ width: `${session.primary_answered * 20}%` }} /></div><p className="muted">جلسه ذخیره شده است؛ بعداً از همین‌جا ادامه بده.</p></section>
      {session.completed ? <section className="card"><h3>گزارش تمرین</h3><p>میانگین امتیاز پاسخ‌های ثبت‌شده، از ۵. این امتیاز تضمین نتیجه استخدام نیست.</p><dl>{Object.entries(session.report.scores).map(([key, value]) => <div key={key}><dt>{SCORE_LABELS[key]}</dt><dd>{fa(value)}</dd></div>)}</dl>{session.history.map(item => <details key={item.question.id}><summary>{item.question.text}</summary><p className="prewrap">{item.answer}</p><Feedback item={item} /></details>)}</section> : review && latest ? <>
        <section className="card"><h3>{latest.question.text}</h3><p className="prewrap">{latest.answer}</p></section><Feedback item={latest} /><button className="btn btn-primary" onClick={() => setReview(false)}>ادامه به {question.primary ? 'سؤال بعدی' : 'سؤال تکمیلی'}</button>
      </> : <section className="card"><p className="muted">{question.primary ? 'سؤال اصلی' : 'سؤال تکمیلی'} · {question.kind === 'technical' ? 'فنی' : 'رفتاری'}</p><h3>{question.text}</h3><form onSubmit={submit}><label htmlFor="practice-answer">پاسخ تو</label><textarea id="practice-answer" rows={7} maxLength={3000} value={text} onChange={e => setText(e.target.value)} disabled={busy} placeholder="از تجربه واقعی خودت و کاری که انجام دادی بنویس…" /><p className="muted">{fa(text.length)} / ۳۰۰۰</p><button className="btn btn-primary" disabled={busy || !text.trim()}>{busy ? 'در حال بررسی پاسخ…' : 'ثبت پاسخ و دریافت بازخورد'}</button></form></section>}
      <section className="card"><button className="btn btn-ghost" disabled={busy} onClick={() => setRestartConfirm(!restartConfirm)}>شروع جلسه جدید</button>{restartConfirm && <div><p>جلسه جدید جایگزین سؤال‌ها و گزارش این جلسه می‌شود.</p><button className="btn btn-primary" disabled={busy} onClick={() => start(true)}>{busy ? 'در حال آماده‌سازی…' : 'تأیید و شروع دوباره'}</button><button className="btn btn-ghost" disabled={busy} onClick={() => setRestartConfirm(false)}>انصراف</button></div>}</section>
    </>}
  </div>
}

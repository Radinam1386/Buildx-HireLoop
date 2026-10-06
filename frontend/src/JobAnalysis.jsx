import { useEffect, useState } from 'react'
import { api } from './api'
import { ErrorBox, Spinner } from './ui'

const STATUS = { evidenced: 'شاهد در پروفایل', ask: 'نیاز به پاسخ شما', conflict: 'ناسازگاری مشخص', unknown: 'نامعلوم' }
export default function JobAnalysis({ jobId, onAnalyzed }) {
  const [data, setData] = useState(null)
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true
    setData(null); setError(''); setText('')
    api(`/api/jobs/${jobId}/analysis`).then(result => {
      if (active) { setData(result); onAnalyzed?.(result) }
    }).catch(e => { if (active) setError(e.message) })
    return () => { active = false }
  }, [jobId])
  async function analyze(e) {
    e.preventDefault(); setBusy(true); setError('')
    try {
      const result = await api(`/api/jobs/${jobId}/analysis`, { method: 'POST', body: text.trim() ? { text } : {} })
      setData(result); onAnalyzed?.(result)
    } catch (e) { setError(e.message) }
    finally { setBusy(false) }
  }
  const analysis = data?.analysis
  return <section className="card job-analysis" aria-labelledby="analysis-title">
    <h2 id="analysis-title">تحلیل شرایط آگهی</h2>
    <p>تحلیل با درخواست شما انجام می‌شود؛ مهارتِ بدون شاهد به رزومه اضافه نمی‌شود.</p>
    <form onSubmit={analyze}>
      <label htmlFor="analysis-source">متن کامل آگهی (اختیاری)</label>
      <textarea id="analysis-source" value={text} onChange={e => setText(e.target.value)} maxLength={12000} minLength={30} rows={5} placeholder="اگر متن ذخیره‌شده خلاصه است، متن کامل را اینجا وارد کن." />
      <button className="btn btn-primary" disabled={busy}>{busy ? <Spinner label="در حال تحلیل" /> : 'تحلیل آگهی'}</button>
    </form>
    {error && <ErrorBox message={error} />}
    {analysis && <>
      <p className="muted">{analysis.scope_notice}</p>
      {['required', 'preferred'].map(priority => <div key={priority}>
        <h3>{priority === 'required' ? 'الزامی' : 'ترجیحی'}</h3>
        {analysis.requirements.filter(r => r.priority === priority).map(r => <article className="requirement" key={r.id}>
          <strong>{r.label}</strong> <span className="chip">{STATUS[r.status]}</span>
          <blockquote dir="auto">{r.quote}</blockquote>
          {r.evidence.map((e, i) => <p key={i}>{e}</p>)}
        </article>)}
      </div>)}
      {!!analysis.unknowns.length && <><h3>موارد نیازمند بررسی</h3><ul>{analysis.unknowns.map((u, i) => <li key={i}>{u}</li>)}</ul></>}
      <details><summary>متن منبع تحلیل</summary><p dir="auto" style={{ whiteSpace: 'pre-wrap' }}>{analysis.source_text}</p></details>
    </>}
  </section>
}

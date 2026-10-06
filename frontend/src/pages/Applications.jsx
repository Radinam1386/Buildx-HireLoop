import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, fa } from '../api'
import { Empty, ErrorBox, Skeleton } from '../ui'

const statuses = [['saved', 'ذخیره‌شده'], ['sent', 'ارسال‌شده'], ['interview', 'مصاحبه'], ['rejected', 'ردشده'], ['offer', 'پیشنهاد همکاری']]

function Snapshot({ snapshot }) {
  function readable(value) {
    if (Array.isArray(value)) return value.map(readable).filter(Boolean).join('\n')
    if (value && typeof value === 'object') return Object.entries(value).filter(([key]) => !key.startsWith('_')).map(([, item]) => readable(item)).filter(Boolean).join('\n')
    return value == null ? '' : String(value)
  }
  return <details><summary>رزومهٔ ثبت‌شده، {snapshot.lang === 'en' ? 'انگلیسی' : 'فارسی'}، نسخهٔ {fa(snapshot.version)}</summary>
    <p className="muted">این متن با ویرایش یا ساخت دوبارهٔ رزومه تغییر نمی‌کند.</p>
    <article className="sheet" dir={snapshot.lang === 'en' ? 'ltr' : 'rtl'} lang={snapshot.lang} style={{ whiteSpace: 'pre-wrap' }}>{readable(snapshot.content)}</article>
  </details>
}

function ApplicationCard({ row, onSaved }) {
  const [status, setStatus] = useState(row.status)
  const [date, setDate] = useState(row.date || '')
  const [notes, setNotes] = useState(row.notes)
  const [resumes, setResumes] = useState(null)
  const [choice, setChoice] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)
  async function loadResumes() {
    setError('')
    try { setResumes((await api('/api/resumes')).resumes.filter((r) => r.job.id === row.job.id)) }
    catch (e) { setError(e.message) }
  }
  async function save(e) {
    e.preventDefault(); setBusy(true); setError(''); setSaved(false)
    const selected = resumes?.find((r) => `${r.lang}:${r.version}` === choice)
    try {
      const body = { version: row.version, status, date: date || null, notes, ...(selected ? { resume_lang: selected.lang, resume_version: selected.version } : {}) }
      onSaved(await api(`/api/applications/${row.id}`, { method: 'PATCH', body })); setChoice(''); setResumes(null); setSaved(true)
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }
  return <article className="card application-card">
    <h3>{row.job.title}</h3><p className="muted">{row.job.company}</p>
    <form onSubmit={save}><fieldset disabled={busy}>
      <label>وضعیت<select className="input" value={status} onChange={(e) => { setStatus(e.target.value); setSaved(false) }}>{statuses.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <label>تاریخ<input className="input" type="date" value={date} onChange={(e) => setDate(e.target.value)} /></label>
      <label>یادداشت<textarea className="input" rows={3} maxLength={5000} value={notes} onChange={(e) => setNotes(e.target.value)} /></label>
      <p className="muted">{row.resume_snapshot ? `رزومهٔ ثبت‌شده: نسخهٔ ${fa(row.resume_snapshot.version)}` : 'نسخهٔ رزومه ثبت نشده است.'}</p>
      {!resumes ? <button type="button" className="btn-text" onClick={loadResumes}>{row.resume_snapshot ? 'انتخاب نسخهٔ جدید به جای متن ثبت‌شده' : 'انتخاب رزومهٔ ارسال‌شده'}</button> : <label>رزومه<select className="input" value={choice} onChange={(e) => setChoice(e.target.value)}><option value="">{row.resume_snapshot ? 'حفظ متن ثبت‌شده' : 'بدون ثبت رزومه'}</option>{resumes.map((r) => <option key={r.lang} value={`${r.lang}:${r.version}`}>{r.lang === 'en' ? 'انگلیسی' : 'فارسی'}، نسخهٔ {fa(r.version)}</option>)}</select></label>}
      <button className="btn btn-primary" type="submit">{busy ? 'در حال ذخیره…' : 'ذخیره تغییرها'}</button>
    </fieldset></form>
    {saved && <p role="status">تغییرها ذخیره شد.</p>}
    {error && <p role="alert">{error}</p>}
    {row.resume_snapshot && <Snapshot snapshot={row.resume_snapshot} />}
    <Link className="btn-text" to={`/app/resume/${row.job.id}`}>رزومهٔ فعلی</Link>
  </article>
}

export default function Applications() {
  const [rows, setRows] = useState(null)
  const [error, setError] = useState('')
  async function load() {
    setError('')
    try { setRows((await api('/api/applications')).applications) } catch (e) { setError(e.message) }
  }
  useEffect(() => { load() }, [])
  return <><div className="page-head"><div><h2>رهگیر درخواست‌ها</h2><p>وضعیت را خودت ثبت کن. باز کردن لینک آگهی به معنی ارسال نیست.</p></div><Link className="btn btn-ghost" to="/app/jobs">آگهی‌ها</Link></div>
    {error ? <ErrorBox message={error} onRetry={load} /> : rows === null ? <div className="card"><Skeleton lines={4} /></div> : !rows.length ? <Empty title="درخواستی ثبت نشده" text="از صفحهٔ آگهی یا رزومه، آگهی را در رهگیر ذخیره کن." /> : <div className="jobs">{rows.map((row) => <ApplicationCard key={row.id} row={row} onSaved={(updated) => setRows((items) => items.map((item) => item.id === updated.id ? updated : item))} />)}</div>}
  </>
}

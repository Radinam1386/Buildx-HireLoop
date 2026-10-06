import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from './api'

export default function TrackJob({ jobId, lang, resumeVersion }) {
  const [saved, setSaved] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function save(sent) {
    setBusy(true); setError('')
    try {
      const body = { job_id: Number(jobId), status: sent ? 'sent' : 'saved', ...(sent ? { resume_lang: lang, resume_version: resumeVersion } : {}) }
      const row = await api('/api/applications', { method: 'POST', body })
      if (sent && (row.status !== 'sent' || row.resume_snapshot?.lang !== lang || row.resume_snapshot?.version !== resumeVersion)) await api(`/api/applications/${row.id}`, { method: 'PATCH', body: { status: 'sent', resume_lang: lang, resume_version: resumeVersion, version: row.version } })
      setSaved(true)
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }
  return <div className="track-job no-print">
    <button className="btn btn-ghost" disabled={busy} onClick={() => save(false)}>ذخیره در رهگیر</button>
    {lang && resumeVersion && <button className="btn btn-blue" disabled={busy} onClick={() => save(true)}>ارسال کردم، ثبت همین نسخه</button>}
    {saved && <p role="status"><Link to="/app/applications">در رهگیر ذخیره شد</Link></p>}
    {error && <p role="alert">{error}</p>}
  </div>
}

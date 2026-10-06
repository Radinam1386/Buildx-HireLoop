import { useState } from 'react'
import { api } from './api'
import { ErrorBox } from './ui'
import ProfileEditor from './ProfileEditor'

const LABELS = { name: 'نام', city: 'شهر', level: 'سطح تجربه', target_role: 'نقش هدف', remote_pref: 'نوع همکاری', skills: 'مهارت‌ها', experience: 'سابقهٔ کار', projects: 'پروژه‌ها', education: 'تحصیلات', languages: 'زبان‌ها', links: 'ارتباط', goals: 'هدف شغلی' }

export default function ResumeImport({ profile, onImported, onClose }) {
  const [text, setText] = useState('')
  const [proposal, setProposal] = useState(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  async function extract(e) {
    e.preventDefault(); setBusy(true); setErr('')
    try { setProposal(await api('/api/profile/import', { method: 'POST', body: { text: text.trim() } })) }
    catch (e) { setErr(e.message) } finally { setBusy(false) }
  }
  return <section className="card no-print" aria-label="ورود رزومهٔ موجود">
    <div className="review-head"><div><h3>ورود رزومهٔ موجود</h3><p className="muted">متن رزومه را بچسبان؛ استخراج با مدل انجام می‌شود. فقط پس از مرور و زدن ذخیره، پروفایل تغییر می‌کند.</p></div>{onClose && <button type="button" className="btn-text" onClick={onClose} disabled={busy}>بستن</button>}</div>
    {!proposal ? <form onSubmit={extract}>
      <label htmlFor="resume-import-text">متن رزومه</label>
      <textarea id="resume-import-text" className="input" rows={12} value={text} onChange={(e) => setText(e.target.value)} minLength={60} maxLength={15000} required disabled={busy} />
      <p className="muted">۶۰ تا ۱۵٬۰۰۰ نویسه. مهارت‌های قبلی و سابقهٔ گفت‌وگو حفظ می‌شوند.{profile?.name ? ` پروفایل فعلی: ${profile.name}` : ''}</p>
      {err && <ErrorBox message={err} />}
      <button className="btn btn-primary" disabled={busy || text.trim().length < 60}>{busy ? 'در حال استخراج…' : 'استخراج و مرور پیشنهاد'}</button>
    </form> : <>
      {proposal.warnings.map((warning, i) => <p className="muted" key={i}>{warning}</p>)}
      <p>بخش‌های پیشنهادی: {proposal.changes.map((key) => LABELS[key] || key).join('، ') || 'تغییری پیدا نشد'}</p>
      <details><summary>مقایسه با متن اصلی</summary><pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{text}</pre></details>
      <ProfileEditor profile={proposal.profile} onSaved={onImported} onClose={() => setProposal(null)} />
    </>}
  </section>
}

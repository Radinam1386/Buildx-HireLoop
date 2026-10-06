import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, fa } from '../api'
import { Chip, ErrorBox, Skeleton } from '../ui'
import ProfileEditor from '../ProfileEditor'
import ResumeImport from '../ResumeImport'
import { useApp } from '../ctx'

const LEVEL = { intern: 'کارآموز', junior: 'تازه‌کار', mid: 'میانی', senior: 'ارشد' }
const REMOTE = { remote: 'دورکاری', hybrid: 'ترکیبی', onsite: 'حضوری', any: 'فرقی ندارد' }

function ProfilePanel({ s, open, onClose }) {
  const p = s.profile
  const row = (label, value) => value ? <><dt>{label}</dt><dd>{value}</dd></> : null
  return (
    <aside className={'card profile' + (open ? ' open' : '')} aria-label="پروفایل من">
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
          <h3>پروفایل تو</h3><strong>{fa(s.completeness)}٪</strong>
        </div>
        <div className="progress" role="progressbar" aria-valuenow={s.completeness} aria-valuemin={0} aria-valuemax={100}><span style={{ width: `${s.completeness}%` }} /></div>
      </div>
      <dl>
        {row('نام', p.name)}
        {row('شهر', p.city)}
        {row('سطح', LEVEL[p.level])}
        {row('نقش هدف', p.target_role)}
        {row('نوع کار', REMOTE[p.remote_pref])}
        {p.skills.length > 0 && <><dt>مهارت‌ها</dt><dd>{p.skills.map((x) => <Chip key={x}>{x}</Chip>)}</dd></>}
        {p.projects.length > 0 && <><dt>پروژه‌ها</dt><dd>{p.projects.map((x) => <Chip key={x.name}>{x.name}</Chip>)}</dd></>}
        {p.experience.length > 0 && <><dt>سابقه</dt><dd>{p.experience.map((x, i) => <Chip key={i}>{x.title || x.org}</Chip>)}</dd></>}
        {p.education.length > 0 && <><dt>تحصیلات</dt><dd>{p.education.map((x, i) => <Chip key={i}>{x.degree || x.school}</Chip>)}</dd></>}
      </dl>
      {s.missing.length > 0 && (
        <div><p className="muted" style={{ fontSize: '.88rem' }}>هنوز لازم است:</p>
          <ul className="todo">{s.missing.map((m) => <li key={m}>{m}</li>)}</ul></div>
      )}
      <button className="btn btn-ghost profile-toggle" onClick={onClose}>بستن</button>
    </aside>
  )
}

const TRACK_CHIPS = [
  'برنامه‌نویس بک‌اند',
  'برنامه‌نویس فرانت‌اند',
  'برنامه‌نویس فول‌استک',
  'مهندس هوش مصنوعی (AI/ML)',
  'توسعه‌دهنده موبایل',
  'مهندس دواپس',
]

export default function Interview() {
  const nav = useNavigate()
  const { refreshKey } = useApp()
  const [s, setS] = useState(null)
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [panel, setPanel] = useState(false)
  const [pending, setPending] = useState(null)
  const [editing, setEditing] = useState(false)
  const [importing, setImporting] = useState(false)
  const started = useRef(false)
  const logRef = useRef(null)

  async function post(message) {
    setBusy(true); setErr('')
    try { setS(await api('/api/interview/message', { method: 'POST', body: { message } })); setPending(null) }
    catch (e) { setErr(e.message); setPending(message) } finally { setBusy(false) }
  }

  useEffect(() => {
    let active = true
    api('/api/interview').then((st) => {
      if (!active) return
      setS(st)
      if (!started.current && !st.ready && !st.messages.length) { started.current = true; post('') }
    }).catch((e) => { if (active) setErr(e.message) })
    return () => { active = false }
  }, [refreshKey])
  useEffect(() => { logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: 'smooth' }) }, [s, busy])

  function send() {
    const m = text.trim()
    if (!m || busy) return
    setText('')
    setS((st) => ({ ...st, messages: [...st.messages, { role: 'user', content: m }] }))
    post(m)
  }

  function sendChip(c) {
    if (busy) return
    setText('')
    setS((st) => ({ ...st, messages: [...st.messages, { role: 'user', content: c }] }))
    post(c)
  }

  if (!s) return err ? <ErrorBox message={err} onRetry={() => location.reload()} /> : <div className="card"><Skeleton lines={4} height={18} /></div>

  return (
    <>
      <div className="page-head">
        <div><h2>پروفایل شغلی تو</h2><p>نقش و مهارت‌ها برای شروع جست‌وجو کافی‌اند. جزئیات پروژه‌ها را می‌توانی بعداً برای هر آگهی تکمیل کنی.</p></div>
        <div className="review-actions"><button className="btn btn-blue" onClick={() => { setImporting(!importing); setEditing(false) }} disabled={busy}>ورود رزومهٔ موجود</button><button className="btn btn-ghost" onClick={() => { setEditing(!editing); setImporting(false) }} disabled={busy}>مرور و ویرایش اطلاعات</button><button className="btn btn-ghost profile-toggle" onClick={() => setPanel(true)}>پروفایل من · {fa(s.completeness)}٪</button></div>
      </div>
      {editing && <ProfileEditor profile={s.profile} onClose={() => setEditing(false)} onSaved={(state) => { setS(state); setEditing(false) }} />}
      {importing && <ResumeImport profile={s.profile} onClose={() => setImporting(false)} onImported={(state) => { setS(state); setImporting(false) }} />}
      <div className="split">
        <section className="card chat" aria-label="گفتگوی مصاحبه">
          <div className="chat-log" ref={logRef} aria-live="polite">
            {!s.messages.length && s.ready && <div className="profile-imported"><h3>اطلاعاتت ثبت شده است</h3><p>می‌توانی جست‌وجوی آگهی‌ها را شروع کنی. برای تکمیل سابقه، از ویرایش اطلاعات استفاده کن یا همین‌جا دربارهٔ پروژه‌هایت بنویس.</p></div>}
            {s.messages.map((m, i) => <div key={i} className={'msg ' + (m.role === 'user' ? 'msg-u' : 'msg-a')}>{m.content}</div>)}
            {busy && <div className="typing" aria-label="در حال فکر کردن"><i /><i /><i /></div>}
            {err && <ErrorBox message={err} onRetry={pending !== null ? () => post(pending) : undefined} />}
          </div>
          {s.ready && (
            <div className="ready-bar">
              <span>برای شروع جست‌وجو اطلاعات کافی داریم؛ تکمیل رزومه اختیاری است.</span>
              <button className="btn btn-primary" onClick={() => nav('/app/jobs', { state: { run: true } })}>ادامه به آگهی‌ها</button>
            </div>
          )}
          {!s.profile?.target_role && (
            <div style={{ padding: '0.6rem 1rem', display: 'flex', gap: '0.4rem', flexWrap: 'wrap', borderTop: '1px solid var(--border)' }}>
              <span className="muted" style={{ fontSize: '.8rem', width: '100%' }}>حوزه یا استک مورد نظرت را انتخاب کن یا در کادر زیر بنویس:</span>
              {TRACK_CHIPS.map((c) => (
                <button key={c} type="button" className="chip" onClick={() => sendChip(c)} disabled={busy}>{c}</button>
              ))}
            </div>
          )}
          <div className="composer">
            <textarea rows={1} value={text} placeholder="جوابت را بنویس…" onChange={(e) => setText(e.target.value)} disabled={busy}
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }} aria-label="پیام" />
            <button className="btn btn-blue" onClick={send} disabled={busy || !text.trim()}>ارسال</button>
          </div>
        </section>
        <ProfilePanel s={s} open={panel} onClose={() => setPanel(false)} />
      </div>
    </>
  )
}

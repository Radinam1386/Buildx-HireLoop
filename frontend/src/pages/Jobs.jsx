import { useCallback, useEffect, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { api, fa } from '../api'
import { useApp } from '../ctx'
import { Chip, Empty, ErrorBox, Meter, Skeleton, Spinner } from '../ui'

const STAGES = ['پروفایلت را مرور می‌کنم…', 'آگهی‌ها را فیلتر و مقایسه می‌کنم…', 'علت تناسب هر آگهی را می‌نویسم…']

function JobCard({ m, top, onNo, busy }) {
  const j = m.job
  return (
    <article className="card job">
      <div className="job-top">
        <div><h3>{j.title}</h3><div className="co">{j.company} · {j.location}</div></div>
        <div style={{ display: 'flex', gap: '.35rem', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
          {j.remote && <span className="tag tag-remote">دورکاری</span>}
          {j.source === 'sample' && <span className="tag tag-sample">نمونه</span>}
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
  const [running, setRunning] = useState(false)
  const [stage, setStage] = useState(0)
  const [err, setErr] = useState('')
  const [remoteOnly, setRemoteOnly] = useState(false)
  const [pasteOpen, setPasteOpen] = useState(false)
  const [paste, setPaste] = useState('')
  const [busy, setBusy] = useState(false)

  const run = useCallback(async () => {
    setRunning(true); setErr('')
    try { setMatches((await api('/api/matches/run', { method: 'POST' })).matches) }
    catch (e) { setErr(e.message); setMatches((m) => m ?? []) } finally { setRunning(false) }
  }, [])

  useEffect(() => {
    if (loc.state?.run) { nav(loc.pathname, { replace: true, state: null }); run(); return }
    api('/api/matches').then((r) => setMatches(r.matches)).catch((e) => { setErr(e.message); setMatches([]) })
  }, [refreshKey])  // eslint-disable-line

  useEffect(() => {
    if (!running) return
    setStage(0)
    const t = setInterval(() => setStage((x) => Math.min(x + 1, STAGES.length - 1)), 6000)
    return () => clearInterval(t)
  }, [running])

  async function dismiss(id) {
    setBusy(true)
    try { await api('/api/refine', { method: 'POST', body: { message: 'این آگهی را نمی‌خواهم', job_id: id } }); setMatches((await api('/api/matches')).matches) }
    catch (e) { setErr(e.message) } finally { setBusy(false) }
  }
  async function addPasted() {
    setBusy(true); setErr('')
    try { setMatches((await api('/api/jobs/paste', { method: 'POST', body: { text: paste } })).matches); setPaste(''); setPasteOpen(false) }
    catch (e) { setErr(e.message) } finally { setBusy(false) }
  }

  if (running) return (
    <div className="card running" role="status">
      <Spinner /><h2>{STAGES[stage]}</h2><p className="muted">این مرحله چند ثانیه طول می‌کشد.</p>
    </div>
  )
  if (!matches) return <div className="jobs">{[0, 1, 2].map((i) => <div key={i} className="card"><Skeleton lines={4} height={16} /></div>)}</div>

  const list = matches.filter((m) => !remoteOnly || m.job.remote)
  return (
    <>
      <div className="page-head">
        <div><h2>آگهی‌های مناسب تو</h2>{matches.length > 0 && <p>{fa(matches.length)} آگهی، به ترتیب میزان تناسب</p>}</div>
        <div style={{ display: 'flex', gap: '.5rem', flexWrap: 'wrap' }}>
          <button className="btn btn-ghost" onClick={() => setPasteOpen(!pasteOpen)}>افزودن آگهی خودم</button>
          <button className="btn btn-ghost" onClick={openRefine}>بازخورد به ایجنت</button>
        </div>
      </div>
      {err && <div style={{ marginBottom: '1rem' }}><ErrorBox message={err} onRetry={matches.length ? undefined : run} /></div>}
      {pasteOpen && (
        <div className="card paste">
          <label htmlFor="paste" className="muted">متن آگهی را اینجا بچسبان؛ تحلیلش می‌کنم و تناسبش را می‌سنجم.</label>
          <textarea id="paste" className="input" value={paste} onChange={(e) => setPaste(e.target.value)} />
          <div><button className="btn btn-blue" onClick={addPasted} disabled={busy || paste.trim().length < 30}>{busy ? <Spinner /> : 'تحلیل آگهی'}</button></div>
        </div>
      )}
      {matches.length === 0 ? (
        <Empty title="هنوز آگهی‌ای پیدا نکرده‌ایم" text="اگر مصاحبه را تمام کرده‌ای، جست‌وجو را شروع کن. وگرنه اول پروفایلت را کامل کن.">
          <button className="btn btn-primary" onClick={run}>پیدا کردن آگهی‌ها</button>
          <Link to="/app/interview" className="btn btn-ghost">برگشت به مصاحبه</Link>
        </Empty>
      ) : (
        <>
          <div className="toolbar"><Chip active={!remoteOnly} onClick={() => setRemoteOnly(false)}>همه</Chip><Chip active={remoteOnly} onClick={() => setRemoteOnly(true)}>فقط دورکاری</Chip></div>
          {list.length === 0 ? <Empty title="آگهی دورکاری‌ای در این فهرست نیست" text="فیلتر را بردار یا از ایجنت بخواه ترجیحاتت را عوض کند."><button className="btn btn-ghost" onClick={() => setRemoteOnly(false)}>نمایش همه</button></Empty> :
            <div className="jobs">{list.map((m, i) => <JobCard key={m.job.id} m={m} top={i === 0} onNo={dismiss} busy={busy} />)}</div>}
        </>
      )}
    </>
  )
}

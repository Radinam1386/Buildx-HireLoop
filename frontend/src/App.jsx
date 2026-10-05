import { useState, useCallback, useMemo } from 'react'
import { Navigate, Outlet, Route, Routes, useLocation, useMatch, useNavigate } from 'react-router-dom'
import { AppCtx } from './ctx'
import { api, clearSession, getToken, getUser } from './api'
import { Brand, Stepper } from './ui'
import Landing from './pages/Landing'
import Auth from './pages/Auth'
import Interview from './pages/Interview'
import Jobs from './pages/Jobs'
import Resume from './pages/Resume'

const CHIPS = [
  'دورکاری می‌خوام',
  'فقط آگهی‌های شهر خودم',
  'مهارت جدیدی هم دارم',
  'رزومه رو کوتاه‌تر کن',
  'روی پروژه‌هام بیشتر تأکید کن',
]

function RefineDrawer({ open, onClose, jobId, lang, onDone }) {
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [log, setLog] = useState([])
  const [err, setErr] = useState('')

  async function send(msg) {
    const m = (msg ?? text).trim()
    if (!m || busy) return
    setBusy(true); setErr(''); setText('')
    setLog((l) => [...l, { who: 'u', text: m }])
    try {
      const r = await api('/api/refine', { method: 'POST', body: { message: m, job_id: jobId, lang } })
      setLog((l) => [...l, { who: 'a', text: r.reply }])
      if (r.changed?.length) onDone(r)
    } catch (e) { setErr(e.message) } finally { setBusy(false) }
  }

  if (!open) return null
  return (
    <>
      <div className="scrim" onClick={onClose} />
      <aside className="drawer" role="dialog" aria-label="اصلاح ترجیحات و رزومه">
        <header>
          <h3>بهبود نتیجه</h3>
          <button className="btn-text" onClick={onClose}>بستن</button>
        </header>
        <div className="body">
          <p className="muted">بگو چه چیزی را تغییر بدهم؛ جست‌وجو و رزومه را بر اساس حرفت اصلاح می‌کنم.</p>
          <div className="chips">
            {CHIPS.filter((c) => jobId || !c.includes('رزومه')).map((c) => (
              <button key={c} type="button" className="chip" onClick={() => send(c)} disabled={busy}>{c}</button>
            ))}
          </div>
          {log.map((m, i) => <div key={i} className={'msg ' + (m.who === 'u' ? 'msg-u' : 'msg-a')}>{m.text}</div>)}
          {busy && <div className="typing" aria-label="در حال فکر کردن"><i /><i /><i /></div>}
          {err && <div className="errorbox" role="alert"><p>{err}</p></div>}
        </div>
        <footer>
          <textarea rows={1} value={text} placeholder="مثلاً: این آگهی رو نمی‌خوام" onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }} />
          <button className="btn btn-blue" onClick={() => send()} disabled={busy || !text.trim()}>ارسال</button>
        </footer>
      </aside>
    </>
  )
}

function Shell() {
  const nav = useNavigate()
  const loc = useLocation()
  const resumeMatch = useMatch('/app/resume/:jobId')
  const [refreshKey, setRefreshKey] = useState(0)
  const [refineOpen, setRefineOpen] = useState(false)
  const bump = useCallback(() => setRefreshKey((k) => k + 1), [])
  const user = getUser()
  const ctx = useMemo(() => ({ refreshKey, bump, openRefine: () => setRefineOpen(true) }), [refreshKey, bump])
  if (!getToken()) return <Navigate to="/auth" replace />

  const current = loc.pathname.includes('/resume') ? 2 : loc.pathname.includes('/jobs') ? 1 : 0
  const lang = new URLSearchParams(loc.search).get('lang') === 'en' ? 'en' : 'fa'
  return (
    <AppCtx.Provider value={ctx}>
      <header className="topbar no-print">
        <div className="topbar-in">
          <Brand light />
          <Stepper current={current} onRefine={() => setRefineOpen(true)} />
          <div className="user">
            <span className="name">{user?.name || user?.email}</span>
            <button className="btn-text" onClick={() => { clearSession(); nav('/') }}>خروج</button>
          </div>
        </div>
      </header>
      <main className="page"><Outlet /></main>
      <RefineDrawer open={refineOpen} onClose={() => setRefineOpen(false)} jobId={resumeMatch ? Number(resumeMatch.params.jobId) : null}
        lang={lang} onDone={() => bump()} />
    </AppCtx.Provider>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/auth" element={<Auth />} />
      <Route path="/app" element={<Shell />}>
        <Route index element={<Navigate to="interview" replace />} />
        <Route path="interview" element={<Interview />} />
        <Route path="jobs" element={<Jobs />} />
        <Route path="resume" element={<Resume />} />
        <Route path="resume/:jobId" element={<Resume />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

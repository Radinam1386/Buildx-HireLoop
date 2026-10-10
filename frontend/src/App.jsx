import { useState, useCallback, useMemo } from 'react'
import { NavLink, Navigate, Outlet, Route, Routes, useLocation, useMatch, useNavigate } from 'react-router-dom'
import { AppCtx } from './ctx'
import { api, clearSession, getToken, getUser } from './api'
import { Brand, Stepper } from './ui'
import Landing from './pages/Landing'
import Auth from './pages/Auth'
import Interview from './pages/Interview'
import Jobs from './pages/Jobs'
import Resume from './pages/Resume'
import JobDetail from './pages/JobDetail'
import Practice from './pages/Practice'
import Applications from './pages/Applications'

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

  const lang = new URLSearchParams(loc.search).get('lang') === 'en' ? 'en' : 'fa'

  const isInterview = loc.pathname === '/app/interview'
  const isJobs = loc.pathname.startsWith('/app/jobs') || loc.pathname.startsWith('/app/practice')
  const isResume = loc.pathname.startsWith('/app/resume')
  const isApplications = loc.pathname.startsWith('/app/applications')

  const displayName = user?.name || user?.email?.split('@')[0] || 'کاربر'
  const avatarChar = (user?.name || user?.email || 'U').trim()[0].toUpperCase()

  const handleLogout = () => {
    clearSession()
    nav('/')
  }

  return (
    <AppCtx.Provider value={ctx}>
      <header className="topbar no-print">
        <div className="topbar-in">
          <Brand light />

          <nav className="topbar-nav" aria-label="بخش‌های اصلی کاری">
            <NavLink to="/app/interview" className={'topbar-tab' + (isInterview ? ' active' : '')}>
              <svg className="tab-icon" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                <circle cx="12" cy="7" r="4" />
              </svg>
              <span>مصاحبه و پروفایل</span>
            </NavLink>
            <NavLink to="/app/jobs" className={'topbar-tab' + (isJobs ? ' active' : '')}>
              <svg className="tab-icon" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <rect x="2" y="7" width="20" height="14" rx="2" ry="2" />
                <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
              </svg>
              <span>فرصت‌های شغلی</span>
            </NavLink>
            <NavLink to="/app/resume" className={'topbar-tab' + (isResume ? ' active' : '')}>
              <svg className="tab-icon" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
                <line x1="16" y1="13" x2="8" y2="13" />
                <line x1="16" y1="17" x2="8" y2="17" />
              </svg>
              <span>رزومه‌های من</span>
            </NavLink>
            <NavLink to="/app/applications" className={'topbar-tab' + (isApplications ? ' active' : '')}>
              <svg className="tab-icon" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M9 11l3 3L22 4" />
                <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
              </svg>
              <span>پیگیری درخواست‌ها</span>
            </NavLink>
            <button
              type="button"
              className="topbar-tab topbar-tab-refine"
              onClick={() => setRefineOpen(true)}
              title="اصلاح ترجیحات و رزومه با دستیار هوشمند"
            >
              <svg className="tab-icon refine-icon" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M12 2l2.4 7.2L22 12l-7.6 2.8L12 22l-2.4-7.2L2 12l7.6-2.8z" />
              </svg>
              <span>بهبود با گفت‌وگو</span>
            </button>
          </nav>

          <div className="topbar-user-area">
            <div className="user-profile-badge" title={user?.email || displayName}>
              <div className="user-avatar" aria-hidden="true">
                {avatarChar}
              </div>
              <div className="user-info">
                <span className="user-name">{displayName}</span>
                <span className="user-status">آنلاین</span>
              </div>
            </div>
            <button
              type="button"
              className="btn-logout"
              onClick={handleLogout}
              title="خروج از حساب کاربری"
              aria-label="خروج"
            >
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                <polyline points="16 17 21 12 16 7" />
                <line x1="21" y1="12" x2="9" y2="12" />
              </svg>
              <span className="logout-text">خروج</span>
            </button>
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
        <Route path="jobs/:jobId" element={<JobDetail />} />
        <Route path="practice/:jobId" element={<Practice />} />
        <Route path="applications" element={<Applications />} />
        <Route path="resume" element={<Resume />} />
        <Route path="resume/:jobId" element={<Resume />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

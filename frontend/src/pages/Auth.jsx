import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { api, getToken, setSession } from '../api'
import { Brand, Spinner } from '../ui'

export default function Auth() {
  const nav = useNavigate()
  const [mode, setMode] = useState('login')
  const [f, setF] = useState({ name: '', email: '', password: '' })
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  if (getToken()) return <Navigate to="/app/interview" replace />

  async function submit(e) {
    e.preventDefault()
    setErr(''); setBusy(true)
    try {
      const r = await api(`/api/auth/${mode}`, { method: 'POST', body: f })
      setSession(r.token, r.user)
      nav('/app/interview')
    } catch (e2) { setErr(e2.message) } finally { setBusy(false) }
  }
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })

  return (
    <div className="auth">
      <form className="auth-card" onSubmit={submit}>
        <Brand />
        <div className="tabs" role="tablist">
          <button type="button" role="tab" className={mode === 'login' ? 'on' : ''} onClick={() => setMode('login')}>ورود</button>
          <button type="button" role="tab" className={mode === 'register' ? 'on' : ''} onClick={() => setMode('register')}>ثبت‌نام</button>
        </div>
        {mode === 'register' && (
          <div className="field"><label htmlFor="name">نام</label>
            <input id="name" className="input" value={f.name} onChange={set('name')} autoComplete="name" /></div>
        )}
        <div className="field"><label htmlFor="email">ایمیل</label>
          <input id="email" className="input" dir="ltr" type="email" required value={f.email} onChange={set('email')} autoComplete="email" /></div>
        <div className="field"><label htmlFor="pw">رمز عبور</label>
          <input id="pw" className="input" dir="ltr" type="password" required minLength={6} value={f.password} onChange={set('password')}
            autoComplete={mode === 'login' ? 'current-password' : 'new-password'} /></div>
        {err && <div className="errorbox" role="alert"><p>{err}</p></div>}
        <button className="btn btn-primary btn-lg" disabled={busy}>
          {busy ? <Spinner /> : mode === 'login' ? 'ورود' : 'ساخت حساب'}
        </button>
      </form>
    </div>
  )
}

import { Link } from 'react-router-dom'
import { fa } from './api'

export function Brand({ light }) {
  return (
    <Link to="/" className={'brand' + (light ? ' brand-light' : '')} aria-label="HireLoop">
      <svg width="26" height="26" viewBox="0 0 26 26" aria-hidden="true">
        <path d="M13 3a10 10 0 1 0 10 10" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
        <circle cx="21.5" cy="5.5" r="3.2" fill="#FF6E42" />
      </svg>
      <span>HireLoop</span>
    </Link>
  )
}

export function Spinner({ label }) {
  return <span className="spinner-wrap" role="status"><span className="spinner" aria-hidden="true" />{label && <span>{label}</span>}</span>
}

export function Skeleton({ lines = 3, height = 14 }) {
  return (
    <div className="skel" aria-hidden="true">
      {Array.from({ length: lines }).map((_, i) => (
        <span key={i} style={{ height, width: `${100 - i * 14}%` }} />
      ))}
    </div>
  )
}

export function ErrorBox({ message, onRetry }) {
  return (
    <div className="errorbox" role="alert">
      <p>{message}</p>
      {onRetry && <button className="btn btn-ghost" onClick={onRetry}>تلاش دوباره</button>}
    </div>
  )
}

export function Empty({ title, text, children }) {
  return (
    <div className="empty">
      <h3>{title}</h3>
      {text && <p>{text}</p>}
      {children}
    </div>
  )
}

export function Chip({ children, onClick, active }) {
  const cls = 'chip' + (active ? ' chip-active' : '')
  return onClick
    ? <button type="button" className={cls} onClick={onClick}>{children}</button>
    : <span className={cls}>{children}</span>
}

export function Meter({ value }) {
  const tone = value >= 75 ? 'hi' : value >= 50 ? 'mid' : 'lo'
  return (
    <div className={`meter meter-${tone}`} aria-label={`تناسب ${fa(value)} درصد`}>
      <div className="meter-bar"><span style={{ width: `${value}%` }} /></div>
      <strong>{fa(value)}٪</strong>
    </div>
  )
}

const STEPS = ['مصاحبه', 'آگهی‌ها', 'رزومه', 'بهبود']
export function Stepper({ current, onRefine }) {
  return (
    <ol className="stepper" aria-label="مراحل">
      {STEPS.map((label, i) => {
        const state = i < current ? 'done' : i === current ? 'now' : 'todo'
        const inner = (<><span className="dot">{state === 'done' ? '✓' : fa(i + 1)}</span><span className="lbl">{label}</span></>)
        return (
          <li key={label} className={`step step-${state}`} aria-current={state === 'now' ? 'step' : undefined}>
            {i === 0 && <Link to="/app/interview">{inner}</Link>}
            {i === 1 && <Link to="/app/jobs">{inner}</Link>}
            {i === 2 && <Link to="/app/resume">{inner}</Link>}
            {i === 3 && <button type="button" onClick={onRefine}>{inner}</button>}
          </li>
        )
      })}
    </ol>
  )
}

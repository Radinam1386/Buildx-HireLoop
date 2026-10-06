import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import JobAnalysis from '../JobAnalysis'

export default function JobDetail() {
  const { jobId } = useParams()
  const [job, setJob] = useState(null)
  const url = job?.url && /^https?:\/\//i.test(job.url) ? job.url : null
  return <div className="job-detail">
    <Link to="/app/jobs">بازگشت به آگهی‌ها</Link>
    <h1>{job?.title || 'جزئیات آگهی'}</h1>
    {job && <section className="card">
      <p>{job.company} · {job.location || 'مکان نامعلوم'}</p>
      <details open><summary>توضیح اصلی ذخیره‌شده</summary><p dir="auto" style={{ whiteSpace: 'pre-wrap' }}>{job.description}</p></details>
      <div className="actions">
        {url && <a className="btn btn-ghost" href={url} target="_blank" rel="noopener noreferrer">مشاهده منبع آگهی</a>}
        <Link className="btn btn-primary" to={`/app/resume/${jobId}`}>ساخت رزومه</Link>
        <Link className="btn btn-ghost" to={`/app/practice/${jobId}`}>تمرین مصاحبه</Link>
      </div>
    </section>}
    <JobAnalysis jobId={jobId} onAnalyzed={result => setJob(result.job)} />
  </div>
}

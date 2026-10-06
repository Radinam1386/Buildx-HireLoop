import { useState } from 'react'
import { api } from './api'
import { ErrorBox } from './ui'

const split = (s) => s.split(/[,،\n]/).map((v) => v.trim()).filter(Boolean)
const GROUPS = {
  projects: { title: 'پروژه‌ها', empty: { name: '', description: '', tech: [] }, fields: [['name', 'نام پروژه'], ['description', 'سهم تو، مسئله و نتیجهٔ واقعی', true], ['tech', 'ابزارها (با ویرگول جدا کن)']] },
  experience: { title: 'سابقهٔ کار', empty: { title: '', org: '', period: '', details: '' }, fields: [['title', 'عنوان نقش'], ['org', 'شرکت یا تیم'], ['period', 'بازهٔ زمانی'], ['details', 'مسئولیت و نتیجهٔ واقعی', true]] },
  education: { title: 'تحصیلات', empty: { degree: '', school: '', period: '' }, fields: [['degree', 'رشته و مدرک'], ['school', 'دانشگاه یا مؤسسه'], ['period', 'بازهٔ زمانی']] },
}

export default function ProfileEditor({ profile, onSaved, onClose }) {
  const [draft, setDraft] = useState(() => ({ ...structuredClone(profile), projects: profile.projects.map((p) => ({ ...p, tech: p.tech.join(', ') })) }))
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const change = (key, value) => setDraft((p) => ({ ...p, [key]: value }))
  function editItem(key, index, field, value) {
    change(key, draft[key].map((item, i) => i === index ? { ...item, [field]: value } : item))
  }
  async function save(e) {
    e.preventDefault(); setBusy(true); setErr('')
    try { await onSaved(await api('/api/profile', { method: 'PATCH', body: { ...draft, projects: draft.projects.map((p) => ({ ...p, tech: split(p.tech) })) } })) }
    catch (e) { setErr(e.message) } finally { setBusy(false) }
  }
  return (
    <form className="card profile-editor no-print" onSubmit={save} aria-label="ویرایش اطلاعات پروفایل">
      <div className="review-head"><div><h3>مرور و ویرایش اطلاعات</h3><p className="muted">اطلاعاتی که رزومه از آن ساخته می‌شود. هر موردی که درست نیست اصلاح یا حذف کن.</p></div><button type="button" className="btn-text" onClick={onClose} disabled={busy}>بستن</button></div>
      <fieldset disabled={busy}>
        <div className="profile-fields">
          {[['name', 'نام برای رزومه'], ['target_role', 'نقش هدف'], ['city', 'شهر']].map(([k, label]) => <label key={k}>{label}<input className="input" value={draft[k] || ''} onChange={(e) => change(k, e.target.value)} maxLength={180} /></label>)}
          <label>سطح تجربه<select className="input" value={draft.level || ''} onChange={(e) => change('level', e.target.value)}><option value="">هنوز مشخص نیست</option><option value="intern">کارآموز</option><option value="junior">تازه‌کار</option><option value="mid">میانی</option><option value="senior">ارشد</option></select></label>
          <label>نوع همکاری<select className="input" value={draft.remote_pref || ''} onChange={(e) => change('remote_pref', e.target.value)}><option value="">هنوز مشخص نیست</option><option value="any">فرقی ندارد</option><option value="remote">دورکاری</option><option value="onsite">حضوری</option><option value="hybrid">ترکیبی</option><option value="city_or_remote">شهر خودم یا دورکاری</option></select></label>
        </div>
        <label>مهارت‌ها (با ویرگول جدا کن)<input className="input" defaultValue={draft.skills.join('، ')} onChange={(e) => change('skills', split(e.target.value))} /></label>
        {Object.entries(GROUPS).map(([key, group]) => <section className="profile-group" key={key}>
          <h4>{group.title}</h4>
          {draft[key].map((item, i) => <fieldset className="profile-item" key={i}>
            <legend>{group.title} · {i + 1}</legend>
            {group.fields.map(([field, label, multiline]) => <label key={field}>{label}{multiline ? <textarea rows={3} className="input" value={item[field] || ''} onChange={(e) => editItem(key, i, field, e.target.value)} maxLength={4000} /> : <input className="input" value={item[field] || ''} onChange={(e) => editItem(key, i, field, e.target.value)} />}</label>)}
            <button type="button" className="btn-text" onClick={() => change(key, draft[key].filter((_, index) => index !== i))}>حذف این مورد</button>
          </fieldset>)}
          <button type="button" className="btn btn-ghost" onClick={() => change(key, [...draft[key], { ...structuredClone(group.empty), ...(key === 'projects' ? { tech: '' } : {}) }])}>افزودن {group.title === 'تحصیلات' ? 'تحصیلات' : key === 'projects' ? 'پروژه' : 'سابقه'}</button>
        </section>)}
        <label>زبان‌ها (با ویرگول جدا کن)<input className="input" defaultValue={draft.languages.join('، ')} onChange={(e) => change('languages', split(e.target.value))} /></label>
        <label>لینک‌ها و راه‌های ارتباط (هر مورد در یک خط)<textarea rows={3} className="input" defaultValue={draft.links.join('\n')} onChange={(e) => change('links', e.target.value.split('\n').map((v) => v.trim()).filter(Boolean))} /></label>
        <label>توضیحات و هدف شغلی<textarea rows={2} className="input" value={draft.goals || ''} onChange={(e) => change('goals', e.target.value)} maxLength={4000} /></label>
        <p className="muted">ذخیرهٔ اطلاعات، رزومه‌های قبلی را تغییر نمی‌دهد. برای اعمال تغییرات، نسخهٔ جدید بساز.</p>
        {err && <ErrorBox message={err} />}
        <button className="btn btn-primary" type="submit">{busy ? 'در حال ذخیره…' : 'ذخیرهٔ اطلاعات'}</button>
      </fieldset>
    </form>
  )
}

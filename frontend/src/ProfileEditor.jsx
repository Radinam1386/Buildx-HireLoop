import { useState } from 'react'
import { api } from './api'
import { ErrorBox } from './ui'

const split = (s) => (s || '').split(/[,،\n]/).map((v) => v.trim()).filter(Boolean)
const GROUPS = {
  projects: {
    title: 'پروژه‌ها',
    empty: { name: '', role: '', link: '', period: '', description: '', tech: [] },
    fields: [
      ['name', 'نام پروژه'],
      ['role', 'نقش شما'],
      ['link', 'لینک پروژه (اختیاری)'],
      ['period', 'بازهٔ زمانی'],
      ['description', 'سهم تو، مسئله و نتیجهٔ واقعی', true],
      ['tech', 'ابزارها (با ویرگول جدا کن)'],
    ],
  },
  experience: {
    title: 'سابقهٔ کار',
    empty: { title: '', org: '', period: '', location: '', details: '' },
    fields: [
      ['title', 'عنوان نقش'],
      ['org', 'شرکت یا تیم'],
      ['period', 'بازهٔ زمانی'],
      ['location', 'محل'],
      ['details', 'مسئولیت و نتیجهٔ واقعی', true],
    ],
  },
  education: {
    title: 'تحصیلات',
    empty: { degree: '', field: '', school: '', period: '', gpa: '', notes: '' },
    fields: [
      ['degree', 'مدرک (دیپلم/کارشناسی/...)'],
      ['field', 'رشتهٔ تحصیلی'],
      ['school', 'دانشگاه، دبیرستان یا مؤسسه'],
      ['period', 'سال یا بازه'],
    ],
  },
  honors: {
    title: 'افتخارات و جوایز (المپیاد، مسابقات و...)',
    empty: { title: '', issuer: '', year: '', location: '', description: '' },
    fields: [
      ['title', 'عنوان دستاورد یا مدال (مثلاً مدال برنز المپیاد هوش مصنوعی)'],
      ['issuer', 'برگزارکننده / مرجع'],
      ['year', 'سال'],
      ['location', 'محل برگزاری'],
      ['description', 'توضیحات تکمیلی', true],
    ],
  },
  certifications: {
    title: 'گواهینامه‌ها و دوره‌ها',
    empty: { name: '', issuer: '', year: '' },
    fields: [
      ['name', 'عنوان مدرک یا دوره'],
      ['issuer', 'مرجع صادرکننده'],
      ['year', 'سال دریافت'],
    ],
  },
}

export default function ProfileEditor({ profile, onSaved, onClose }) {
  const [draft, setDraft] = useState(() => {
    const p = structuredClone(profile || {})
    return {
      ...p,
      contact: p.contact || {},
      skills: (p.skills || []).map((s) => typeof s === 'string' ? { name: s, level: '', tools: [] } : s),
      languages: (p.languages || []).map((l) => typeof l === 'string' ? { name: l, level: '' } : l),
      honors: p.honors || [],
      certifications: p.certifications || [],
      education: p.education || [],
      experience: p.experience || [],
      projects: (p.projects || []).map((pr) => ({ ...pr, tech: Array.isArray(pr.tech) ? pr.tech.join(', ') : (pr.tech || '') })),
    }
  })
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const change = (key, value) => setDraft((p) => ({ ...p, [key]: value }))
  const contactChange = (field, value) => setDraft((p) => ({ ...p, contact: { ...p.contact, [field]: value } }))

  function editItem(key, index, field, value) {
    change(key, draft[key].map((item, i) => i === index ? { ...item, [field]: value } : item))
  }

  async function save(e) {
    e.preventDefault(); setBusy(true); setErr('')
    try {
      const payload = {
        ...draft,
        projects: draft.projects.map((p) => ({ ...p, tech: split(p.tech) })),
      }
      await onSaved(await api('/api/profile', { method: 'PATCH', body: payload }))
    } catch (e) { setErr(e.message) } finally { setBusy(false) }
  }

  const skillsStr = (draft.skills || []).map((s) => s.name || s).join('، ')
  const langsStr = (draft.languages || []).map((l) => l.name ? `${l.name}${l.level ? ` (${l.level})` : ''}` : l).join('، ')

  return (
    <form className="card profile-editor no-print" onSubmit={save} aria-label="ویرایش اطلاعات پروفایل">
      <div className="review-head"><div><h3>مرور و ویرایش اطلاعات</h3><p className="muted">اطلاعاتی که رزومه از آن ساخته می‌شود. هر موردی که درست نیست اصلاح یا حذف کن.</p></div><button type="button" className="btn-text" onClick={onClose} disabled={busy}>بستن</button></div>
      <fieldset disabled={busy}>
        <div className="profile-fields">
          {[['name', 'نام (فارسی)'], ['name_en', 'نام انگلیسی (Full Name)'], ['headline', 'عنوان شغلی']].map(([k, label]) => (
            <label key={k}>{label}<input className="input" value={draft[k] || ''} onChange={(e) => change(k, e.target.value)} maxLength={180} /></label>
          ))}
          <label>نقش هدف<input className="input" value={draft.target_role || ''} onChange={(e) => change('target_role', e.target.value)} maxLength={180} /></label>
          <label>شهر<input className="input" value={draft.city || draft.contact?.city || ''} onChange={(e) => { change('city', e.target.value); contactChange('city', e.target.value) }} maxLength={180} /></label>
          <label>کشور<input className="input" value={draft.contact?.country || ''} onChange={(e) => contactChange('country', e.target.value)} maxLength={180} /></label>
          <label>ایمیل<input className="input" type="email" value={draft.contact?.email || ''} onChange={(e) => contactChange('email', e.target.value)} maxLength={180} /></label>
          <label>تلفن<input className="input" value={draft.contact?.phone || ''} onChange={(e) => contactChange('phone', e.target.value)} maxLength={50} /></label>
          <label>لینکدین (LinkedIn URL)<input className="input" value={draft.contact?.linkedin || ''} onChange={(e) => contactChange('linkedin', e.target.value)} maxLength={250} /></label>
          <label>گیتهاب (GitHub URL)<input className="input" value={draft.contact?.github || ''} onChange={(e) => contactChange('github', e.target.value)} maxLength={250} /></label>
          <label>سطح تجربه<select className="input" value={draft.level || ''} onChange={(e) => change('level', e.target.value)}><option value="">هنوز مشخص نیست</option><option value="intern">کارآموز</option><option value="junior">تازه‌کار</option><option value="mid">میانی</option><option value="senior">ارشد</option></select></label>
          <label>نوع همکاری<select className="input" value={draft.remote_pref || ''} onChange={(e) => change('remote_pref', e.target.value)}><option value="">هنوز مشخص نیست</option><option value="any">فرقی ندارد</option><option value="remote">دورکاری</option><option value="onsite">حضوری</option><option value="hybrid">ترکیبی</option><option value="city_or_remote">شهر خودم یا دورکاری</option></select></label>
        </div>

        <label>مهارت‌ها (با ویرگول جدا کن)<input className="input" defaultValue={skillsStr} onChange={(e) => change('skills', split(e.target.value).map((n) => ({ name: n })))} /></label>
        <label>زبان‌ها (با ویرگول جدا کن، مثلاً فارسی (زبان مادری)، انگلیسی (پیشرفته))<input className="input" defaultValue={langsStr} onChange={(e) => change('languages', split(e.target.value).map((l) => {
          const m = l.match(/^(.+?)\s*\((.+?)\)$/)
          return m ? { name: m[1].trim(), level: m[2].trim() } : { name: l.trim(), level: '' }
        }))} /></label>

        {Object.entries(GROUPS).map(([key, group]) => (
          <section className="profile-group" key={key}>
            <h4>{group.title}</h4>
            {(draft[key] || []).map((item, i) => (
              <fieldset className="profile-item" key={i}>
                <legend>{group.title} · {i + 1}</legend>
                {group.fields.map(([field, label, multiline]) => (
                  <label key={field}>{label}{multiline ? <textarea rows={3} className="input" value={item[field] || ''} onChange={(e) => editItem(key, i, field, e.target.value)} maxLength={4000} /> : <input className="input" value={item[field] || ''} onChange={(e) => editItem(key, i, field, e.target.value)} />}</label>
                ))}
                <button type="button" className="btn-text" onClick={() => change(key, draft[key].filter((_, index) => index !== i))}>حذف این مورد</button>
              </fieldset>
            ))}
            <button type="button" className="btn btn-ghost" onClick={() => change(key, [...(draft[key] || []), { ...structuredClone(group.empty), ...(key === 'projects' ? { tech: '' } : {}) }])}>افزودن مورد جدید به {group.title}</button>
          </section>
        ))}

        <label>لینک‌ها و راه‌های ارتباط دیگر (هر مورد در یک خط)<textarea rows={2} className="input" defaultValue={(draft.links || []).join('\n')} onChange={(e) => change('links', e.target.value.split('\n').map((v) => v.trim()).filter(Boolean))} /></label>
        <label>توضیحات و خلاصه/هدف شغلی<textarea rows={2} className="input" value={draft.goals || ''} onChange={(e) => change('goals', e.target.value)} maxLength={4000} /></label>
        <p className="muted">ذخیرهٔ اطلاعات، رزومه‌های قبلی را تغییر نمی‌دهد. برای اعمال تغییرات، نسخهٔ جدید بساز.</p>
        {err && <ErrorBox message={err} />}
        <button className="btn btn-primary" type="submit">{busy ? 'در حال ذخیره…' : 'ذخیرهٔ اطلاعات'}</button>
      </fieldset>
    </form>
  )
}

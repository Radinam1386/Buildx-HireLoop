import { useEffect, useState } from "react"
import { Link, useParams, useSearchParams } from "react-router-dom"
import { api, fa } from "../api"
import { useApp } from "../ctx"
import { Empty, ErrorBox, Skeleton, Spinner } from "../ui"
import ProfileEditor from "../ProfileEditor"
import TrackJob from "../TrackJob"

const L = {
  fa: {
    summary: "خلاصه",
    skills: "مهارت‌ها",
    exp: "سابقهٔ کار",
    proj: "پروژه‌ها",
    edu: "تحصیلات",
    lang: "زبان‌ها",
    honors: "افتخارات و جوایز",
    certs: "گواهینامه‌ها",
  },
  en: {
    summary: "Summary",
    skills: "Skills",
    exp: "Experience",
    proj: "Projects",
    edu: "Education",
    lang: "Languages",
    honors: "Honors & Awards",
    certs: "Certifications",
  },
}

function getContactItems(contact) {
  if (!contact) return {}
  if (typeof contact === "object" && !Array.isArray(contact)) {
    return {
      email: contact.email || "",
      phone: contact.phone || "",
      city: contact.city || "",
      country: contact.country || "",
      linkedin: contact.linkedin || "",
      github: contact.github || "",
      website: contact.website || "",
    }
  }
  if (Array.isArray(contact)) {
    const res = { email: "", phone: "", city: "", country: "", linkedin: "", github: "", website: "" }
    for (const item of contact) {
      if (typeof item !== "string") continue
      const val = item.trim()
      if (val.includes("@")) res.email = val
      else if (val.includes("linkedin.com")) res.linkedin = val
      else if (val.includes("github.com")) res.github = val
      else if (val.startsWith("http://") || val.startsWith("https://")) res.website = val
      else if (/\d{7,}/.test(val.replace(/[\s-]/g, ""))) res.phone = val
      else if (!res.city) res.city = val
    }
    return res
  }
  return {}
}

function ContactLinks({ contact, lang = "fa" }) {
  const c = getContactItems(contact)
  const items = []

  if (c.email) {
    items.push(
      <a key="email" href={"mailto:" + c.email} className="contact-link" title="Email" dir="ltr">
        <svg className="contact-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2"><rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/></svg>
        <span>{c.email}</span>
      </a>
    )
  }
  if (c.phone) {
    items.push(
      <a key="phone" href={"tel:" + c.phone} className="contact-link" title="Phone" dir="ltr">
        <svg className="contact-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/></svg>
        <span>{c.phone}</span>
      </a>
    )
  }
  const loc = [c.city, c.country].filter(Boolean).join(lang === "en" ? ", " : "، ")
  if (loc) {
    items.push(
      <span key="loc" className="contact-item" title="Location">
        <svg className="contact-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/></svg>
        <span>{loc}</span>
      </span>
    )
  }
  if (c.linkedin) {
    const display = c.linkedin.replace(/^https?:\/\/(www\.)?linkedin\.com\/(in\/)?/, "").replace(/\/$/, "")
    items.push(
      <a key="linkedin" href={c.linkedin.startsWith("http") ? c.linkedin : "https://" + c.linkedin} target="_blank" rel="noopener noreferrer" className="contact-link" title="LinkedIn" dir="ltr">
        <svg className="contact-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2"><path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z"/><rect width="4" height="12" x="2" y="9"/><circle cx="4" cy="4" r="2"/></svg>
        <span>{display || "LinkedIn"}</span>
      </a>
    )
  }
  if (c.github) {
    const display = c.github.replace(/^https?:\/\/(www\.)?github\.com\//, "").replace(/\/$/, "")
    items.push(
      <a key="github" href={c.github.startsWith("http") ? c.github : "https://" + c.github} target="_blank" rel="noopener noreferrer" className="contact-link" title="GitHub" dir="ltr">
        <svg className="contact-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2"><path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4"/><path d="M9 18c-4.51 2-5-2-7-2"/></svg>
        <span>{display || "GitHub"}</span>
      </a>
    )
  }
  if (c.website) {
    const display = c.website.replace(/^https?:\/\//, "").replace(/\/$/, "")
    items.push(
      <a key="website" href={c.website.startsWith("http") ? c.website : "https://" + c.website} target="_blank" rel="noopener noreferrer" className="contact-link" title="Website" dir="ltr">
        <svg className="contact-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>
        <span>{display || "Website"}</span>
      </a>
    )
  }

  if (!items.length) return null
  return <div className="contact contact-links">{items}</div>
}

function EvidenceText({ text, path, evidence }) {
  if (evidence === false) return <span>{text}</span>
  const claim = evidence?.claims.find((c) => c.path === path)
  const sources = evidence?.sources.filter((s) => claim?.source_ids.includes(s.id)) || []
  return (
    <>
      <span>{text}</span>
      <details className="claim-source no-print">
        <summary>{claim?.user_confirmed ? "تأیید مستقیم شما" : sources.length ? "منبع جمله" : "بررسی منبع لازم است"}</summary>
        {sources.length ? (
          sources.map((s) => (
            <div key={s.id}>
              <strong>{s.label}</strong>
              <p dir="auto">{s.text}</p>
            </div>
          ))
        ) : (
          <p>برای این جمله منبع ثبت نشده؛ پیش از ارسال بررسی یا ویرایشش کن.</p>
        )}
        {sources.length > 0 && !claim?.user_confirmed && (
          <p className="muted">این منبع پیشنهادی جمله است؛ معنی و نتیجهٔ ادعا را خودت بررسی کن.</p>
        )}
      </details>
    </>
  )
}

function Sheet({ c, lang, evidence }) {
  const t = L[lang] || L.fa
  const displayName = (lang === "en" ? (c.name_en || c.name) : c.name) || c.name

  return (
    <article className="sheet" dir={lang === "en" ? "ltr" : "rtl"} lang={lang}>
      <h1>{displayName}</h1>
      {c.headline && (
        <div className="head">
          <EvidenceText text={c.headline} path="headline" evidence={evidence} />
        </div>
      )}

      <ContactLinks contact={c.contact} lang={lang} />

      {c.summary && (
        <section>
          <h2>{t.summary}</h2>
          <div className="summary-text">
            <EvidenceText text={c.summary} path="summary" evidence={evidence} />
          </div>
        </section>
      )}

      {c.skills && c.skills.length > 0 && (
        <section>
          <h2>{t.skills}</h2>
          <div className="skills-container">
            {c.skills.map((s, i) => {
              if (typeof s === "string") {
                return <span key={i} className="skill-tag">{s}</span>
              }
              const hasLevel = Boolean(s.level)
              const hasTools = Boolean(s.tools && s.tools.length > 0)
              return (
                <div key={i} className="skill-item-row">
                  <span className="skill-name"><strong>{s.name}</strong></span>
                  {hasLevel && <span className="skill-level-badge">{s.level}</span>}
                  {hasTools && (
                    <span className="skill-tools-text">
                      ({s.tools.join(lang === "en" ? ", " : "، ")})
                    </span>
                  )}
                </div>
              )
            })}
          </div>
        </section>
      )}

      {c.languages && c.languages.length > 0 && (
        <section>
          <h2>{t.lang}</h2>
          <div className="languages-container">
            {c.languages.map((l, i) => {
              if (typeof l === "string") return <span key={i} className="lang-tag">{l}</span>
              return (
                <span key={i} className="lang-item">
                  <strong>{l.name}</strong>
                  {l.level && <span className="lang-level-badge"> ({l.level})</span>}
                </span>
              )
            })}
          </div>
        </section>
      )}

      {c.honors && c.honors.length > 0 && (
        <section>
          <h2>{t.honors}</h2>
          {c.honors.map((h, i) => (
            <div className="item honor-item" key={i}>
              <div className="row">
                <span className="honor-title">
                  <span className="honor-medal" role="img" aria-label="medal">🏅</span>
                  <strong>{h.title}</strong>
                </span>
                <small>{[h.issuer, h.year, h.location].filter(Boolean).join(" — ")}</small>
              </div>
              {h.description && (
                <p className="honor-desc">
                  <EvidenceText text={h.description} path={"honors." + i + ".description"} evidence={evidence} />
                </p>
              )}
            </div>
          ))}
        </section>
      )}

      {c.projects && c.projects.length > 0 && (
        <section>
          <h2>{t.proj}</h2>
          {c.projects.map((p, i) => (
            <div className="item project-item" key={i}>
              <div className="row">
                <div className="proj-title-group">
                  <strong>{p.name}</strong>
                  {p.role && <span className="proj-role-badge">{p.role}</span>}
                  {p.link && (
                    <a
                      href={p.link.startsWith("http") ? p.link : "https://" + p.link}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="proj-ext-link"
                      title="Link"
                      dir="ltr"
                    >
                      <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
                      <span>{p.link.replace(/^https?:\/\//, "")}</span>
                    </a>
                  )}
                </div>
                {p.period && <small>{p.period}</small>}
              </div>
              {p.tech && p.tech.length > 0 && (
                <div className="proj-tech-chips">
                  {p.tech.map((tItem, tIdx) => (
                    <span key={tIdx} className="tech-badge">{tItem}</span>
                  ))}
                </div>
              )}
              {p.bullets && p.bullets.length > 0 && (
                <ul>
                  {p.bullets.map((b, j) => (
                    <li key={j}>
                      <EvidenceText text={b} path={"projects." + i + ".bullets." + j} evidence={evidence} />
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </section>
      )}

      {c.experience && c.experience.length > 0 && (
        <section>
          <h2>{t.exp}</h2>
          {c.experience.map((e, i) => (
            <div className="item" key={i}>
              <div className="row">
                <span>{[e.title, e.org].filter(Boolean).join(" — ")}</span>
                <small>{[e.location, e.period].filter(Boolean).join(" · ")}</small>
              </div>
              {e.bullets && e.bullets.length > 0 && (
                <ul>
                  {e.bullets.map((b, j) => (
                    <li key={j}>
                      <EvidenceText text={b} path={"experience." + i + ".bullets." + j} evidence={evidence} />
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </section>
      )}

      {c.education && c.education.length > 0 && (
        <section>
          <h2>{t.edu}</h2>
          {c.education.map((e, i) => (
            <div className="item" key={i}>
              <div className="row">
                <span>{[e.degree, e.field, e.school].filter(Boolean).join(" — ")}</span>
                <small>{[e.period, e.gpa && ((lang === "en" ? "GPA: " : "معدل: ") + e.gpa)].filter(Boolean).join(" · ")}</small>
              </div>
              {e.notes && <p className="muted" style={{ fontSize: ".85rem", marginTop: ".25rem" }}>{e.notes}</p>}
            </div>
          ))}
        </section>
      )}

      {c.certifications && c.certifications.length > 0 && (
        <section>
          <h2>{t.certs}</h2>
          {c.certifications.map((item, i) => (
            <div className="item" key={i}>
              <div className="row">
                <span>{[item.name, item.issuer].filter(Boolean).join(" — ")}</span>
                {item.year && <small>{item.year}</small>}
              </div>
            </div>
          ))}
        </section>
      )}

      {c.extra_sections && c.extra_sections.length > 0 && c.extra_sections.map((sec, i) => (
        <section key={i}>
          <h2>{sec.title}</h2>
          {sec.items && sec.items.length > 0 && (
            <ul>
              {sec.items.map((it, j) => <li key={j}>{it}</li>)}
            </ul>
          )}
        </section>
      ))}
    </article>
  )
}

function ResumeCompletenessBar({ prep }) {
  if (!prep) return null
  const { completeness: pct = 0, missing = [], resume_ready = false } = prep

  return (
    <div className="card resume-completeness-bar no-print">
      <div className="completeness-content">
        <div className="completeness-header">
          <div className="completeness-title">
            <span className="completeness-label">تکمیل پروفایل و رزومه:</span>
            <strong>{fa(pct)}٪</strong>
            {resume_ready ? (
              <span className="badge-ready">🎉 اطلاعات برای رزومهٔ کامل آماده است</span>
            ) : (
              <span className="badge-pending">نیاز به بهبود برای رزومهٔ قوی‌تر</span>
            )}
          </div>
          <Link to="/app/interview" className="btn btn-primary btn-sm">
            تکمیل در مصاحبه هوشمند
          </Link>
        </div>
        <div className="progress" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
          <span style={{ width: pct + "%", background: resume_ready ? "var(--blue)" : "var(--orange)" }} />
        </div>
        {missing && missing.length > 0 && (
          <div className="missing-tags-list">
            <span className="missing-title">پیشنهاد بهبود:</span>
            {missing.map((m) => (
              <span key={m} className="missing-chip">{m}</span>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

const splitList = (s) => (typeof s === "string" ? s.split(/[,،\n]/).map((v) => v.trim()).filter(Boolean) : (Array.isArray(s) ? s : []))
const lines = (s) => (typeof s === "string" ? s.split("\n").map((v) => v.trim()).filter(Boolean) : (Array.isArray(s) ? s : []))

function ContentEditor({ resume, onSaved, onClose, jobId }) {
  const [draft, setDraft] = useState(() => {
    const c = structuredClone(resume.content || {})
    const contactObj = getContactItems(c.contact)
    return {
      name: c.name || "",
      name_en: c.name_en || "",
      headline: c.headline || "",
      summary: c.summary || "",
      contact: contactObj,
      skills: (c.skills || []).map((s) => (
        typeof s === "string"
          ? { name: s, level: "", tools: "" }
          : { name: s.name || "", level: s.level || "", tools: (s.tools || []).join(", ") }
      )),
      languages: (c.languages || []).map((l) => (
        typeof l === "string"
          ? { name: l, level: "" }
          : { name: l.name || "", level: l.level || "" }
      )),
      honors: (c.honors || []).map((h) => ({ ...h })),
      education: (c.education || []).map((e) => ({ ...e })),
      certifications: (c.certifications || []).map((cert) => ({ ...cert })),
      experience: (c.experience || []).map((e) => ({ ...e, bullets: (e.bullets || []).join("\n") })),
      projects: (c.projects || []).map((p) => ({
        ...p,
        tech: (p.tech || []).join(", "),
        bullets: (p.bullets || []).join("\n"),
      })),
      extra_sections: c.extra_sections || [],
    }
  })

  const [review, setReview] = useState(false)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState()

  const change = (key, value) => { setDraft((p) => ({ ...p, [key]: value })); setReview(false) }
  const contactChange = (field, value) => { setDraft((p) => ({ ...p, contact: { ...p.contact, [field]: value } })); setReview(false) }
  const itemChange = (key, i, field, value) => {
    setDraft((p) => ({
      ...p,
      [key]: p[key].map((item, n) => (n === i ? { ...item, [field]: value } : item)),
    }))
    setReview(false)
  }

  function buildPayload() {
    return {
      name: draft.name || "",
      name_en: draft.name_en || "",
      headline: draft.headline || "",
      summary: draft.summary || "",
      contact: {
        email: draft.contact?.email || "",
        phone: draft.contact?.phone || "",
        city: draft.contact?.city || "",
        country: draft.contact?.country || "",
        linkedin: draft.contact?.linkedin || "",
        github: draft.contact?.github || "",
        website: draft.contact?.website || "",
      },
      skills: (draft.skills || []).map((s) => ({
        name: s.name || "",
        level: s.level || "",
        tools: splitList(s.tools),
      })),
      languages: (draft.languages || []).map((l) => ({
        name: l.name || "",
        level: l.level || "",
      })),
      honors: (draft.honors || []).map((h) => ({
        title: h.title || "",
        issuer: h.issuer || "",
        year: h.year || "",
        location: h.location || "",
        description: h.description || "",
      })),
      education: (draft.education || []).map((e) => ({
        degree: e.degree || "",
        field: e.field || "",
        school: e.school || "",
        period: e.period || "",
        gpa: e.gpa || "",
        notes: e.notes || "",
      })),
      experience: (draft.experience || []).map((e) => ({
        title: e.title || "",
        org: e.org || "",
        period: e.period || "",
        location: e.location || "",
        bullets: lines(e.bullets),
      })),
      projects: (draft.projects || []).map((p) => ({
        name: p.name || "",
        role: p.role || "",
        link: p.link || "",
        period: p.period || "",
        tech: splitList(p.tech),
        bullets: lines(p.bullets),
      })),
      certifications: (draft.certifications || []).map((c) => ({
        name: c.name || "",
        issuer: c.issuer || "",
        year: c.year || "",
      })),
      extra_sections: draft.extra_sections || [],
    }
  }

  async function save(e) {
    e.preventDefault()
    setBusy(true)
    setErr("")
    try {
      const payload = buildPayload()
      const saved = await api("/api/resume", {
        method: "PATCH",
        body: {
          job_id: Number(jobId),
          lang: resume.lang,
          version: resume.version,
          content: payload,
        },
      })
      onSaved(saved)
    } catch (errExp) {
      setErr(errExp.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="card content-editor no-print" onSubmit={save} aria-label="ویرایش مستقیم رزومه">
      <div className="review-head">
        <div>
          <h3>ویرایش مستقیم متن رزومه</h3>
          <p className="muted">این متن فقط برای همین نسخه است. تغییرات جدید به عنوان تأیید مستقیم شما ثبت می‌شود.</p>
        </div>
        <button type="button" className="btn-text" onClick={onClose} disabled={busy}>انصراف</button>
      </div>

      <fieldset disabled={busy}>
        <div className="profile-fields">
          <label>نام (فارسی)<input className="input" value={draft.name} onChange={(e) => change("name", e.target.value)} /></label>
          <label>نام انگلیسی (Full Name)<input className="input" value={draft.name_en} onChange={(e) => change("name_en", e.target.value)} /></label>
          <label>عنوان رزومه (Headline)<input className="input" value={draft.headline} onChange={(e) => change("headline", e.target.value)} /></label>
          <label>ایمیل<input className="input" type="email" value={draft.contact.email} onChange={(e) => contactChange("email", e.target.value)} /></label>
          <label>تلفن<input className="input" value={draft.contact.phone} onChange={(e) => contactChange("phone", e.target.value)} /></label>
          <label>شهر<input className="input" value={draft.contact.city} onChange={(e) => contactChange("city", e.target.value)} /></label>
          <label>کشور<input className="input" value={draft.contact.country} onChange={(e) => contactChange("country", e.target.value)} /></label>
          <label>لینکدین (LinkedIn URL)<input className="input" value={draft.contact.linkedin} onChange={(e) => contactChange("linkedin", e.target.value)} /></label>
          <label>گیتهاب (GitHub URL)<input className="input" value={draft.contact.github} onChange={(e) => contactChange("github", e.target.value)} /></label>
          <label>وبسایت / پورتفولیو<input className="input" value={draft.contact.website} onChange={(e) => contactChange("website", e.target.value)} /></label>
        </div>

        <label>خلاصهٔ حرفه‌ای<textarea className="input" rows={4} dir="auto" maxLength={4000} value={draft.summary} onChange={(e) => change("summary", e.target.value)} /></label>

        {/* مهارت‌ها */}
        <section className="profile-group">
          <h4>مهارت‌ها</h4>
          {draft.skills.map((s, i) => (
            <fieldset className="profile-item" key={i}>
              <legend>مهارت · {i + 1}</legend>
              <div className="profile-fields">
                <label>نام مهارت<input className="input" value={s.name} onChange={(e) => itemChange("skills", i, "name", e.target.value)} /></label>
                <label>سطح تسلط<input className="input" placeholder="مسلط / پیشرفته / متوسط" value={s.level} onChange={(e) => itemChange("skills", i, "level", e.target.value)} /></label>
              </div>
              <label>ابزارها و کتابخانه‌ها (با ویرگول جدا کن)<input className="input" value={s.tools} onChange={(e) => itemChange("skills", i, "tools", e.target.value)} /></label>
              <button className="btn-text" type="button" onClick={() => change("skills", draft.skills.filter((_, n) => n !== i))}>حذف این مهارت</button>
            </fieldset>
          ))}
          <button type="button" className="btn btn-ghost" onClick={() => change("skills", [...draft.skills, { name: "", level: "", tools: "" }])}>افزودن مهارت جدید</button>
        </section>

        {/* زبان‌ها */}
        <section className="profile-group">
          <h4>زبان‌ها</h4>
          {draft.languages.map((l, i) => (
            <fieldset className="profile-item" key={i}>
              <legend>زبان · {i + 1}</legend>
              <div className="profile-fields">
                <label>نام زبان<input className="input" value={l.name} onChange={(e) => itemChange("languages", i, "name", e.target.value)} /></label>
                <label>سطح تسلط<input className="input" placeholder="زبان مادری / پیشرفته / متوسط" value={l.level} onChange={(e) => itemChange("languages", i, "level", e.target.value)} /></label>
              </div>
              <button className="btn-text" type="button" onClick={() => change("languages", draft.languages.filter((_, n) => n !== i))}>حذف این زبان</button>
            </fieldset>
          ))}
          <button type="button" className="btn btn-ghost" onClick={() => change("languages", [...draft.languages, { name: "", level: "" }])}>افزودن زبان جدید</button>
        </section>

        {/* افتخارات */}
        <section className="profile-group">
          <h4>افتخارات و جوایز (المپیاد، مسابقات و...)</h4>
          {draft.honors.map((h, i) => (
            <fieldset className="profile-item" key={i}>
              <legend>افتخار · {i + 1}</legend>
              <label>عنوان دستاورد یا مدال<input className="input" value={h.title || ""} onChange={(e) => itemChange("honors", i, "title", e.target.value)} /></label>
              <div className="profile-fields">
                <label>برگزارکننده / مرجع<input className="input" value={h.issuer || ""} onChange={(e) => itemChange("honors", i, "issuer", e.target.value)} /></label>
                <label>سال<input className="input" value={h.year || ""} onChange={(e) => itemChange("honors", i, "year", e.target.value)} /></label>
                <label>محل برگزاری<input className="input" value={h.location || ""} onChange={(e) => itemChange("honors", i, "location", e.target.value)} /></label>
              </div>
              <label>توضیحات تکمیلی<textarea className="input" rows={2} value={h.description || ""} onChange={(e) => itemChange("honors", i, "description", e.target.value)} /></label>
              <button className="btn-text" type="button" onClick={() => change("honors", draft.honors.filter((_, n) => n !== i))}>حذف این افتخار</button>
            </fieldset>
          ))}
          <button type="button" className="btn btn-ghost" onClick={() => change("honors", [...draft.honors, { title: "", issuer: "", year: "", location: "", description: "" }])}>افزودن افتخار جدید</button>
        </section>

        {/* پروژه‌ها */}
        <section className="profile-group">
          <h4>پروژه‌ها</h4>
          {draft.projects.map((p, i) => (
            <fieldset className="profile-item" key={i}>
              <legend>پروژه · {i + 1}</legend>
              <div className="profile-fields">
                <label>نام پروژه<input className="input" value={p.name || ""} onChange={(e) => itemChange("projects", i, "name", e.target.value)} /></label>
                <label>نقش شما<input className="input" value={p.role || ""} onChange={(e) => itemChange("projects", i, "role", e.target.value)} /></label>
                <label>لینک پروژه (اختیاری)<input className="input" value={p.link || ""} onChange={(e) => itemChange("projects", i, "link", e.target.value)} /></label>
                <label>بازهٔ زمانی<input className="input" value={p.period || ""} onChange={(e) => itemChange("projects", i, "period", e.target.value)} /></label>
              </div>
              <label>ابزارها و تکنولوژی‌ها (با ویرگول جدا کن)<input className="input" value={p.tech || ""} onChange={(e) => itemChange("projects", i, "tech", e.target.value)} /></label>
              <label>جمله‌ها و بولت‌ها (هر جمله در یک خط)<textarea className="input" rows={4} dir="auto" value={p.bullets || ""} onChange={(e) => itemChange("projects", i, "bullets", e.target.value)} /></label>
              <button className="btn-text" type="button" onClick={() => change("projects", draft.projects.filter((_, n) => n !== i))}>حذف این پروژه</button>
            </fieldset>
          ))}
          <button type="button" className="btn btn-ghost" onClick={() => change("projects", [...draft.projects, { name: "", role: "", link: "", period: "", tech: "", bullets: "" }])}>افزودن پروژه جدید</button>
        </section>

        {/* سوابق کاری */}
        <section className="profile-group">
          <h4>سابقهٔ کار</h4>
          {draft.experience.map((ex, i) => (
            <fieldset className="profile-item" key={i}>
              <legend>سابقه · {i + 1}</legend>
              <div className="profile-fields">
                <label>عنوان شغل<input className="input" value={ex.title || ""} onChange={(e) => itemChange("experience", i, "title", e.target.value)} /></label>
                <label>شرکت یا تیم<input className="input" value={ex.org || ""} onChange={(e) => itemChange("experience", i, "org", e.target.value)} /></label>
                <label>بازهٔ زمانی<input className="input" value={ex.period || ""} onChange={(e) => itemChange("experience", i, "period", e.target.value)} /></label>
                <label>محل (شهر/دورکار)<input className="input" value={ex.location || ""} onChange={(e) => itemChange("experience", i, "location", e.target.value)} /></label>
              </div>
              <label>جمله‌ها و مسئولیت‌ها (هر مورد در یک خط)<textarea className="input" rows={4} dir="auto" value={ex.bullets || ""} onChange={(e) => itemChange("experience", i, "bullets", e.target.value)} /></label>
              <button className="btn-text" type="button" onClick={() => change("experience", draft.experience.filter((_, n) => n !== i))}>حذف این سابقه</button>
            </fieldset>
          ))}
          <button type="button" className="btn btn-ghost" onClick={() => change("experience", [...draft.experience, { title: "", org: "", period: "", location: "", bullets: "" }])}>افزودن سابقه جدید</button>
        </section>

        {/* تحصیلات */}
        <section className="profile-group">
          <h4>تحصیلات</h4>
          {draft.education.map((ed, i) => (
            <fieldset className="profile-item" key={i}>
              <legend>تحصیلات · {i + 1}</legend>
              <div className="profile-fields">
                <label>مدرک (دیپلم/کارشناسی/...)<input className="input" value={ed.degree || ""} onChange={(e) => itemChange("education", i, "degree", e.target.value)} /></label>
                <label>رشتهٔ تحصیلی<input className="input" value={ed.field || ""} onChange={(e) => itemChange("education", i, "field", e.target.value)} /></label>
                <label>دانشگاه یا مدرسه<input className="input" value={ed.school || ""} onChange={(e) => itemChange("education", i, "school", e.target.value)} /></label>
                <label>بازه یا سال فراغت<input className="input" value={ed.period || ""} onChange={(e) => itemChange("education", i, "period", e.target.value)} /></label>
                <label>معدل (GPA)<input className="input" value={ed.gpa || ""} onChange={(e) => itemChange("education", i, "gpa", e.target.value)} /></label>
              </div>
              <label>توضیحات یا افتخار تحصیلی<textarea className="input" rows={2} value={ed.notes || ""} onChange={(e) => itemChange("education", i, "notes", e.target.value)} /></label>
              <button className="btn-text" type="button" onClick={() => change("education", draft.education.filter((_, n) => n !== i))}>حذف این مورد</button>
            </fieldset>
          ))}
          <button type="button" className="btn btn-ghost" onClick={() => change("education", [...draft.education, { degree: "", field: "", school: "", period: "", gpa: "", notes: "" }])}>افزودن مقطع تحصیلی جدید</button>
        </section>

        {/* گواهینامه‌ها */}
        <section className="profile-group">
          <h4>گواهینامه‌ها</h4>
          {draft.certifications.map((cert, i) => (
            <fieldset className="profile-item" key={i}>
              <legend>گواهی · {i + 1}</legend>
              <div className="profile-fields">
                <label>نام مدرک یا دوره<input className="input" value={cert.name || ""} onChange={(e) => itemChange("certifications", i, "name", e.target.value)} /></label>
                <label>مرجع صادرکننده<input className="input" value={cert.issuer || ""} onChange={(e) => itemChange("certifications", i, "issuer", e.target.value)} /></label>
                <label>سال دریافت<input className="input" value={cert.year || ""} onChange={(e) => itemChange("certifications", i, "year", e.target.value)} /></label>
              </div>
              <button className="btn-text" type="button" onClick={() => change("certifications", draft.certifications.filter((_, n) => n !== i))}>حذف این گواهی</button>
            </fieldset>
          ))}
          <button type="button" className="btn btn-ghost" onClick={() => change("certifications", [...draft.certifications, { name: "", issuer: "", year: "" }])}>افزودن گواهینامه جدید</button>
        </section>

        <button className="btn btn-ghost" type="button" onClick={() => setReview(!review)}>
          {review ? "بستن مقایسه" : "مقایسهٔ قبل و بعد"}
        </button>

        {review && (
          <div className="edit-comparison">
            <section>
              <h4>نسخهٔ ذخیره‌شده فعلی</h4>
              <Sheet c={resume.content} lang={resume.lang} evidence={false} />
            </section>
            <section>
              <h4>پیش‌نمایش تغییرات جدید</h4>
              <Sheet c={buildPayload()} lang={resume.lang} evidence={false} />
            </section>
          </div>
        )}

        {err && <ErrorBox message={err} />}
        <button className="btn btn-primary" type="submit">
          {busy ? "در حال ذخیره…" : "تأیید متن و ذخیرهٔ نسخه جدید"}
        </button>
      </fieldset>
    </form>
  )
}

function ResumeEditor() {
  const { jobId } = useParams()
  const [sp, setSp] = useSearchParams()
  const lang = sp.get("lang") === "en" ? "en" : "fa"
  const { refreshKey, openRefine } = useApp()
  const [r, setR] = useState(null)
  const [err, setErr] = useState("")
  const [making, setMaking] = useState(false)
  const [prep, setPrep] = useState(null)
  const [preparing, setPreparing] = useState(false)
  const [editing, setEditing] = useState(false)
  const [contentEditing, setContentEditing] = useState(false)
  const [downloading, setDownloading] = useState(false)

  useEffect(() => {
    let active = true
    setErr("")
    setR(null)
    setPrep(null)
    setPreparing(false)
    setEditing(false)
    setContentEditing(false)
    Promise.all([
      api("/api/resume?job_id=" + jobId + "&lang=" + lang),
      api("/api/resume/preparation?job_id=" + jobId),
    ])
      .then(([saved, preparation]) => {
        if (active) {
          setR(saved)
          setPrep(preparation)
          setPreparing(!saved)
        }
      })
      .catch((e) => {
        if (active) setErr(e.message)
      })
    return () => {
      active = false
    }
  }, [jobId, lang, refreshKey])

  function answer(index, patch) {
    setPrep((p) => ({
      ...p,
      questions: p.questions.map((q, i) => (i === index ? { ...q, ...patch } : q)),
    }))
  }

  async function make(skip = false) {
    if (making) return
    const answers = prep.questions.map((q) => ({
      id: q.id,
      status: skip ? "skip" : q.status,
      answer: skip || q.status !== "yes" ? "" : q.answer,
    }))
    if (answers.some((a) => a.status === "yes" && !a.answer.trim())) {
      setErr("برای مواردی که تجربه داری، یک توضیح کوتاه بنویس یا سؤال را رد کن.")
      return
    }
    setMaking(true)
    setErr("")
    try {
      setPrep(
        await api("/api/resume/preparation", {
          method: "POST",
          body: { job_id: Number(jobId), fingerprint: prep.fingerprint, answers },
        })
      )
      setR(await api("/api/resume", { method: "POST", body: { job_id: Number(jobId), lang } }))
      setPreparing(false)
    } catch (e) {
      setErr(e.message)
    } finally {
      setMaking(false)
    }
  }

  async function profileSaved() {
    setEditing(false)
    setErr("")
    try {
      setPrep(await api("/api/resume/preparation?job_id=" + jobId))
      setPreparing(true)
    } catch (e) {
      setErr(e.message)
    }
  }

  async function word() {
    setDownloading(true)
    setErr("")
    try {
      const blob = await api("/api/resume/export?job_id=" + jobId + "&lang=" + lang, { download: true })
      const url = URL.createObjectURL(blob)
      const link = document.createElement("a")
      link.href = url
      link.download = "HireLoop-" + lang + "-v" + r.version + ".docx"
      document.body.appendChild(link)
      link.click()
      link.remove()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (e) {
      setErr(e.message)
    } finally {
      setDownloading(false)
    }
  }

  return (
    <>
      <div className="page-head no-print">
        <div>
          <h2>رزومهٔ اختصاصی</h2>
          {(r || prep) && (
            <p className="muted">
              برای «{(r || prep).job.title}»
              {(r || prep).job.company ? " · " + (r || prep).job.company : ""}
            </p>
          )}
        </div>
        <Link to="/app/jobs" className="btn btn-ghost">برگشت به آگهی‌ها</Link>
      </div>

      {prep && <ResumeCompletenessBar prep={prep} />}

      {editing && prep && (
        <ProfileEditor profile={prep.profile} onClose={() => setEditing(false)} onSaved={profileSaved} />
      )}

      {contentEditing && r && (
        <ContentEditor
          key={jobId + ":" + lang + ":" + r.version}
          resume={r}
          jobId={jobId}
          onClose={() => setContentEditing(false)}
          onSaved={(saved) => {
            setR(saved)
            setContentEditing(false)
          }}
        />
      )}

      {err && (
        <div className="no-print" style={{ marginBottom: "1rem" }}>
          <ErrorBox message={err} onRetry={!prep ? () => location.reload() : undefined} />
        </div>
      )}

      <div className="rsplit">
        <div>
          {prep && preparing && (
            <form className="card resume-prep no-print" onSubmit={(e) => { e.preventDefault(); make() }}>
              <h3>چند نکته برای همین آگهی</h3>
              <p className="muted">
                {prep.questions.length
                  ? "این موارد در پروفایلت مشخص نیستند. اگر تجربه داری توضیح بده؛ پاسخ‌ها فقط برای رزومهٔ همین آگهی استفاده می‌شوند."
                  : "اطلاعات اولیهٔ این آگهی را داریم. می‌توانی اطلاعاتت را مرور کنی و رزومه را بسازی."}
              </p>
              <fieldset disabled={making || editing}>
                {prep.questions.map((q, i) => (
                  <fieldset className="prep-question" key={q.id}>
                    <legend>{q.question}</legend>
                    <div className="answer-options">
                      {[
                        ["yes", "تجربه دارم"],
                        ["no", "تجربه ندارم"],
                        ["skip", "رد کردن"],
                      ].map(([value, title]) => (
                        <label key={value}>
                          <input
                            type="radio"
                            name={"answer-" + q.id}
                            value={value}
                            checked={q.status === value}
                            onChange={() => answer(i, { status: value })}
                          />
                          {title}
                        </label>
                      ))}
                    </div>
                    {q.status === "yes" && (
                      <label>
                        توضیح تجربهٔ واقعی
                        <textarea
                          className="input"
                          rows={3}
                          value={q.answer}
                          onChange={(e) => answer(i, { answer: e.target.value })}
                          maxLength={2000}
                          placeholder="خودت چه کاری انجام دادی و نتیجه چه بود؟"
                          required
                        />
                      </label>
                    )}
                  </fieldset>
                ))}
                <div className="review-actions">
                  <button className="btn btn-primary" type="submit">
                    {making ? <Spinner label="در حال ساخت رزومه…" /> : r ? "ذخیره و ساخت نسخهٔ جدید" : "ذخیره و ساخت رزومه"}
                  </button>
                  <button className="btn btn-ghost" type="button" onClick={() => make(true)}>
                    ساخت فقط با پروفایل فعلی
                  </button>
                  {r && (
                    <button className="btn-text" type="button" onClick={() => setPreparing(false)}>
                      برگشت به نسخهٔ ذخیره‌شده
                    </button>
                  )}
                </div>
              </fieldset>
            </form>
          )}

          {!prep && !err && <div className="card"><Skeleton lines={6} height={16} /></div>}

          {r && <Sheet c={r.content} lang={lang} evidence={r.evidence} />}
        </div>

        <aside className="side no-print">
          <div className="card" style={{ display: "grid", gap: ".9rem" }}>
            <Link to="/app/resume" className="btn btn-ghost">رزومه‌های من</Link>
            <Link to={"/app/jobs/" + jobId} className="btn btn-ghost">تحلیل شرایط آگهی</Link>
            <Link to={"/app/practice/" + jobId} className="btn btn-blue">تمرین مصاحبه برای این شغل</Link>
            <div className="seg" role="group" aria-label="زبان رزومه">
              <button className={lang === "fa" ? "on" : ""} disabled={making || contentEditing} onClick={() => setSp({})}>فارسی</button>
              <button className={lang === "en" ? "on" : ""} disabled={making || contentEditing} onClick={() => setSp({ lang: "en" })}>English</button>
            </div>
            <button className="btn btn-ghost" disabled={!prep || making} onClick={() => setEditing(!editing)}>مرور و ویرایش اطلاعات</button>
            {r && !preparing && (
              <button className="btn btn-blue" disabled={!prep || making} onClick={() => setPreparing(true)}>تکمیل اطلاعات این آگهی</button>
            )}
            <button className="btn btn-primary" disabled={!r || making} onClick={() => window.print()}>دانلود PDF</button>
            <button className="btn btn-ghost" disabled={!r || making || downloading} onClick={word}>
              {downloading ? "در حال دریافت…" : "دانلود Word"}
            </button>
            <button className="btn btn-blue" disabled={!r || making || preparing || editing} onClick={() => setContentEditing(!contentEditing)}>
              ویرایش مستقیم رزومه
            </button>
            <button className="btn btn-ghost" disabled={!r || making || contentEditing} onClick={openRefine}>درخواست تغییر با گفت‌وگو</button>
            <TrackJob key={jobId + ":" + lang} jobId={jobId} lang={r?.lang} resumeVersion={r?.version} />
            {r && <p className="muted">نسخهٔ {fa(r.version)} · با باز کردن مجدد، همین نسخه نمایش داده می‌شود.</p>}
            <p className="muted" style={{ fontSize: ".85rem" }}>پیش از ارسال، متن رزومه را بررسی کن. برای PDF در پنجرهٔ چاپ «ذخیره به‌صورت PDF» را انتخاب کن.</p>
          </div>

          {!!r?.evidence?.omitted?.length && (
            <div className="card">
              <h3>ادعاهای کنارگذاشته‌شده</h3>
              <p className="muted">این جمله‌ها عددی داشتند که در منبع پیدا نشد و وارد رزومه نشدند.</p>
              {r.evidence.omitted.map((item, i) => (
                <details key={i}>
                  <summary>مرور ادعای {fa(i + 1)}</summary>
                  <p dir="auto">{item.text}</p>
                  <p>{item.reason}</p>
                </details>
              ))}
            </div>
          )}

          {r?.tailoring && (
            <div className="card tailoring">
              <h3>ارتباط رزومه با آگهی</h3>
              {r.tailoring.highlighted_skills.length > 0 && (
                <div>
                  <h4>مهارت‌های مرتبط در رزومه</h4>
                  <p>{r.tailoring.highlighted_skills.join(lang === "en" ? ", " : "، ")}</p>
                </div>
              )}
              {r.tailoring.projects.length > 0 && (
                <div>
                  <h4>ترتیب پروژه‌ها در این نسخه</h4>
                  <ol>{r.tailoring.projects.map((name, i) => <li key={i}>{name}</li>)}</ol>
                </div>
              )}
              {r.tailoring.unconfirmed.length > 0 && (
                <div>
                  <h4>نیازهای ذکر یا تأییدنشده</h4>
                  <p>{r.tailoring.unconfirmed.join(lang === "en" ? ", " : "، ")}</p>
                  <p className="muted">این موارد در اطلاعات این نسخه پشتوانه ندارند؛ این به معنی بلد نبودن تو نیست.</p>
                </div>
              )}
            </div>
          )}
        </aside>
      </div>
    </>
  )
}

function SavedResumes() {
  const { refreshKey } = useApp()
  const [items, setItems] = useState(null)
  const [err, setErr] = useState("")

  async function load() {
    setErr("")
    try {
      setItems((await api("/api/resumes")).resumes)
    } catch (e) {
      setErr(e.message)
    }
  }

  useEffect(() => {
    load()
  }, [refreshKey]) // eslint-disable-line

  return (
    <>
      <div className="page-head">
        <div>
          <h2>رزومه‌های من</h2>
          <p>نسخه‌های ذخیره‌شده برای آگهی‌ها، آمادهٔ باز کردن و دریافت.</p>
        </div>
        <Link to="/app/jobs" className="btn btn-ghost">دیدن آگهی‌ها</Link>
      </div>
      {err ? (
        <ErrorBox message={err} onRetry={load} />
      ) : !items ? (
        <div className="card"><Skeleton lines={3} /></div>
      ) : !items.length ? (
        <Empty title="هنوز رزومه‌ای نساخته‌ای" text="یک آگهی را انتخاب کن تا رزومهٔ متناسب با آن ساخته و اینجا ذخیره شود.">
          <Link to="/app/jobs" className="btn btn-primary">انتخاب آگهی</Link>
        </Empty>
      ) : (
        <div className="jobs">
          {items.map((r) => (
            <article className="card" key={r.job.id + "-" + r.lang}>
              <h3>{r.job.title}</h3>
              {r.job.company && <p className="muted">{r.job.company}</p>}
              <p className="muted">{r.lang === "en" ? "انگلیسی" : "فارسی"} · نسخهٔ {fa(r.version)}</p>
              <Link className="btn btn-blue" to={"/app/resume/" + r.job.id + "?lang=" + r.lang}>باز کردن رزومه</Link>
            </article>
          ))}
        </div>
      )}
    </>
  )
}

export default function Resume() {
  const { jobId } = useParams()
  return jobId ? <ResumeEditor /> : <SavedResumes />
}

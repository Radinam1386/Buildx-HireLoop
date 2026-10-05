"use strict";

const $ = (selector) => document.querySelector(selector);
const state = {
  user: null,
  profile: {},
  messages: [],
  jobs: [],
  search: null,
  matches: [],
  resumes: [],
  selectedResume: null,
  configured: false,
  sources: [],
  usage: {},
  authMode: "login",
  currentView: "interview"
};

const titles = {
  interview: "گفت‌وگو درباره تجربه شما",
  jobs: "جست‌وجوی فرصت‌های شغلی",
  resumes: "رزومه‌های شما",
  profile: "بررسی و تأیید پرونده"
};

const emptyChatTemplate = $("#chat-empty").cloneNode(true);
let noticeTimer;
let sessionVersion = 0;
let authBusy = false;
const requests = new Set();
const pendingButtons = new Map();

function changeSession() {
  sessionVersion += 1;
  for (const controller of requests) controller.abort();
  for (const [button, record] of pendingButtons) {
    button.textContent = record.original;
    button.disabled = button.hasAttribute("data-ai") && !state.configured;
  }
  pendingButtons.clear();
}

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

function notify(message, error = false) {
  const notice = $("#notice");
  notice.textContent = message;
  notice.classList.toggle("error", error);
  notice.hidden = false;
  clearTimeout(noticeTimer);
  noticeTimer = setTimeout(() => { notice.hidden = true; }, error ? 9000 : 5000);
}

function errorMessage(detail) {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((item) => item.msg || "ورودی را بررسی کنید.").join("؛ ");
  return "درخواست انجام نشد. دوباره تلاش کنید.";
}

async function api(path, options = {}) {
  const version = sessionVersion;
  const controller = new AbortController();
  requests.add(controller);
  const timer = setTimeout(() => controller.abort(), path === "/api/chat" ? 210000 : 120000);
  try {
    const response = await fetch(path, {
      credentials: "same-origin", ...options, signal: controller.signal,
      headers: { "Content-Type": "application/json", ...options.headers },
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    });
    const data = await response.json().catch(() => ({}));
    if (version !== sessionVersion) throw new Error("Session changed");
    if (!response.ok) {
      if (response.status === 401 && state.user) showAuth();
      const error = new Error(errorMessage(data.detail || data.error));
      error.status = response.status;
      throw error;
    }
    return data;
  } catch (error) {
    if (version !== sessionVersion) { error.name = "SessionChanged"; throw error; }
    if (error.name === "AbortError") throw new Error("پاسخ بیش از حد طول کشید. اتصال را بررسی و دوباره تلاش کنید.");
    if (error instanceof TypeError) throw new Error("ارتباط با سرور برقرار نشد. اتصال را بررسی و دوباره تلاش کنید.");
    throw error;
  } finally { clearTimeout(timer); requests.delete(controller); }
}

async function pending(button, label, work) {
  const version = sessionVersion;
  const record = { original: button.textContent };
  pendingButtons.set(button, record);
  button.disabled = true;
  button.textContent = label;
  try { return await work(); }
  catch (error) { if (version === sessionVersion) notify(error.message, true); return null; }
  finally {
    if (pendingButtons.get(button) === record) {
      pendingButtons.delete(button);
      button.textContent = record.original;
      button.disabled = button.hasAttribute("data-ai") && !state.configured;
    }
  }
}

function safeLink(url, label, className = "") {
  try {
    const parsed = new URL(url);
    if (!["http:", "https:"].includes(parsed.protocol)) return null;
    const link = element("a", className, label);
    link.href = parsed.href;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    return link;
  } catch { return null; }
}

function updateStepper(currentView) {
  const steps = [
    { id: "interview", index: 1 },
    { id: "jobs", index: 2 },
    { id: "resumes", index: 3 },
    { id: "profile", index: 4 },
  ];

  const profileReady = Boolean(state.profile?.confirmed || (state.profile?.skills?.length && state.profile?.full_name));
  const jobsReady = Boolean(state.jobs?.length);
  const resumeReady = Boolean(state.resumes?.length);

  const completedMap = {
    interview: profileReady,
    jobs: jobsReady,
    resumes: resumeReady,
    profile: Boolean(state.profile?.confirmed),
  };

  const stepItems = document.querySelectorAll(".step-item");
  const dividers = document.querySelectorAll(".step-divider");

  stepItems.forEach((btn, idx) => {
    const stepId = btn.dataset.step;
    const isActive = stepId === currentView;
    const isCompleted = completedMap[stepId];

    btn.classList.toggle("active", isActive);
    btn.classList.toggle("completed", isCompleted && !isActive);
    if (isActive) btn.setAttribute("aria-current", "step");
    else btn.removeAttribute("aria-current");

    if (dividers[idx]) {
      dividers[idx].classList.toggle("completed", isCompleted);
    }
  });
}

function updateDossierProgress() {
  const profile = state.profile || {};
  let score = 10; // Base score for account
  if (profile.full_name) score += 15;
  if (profile.city) score += 10;
  if (profile.skills?.length) score += Math.min(30, profile.skills.length * 6);
  if (profile.projects?.length) score += Math.min(20, profile.projects.length * 10);
  if (profile.experience?.length) score += Math.min(15, profile.experience.length * 8);
  if (profile.summary) score += 10;
  if (profile.confirmed) score = 100;

  score = Math.min(100, score);
  const progressBar = $("#dossier-progress-bar");
  if (progressBar) {
    progressBar.style.width = `${score}%`;
    progressBar.setAttribute("aria-valuenow", String(score));
  }
}

function showAuth() {
  changeSession();
  Object.assign(state, {
    user: null, profile: {}, messages: [], jobs: [],
    search: null, matches: [], resumes: [], selectedResume: null, usage: {}
  });
  $("#profile-form").reset();
  $("#profile-projects").replaceChildren();
  $("#profile-experience").replaceChildren();
  $("#chat-input").value = "";
  $("#chat-input").disabled = false;
  $("#job-text").value = "";
  $("#job-query").value = "";
  $("#job-city").value = "";
  $("#account-name").textContent = "";
  $("#source-status").replaceChildren();
  $("#job-results").replaceChildren();
  $("#resume-preview").replaceChildren();
  renderMessages(); renderDossier(); renderResumeList(); renderUsage();
  $("#boot").hidden = true;
  $("#workspace").hidden = true;
  $("#auth-view").hidden = false;
}

function setAuthMode(mode) {
  if (authBusy) return;
  state.authMode = mode;
  const register = mode === "register";
  $("#name-field").hidden = !register;
  $("#auth-name").required = register;
  $("#auth-password").minLength = register ? 8 : 1;
  $("#auth-password").autocomplete = register ? "new-password" : "current-password";
  $("#auth-heading").textContent = register ? "پرونده خودتان را بسازید." : "خوش برگشتید.";
  $("#auth-description").textContent = register ? "نام، ایمیل و یک رمز حداقل ۸ کاراکتری وارد کنید." : "برای ادامه مسیر، وارد حساب خود شوید.";
  $("#auth-submit").textContent = register ? "ساخت حساب و شروع" : "ورود به پرونده";
  $("#auth-error").hidden = true;
  for (const button of [$("#login-tab"), $("#register-tab")]) {
    const active = button.id === `${mode}-tab`;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  }
}

function showView(view, focus = true) {
  if (!titles[view]) return;
  state.currentView = view;
  for (const section of document.querySelectorAll(".view")) {
    section.hidden = section.id !== `view-${view}`;
  }
  for (const button of document.querySelectorAll("[data-view]")) {
    const active = button.dataset.view === view;
    button.classList.toggle("active", active);
    if (active) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  }
  $("#page-title").textContent = titles[view];
  updateStepper(view);
  if (view === "profile") fillProfileForm();
  if (focus) $("#main").focus({ preventScroll: true });
}

function renderUsage(usage) {
  if (usage) state.usage = usage;
  const calls = state.usage.calls || 0;
  $("#usage").textContent = `${calls.toLocaleString("fa-IR")} درخواست هوش مصنوعی`;
}

function renderConfiguration() {
  $("#config-banner").hidden = state.configured;
  for (const button of document.querySelectorAll("[data-ai], #chat-submit, #match-jobs")) {
    button.disabled = !state.configured;
  }
  $("#chat-status").textContent = state.configured ? "پاسخ‌ها ذخیره می‌شوند." : "گفت‌وگو پس از تنظیم سرویس فعال می‌شود.";
  const filters = $("#source-filters");
  filters.replaceChildren();
  for (const source of state.sources) {
    const label = element("label");
    const input = element("input");
    input.type = "checkbox";
    input.value = source.id;
    input.checked = true;
    label.append(input, document.createTextNode(source.name));
    filters.append(label);
  }
}

function renderDossier() {
  const profile = state.profile || {};
  $("#dossier-name").textContent = profile.full_name || state.user?.name || "نام شما";
  $("#dossier-location").textContent = [profile.city, profile.remote ? "آماده دورکاری" : ""].filter(Boolean).join(" · ") || "شهر هنوز ثبت نشده";
  
  const skills = $("#dossier-skills");
  skills.replaceChildren();
  for (const skill of profile.skills || []) {
    skills.append(element("span", "chip", skill));
  }
  if (!skills.childElementCount) {
    skills.append(element("p", "muted", "مهارت‌ها از گفت‌وگو یا ویرایش پرونده اضافه می‌شوند."));
  }

  const work = $("#dossier-work");
  work.replaceChildren();
  for (const item of [...(profile.experience || []), ...(profile.projects || [])].slice(0, 4)) {
    const entry = element("div", "dossier-item");
    entry.append(
      element("strong", "", item.role || item.name || item.company),
      element("p", "muted", item.company || item.description)
    );
    work.append(entry);
  }
  if (!work.childElementCount) {
    work.append(element("p", "muted", "از یک تجربه یا پروژه فرانت‌اند شروع کنید."));
  }

  $("#dossier-summary").textContent = profile.summary || "خلاصه حرفه‌ای شما پس از ثبت تجربه‌ها اینجا قرار می‌گیرد.";
  $("#profile-status").textContent = profile.confirmed ? "اطلاعات تأیید شده" : "نیاز به بررسی و تأیید شما";
  $("#profile-status").classList.toggle("confirmed", Boolean(profile.confirmed));
  
  updateDossierProgress();
}

function appendMessage(message) {
  const row = element("div", `message ${message.role === "user" ? "user" : "assistant"}`);
  const text = message.role === "user" ? message.content : String(message.content || "").replace(/\*\*([^*]+)\*\*/g, "$1");
  row.append(
    element("div", "message-label", message.role === "user" ? "شما" : "دستیار کاریابی"),
    element("div", "message-body", text)
  );
  $("#messages").append(row);
  $("#messages").scrollTop = $("#messages").scrollHeight;
  return row;
}

function renderMessages() {
  const box = $("#messages");
  const empty = emptyChatTemplate.cloneNode(true);
  box.replaceChildren();
  if (!state.messages.length) {
    box.append(empty);
  } else {
    for (const message of state.messages) appendMessage(message);
  }
  renderChatActions();
}

function renderChatActions() {
  $("#chat-actions")?.remove();
  if (!state.user || (!state.search && state.profile.confirmed)) return;
  
  const row = element("div", "message assistant");
  row.id = "chat-actions";
  const body = element("div", "message-body");
  
  if (state.search) {
    const search = state.search;
    body.append(element("strong", "", `${(search.jobs || []).length.toLocaleString("fa-IR")} آگهی در نتایج این جست‌وجو`));
    if (search.query) body.append(element("p", "", `عبارت جست‌وجو: ${search.query}`));
    const location = !Object.hasOwn(search, "city")
      ? "فیلترهای این جست‌وجوی قبلی ثبت نشده‌اند؛ دوباره جست‌وجو کنید"
      : search.city
      ? search.city + (search.remote ? " یا دورکاری" : "")
      : search.remote
      ? "فقط دورکاری"
      : "بدون محدودیت شهر یا دورکاری";
    body.append(element("p", "", `فیلتر مکان: ${location}`));
    if (search.broadened) {
      body.append(element("p", "", `جست‌وجوی اولیه برای «${search.requested?.query || ""}» نتیجه نداشت؛ این جست‌وجوی گسترده‌تر با یک مهارت پروفایل و بدون فیلتر مکان انجام شده است. این‌ها تطابق دقیق با درخواست اولیه نیستند.`));
    }
    for (const source of search.sources || []) {
      const status = source.status === "error" ? "دسترسی ناموفق" : source.count ? `${source.count} نتیجه` : "بدون نتیجه";
      body.append(element("p", "", `${source.name || source.id}: ${status}${source.error ? `؛ ${source.error}` : ""}`));
    }
    const jobs = element("button", "button secondary", "مشاهده نتایج و وضعیت منابع");
    jobs.type = "button";
    jobs.dataset.go = "jobs";
    body.append(jobs);
  }

  if (!state.profile.confirmed) {
    body.append(element("p", "", "برای جست‌وجو نیازی به تأیید نیست. پیش از ساخت رزومه، اطلاعات را بررسی و تأیید کنید."));
    const confirm = element("button", "button primary", "بررسی و تأیید پروفایل");
    confirm.type = "button";
    confirm.dataset.go = "profile";
    body.append(confirm);
  }
  
  row.append(body);
  $("#messages").append(row);
  $("#messages").scrollTop = $("#messages").scrollHeight;
}

function lines(value) {
  return String(value || "").split(/\n/).map((line) => line.trim()).filter(Boolean);
}

function printableItems(items) {
  return (items || []).map((item) => typeof item === "string" ? item : Object.values(item).filter(Boolean).join(" | ")).join("\n");
}

function addProfileEntry(key, item = {}) {
  const container = $(`#profile-${key}`);
  if (container.childElementCount >= 12) {
    notify("حداکثر ۱۲ مورد می‌توانید ثبت کنید.", true);
    return;
  }
  const row = element("div", "profile-entry");
  row.dataset.profileEntry = key;
  const fields = key === "projects"
    ? [["name", "نام پروژه"], ["description", "نقش شما، فناوری‌ها و نتیجه پروژه"], ["url", "پیوند پروژه آنلاین / گیت‌هاب (اختیاری)"]]
    : [["company", "نام شرکت یا تیم"], ["role", "عنوان شغلی / کارآموزی"], ["description", "شرح وظایف و دستاوردها"]];
  
  for (const [field, title] of fields) {
    const label = element("label", "", title);
    const input = element(field === "description" ? "textarea" : "input");
    input.dataset.entryField = field;
    input.value = item[field] || "";
    input.maxLength = field === "description" ? 3000 : 200;
    if (field === "description") input.rows = 3;
    if (field === "url") { input.type = "url"; input.dir = "ltr"; }
    label.append(input);
    row.append(label);
  }
  const remove = element("button", "text-button", "حذف این مورد");
  remove.type = "button";
  remove.dataset.removeEntry = "";
  row.append(remove);
  container.append(row);
}

function fillProfileForm() {
  const form = $("#profile-form");
  for (const key of ["full_name", "email", "phone", "city", "summary"]) {
    form.elements[key].value = state.profile[key] || "";
  }
  form.elements.remote.checked = Boolean(state.profile.remote);
  form.elements.skills.value = (state.profile.skills || []).join("، ");
  for (const key of ["projects", "experience"]) {
    $(`#profile-${key}`).replaceChildren();
    for (const item of state.profile[key] || []) addProfileEntry(key, item);
  }
  form.elements.education.value = printableItems(state.profile.education);
  form.elements.languages.value = printableItems(state.profile.languages);
}

function profileFromForm() {
  const form = $("#profile-form");
  const profile = { ...state.profile, confirmed: true };
  for (const key of ["full_name", "email", "phone", "city", "summary"]) {
    profile[key] = form.elements[key].value.trim();
  }
  profile.remote = form.elements.remote.checked;
  profile.skills = [...new Set(form.elements.skills.value.split(/[,،\n]/).map((value) => value.trim()).filter(Boolean))];
  for (const key of ["projects", "experience"]) {
    profile[key] = [...document.querySelectorAll(`[data-profile-entry="${key}"]`)].map((row) =>
      Object.fromEntries([...row.querySelectorAll("[data-entry-field]")].map((input) => [input.dataset.entryField, input.value]))
    );
  }
  for (const key of ["education", "languages"]) {
    profile[key] = lines(form.elements[key].value);
  }
  return profile;
}

function renderSources(sources) {
  const box = $("#source-status");
  box.replaceChildren();
  for (const source of sources || []) {
    const failed = ["failed", "error", "blocked", "unavailable"].includes(source.status);
    const count = source.count === undefined ? "" : ` · ${Number(source.count).toLocaleString("fa-IR")} نتیجه`;
    const status = failed ? "جست‌وجو انجام نشد" : source.status === "empty" || source.count === 0 ? "نتیجه‌ای پیدا نشد" : source.error ? "نتیجه با دسترسی محدود" : "جست‌وجو انجام شد";
    box.append(element("p", `source-result${failed ? " failed" : ""}`, `${source.name || source.id}: ${status}${count}${source.error ? ` · ${source.error}` : ""}`));
  }
}

function emptyState(title, description, buttonLabel = null, goView = null) {
  const box = element("div", "panel empty-state");
  box.append(element("h3", "", title), element("p", "", description));
  if (buttonLabel && goView) {
    const btn = element("button", "button primary", buttonLabel);
    btn.type = "button";
    btn.dataset.go = goView;
    box.append(btn);
  }
  return box;
}

function renderJobs() {
  const box = $("#job-results");
  box.replaceChildren();
  $("#job-toolbar").hidden = !state.jobs.length;
  $("#job-count").textContent = `${state.jobs.length.toLocaleString("fa-IR")} فرصت شغلی پیدا شد`;
  $("#match-jobs").textContent = state.jobs.length > 12 ? "مقایسه ۱۲ فرصت اول با پرونده من" : "مقایسه و سنجش تناسب با پرونده من";
  
  if (!state.jobs.length) {
    box.append(emptyState("آگهی‌ای برای این جست‌وجو پیدا نشد.", "عبارت جست‌وجو را کوتاه‌تر کنید، شهر را حذف کنید یا منبع دیگری انتخاب کنید. وضعیت هر منبع بالای این بخش آمده است."));
    return;
  }

  for (const [index, job] of state.jobs.entries()) {
    const card = element("article", "panel job-card");
    const body = element("div");
    body.append(
      element("h3", "", job.title),
      element("p", "job-company", [job.company, job.location].filter(Boolean).join(" · ") || "شرکت و محل کار در نتیجه مشخص نیست")
    );

    const evidence = element("div", "job-evidence");
    const sourceName = state.sources.find((source) => source.id === job.source)?.name || job.source || "نامشخص";
    evidence.append(
      element("span", "", `منبع: ${sourceName}`),
      element("span", job.verified ? "verified" : "", ["snippet", "search_snippet"].includes(job.evidence_type) ? "نتیجه نمایه‌شده جست‌وجو" : job.verified ? "اطلاعات صفحه منبع" : "جزئیات در صفحه منبع نیاز به بررسی دارد")
    );
    if (job.checked_at) {
      const date = new Date(job.checked_at);
      if (!Number.isNaN(date.getTime())) evidence.append(element("span", "", `بررسی: ${date.toLocaleDateString("fa-IR")}`));
    }
    body.append(evidence);

    if (job.description) body.append(element("p", "job-description", job.description));

    const chips = element("div", "chips");
    for (const skill of job.skills || []) chips.append(element("span", "chip", skill));
    body.append(chips);

    const actions = element("div", "job-actions");
    const source = safeLink(job.url, "مشاهده در سایت مرجع ↗");
    if (source) actions.append(source);

    // Single primary action per card
    const resume = element("button", "button primary", "ساخت رزومه برای این شغل");
    resume.type = "button";
    resume.dataset.resumeJob = index;
    resume.setAttribute("data-ai", "");
    resume.disabled = !state.configured;
    actions.append(resume, element("span", "cost-note", "یک درخواست هوش مصنوعی"));
    card.append(body, actions);

    const match = state.matches.find((item) => String(item.id) === String(job.id));
    if (match) {
      const section = element("div", "job-match");
      const score = Number(match.score);
      section.append(
        element("strong", "", Number.isFinite(score) ? `ارزیابی تناسب شغلی: ${score.toLocaleString("fa-IR")} از ۱۰۰` : "ارزیابی تناسب"),
        element("p", "", `چرا مناسب است: ${match.reason}`)
      );
      if (match.gaps?.length) {
        section.append(element("p", "match-gaps", `چه چیزهایی کم است (فاصله‌های مهارتی): ${match.gaps.join("، ")}`));
      }
      card.append(section);
    }
    box.append(card);
  }
}

function resumeDate(resume) {
  const date = new Date(resume.created_at);
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleDateString("fa-IR");
}

function renderResumeList() {
  const box = $("#resume-list");
  box.replaceChildren();
  if (!state.resumes.length) box.append(element("p", "muted", "رزومه‌ای ذخیره نشده است."));
  for (const resume of state.resumes) {
    const button = element("button", `resume-item${state.selectedResume?.id === resume.id ? " active" : ""}`);
    button.type = "button";
    button.dataset.openResume = resume.id;
    button.append(
      element("strong", "", resume.title || "رزومه"),
      element("span", "", resumeDate(resume))
    );
    box.append(button);
  }
}

function renderResume(resume) {
  state.selectedResume = resume;
  renderResumeList();
  const box = $("#resume-preview");
  box.replaceChildren();
  
  const toolbar = element("div", "resume-toolbar");
  const print = element("a", "button secondary", "چاپ / ذخیره PDF");
  print.href = `/api/resumes/${encodeURIComponent(resume.id)}/print`;
  print.target = "_blank";
  print.rel = "noopener noreferrer";
  toolbar.append(element("span", "", resume.title || "پیش‌نمایش رزومه"), print);
  box.append(toolbar);

  const content = resume.content || {};
  const profile = content.profile || {};
  const doc = element("div", "resume-document");
  doc.append(element("h2", "", profile.full_name || "رزومه اختصاصی"));

  const contact = element("div", "resume-contact");
  for (const value of [profile.email, profile.phone, profile.city]) {
    if (value) contact.append(element("span", "", value));
  }
  doc.append(contact);

  function section(title) {
    const node = element("section", "resume-section");
    node.append(element("h3", "", title));
    doc.append(node);
    return node;
  }

  if (content.summary || profile.summary) {
    section("خلاصه حرفه‌ای").append(element("p", "", content.summary || profile.summary));
  }

  if (profile.skills?.length) {
    const skills = element("div", "chips");
    for (const value of profile.skills) skills.append(element("span", "chip", value));
    section("مهارت‌های تخصصی").append(skills);
  }

  for (const [key, title] of [["experience", "سوابق کاری و کارآموزی"], ["projects", "پروژه‌ها و نمونه‌کارها"]]) {
    if (!profile[key]?.length) continue;
    const group = section(title);
    for (const item of profile[key]) {
      const entry = element("div", "resume-entry");
      entry.append(
        element("strong", "", [item.role || item.name, item.company].filter(Boolean).join(" · ")),
        element("p", "", item.description)
      );
      const url = safeLink(item.url, item.url);
      if (url) entry.append(url);
      group.append(entry);
    }
  }

  for (const [key, title] of [["education", "تحصیلات"], ["languages", "زبان‌ها"]]) {
    if (profile[key]?.length) section(title).append(element("p", "", printableItems(profile[key])));
  }

  for (const note of content.notes || []) doc.append(element("p", "resume-note", note));
  box.append(doc);

  // Refine Feedback Form
  const form = element("form", "resume-feedback");
  form.id = "refine-form";
  const label = element("label", "", "بازخورد و اصلاح رزومه (چه مهارت‌ها یا پروژه‌هایی اولویت یابند؟)");
  
  // Quick Feedback Chips
  const quickChips = element("div", "quick-feedback-chips");
  const chipSuggestions = [
    "دورکاری می‌خواهم",
    "این آگهی را نمی‌خواهم",
    "پروژه‌ها قبل از سوابق قرار گیرند",
    "مهارت‌های فرانت‌اند پررنگ‌تر شوند"
  ];
  for (const text of chipSuggestions) {
    const chipBtn = element("button", "chip chip-action", text);
    chipBtn.type = "button";
    chipBtn.addEventListener("click", () => {
      const current = form.elements.feedback.value.trim();
      form.elements.feedback.value = current ? `${current}؛ ${text}` : text;
      form.elements.feedback.focus();
    });
    quickChips.append(chipBtn);
  }

  const feedback = element("textarea");
  feedback.name = "feedback";
  feedback.rows = 3;
  feedback.required = true;
  feedback.maxLength = 3000;
  feedback.placeholder = "مثلاً: پروژه مرتبط فرانت‌اند در ابتدای رزومه قرار گیرد یا ترتیب مهارت‌ها تغییر کند…";
  
  label.append(quickChips, feedback);

  // Single primary CTA button for resume refinement
  const button = element("button", "button primary", "اصلاح رزومه");
  button.type = "submit";
  button.setAttribute("data-ai", "");
  button.disabled = !state.configured;

  form.append(
    label,
    button,
    element("p", "cost-note", "اصلاح ترتیب و انتخاب مهارت‌ها و پروژه‌ها یک درخواست مصرف می‌کند. برای تغییر خلاصه یا سوابق، بخش اطلاعات من را ویرایش و تأیید کنید.")
  );
  box.append(form);
}

function rememberResume(resume) {
  state.resumes = [resume, ...state.resumes.filter((item) => item.id !== resume.id)];
  renderResume(resume);
  showView("resumes");
}

async function createResume(button, payload) {
  if (!state.profile.confirmed) {
    showView("profile");
    notify("پیش از ساخت رزومه، اطلاعات پرونده را بررسی و تأیید کنید.");
    return;
  }
  await pending(button, "در حال آماده‌سازی…", async () => {
    const data = await api("/api/resumes", { method: "POST", body: payload });
    renderUsage(data.usage);
    rememberResume(data.resume);
    notify("رزومه اختصاصی آماده شد. لطفاً متن را بررسی کنید.");
  });
}

async function loadAccount() {
  const data = await api("/api/me");
  Object.assign(state, {
    user: data.user,
    profile: data.profile || {},
    messages: data.messages || [],
    resumes: data.resumes || [],
    usage: data.usage || {},
    configured: Boolean(data.configured)
  });
  state.jobs = data.search?.jobs || [];
  state.search = data.search?.sources?.length ? data.search : null;
  state.matches = [];
  state.selectedResume = null;
  
  $("#account-name").textContent = state.user.name;
  $("#auth-view").hidden = true;
  $("#boot").hidden = true;
  $("#workspace").hidden = false;

  renderConfiguration();
  renderDossier();
  renderMessages();
  renderResumeList();
  renderUsage();

  if (data.search) {
    renderJobs();
    renderSources(data.search.sources);
  } else {
    $("#job-results").replaceChildren(emptyState("فرصت‌های شغلی را جست‌وجو کنید.", "عنوان شغل یا یک مهارت را بنویسید و منابع مورد نظر را انتخاب کنید."));
    $("#job-toolbar").hidden = true;
    $("#source-status").replaceChildren();
  }

  if (state.resumes.length) {
    renderResume(state.resumes[0]);
  } else {
    $("#resume-preview").replaceChildren(emptyState("اولین رزومه هنوز ساخته نشده است.", "پرونده را تأیید کنید، سپس در بخش فرصت‌های شغلی یک آگهی انتخاب کنید.", "دیدن فرصت‌های شغلی", "jobs"));
  }

  showView("interview", false);
}

// Event Listeners
$("#login-tab").addEventListener("click", () => setAuthMode("login"));
$("#register-tab").addEventListener("click", () => setAuthMode("register"));

$("#auth-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (authBusy) return;
  authBusy = true;
  changeSession();
  const button = $("#auth-submit");
  const original = button.textContent;
  button.disabled = true;
  button.textContent = "در حال ورود…";
  $("#auth-error").hidden = true;
  try {
    const body = { email: $("#auth-email").value.trim(), password: $("#auth-password").value };
    if (state.authMode === "register") body.name = $("#auth-name").value.trim();
    await api(`/api/auth/${state.authMode}`, { method: "POST", body });
    await loadAccount();
    $("#auth-password").value = "";
  } catch (error) {
    if (error.name !== "SessionChanged") {
      $("#auth-error").textContent = error.message;
      $("#auth-error").hidden = false;
    }
  } finally {
    authBusy = false;
    button.disabled = false;
    button.textContent = original;
  }
});

$("#logout").addEventListener("click", async () => {
  if (authBusy) return;
  authBusy = true;
  changeSession();
  try {
    await pending($("#logout"), "در حال خروج…", async () => {
      await api("/api/auth/logout", { method: "POST" });
      showAuth();
    });
  } finally {
    authBusy = false;
  }
});

document.addEventListener("click", async (event) => {
  const add = event.target.closest("[data-add-entry]");
  if (add) addProfileEntry(add.dataset.addEntry);

  const remove = event.target.closest("[data-remove-entry]");
  if (remove) remove.closest("[data-profile-entry]").remove();

  if (event.target.closest("#start-chat")) $("#chat-input").focus();

  const navigation = event.target.closest("[data-view], [data-go]");
  if (navigation) showView(navigation.dataset.view || navigation.dataset.go);

  const jobButton = event.target.closest("[data-resume-job]");
  if (jobButton) await createResume(jobButton, { job: state.jobs[Number(jobButton.dataset.resumeJob)] });

  const resumeButton = event.target.closest("[data-open-resume]");
  if (resumeButton) await pending(resumeButton, "در حال باز کردن…", async () => {
    const data = await api(`/api/resumes/${encodeURIComponent(resumeButton.dataset.openResume)}`);
    renderResume(data.resume);
  });
});

$("#chat-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const input = $("#chat-input");
  const message = input.value.trim();
  if (!message || !state.configured) return;
  const version = sessionVersion;
  $("#chat-empty")?.remove();

  const userRow = appendMessage({ role: "user", content: message });
  userRow.classList.add("pending");
  input.disabled = true;

  // Thinking indicator row
  const thinkingRow = element("div", "message assistant pending");
  const thinkingBody = element("div", "message-body");
  thinkingBody.innerHTML = 'ایجنت در حال تحلیل پرونده شغلی است <span class="thinking-dots" aria-hidden="true"><span></span><span></span><span></span></span>';
  thinkingRow.append(element("div", "message-label", "دستیار کاریابی"), thinkingBody);
  $("#messages").append(thinkingRow);
  $("#messages").scrollTop = $("#messages").scrollHeight;

  $("#chat-status").textContent = "در حال دریافت پاسخ…";
  await pending($("#chat-submit"), "در حال ارسال…", async () => {
    const data = await api("/api/chat", { method: "POST", body: { message } });
    userRow.classList.remove("pending");
    thinkingRow.remove();
    state.messages.push({ role: "user", content: message }, { role: "assistant", content: data.reply });
    input.value = "";
    if (data.profile) { state.profile = data.profile; renderDossier(); }
    if (data.jobs) {
      state.jobs = data.jobs;
      state.search = data.search || { jobs: data.jobs, sources: data.source_status };
      state.matches = [];
      renderJobs();
      renderSources(data.source_status);
    }
    renderMessages();
    if (data.resume) rememberResume(data.resume);
    renderUsage(data.usage);
  });

  if (version !== sessionVersion) return;
  thinkingRow.remove();
  if (userRow.classList.contains("pending")) userRow.remove();
  input.disabled = false;
  $("#chat-status").textContent = "پاسخ‌ها ذخیره می‌شوند.";
  input.focus();
});

$("#profile-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  await pending($("#profile-submit"), "در حال ذخیره…", async () => {
    const data = await api("/api/profile", { method: "PUT", body: profileFromForm() });
    state.profile = data.profile;
    renderDossier();
    renderChatActions();
    notify("اطلاعات پرونده ذخیره و تأیید شد.");
  });
});

$("#search-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const sources = [...document.querySelectorAll("#source-filters input:checked")].map((input) => input.value);
  if (!sources.length) {
    notify("حداقل یک منبع را برای جست‌وجو انتخاب کنید.", true);
    return;
  }
  await pending($("#search-submit"), "در حال جست‌وجو…", async () => {
    const data = await api("/api/jobs/search", {
      method: "POST",
      body: {
        query: $("#job-query").value.trim(),
        city: $("#job-city").value.trim(),
        remote: $("#job-remote").checked,
        sources
      }
    });
    state.jobs = data.jobs || [];
    state.search = data;
    state.matches = [];
    renderSources(data.sources);
    renderJobs();
    renderChatActions();
  });
});

$("#match-jobs").addEventListener("click", () => pending($("#match-jobs"), "در حال مقایسه…", async () => {
  const data = await api("/api/jobs/match", {
    method: "POST",
    body: { jobs: state.jobs.slice(0, 12) }
  });
  state.matches = data.matches || [];
  renderUsage(data.usage);
  renderJobs();
  notify("ارزیابی تناسب به آگهی‌ها اضافه شد.");
}));

$("#paste-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = $("#job-text").value.trim();
  if (text) await createResume(event.target.querySelector("button"), { job_text: text });
});

$("#resume-preview").addEventListener("submit", async (event) => {
  if (event.target.id !== "refine-form") return;
  event.preventDefault();
  const form = event.target;
  await pending(form.querySelector("button"), "در حال اصلاح…", async () => {
    const data = await api(`/api/resumes/${encodeURIComponent(state.selectedResume.id)}/refine`, {
      method: "POST",
      body: { feedback: form.elements.feedback.value.trim() }
    });
    renderUsage(data.usage);
    rememberResume(data.resume);
    notify("رزومه اصلاح و ذخیره شد.");
  });
});

async function boot() {
  try {
    const config = await api("/api/config");
    state.configured = Boolean(config.configured);
    state.sources = config.sources || [];
    await loadAccount();
  } catch (error) {
    if (error.name === "SessionChanged") return;
    showAuth();
    if (error.status !== 401) notify(error.message, true);
  }
}

boot();

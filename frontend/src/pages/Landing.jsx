import { Link } from 'react-router-dom'
import { Brand } from '../ui'
import { getToken } from '../api'

const questions = [
  ['برای شروع باید رزومه داشته باشم؟', 'نه، می‌توانی با گفت‌وگو دربارهٔ نقش و مهارت‌هایت شروع کنی یا رزومهٔ موجودت را وارد کنی و بعد اطلاعات را مرور و تکمیل کنی.'],
  ['آگهی‌ها از کجا می‌آیند؟', 'HireLoop منابع کاریابی از جمله جابینجا، جاب‌ویژن، کوئرا، ایران‌تلنت و کاربوم را بررسی می‌کند. تعداد نتایج به وضعیت هر منبع و معیارهای جست‌وجوی تو بستگی دارد.'],
  ['رزومه چطور ساخته می‌شود؟', 'رزومه بر پایهٔ اطلاعات پروفایل و پاسخ‌های خودت برای آگهی انتخابی ساخته می‌شود. می‌توانی آن را ویرایش کنی و پیش از ارسال، نسخهٔ نهایی را بررسی کنی.'],
  ['HireLoop به جای من درخواست ارسال می‌کند؟', 'خیر. تو آگهی اصلی را بررسی و خودت اقدام می‌کنی؛ سپس می‌توانی وضعیت، یادداشت و نسخهٔ رزومه را در رهگیر ثبت کنی.'],
  ['تمرین مصاحبه چگونه است؟', 'برای یک فرصت شغلی، سؤال‌های فنی و رفتاری متناسب با آگهی و پروفایلت ساخته می‌شوند. پس از پاسخ دادن، بازخورد و پاسخ نمونه را می‌بینی.'],
]

export default function Landing() {
  const signedIn = Boolean(getToken())
  const home = signedIn ? '/app/interview' : '/auth'
  return (
    <>
      <nav className="l-nav" aria-label="ناوبری صفحهٔ اصلی">
        <Brand />
        <div className="l-nav-links"><a href="#how">چطور کار می‌کند؟</a><a href="#features">امکانات</a><a href="#faq">سوالات متداول</a></div>
        <Link to={home} className="btn btn-ghost">{signedIn ? 'ورود به برنامه' : 'ورود / ثبت‌نام'}</Link>
      </nav>
      <main>
        <section className="hero">
          <div>
            <h1>همراه کاریابی تخصصی برنامه‌نویسان، <span className="hero-highlight">در تمامی استک‌ها</span></h1>
            <p className="lead">از فرانت‌اند و بک‌اند تا فول‌استک، هوش مصنوعی، موبایل و دوآپس؛ استک فنی‌ات را بگو تا HireLoop فرصت‌های شغلی را با تجربه‌ات بررسی کند و به ساخت رزومهٔ اختصاصی کمک کند.</p>
            <div className="cta"><Link to={home} className="btn btn-primary btn-lg">{signedIn ? 'ادامه مسیر' : 'شروع کن'}</Link><a href="#how" className="btn btn-ghost btn-lg">ببین چطور کار می‌کند</a></div>
          </div>
          <div className="stack" aria-hidden="true">
            <div className="s-chat"><div className="bubble-a">در چه استک و حوزه‌ای از برنامه‌نویسی فعالیت می‌کنی؟</div><div className="bubble-u">بک‌اند پایتون و جنگو، با داکر و پستگرس کار کرده‌ام و دنبال پوزیشن میدلول هستم.</div></div>
            <div className="s-fit"><strong>بررسی تناسب شغلی</strong><p>انطباق استک فنی، زبان‌ها و فریم‌ورک‌های تو در کنار نیازمندی‌های آگهی.</p><small>با سنجش نقاط قوت فنی و تکنولوژی‌هایی که نیاز به ارتقا دارند.</small></div>
            <div className="s-doc"><strong>رزومه برای این آگهی</strong><i style={{ width: '90%' }} /><i style={{ width: '70%' }} /><i style={{ width: '80%' }} /></div>
          </div>
        </section>
        <section className="how" id="how"><div className="how-in"><h2>از سابقهٔ تو تا پیگیری درخواست</h2><p className="landing-section-lead">یک مسیر روشن برای هر قدم کاریابی؛ از شناخت مهارت‌هایت تا آماده شدن برای مصاحبه.</p><ol>
          <li><h3>پروفایل شغلی</h3><p>رزومهٔ موجودت را وارد کن یا دربارهٔ مهارت‌ها و پروژه‌هایت بگو.</p></li>
          <li><h3>آگهی‌های متناسب</h3><p>آگهی‌ها را پیدا کن و شرط‌های ضروری و ترجیحی‌شان را بررسی کن.</p></li>
          <li><h3>رزومهٔ اختصاصی</h3><p>برای هر آگهی بر پایهٔ مهارت‌ها و پروژه‌های واقعی‌ات رزومه بساز.</p></li>
          <li><h3>تمرین مصاحبه</h3><p>به سؤال‌های مربوط به همان شغل پاسخ بده و بازخورد بگیر.</p></li>
          <li><h3>پیگیری درخواست‌ها</h3><p>وضعیت اقدام و نسخهٔ رزومهٔ ارسال‌شده را نگه دار.</p></li>
        </ol></div></section>
        <section className="landing-features" id="features">
          <div className="landing-section-heading"><span className="landing-eyebrow">همه‌چیز کنار هم</span><h2>برای هر مرحله، یک همراه داری</h2><p>کمتر بین ابزارها و آگهی‌ها گم شو و با تمرکز بیشتری برای فرصت بعدی‌ات آماده شو.</p></div>
          <div className="landing-feature-row"><div className="landing-feature-copy"><span className="landing-feature-number">۰۱</span><h3>فرصت‌ها را با شناخت بیشتری ببین</h3><p>بعد از ساخت پروفایل، آگهی‌ها با نقش و مهارت‌های تو بررسی می‌شوند. نیازمندی‌های هر فرصت و مهارت‌های مرتبط را کنار هم ببین و خودت تصمیم بگیر کجا اقدام کنی.</p><div className="landing-pills"><span>جست‌وجوی آگهی</span><span>بررسی تناسب</span><span>لینک آگهی اصلی</span></div></div><div className="landing-feature-demo demo-job" aria-label="نمونهٔ نمایشی بررسی آگهی"><div className="demo-caption"><span>یک فرصت شغلی</span><span>نمونهٔ نمایشی</span></div><h4>توسعه‌دهندهٔ بک‌اند Python</h4><p>مهارت‌های مرتبط با پروفایل تو</p><div className="landing-pills"><span>Python</span><span>Django</span><span>PostgreSQL</span></div><div className="demo-note"><span>✓</span> جزئیات آگهی را پیش از اقدام بررسی کن.</div></div></div>
          <div className="landing-feature-row reverse"><div className="landing-feature-copy"><span className="landing-feature-number">۰۲</span><h3>رزومه‌ای برای همان فرصت</h3><p>از تجربه‌ها و پروژه‌های واقعی‌ات شروع کن. برای هر آگهی رزومهٔ فارسی یا انگلیسی بساز، ویرایشش کن و از پنجرهٔ چاپ خروجی PDF بگیر.</p><div className="landing-pills"><span>فارسی و انگلیسی</span><span>قابل ویرایش</span><span>خروجی PDF</span></div></div><div className="landing-feature-demo demo-resume" aria-label="نمونهٔ نمایشی رزومه"><div className="demo-caption"><span>رزومهٔ اختصاصی</span><span>نمونهٔ نمایشی</span></div><h4>تجربه‌های مرتبط تو</h4><div className="demo-resume-item"><strong>مهارت‌ها</strong><p>تکنولوژی‌هایی که برای این موقعیت مهم‌اند.</p></div><div className="demo-resume-item"><strong>پروژه‌ها و سابقه</strong><p>تجربه‌های واقعی تو، آمادهٔ مرور و ویرایش.</p></div></div></div>
          <div className="landing-feature-row"><div className="landing-feature-copy"><span className="landing-feature-number">۰۳</span><h3>با آمادگی بیشتری وارد مصاحبه شو</h3><p>سؤال‌های فنی و رفتاری متناسب با آگهی و پروفایلت را تمرین کن. پاسخ بده، بازخورد بگیر و پیش از گفت‌وگوی واقعی برای بهتر شدن وقت بگذار.</p><div className="landing-pills"><span>سؤال‌های مرتبط</span><span>بازخورد</span><span>پاسخ نمونه</span></div></div><div className="landing-feature-demo demo-practice" aria-label="نمونهٔ نمایشی تمرین مصاحبه"><div className="demo-caption"><span>تمرین مصاحبه</span><span>نمونهٔ نمایشی</span></div><div className="demo-question">در یک پروژهٔ واقعی، چطور عملکرد یک API را بهتر کرده‌ای؟</div><div className="demo-answer">پاسخ تو، شروع یک تمرین است.</div></div></div>
          <div className="landing-feature-row reverse"><div className="landing-feature-copy"><span className="landing-feature-number">۰۴</span><h3>درخواست‌ها را از یاد نبر</h3><p>وضعیت هر درخواست را خودت ثبت کن، یادداشت بگذار و نسخهٔ رزومه‌ای را که فرستاده‌ای نگه دار. مسیر هر فرصت، همیشه در دسترس توست.</p><div className="landing-pills"><span>وضعیت درخواست</span><span>یادداشت شخصی</span><span>نسخهٔ رزومه</span></div></div><div className="landing-feature-demo demo-tracker" aria-label="نمونهٔ نمایشی رهگیر درخواست"><div className="demo-caption"><span>رهگیر درخواست‌ها</span><span>نمونهٔ نمایشی</span></div><h4>توسعه‌دهندهٔ بک‌اند</h4><div className="tracker-line"><span>وضعیت</span><strong>ارسال‌شده</strong></div><div className="tracker-line"><span>رزومه</span><strong>نسخهٔ ثبت‌شده</strong></div><div className="demo-note"><span>✓</span> همهٔ جزئیات یک فرصت در یک جا</div></div></div>
        </section>
        <section className="landing-faq" id="faq"><div className="landing-faq-in"><div><span className="landing-eyebrow">قبل از شروع</span><h2>سوالی داری؟</h2><p>چند نکته برای اینکه با خیال راحت‌تری مسیرت را شروع کنی.</p></div><div className="landing-faq-list">{questions.map(([question, answer]) => <details key={question}><summary>{question}<span aria-hidden="true">+</span></summary><p>{answer}</p></details>)}</div></div></section>
        <section className="landing-end"><div><span className="landing-eyebrow">قدم بعدی منتظر توست</span><h2>آماده‌ای مسیرت رو شروع کنی؟</h2><p>تجربه‌هایت را بگو و فرصت‌های شغلی را با شناخت بیشتری بررسی کن.</p><Link to={home} className="btn btn-primary btn-lg">{signedIn ? 'ورود به برنامه' : 'شروع با HireLoop'}</Link></div></section>
      </main>
      <footer className="l-foot"><Brand /><p>همراه هوشمند کاریابی و رزومه‌نویسی برنامه‌نویسان در تمام استک‌ها</p><div><a href="#how">مسیر کاریابی</a><a href="#features">امکانات</a><a href="#faq">سوالات متداول</a></div></footer>
    </>
  )
}

import { Link } from 'react-router-dom'
import { Brand } from '../ui'
import { getToken } from '../api'

export default function Landing() {
  const home = getToken() ? '/app/interview' : '/auth'
  return (
    <>
      <nav className="l-nav">
        <Brand />
        <Link to={home} className="btn btn-ghost">{getToken() ? 'ورود به برنامه' : 'ورود / ثبت‌نام'}</Link>
      </nav>
      <section className="hero">
        <div>
          <h1>همراه کاریابی تخصصی برنامه‌نویسان، <span className="hero-highlight">در تمامی استک‌ها</span></h1>
          <p className="lead">
            از فرانت‌اند و بک‌اند تا فول‌استک، هوش مصنوعی، موبایل و دوآپس؛ استک فنی‌ات را بگو تا HireLoop آگهی‌های متناسب را از معتبرترین پلتفرم‌های کاریابی استخراج کند و رزومه اختصاصی بسازد.
          </p>
          <div className="cta">
            <Link to={home} className="btn btn-primary btn-lg">شروع کن</Link>
          </div>
        </div>
        <div className="stack" aria-hidden="true">
          <div className="s-chat">
            <div className="bubble-a">در چه استک و حوزه‌ای از برنامه‌نویسی فعالیت می‌کنی؟</div>
            <div className="bubble-u">بک‌اند پایتون و جنگو، با داکر و پستگرس کار کرده‌ام و دنبال پوزیشن میدلول هستم.</div>
          </div>
          <div className="s-fit">
            <strong>بررسی تناسب شغلی</strong>
            <p>انطباق استک فنی، زبان‌ها و فریم‌ورک‌های تو در کنار نیازمندی‌های آگهی.</p>
            <small>با سنجش نقاط قوت فنی و تکنولوژی‌هایی که نیاز به ارتقا دارند.</small>
          </div>
          <div className="s-doc">
            <strong>رزومه برای این آگهی</strong>
            <i style={{ width: '90%' }} /><i style={{ width: '70%' }} /><i style={{ width: '80%' }} />
          </div>
        </div>
      </section>
      <section className="how">
        <div className="how-in">
          <h2>چهار قدم تا درخواست آماده</h2>
          <ol>
            <li><h3>مصاحبهٔ فنی</h3><p>گفتگوی هوشمند فارسی بر اساس استک تخصصی و سابقه برنامه‌نویسی‌ات.</p></li>
            <li><h3>آگهی‌های متناسب</h3><p>جست‌وجوی خودکار منابع کاریابی با ارزیابی دلایل تناسب استک و خلاءها.</p></li>
            <li><h3>رزومهٔ اختصاصی</h3><p>تولید رزومه متناسب با آگهی بر پایه مهارت‌ها و پروژه‌های واقعی‌ات.</p></li>
            <li><h3>بهبود</h3><p>اصلاح استک، تغییر ترجیحات یا تنظیم رزومه با یک پیام متنی.</p></li>
          </ol>
        </div>
      </section>
      <footer className="l-foot">HireLoop · همراه هوشمند کاریابی و رزومه‌نویسی برنامه‌نویسان در تمام استک‌ها</footer>
    </>
  )
}

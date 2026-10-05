import { Link } from 'react-router-dom'
import { Brand } from '../ui'
import { getToken } from '../api'

export default function Landing() {
  const home = getToken() ? '/app/interview' : '/auth'
  return (
    <>
      <nav className="l-nav">
        <Brand />
        <Link to="/auth" className="btn btn-ghost">{getToken() ? 'ورود به برنامه' : 'ورود / ثبت‌نام'}</Link>
      </nav>
      <section className="hero">
        <div>
          <h1>از یک گفتگو تا <span className="hero-highlight">رزومه‌ای که دقیقاً به آگهی می‌خورد</span></h1>
          <p className="lead">
            HireLoop با چند سؤال تو را می‌شناسد، آگهی‌های مناسب کارآموز و جونیور فرانت‌اند را با دلیل پیشنهاد می‌دهد
            و برای هر آگهی یک رزومهٔ اختصاصی می‌سازد. هر چه بگویی را هم همان‌جا اصلاح می‌کند.
          </p>
          <div className="cta">
            <Link to={home} className="btn btn-primary btn-lg">شروع کن</Link>
          </div>
        </div>
        <div className="stack" aria-hidden="true">
          <div className="s-chat">
            <div className="bubble-a">بیشتر با چه ابزارهایی کار کرده‌ای؟</div>
            <div className="bubble-u">React و کمی TypeScript. یک پروژهٔ فروشگاهی هم دارم.</div>
          </div>
          <div className="s-fit">
            <strong>توسعه‌دهندهٔ جونیور React</strong>
            <div className="meter meter-hi" style={{ margin: '.6rem 0' }}>
              <div className="meter-bar"><span style={{ width: '86%' }} /></div><strong>۸۶٪</strong>
            </div>
            <small>پروژهٔ فروشگاهی‌ات با نیاز تیم هم‌خوان است؛ تست‌نویسی کم است.</small>
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
            <li><h3>مصاحبه</h3><p>یک گفتگوی کوتاه فارسی دربارهٔ سوابق و ترجیحاتت.</p></li>
            <li><h3>آگهی‌های مناسب</h3><p>فقط آگهی‌هایی که می‌خورند، همراه علت تناسب و کمبودها.</p></li>
            <li><h3>رزومهٔ اختصاصی</h3><p>فارسی یا انگلیسی، فقط با اطلاعات واقعی خودت.</p></li>
            <li><h3>بهبود</h3><p>بگو چه چیزی عوض شود تا جست‌وجو و رزومه اصلاح شوند.</p></li>
          </ol>
        </div>
      </section>
      <footer className="l-foot">HireLoop · ساخته‌شده برای مسابقهٔ buildX</footer>
    </>
  )
}

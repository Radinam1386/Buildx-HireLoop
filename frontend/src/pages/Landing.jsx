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
          <h1>شغل بعدی‌ات را پیدا کن، <span className="hero-highlight">رزومه‌ات را برایش آماده کن</span></h1>
          <p className="lead">
            از تجربه‌ها و شغلی که می‌خواهی بگو. HireLoop در سایت‌های کاریابی جست‌وجو می‌کند،
            دلیل تناسب و کمبودهای هر گزینه را نشان می‌دهد و با اطلاعات واقعی خودت رزومه می‌سازد.
          </p>
          <div className="cta">
            <Link to={home} className="btn btn-primary btn-lg">شروع کن</Link>
          </div>
        </div>
        <div className="stack" aria-hidden="true">
          <div className="s-chat">
            <div className="bubble-a">دنبال چه شغلی هستی و چه تجربه‌ای داری؟</div>
            <div className="bubble-u">کارشناس فروش. سه سال با مشتری‌ها و تیم فروش کار کرده‌ام.</div>
          </div>
          <div className="s-fit">
            <strong>بررسی تناسب شغلی</strong>
            <p>سابقه، مهارت‌ها و شرایط کاری تو در کنار نیازهای آگهی.</p>
            <small>با توضیح دلیل انتخاب و شرایطی که باید بررسی کنی.</small>
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
            <li><h3>آگهی‌های مناسب</h3><p>جست‌وجوی منابع کاریابی، همراه علت تناسب و کمبودها.</p></li>
            <li><h3>رزومهٔ اختصاصی</h3><p>فارسی یا انگلیسی، فقط با اطلاعات واقعی خودت.</p></li>
            <li><h3>بهبود</h3><p>بگو چه چیزی عوض شود تا جست‌وجو و رزومه اصلاح شوند.</p></li>
          </ol>
        </div>
      </section>
      <footer className="l-foot">HireLoop · جست‌وجوی شغل و رزومه بر اساس تجربه‌های واقعی تو</footer>
    </>
  )
}

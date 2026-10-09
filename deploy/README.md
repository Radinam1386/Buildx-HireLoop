# استقرار HireLoop

نشانی محصول: https://78.157.54.151/

فرانت React با Nginx و بک‌اند FastAPI با systemd اجرا می‌شود. Nginx درخواست‌های IP را به HireLoop و درخواست‌های `mentoralearn.ir` را به منتورا می‌رساند. بک‌اند HireLoop فقط روی `127.0.0.1:8001` گوش می‌دهد.

| بخش | مسیر یا سرویس |
|---|---|
| نسخهٔ فعال | `/var/www/hireloop/current` |
| نسخه‌های انتشار | `/var/www/hireloop/releases/` |
| تنظیمات و کلید مدل | `/etc/hireloop/hireloop.env` |
| دیتابیس | `/var/lib/hireloop/hireloop.db` |
| پشتیبان‌های دیتابیس | `/var/backups/hireloop/` |
| پشتیبان تنظیمات اولیهٔ Nginx | `/var/backups/hireloop-server/` |
| بک‌اند | `hireloop.service` |
| تمدید گواهی IP | `hireloop-certbot.timer` |

## انتشار خودکار

با push به `main` یا اجرای دستی workflow، GitHub Actions تست‌های بک‌اند را بدون مدل اجرا می‌کند و فرانت را با `npm ci` می‌سازد. سپس فقط کد بک‌اند، requirements و خروجی فرانت بسته‌بندی می‌شوند. فایل محیطی و دیتابیس در بستهٔ انتشار نیستند.

دو Secret در مخزن تنظیم می‌شوند:

- `HIRELOOP_SSH_KEY`: کلید خصوصی مخصوص انتشار.
- `HIRELOOP_KNOWN_HOSTS`: کلید عمومی تأییدشدهٔ SSH سرور.

کلید انتشار با حساب `hireloop-deploy` و فرمان اجباری `/usr/local/bin/hireloop-release` کار می‌کند. فرمان مجاز `deploy <commit-sha>` است؛ این کلید شِل، TTY یا انتقال پورت باز نمی‌کند. مجوز sudo این حساب به restart و stop سرویس HireLoop محدود است.

هر انتشار در پوشه و محیط Python جدا نصب می‌شود. قبل از فعال‌سازی، پشتیبان SQLite ساخته و با `PRAGMA quick_check` بررسی می‌شود. پس از تعویض اتمی لینک نسخه، سرویس راه‌اندازی و `/api/health` بررسی می‌شود. اگر راه‌اندازی موفق نباشد، لینک نسخه و سرویس به انتشار قبلی برمی‌گردند. بازگشت نسخه، دیتابیس را به عقب برنمی‌گرداند.

## راه‌اندازی اولیه روی این سرور

Python 3.12، venv، Nginx، sudo، curl و systemd باید نصب باشند. مدیر سرور فایل `/etc/hireloop/hireloop.env` را با کلید مدل، `JWT_SECRET` تصادفی، `DATABASE_URL=sqlite:////var/lib/hireloop/hireloop.db` و `CORS_ORIGINS=https://78.157.54.151` ایجاد می‌کند. سپس فایل‌های پوشهٔ `deploy` و کلید عمومی انتشار به سرور منتقل می‌شوند:

```bash
bash deploy/setup.sh /path/to/hireloop_actions.pub
```

اسکریپت از تنظیمات فعلی منتورا پشتیبان می‌گیرد، فقط IP را از مسیر HTTP منتورا جدا می‌کند و حساب‌ها و سرویس‌های HireLoop را نصب می‌کند. تنظیمات Nginx پیش از reload بررسی می‌شوند. فایل محیطی بیرون از پوشهٔ انتشار باقی می‌ماند.

گواهی IP با Certbot 5.4 یا جدیدتر، webroot و پروفایل `shortlived` صادر می‌شود. نصب Certbot، فایل‌های گواهی و تایمر تمدید HireLoop از Certbot منتورا جدا هستند. تایمر روزی دو بار تمدید را بررسی می‌کند. [راهنمای رسمی گواهی IP](https://letsencrypt.org/2026/03/11/shorter-certs-certbot)

## بررسی و نگهداری

```bash
systemctl status hireloop --no-pager
journalctl -u hireloop -n 80 --no-pager
curl --fail https://78.157.54.151/api/health
systemctl list-timers hireloop-certbot.timer
python3 deploy/check.py release.tgz
```

برای آزمون تمدید بدون تغییر گواهی فعال:

```bash
/opt/hireloop-certbot/bin/certbot renew --dry-run --no-random-sleep-on-renew --run-deploy-hooks \
  --config-dir /etc/hireloop/letsencrypt --work-dir /var/lib/hireloop-certbot --logs-dir /var/log/hireloop-certbot
```

تغییر کلید یا مدل در فایل سرور با `systemctl restart hireloop` اعمال می‌شود. تغییر اسکریپت نصب، واحد systemd یا تنظیمات Nginx را مدیر سرور با اجرای دوبارهٔ setup اعمال می‌کند؛ انتشار معمول برنامه به این فایل‌های مدیریتی دسترسی نوشتن ندارد. نسخه‌ها و پشتیبان‌های قبلی برای بازگشت حفظ می‌شوند و مدیر سرور با بررسی فضای دیسک نسخه‌های قدیمی را پاک می‌کند.

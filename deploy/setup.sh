#!/usr/bin/env bash
# Run once as root: bash deploy/setup.sh /path/to/hireloop_actions.pub
set -Eeuo pipefail
umask 0077
test "$(id -u)" -eq 0
test -s /etc/hireloop/hireloop.env
test -s "${1:?Actions public key required}"
ssh-keygen -lf "$1" >/dev/null
here=$(cd -- "$(dirname -- "$0")" && pwd)

id hireloop >/dev/null 2>&1 || useradd --system --user-group --home-dir /var/lib/hireloop --shell /usr/sbin/nologin hireloop
id hireloop-deploy >/dev/null 2>&1 || useradd --system --user-group --create-home --home-dir /var/lib/hireloop-deploy --shell /bin/bash hireloop-deploy
usermod -aG hireloop hireloop-deploy
install -d -o hireloop -g hireloop -m 2770 /var/lib/hireloop
install -d -o hireloop-deploy -g hireloop -m 0755 /var/www/hireloop /var/www/hireloop/releases
install -d -o hireloop-deploy -g hireloop -m 0700 /var/backups/hireloop
install -d -m 0700 /var/backups/hireloop-server
install -d -m 0755 /var/lib/hireloop-acme
install -d -m 0700 /var/lib/hireloop-certbot
chown root:hireloop /etc/hireloop /etc/hireloop/hireloop.env
chmod 0750 /etc/hireloop
chmod 0640 /etc/hireloop/hireloop.env
install -d -o root -g hireloop-deploy -m 0750 /var/lib/hireloop-deploy/.ssh
printf 'restrict,command="/usr/local/bin/hireloop-release" %s\n' "$(cat "$1")" > /var/lib/hireloop-deploy/.ssh/authorized_keys
chown root:hireloop-deploy /var/lib/hireloop-deploy/.ssh/authorized_keys
chmod 0640 /var/lib/hireloop-deploy/.ssh/authorized_keys
install -m 0755 "$here/release.sh" /usr/local/bin/hireloop-release
printf '%s\n' 'hireloop-deploy ALL=(root) NOPASSWD: /usr/bin/systemctl restart hireloop.service, /usr/bin/systemctl stop hireloop.service' > /etc/sudoers.d/hireloop
chmod 0440 /etc/sudoers.d/hireloop
visudo -cf /etc/sudoers.d/hireloop
install -m 0644 "$here/hireloop.service" /etc/systemd/system/hireloop.service
install -m 0644 "$here/hireloop-certbot.service" "$here/hireloop-certbot.timer" /etc/systemd/system/

if [[ ! -x /opt/hireloop-certbot/bin/certbot ]]; then
    python3 -m venv /opt/hireloop-certbot
    /opt/hireloop-certbot/bin/pip install --disable-pip-version-check 'certbot>=5.4'
fi

mentora=/etc/nginx/sites-available/mentoralearn.ir
backup="/var/backups/hireloop-server/mentora-nginx-$(date -u +%Y%m%dT%H%M%S).conf"
cp -p "$mentora" "$backup"
python3 - "$mentora" <<'PY'
import pathlib, sys
path = pathlib.Path(sys.argv[1])
text = path.read_text()
before = 'server_name mentoralearn.ir www.mentoralearn.ir 78.157.54.151;'
after = 'server_name mentoralearn.ir www.mentoralearn.ir;'
assert text.count(before) == 1 or (before not in text and after in text), 'Review existing Nginx IP routing before installing'
path.write_text(text.replace(before, after))
PY
if [[ ! -s /etc/hireloop/letsencrypt/live/78.157.54.151/fullchain.pem ]]; then
    sed -n '1,/^}/p' "$here/nginx.conf" > /etc/nginx/sites-available/hireloop
else
    install -m 0644 "$here/nginx.conf" /etc/nginx/sites-available/hireloop
fi
chmod 0644 /etc/nginx/sites-available/hireloop
ln -sfn /etc/nginx/sites-available/hireloop /etc/nginx/sites-enabled/hireloop
if ! nginx -t; then
    cp -p "$backup" "$mentora"
    unlink /etc/nginx/sites-enabled/hireloop
    exit 1
fi
systemctl reload nginx

if [[ ! -s /etc/hireloop/letsencrypt/live/78.157.54.151/fullchain.pem ]]; then
    /opt/hireloop-certbot/bin/certbot certonly --non-interactive --agree-tos --register-unsafely-without-email \
        --preferred-profile shortlived --webroot --webroot-path /var/lib/hireloop-acme --ip-address 78.157.54.151 \
        --config-dir /etc/hireloop/letsencrypt --work-dir /var/lib/hireloop-certbot --logs-dir /var/log/hireloop-certbot \
        --deploy-hook '/usr/sbin/nginx -t && /usr/bin/systemctl reload nginx'
fi
install -m 0644 "$here/nginx.conf" /etc/nginx/sites-available/hireloop
nginx -t
systemctl reload nginx
systemctl daemon-reload
systemctl enable hireloop.service
systemctl enable --now hireloop-certbot.timer
echo 'HireLoop server configured; upload the first release next.'

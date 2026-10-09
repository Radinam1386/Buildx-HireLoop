#!/usr/bin/env bash
set -Eeuo pipefail
umask 0022

command=${SSH_ORIGINAL_COMMAND:-}
revision=${1:-${command#deploy }}
if [[ ! "$revision" =~ ^[a-f0-9]{40}$ ]] || { [[ -n "$command" ]] && [[ "$command" != "deploy $revision" ]]; }; then
    echo 'Invalid deployment revision' >&2
    exit 2
fi

base=/var/www/hireloop
# ponytail: retain releases/backups for rollback; prune reviewed old ones before disk fills.
exec 9>"$base/.deploy.lock"
flock -w 120 9
release="$base/releases/$revision-$(date -u +%Y%m%dT%H%M%S%N)"
previous=''
[[ ! -L "$base/current" ]] || previous=$(readlink -f "$base/current")
activated=false

activate() {
    ln -sfn "$1" "$base/.next"
    mv -Tf "$base/.next" "$base/current"
}

wait_healthy() {
    for attempt in {1..30}; do
        if curl --max-time 3 -fsS http://127.0.0.1:8001/api/health >/dev/null 2>&1; then
            return 0
        fi
        sleep 1
    done
    return 1
}

rollback() {
    status=$?
    trap - ERR
    if $activated; then
        if [[ -n "$previous" ]]; then
            activate "$previous"
            if sudo /usr/bin/systemctl restart hireloop.service && wait_healthy; then
                echo 'Release failed; previous backend is healthy again.' >&2
            else
                echo 'Previous release selected; backend requires manual recovery.' >&2
            fi
        else
            sudo /usr/bin/systemctl stop hireloop.service || true
            unlink "$base/current"
            echo 'First release failed; service stopped.' >&2
        fi
    fi
    exit "$status"
}
trap rollback ERR

mkdir -p "$release"
python3 -c 'import sys, tarfile; tarfile.open(fileobj=sys.stdin.buffer, mode="r|gz").extractall(sys.argv[1], filter="data")' "$release"
test -s "$release/frontend/dist/index.html"
test -s "$release/backend/app/main.py"
python3 -m compileall -q "$release/backend/app"
python3 -m venv "$release/.venv"
"$release/.venv/bin/python" -m pip install --disable-pip-version-check -q -r "$release/backend/requirements.txt"
printf '%s\n' "$revision" > "$release/REVISION"

if [[ -f /var/lib/hireloop/hireloop.db ]]; then
    (umask 0077
    python3 - "$release" <<'PY'
import os, pathlib, sqlite3, sys
backup = pathlib.Path('/var/backups/hireloop') / (pathlib.Path(sys.argv[1]).name + '.db')
temporary = str(backup) + '.tmp'
with sqlite3.connect('file:/var/lib/hireloop/hireloop.db?mode=ro', uri=True) as source, sqlite3.connect(temporary) as target:
    source.backup(target)
    assert target.execute('PRAGMA quick_check').fetchone()[0] == 'ok'
os.replace(temporary, backup)
PY
    )
fi

activate "$release"
activated=true
sudo /usr/bin/systemctl restart hireloop.service
if wait_healthy; then
    echo "Deployed $revision"
    exit 0
fi
echo 'New backend did not become healthy.' >&2
false

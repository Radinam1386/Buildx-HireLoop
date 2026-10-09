"""Integration check: python deploy/check-rollback.py release.tgz ADMIN_KEY DEPLOY_KEY.

Run before opening a release to users: deliberately interrupts HireLoop briefly.
"""
import io
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import urllib.request

archive, admin_key, deploy_key = sys.argv[1:]
def admin(command):
    return subprocess.check_output(['ssh', '-i', admin_key, '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
                                    'root@78.157.54.151', command], text=True).strip()

previous = admin('readlink -f /var/www/hireloop/current')
with tempfile.TemporaryDirectory() as folder:
    broken = Path(folder) / 'broken.tgz'
    with tarfile.open(archive) as source, tarfile.open(broken, 'w:gz') as target:
        for member in source.getmembers():
            content = source.extractfile(member) if member.isfile() else None
            if member.name.removeprefix('./') == 'backend/app/main.py':
                data = b'raise RuntimeError("deliberate HireLoop rollback check")\n'
                member.size = len(data)
                content = io.BytesIO(data)
            target.addfile(member, content)
    with broken.open('rb') as data:
        failed = subprocess.run(['ssh', '-i', deploy_key, '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
                                 'hireloop-deploy@78.157.54.151', 'deploy ' + '0' * 40], stdin=data)
    assert failed.returncode != 0, 'Broken release must fail'
assert admin('readlink -f /var/www/hireloop/current') == previous, 'Previous release must be restored'
direct = urllib.request.build_opener(urllib.request.ProxyHandler({}))
with direct.open('https://78.157.54.151/api/health', timeout=15) as response:
    assert response.status == 200
with direct.open('https://mentoralearn.ir/', timeout=15) as response:
    assert response.status == 200
print('Broken release rejected; previous release restored; HireLoop and Mentora healthy')

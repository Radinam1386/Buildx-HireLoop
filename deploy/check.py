"""Run with Python 3.12 on Linux; optionally verify a CI release archive."""
import os
from pathlib import Path
import subprocess
import sys
import tarfile

script = Path(__file__).with_name("release.sh")
assert script.is_file(), "Missing release script"
subprocess.run(["bash", "-n", str(script)], check=True)
for command in ("", "deploy not-a-sha", "deploy " + "a" * 40 + "; id", "other " + "a" * 40):
    result = subprocess.run(
        ["bash", str(script)], input=b"", capture_output=True,
        env={**os.environ, "SSH_ORIGINAL_COMMAND": command},
    )
    assert result.returncode != 0 and b"Invalid deployment revision" in result.stderr, command

if len(sys.argv) == 2:
    with tarfile.open(sys.argv[1]) as archive:
        names = {m.name.removeprefix("./") for m in archive.getmembers() if m.isfile()}
        assert {"backend/app/main.py", "backend/requirements.txt", "frontend/dist/index.html"} <= names
        for name in names:
            assert name.startswith(("backend/app/", "frontend/dist/")) or name == "backend/requirements.txt", name
            assert not any(p.startswith(".env") or p == "__pycache__" for p in Path(name).parts), name
            assert Path(name).suffix not in {".db", ".pem", ".key", ".pyc"}, name
print("Deployment command and archive checks passed")

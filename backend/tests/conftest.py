"""Set isolated test settings before any app module is imported."""
import os
import tempfile

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/hireloop-test.db"
os.environ["JWT_SECRET"] = "hireloop-tests-only-secret-32-characters"

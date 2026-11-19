import io
import os
import sys
import tempfile
from pathlib import Path

_tmp = tempfile.mkdtemp(prefix="findback_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_tmp, 'test.db').as_posix()}"
os.environ["UPLOAD_DIR"] = str(Path(_tmp, "uploads"))
os.environ["SECRET_KEY"] = "test-secret-not-for-production"
os.environ["IMAGE_MATCHING_ENABLED"] = "false"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402


@pytest.fixture(scope="session")
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


def png_bytes(color=(200, 30, 30)):
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), color).save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture()
def make_user(client):
    counter = {"n": 0}

    def _make(name="User"):
        counter["n"] += 1
        email = f"{name.lower()}{counter['n']}_{os.urandom(3).hex()}@example.com"
        r = client.post("/api/v1/auth/register", json={"name": name, "email": email, "password": "password123"})
        assert r.status_code == 201, r.text
        body = r.json()
        return {"id": body["user"]["id"], "email": email,
                "headers": {"Authorization": f"Bearer {body['access_token']}"}}
    return _make

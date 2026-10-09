import os

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["AUTH_DISABLED"] = "true"
os.environ["CORS_ORIGINS"] = "http://localhost"

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

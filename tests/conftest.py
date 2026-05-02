import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/testdb")

import pytest
from contextlib import asynccontextmanager
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.main import app

@asynccontextmanager
async def _noop_lifespan(_):
    yield

app.router.lifespan_context = _noop_lifespan


@pytest.fixture(autouse=True)
def reset_overrides():
    app.dependency_overrides.pop(get_current_user, None)
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

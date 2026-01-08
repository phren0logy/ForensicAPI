from pathlib import Path
import os

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture(scope="session")
def test_client():
    return TestClient(app)


@pytest.fixture(scope="session")
def fixtures_dir():
    return Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def azure_credentials():
    endpoint = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
    key = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY")
    if not endpoint or not key:
        pytest.skip("Azure Document Intelligence credentials not set in .env")
    return {"endpoint": endpoint, "key": key}

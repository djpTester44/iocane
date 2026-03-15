"""
Pytest Conftest Template
========================
Common fixtures and configuration for test suites.
"""

from pathlib import Path
from unittest.mock import Mock

import pytest


@pytest.fixture
def project_root() -> Path:
    """Return the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture
def test_data_dir(project_root: Path) -> Path:
    """Return the test data directory."""
    return project_root / "tests" / "data"


@pytest.fixture
def tmp_output_dir(tmp_path: Path) -> Path:
    """Provide a temporary output directory for test artifacts."""
    output = tmp_path / "output"
    output.mkdir(parents=True, exist_ok=True)
    return output


@pytest.fixture
def mock_config() -> dict:
    """Provide a standard mock configuration."""
    return {"debug": True, "log_level": "DEBUG", "timeout": 30}


@pytest.fixture
def mock_client() -> Mock:
    """Provide a mock API client."""
    client = Mock()
    client.get.return_value = {"status": "ok"}
    client.post.return_value = {"id": "123"}
    return client


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "slow: marks tests as slow")
    config.addinivalue_line("markers", "integration: marks integration tests")
    config.addinivalue_line("markers", "unit: marks unit tests")

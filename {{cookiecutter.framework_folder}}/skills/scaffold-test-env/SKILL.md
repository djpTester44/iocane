---
name: scaffold-test-env
description: Generates conftest.py fixtures for isolated E2E tests requiring config files or external service mocks. Use when setting up test infrastructure for integration or E2E tests that need filesystem isolation or mocked external services.
---

# Scaffold Test Environment

Generate conftest.py fixtures for isolated E2E tests.

## Workflow

1. **Detect Config Dependencies** - Scan codebase for config loaders:
   - `tomllib.load`
   - `os.getenv`
   - `yaml.safe_load`
   - Map them to their config files

2. **Identify External Services** - Find client instantiations needing mocks:
   - `googlemaps.Client`
   - `boto3.client`
   - HTTP clients (`requests`, `httpx`)

3. **Generate conftest.py** - Create `tests/conftest.py` with an `e2e_env` fixture that:
   - Isolates filesystem via `tmp_path`/`monkeypatch.chdir`
   - Creates config files with test values
   - Patches external services

4. **Output** - Produce `tests/conftest.py` with shared E2E fixtures

## Constraints

- Fixtures **must** use `tmp_path` for filesystem isolation
- All external API calls **must** be mocked
- Config content should mirror production structure with test values

## Example Fixture

```python
@pytest.fixture
def e2e_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Isolated E2E test environment."""
    # Filesystem isolation
    monkeypatch.chdir(tmp_path)
    
    # Config files
    config = tmp_path / "config.toml"
    config.write_text('[app]\ndebug = true\n')
    
    # Mock external services
    with patch("module.external_client") as mock:
        mock.return_value = {"status": "ok"}
        yield {"tmp_path": tmp_path, "mock": mock}
```

## Required Input

Caller MUST provide:

- `project_root`: Path to project (skill will scan for config loaders)

## Tool Strategy

- `grep_search`: Pattern `tomllib\.load|os\.getenv|yaml\.safe_load` to find config loaders
- `grep_search`: Pattern `Client\(|boto3\.client` to find external services
- Do NOT read every file - grep first, then read matches for context

## Output Format

Return conftest.py content:

```json
{
  "conftest_code": "<full conftest.py content>",
  "detected_configs": ["config.toml", ".env"],
  "mocked_services": ["httpx.Client"]
}
```
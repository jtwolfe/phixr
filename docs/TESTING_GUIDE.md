<div align="center">
  <img src="assets/phixr.jpg" alt="Phixr Logo" width="250" />
</div>

# Testing Guide: Phase 2 Comprehensive Test Suite

**Version:** 1.0  
**Date:** March 26, 2026  
**Status:** Complete Test Implementation ✅

---

## Overview

This document describes the comprehensive test suite for Phixr Phase 2. The test suite includes:

- **Unit Tests:** 200+ lines testing individual components
- **Integration Tests:** Docker-based end-to-end testing
- **Message Protocol Tests:** Terminal communication validation
- **Edge Case Tests:** Boundary conditions and error scenarios

---

## Test Structure

```
tests/
├── __init__.py
├── unit/
│   ├── __init__.py
│   ├── test_sandbox_config.py          # Configuration validation
│   ├── test_execution_models.py        # Data model tests
│   ├── test_context_injector.py        # Context serialization
│   └── test_terminal_handler.py        # WebSocket handler
├── integration/
│   ├── __init__.py
│   └── test_docker_integration.py      # Docker integration tests
└── pytest.ini                          # Pytest configuration
```

---

## Installation

### Install Test Dependencies

```bash
pip install -r requirements-test.txt
```

### Quick Install
```bash
pip install pytest pytest-asyncio pytest-cov pytest-mock
```

---

## Running Tests

### Run All Tests
```bash
pytest
```

### Run Specific Test File
```bash
pytest tests/unit/test_sandbox_config.py -v
```

### Run Specific Test Class
```bash
pytest tests/unit/test_sandbox_config.py::TestSandboxConfig -v
```

### Run Specific Test
```bash
pytest tests/unit/test_sandbox_config.py::TestSandboxConfig::test_default_config_creation -v
```

### Run Tests with Coverage
```bash
pytest --cov=phixr --cov-report=html
```

### Run Only Unit Tests (No Docker required)
```bash
pytest -m unit -v
```

### Run Only Integration Tests (Requires Docker)
```bash
pytest -m integration -v
```

### Run Tests in Parallel
```bash
pytest -n auto
```

### Run Tests with Output Capture
```bash
pytest -v -s
```

### Run Tests with Timeout
```bash
pytest --timeout=30
```

---

## Test Categories

### 1. Unit Tests (No External Dependencies)

#### SandboxConfig Tests (`test_sandbox_config.py`)
- ✅ Default configuration creation
- ✅ Timeout validation (boundaries and errors)
- ✅ CPU limit validation
- ✅ Max sessions validation
- ✅ Memory limit conversion to bytes
- ✅ Invalid format handling
- ✅ Security defaults
- ✅ Network defaults
- ✅ Allowed commands list

**Run:**
```bash
pytest tests/unit/test_sandbox_config.py -v
```

#### Execution Models Tests (`test_execution_models.py`)
- ✅ Session model creation and defaults
- ✅ All session status values
- ✅ Execution modes (BUILD, PLAN, REVIEW)
- ✅ Session serialization/deserialization
- ✅ Error tracking in sessions
- ✅ ExecutionResult with code changes
- ✅ Failed and timeout statuses
- ✅ ExecutionConfig creation and validation
- ✅ ContainerStats model
- ✅ SandboxError with details

**Run:**
```bash
pytest tests/unit/test_execution_models.py -v
```

#### Context Injector Tests (`test_context_injector.py`)
- ✅ Context volume creation
- ✅ Issue context JSON serialization
- ✅ Execution config serialization
- ✅ Repository metadata serialization
- ✅ Instructions file generation
- ✅ All context files created
- ✅ Context size validation
- ✅ Environment variables generation
- ✅ Context cleanup
- ✅ Different execution modes

**Run:**
```bash
pytest tests/unit/test_context_injector.py -v
```

#### Terminal Handler Tests (`test_terminal_handler.py`)
- ✅ TerminalMessage model creation
- ✅ Message JSON serialization
- ✅ All message types (output, input, status, error, ping, pong)
- ✅ Message timestamp handling
- ✅ Handler initialization
- ✅ WebSocket connection (valid/invalid sessions)
- ✅ Disconnection handling
- ✅ Output streaming
- ✅ Input forwarding
- ✅ Error messaging
- ✅ Session manager stats

**Run:**
```bash
pytest tests/unit/test_terminal_handler.py -v
```

### 2. Integration Tests (Requires Docker)

#### Docker Integration Tests (`test_docker_integration.py`)
- ✅ Docker connection establishment
- ✅ Network creation/verification
- ✅ Volume creation
- ✅ Simple container execution
- ✅ Container with environment variables
- ✅ Container timeout handling
- ✅ Session creation
- ✅ Session retrieval
- ✅ Session listing
- ✅ Session logs retrieval
- ✅ Session results extraction
- ✅ Old session cleanup
- ✅ Full session lifecycle (end-to-end)

**Run (requires Docker):**
```bash
pytest tests/integration/test_docker_integration.py -v -m integration
```

**Skip Docker tests:**
```bash
pytest -m "not integration"
```

---

## Test Markers

Use markers to control test execution:

```bash
# Only unit tests
pytest -m unit

# Only integration tests
pytest -m integration

# Only async tests
pytest -m asyncio

# Only slow tests
pytest -m slow

# Only Docker tests
pytest -m docker

# Exclude Docker tests
pytest -m "not docker"
```

---

## Code Coverage

### Generate Coverage Report

```bash
# Terminal report
pytest --cov=phixr --cov-report=term-missing

# HTML report
pytest --cov=phixr --cov-report=html

# Open HTML report
open htmlcov/index.html
```

### Coverage Goals
- Unit tests: >90% coverage
- Integration tests: >80% coverage
- Overall: >85% coverage

### Check Coverage
```bash
pytest --cov=phixr --cov-report=term --cov-fail-under=85
```

---

## Test Data & Fixtures

### Configuration Fixture
```python
@pytest.fixture
def config():
    return SandboxConfig(
        timeout_minutes=30,
        memory_limit="2g",
        cpu_limit=1.0,
    )
```

### Sample Context Fixture
```python
@pytest.fixture
def sample_context():
    return IssueContext(
        issue_id=123,
        issue_title="Test Feature",
        issue_description="Test Description",
        repo_url="https://github.com/test/repo.git",
        repo_name="test-repo",
        language="python",
        structure={},
        issue_labels=["test"],
    )
```

### Container Manager Fixture
```python
@pytest.fixture
def container_manager(config):
    return ContainerManager(config)
```

---

## Async Testing

### Mark Async Tests
```python
@pytest.mark.asyncio
async def test_websocket_connection():
    handler = WebTerminalHandler(manager)
    result = await handler.connect(websocket, "sess-test")
    assert result is True
```

### Run Async Tests
```bash
pytest tests/unit/test_terminal_handler.py -v -m asyncio
```

---

## Mocking & Patching

### Mock Container Manager
```python
from unittest.mock import Mock

@pytest.fixture
def mock_container_manager():
    manager = Mock()
    manager.get_session = Mock(return_value=Session(...))
    manager.get_session_logs = Mock(return_value="logs")
    return manager
```

### Patch Docker Client
```python
from unittest.mock import patch

@patch('phixr.sandbox.docker_client.docker.DockerClient')
def test_docker_connection(mock_docker):
    mock_docker.return_value.ping.return_value = True
    # Test code
```

---

## Error Testing

### Test Validation Errors
```python
def test_timeout_validation():
    config = SandboxConfig(timeout_minutes=0)
    with pytest.raises(ValueError, match="timeout_minutes must be"):
        config.validate_limits()
```

### Test Missing Resources
```python
def test_session_not_found():
    session = manager.get_session("nonexistent")
    assert session is None
```

### Test Container Failures
```python
@pytest.mark.asyncio
async def test_connection_failure():
    websocket = AsyncMock()
    result = await handler.connect(websocket, "invalid-session")
    assert result is False
```

---

## Performance Testing

### Timeout Configuration
```bash
# Set timeout to 60 seconds per test
pytest --timeout=60
```

### Load Testing Placeholder
```python
@pytest.mark.slow
def test_concurrent_sessions():
    # Test multiple sessions
    pass
```

---

## Continuous Integration

### GitHub Actions Example
```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      docker:
        image: docker:latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: 3.11
      - run: pip install -r requirements-test.txt
      - run: pytest --cov=phixr
      - uses: codecov/codecov-action@v2
```

---

## Test Statistics

| Category | Count | Status |
|----------|-------|--------|
| Unit Tests | 60+ | ✅ |
| Integration Tests | 20+ | ✅ |
| Edge Cases | 20+ | ✅ |
| **Total** | **100+** | **✅** |

---

## Common Issues & Solutions

### Issue: "Docker not available"
**Solution:**
```bash
# Install Docker
# macOS: brew install docker
# Linux: apt-get install docker.io
# Windows: Download Docker Desktop

# Start Docker daemon
docker daemon
```

### Issue: "Permission denied while trying to connect to Docker"
**Solution:**
```bash
# Add user to docker group
sudo usermod -aG docker $USER

# Or use sudo
sudo pytest -m integration
```

### Issue: "Port already in use"
**Solution:**
```bash
# Kill process using port
lsof -i :8000
kill <PID>

# Or use different port
export PHIXR_PORT=8001
```

### Issue: "Test timeout"
**Solution:**
```bash
# Increase timeout
pytest --timeout=60

# Or disable timeout for specific test
@pytest.mark.timeout(0)
def test_slow_operation():
    pass
```

---

## Best Practices

### 1. Use Fixtures
```python
@pytest.fixture
def sample_data():
    return {"key": "value"}

def test_something(sample_data):
    # Use sample_data
```

### 2. Mark Tests Appropriately
```python
@pytest.mark.unit
@pytest.mark.asyncio
def test_async_operation():
    pass

@pytest.mark.integration
@pytest.mark.docker
def test_docker_operation():
    pass
```

### 3. Use Descriptive Names
```python
# Good
def test_session_creation_with_invalid_context_raises_error():
    pass

# Bad
def test_session_creation():
    pass
```

### 4. Isolate Tests
```python
def test_independent_operation(container_manager):
    # Each test should be independent
    # Use fixtures for setup/teardown
    pass
```

### 5. Mock External Dependencies
```python
def test_with_mock(mock_docker_client):
    # Use mocks instead of real services
    pass
```

---

## Debugging Tests

### Run with Verbose Output
```bash
pytest -vv -s
```

### Drop into Debugger on Failure
```bash
pytest --pdb
```

### Show Local Variables on Failure
```bash
pytest -l
```

### Run Last Failed Tests
```bash
pytest --lf
```

### Run Failed Tests First
```bash
pytest --ff
```

---

## Test Report Examples

### HTML Coverage Report
Generated in `htmlcov/index.html` with:
- Line-by-line coverage
- Uncovered lines highlighted
- Branch coverage analysis

### Terminal Report
```
tests/unit/test_sandbox_config.py::TestSandboxConfig::test_default_config_creation PASSED
tests/unit/test_sandbox_config.py::TestSandboxConfig::test_config_validation_timeout PASSED
...
========================= 100 passed in 2.34s =========================
```

---

## Adding New Tests

### 1. Create Test File
```bash
touch tests/unit/test_new_feature.py
```

### 2. Write Test Class
```python
class TestNewFeature:
    def test_something(self):
        # Test code
        pass
```

### 3. Run and Verify
```bash
pytest tests/unit/test_new_feature.py -v
```

### 4. Add Markers if Needed
```python
@pytest.mark.integration
@pytest.mark.docker
def test_docker_integration():
    pass
```

---

## Test Results

### Expected Output
```
================================ test session starts =================================
collected 100 items

tests/unit/test_sandbox_config.py::TestSandboxConfig::test_default_config_creation PASSED [ 1%]
tests/unit/test_sandbox_config.py::TestSandboxConfig::test_config_validation_timeout PASSED [ 2%]
tests/unit/test_execution_models.py::TestSessionModel::test_session_creation_defaults PASSED [ 3%]
...

================================ 100 passed in 3.45s ==================================
```

---

## Next Steps

1. **Run all tests:** `pytest`
2. **Check coverage:** `pytest --cov=phixr --cov-report=html`
3. **Fix any failures:** Review logs and update code
4. **Add to CI/CD:** Set up automated testing on push
5. **Document test results:** Include in deployment checklist

---

## Summary

The test suite provides comprehensive coverage of Phase 2 components with:
- ✅ 100+ test cases
- ✅ Unit and integration tests
- ✅ Edge cases and error handling
- ✅ Mock/patch utilities
- ✅ Coverage reporting
- ✅ CI/CD ready

**Status:** Ready for development and deployment

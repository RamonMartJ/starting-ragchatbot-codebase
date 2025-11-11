# RAG System Testing Guide

## Quick Start

### Run all unit and API tests:
```bash
uv run pytest backend/tests/unit/ backend/tests/test_api_endpoints.py -v
```

### Run only API tests:
```bash
uv run pytest backend/tests/test_api_endpoints.py -v
```

### Run with markers:
```bash
uv run pytest -m api           # API endpoint tests only
uv run pytest -m unit          # Unit tests only
uv run pytest -m integration   # Integration tests only
```

## Test Structure

```
backend/tests/
├── conftest.py              # Shared fixtures and configuration
├── test_api_endpoints.py    # API endpoint tests (NEW)
├── unit/                    # Unit tests for components
│   ├── test_ai_generator.py
│   ├── test_search_tools.py
│   └── test_vector_store.py
├── diagnostics/             # Environment/system checks
│   ├── test_chromadb_health.py
│   ├── test_environment.py
│   └── test_tools_basic.py
└── test_data/               # Test data files
```

## Available Fixtures

### API Testing Fixtures
- `test_app` - Minimal FastAPI app for testing
- `test_client` - TestClient for HTTP requests
- `mock_rag_system` - Mocked RAG system

### Component Fixtures
- `test_config` - Test configuration
- `mock_anthropic_client` - Mocked Anthropic API
- `test_vector_store` - Temporary ChromaDB
- `sample_article_data` - Sample article for testing
- `mock_search_tool` - Mocked search tool
- `mock_tool_manager` - Mocked tool manager

## Writing New Tests

### API Endpoint Test Example:
```python
import pytest
from fastapi import status

@pytest.mark.api
def test_my_endpoint(test_client):
    """Test description"""
    response = test_client.post("/api/my-endpoint", json={"key": "value"})
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "expected_field" in data
```

### Unit Test Example:
```python
import pytest

@pytest.mark.unit
def test_my_function(mock_component):
    """Test description"""
    result = my_function(mock_component)
    assert result == expected_value
```

## Test Markers

Use markers to categorize tests:
- `@pytest.mark.unit` - Unit tests for individual components
- `@pytest.mark.api` - API endpoint tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.slow` - Slow-running tests

## Configuration

Pytest configuration is in `pyproject.toml`:
- Test discovery in `backend/tests/`
- Verbose output enabled
- Short traceback format
- Python path set to `backend/`

## Common Commands

### Run all tests:
```bash
uv run pytest backend/tests/
```

### Run with coverage:
```bash
uv run pytest backend/tests/ --cov=backend --cov-report=html
```

### Run specific test file:
```bash
uv run pytest backend/tests/test_api_endpoints.py
```

### Run specific test function:
```bash
uv run pytest backend/tests/test_api_endpoints.py::test_query_endpoint_basic_request
```

### Run tests matching pattern:
```bash
uv run pytest -k "endpoint"  # Run tests with "endpoint" in name
```

### Show test output:
```bash
uv run pytest -v -s  # Verbose with stdout/stderr
```

## Troubleshooting

### Import errors:
- Ensure you're running from project root
- Check `pythonpath = ["backend"]` in pyproject.toml

### Fixture not found:
- Check fixture is defined in conftest.py
- Ensure fixture is imported if in separate file

### Test collection fails:
- Verify test file names start with `test_`
- Check test function names start with `test_`

### ChromaDB errors in unit tests:
- Unit tests use temporary ChromaDB (auto-cleanup)
- Check `temp_chroma_path` fixture is being used

## API Testing Notes

### Why separate test app?
The test app avoids:
- Static file mounting (no frontend dependency)
- Lifespan events (no document loading)
- Real database connections
- Real API calls

### Customizing mock behavior:
```python
def test_custom_behavior(test_client, mock_rag_system):
    # Configure mock for this test
    mock_rag_system.query.return_value = ("Custom answer", [])

    # Test with custom behavior
    response = test_client.post("/api/query", json={"query": "test"})
    assert "Custom answer" in response.json()["answer"]
```

## Test Results Summary

Current test status:
- ✅ 64 unit tests passing
- ✅ 19 API tests passing
- ⚠️ 7 diagnostic tests fail (require ChromaDB initialization)
- ⚠️ 2 diagnostic tests skipped (require articles loaded)

The diagnostic test failures are expected in clean test environment.

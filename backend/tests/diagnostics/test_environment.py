"""
Environment diagnostics tests - verify basic setup and configuration.

These tests run very quickly (< 1 second) and check:
- ANTHROPIC_API_KEY is set and has valid format
- Config loads correctly with all required fields
- All imports work without errors
- Basic Python dependencies are available

Run with: pytest tests/diagnostics/test_environment.py -v
"""

import pytest
import os
import sys
from pathlib import Path


def test_anthropic_api_key_exists():
    """Verify ANTHROPIC_API_KEY environment variable is set."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    assert api_key is not None, "ANTHROPIC_API_KEY environment variable is not set"
    assert len(api_key) > 0, "ANTHROPIC_API_KEY is empty"


def test_anthropic_api_key_format():
    """Verify ANTHROPIC_API_KEY has expected format (starts with sk-ant-)."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:  # Only check format if key exists
        assert api_key.startswith("sk-ant-"), \
            f"ANTHROPIC_API_KEY has unexpected format. Should start with 'sk-ant-', got: {api_key[:10]}..."


def test_config_module_loads():
    """Verify config module can be imported without errors."""
    try:
        import config
        assert hasattr(config, 'config'), "config.config object not found"
    except ImportError as e:
        pytest.fail(f"Failed to import config module: {e}")


def test_config_has_required_fields():
    """Verify config object has all required configuration fields."""
    from config import config

    required_fields = [
        'ANTHROPIC_API_KEY',
        'ANTHROPIC_MODEL',
        'EMBEDDING_MODEL',
        'CHUNK_SIZE',
        'CHUNK_OVERLAP',
        'MAX_RESULTS',
        'MAX_HISTORY',
        'CHROMA_PATH'
    ]

    for field in required_fields:
        assert hasattr(config, field), f"Config missing required field: {field}"
        value = getattr(config, field)
        assert value is not None, f"Config field {field} is None"
        assert value != "", f"Config field {field} is empty string"


def test_config_api_key_matches_env():
    """Verify config.ANTHROPIC_API_KEY matches environment variable."""
    from config import config
    env_key = os.getenv("ANTHROPIC_API_KEY")

    if env_key:
        assert config.ANTHROPIC_API_KEY == env_key, \
            "Config API key doesn't match environment variable"


def test_all_core_modules_import():
    """Verify all core modules can be imported without errors."""
    modules_to_test = [
        'models',
        'vector_store',
        'document_processor',
        'ai_generator',
        'session_manager',
        'search_tools',
        'rag_system',
        'app'
    ]

    failed_imports = []

    for module_name in modules_to_test:
        try:
            __import__(module_name)
        except Exception as e:
            failed_imports.append((module_name, str(e)))

    assert len(failed_imports) == 0, \
        f"Failed to import {len(failed_imports)} modules: {failed_imports}"


def test_python_version():
    """Verify Python version is 3.13 or higher."""
    version = sys.version_info
    assert version.major == 3, f"Python major version should be 3, got {version.major}"
    assert version.minor >= 13, \
        f"Python minor version should be >= 13, got {version.minor} (Python {version.major}.{version.minor})"


def test_required_dependencies_available():
    """Verify all required Python packages are installed."""
    required_packages = [
        'anthropic',
        'chromadb',
        'fastapi',
        'sentence_transformers',
        'pydantic'
    ]

    missing_packages = []

    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)

    assert len(missing_packages) == 0, \
        f"Missing required packages: {missing_packages}. Install with: uv sync"


def test_project_structure():
    """Verify expected project directory structure exists."""
    # Get backend directory (tests are in backend/tests/)
    backend_dir = Path(__file__).parent.parent.parent

    expected_files = [
        'app.py',
        'config.py',
        'models.py',
        'vector_store.py',
        'document_processor.py',
        'ai_generator.py',
        'session_manager.py',
        'search_tools.py',
        'rag_system.py',
        'logger.py'
    ]

    missing_files = []

    for file_name in expected_files:
        file_path = backend_dir / file_name
        if not file_path.exists():
            missing_files.append(file_name)

    assert len(missing_files) == 0, \
        f"Missing expected files in backend/: {missing_files}"


def test_docs_folder_exists():
    """Verify docs folder exists with article files."""
    # Docs folder is at ../docs relative to backend/
    backend_dir = Path(__file__).parent.parent.parent
    docs_dir = backend_dir.parent / "docs"

    assert docs_dir.exists(), \
        f"Docs folder not found at {docs_dir}. Articles should be in ../docs/"

    assert docs_dir.is_dir(), \
        f"{docs_dir} exists but is not a directory"

    # Check if there are any .txt files
    txt_files = list(docs_dir.glob("*.txt"))
    assert len(txt_files) > 0, \
        f"No .txt article files found in {docs_dir}"


def test_logging_module_works():
    """Verify logging module can be imported and used."""
    try:
        from logger import get_logger, setup_logging

        # Test getting a logger
        logger = get_logger("test")
        assert logger is not None, "get_logger returned None"

        # Test that logger has expected methods
        assert hasattr(logger, 'debug'), "Logger missing debug method"
        assert hasattr(logger, 'info'), "Logger missing info method"
        assert hasattr(logger, 'warning'), "Logger missing warning method"
        assert hasattr(logger, 'error'), "Logger missing error method"

    except Exception as e:
        pytest.fail(f"Logging module test failed: {e}")


if __name__ == "__main__":
    # Allow running tests directly with: python test_environment.py
    pytest.main([__file__, "-v"])

"""
Pytest configuration and shared fixtures for RAG system tests.

This file provides reusable test fixtures including:
- Mock Anthropic API client
- Test VectorStore with temporary ChromaDB
- Sample article data
- Mock tools and managers
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock


# ============================================================================
# CONFIG FIXTURES
# ============================================================================

@pytest.fixture
def test_config():
    """
    Provide a test configuration object with all required settings.

    Uses temporary directories for ChromaDB to avoid polluting real data.
    """
    config = Mock()
    config.ANTHROPIC_API_KEY = "sk-ant-test-key-12345"
    config.ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
    config.EMBEDDING_MODEL = "all-MiniLM-L6-v2"
    config.CHUNK_SIZE = 800
    config.CHUNK_OVERLAP = 100
    config.MAX_RESULTS = 5
    config.MAX_HISTORY = 2
    # Use temporary directory for test ChromaDB
    config.CHROMA_PATH = tempfile.mkdtemp(prefix="test_chroma_")
    return config


# ============================================================================
# MOCK ANTHROPIC API FIXTURES
# ============================================================================

@pytest.fixture
def mock_anthropic_response():
    """
    Provide a mock Anthropic API response for testing.

    Returns a response object that simulates Claude's text response.
    """
    response = Mock()
    response.stop_reason = "end_turn"

    # Mock content structure
    content_block = Mock()
    content_block.type = "text"
    content_block.text = "This is a test response from Claude"

    response.content = [content_block]
    return response


@pytest.fixture
def mock_anthropic_tool_use_response():
    """
    Provide a mock Anthropic API response with tool use.

    Simulates Claude requesting to use the search_news_content tool.
    """
    response = Mock()
    response.stop_reason = "tool_use"

    # Mock tool use content block
    tool_block = Mock()
    tool_block.type = "tool_use"
    tool_block.name = "search_news_content"
    tool_block.id = "tool_use_123"
    tool_block.input = {"query": "test query"}

    response.content = [tool_block]
    return response


@pytest.fixture
def mock_anthropic_client(mock_anthropic_response):
    """
    Provide a mock Anthropic client for testing without API calls.

    Returns a client that simulates the Anthropic SDK interface.
    """
    client = Mock()
    client.messages = Mock()
    client.messages.create = Mock(return_value=mock_anthropic_response)
    return client


# ============================================================================
# VECTOR STORE FIXTURES
# ============================================================================

@pytest.fixture
def temp_chroma_path(tmp_path):
    """
    Provide a temporary directory for ChromaDB testing.

    Automatically cleaned up after test completes.
    """
    chroma_dir = tmp_path / "test_chroma"
    chroma_dir.mkdir()
    yield str(chroma_dir)
    # Cleanup happens automatically with tmp_path


@pytest.fixture
def test_vector_store(temp_chroma_path):
    """
    Provide a clean VectorStore instance for testing.

    Uses temporary ChromaDB that's cleaned up after test.
    """
    from vector_store import VectorStore

    store = VectorStore(
        chroma_path=temp_chroma_path,
        embedding_model="all-MiniLM-L6-v2",
        max_results=5
    )

    yield store

    # Cleanup
    try:
        store.clear_all_data()
    except:
        pass


# ============================================================================
# SAMPLE DATA FIXTURES
# ============================================================================

@pytest.fixture
def sample_article_data():
    """
    Provide sample article data for testing.

    Returns a dictionary with article metadata and content.
    """
    return {
        "title": "Test Article About AI Technology",
        "content": "This is a test article about artificial intelligence and machine learning. "
                   "It discusses various aspects of modern AI technology and its applications. "
                   "The article covers topics like neural networks, deep learning, and NLP.",
        "link": "https://example.com/test-article",
        "people": [
            {
                "nombre": "Dr. Jane Smith",
                "cargo": "AI Researcher",
                "organizacion": "Tech University",
                "datos_interes": "Leading expert in machine learning"
            },
            {
                "nombre": "John Doe",
                "cargo": "CTO",
                "organizacion": "AI Corp",
                "datos_interes": "Pioneer in AI applications"
            }
        ]
    }


@pytest.fixture
def sample_article_file(tmp_path, sample_article_data):
    """
    Provide a temporary article file for testing document processing.

    Creates a .txt file with valid article format.
    """
    article_path = tmp_path / "test_article.txt"

    content = f"""Titular: {sample_article_data['title']}

Personas Mencionadas:
- Dr. Jane Smith | AI Researcher | Tech University | Leading expert in machine learning
- John Doe | CTO | AI Corp | Pioneer in AI applications

{sample_article_data['content']}

Enlace: {sample_article_data['link']}
"""

    article_path.write_text(content, encoding='utf-8')
    return str(article_path)


# ============================================================================
# MOCK TOOL FIXTURES
# ============================================================================

@pytest.fixture
def mock_search_tool():
    """
    Provide a mock ArticleSearchTool for testing.

    Returns tool results without actual vector search.
    """
    tool = Mock()
    tool.last_sources = []

    def mock_execute(query: str, article_title: str = None):
        result = f"Mock search results for query: {query}"
        if article_title:
            result += f" in article: {article_title}"

        # Simulate storing sources
        tool.last_sources = [{
            "text": "Test Article",
            "url": "https://example.com/test",
            "index": 1
        }]

        return result

    tool.execute = mock_execute
    tool.get_tool_definition = Mock(return_value={
        "name": "search_news_content",
        "description": "Search news articles",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "article_title": {"type": "string"}
            },
            "required": ["query"]
        }
    })

    return tool


@pytest.fixture
def mock_tool_manager(mock_search_tool):
    """
    Provide a mock ToolManager for testing.

    Pre-configured with mock search tool.
    """
    from search_tools import ToolManager

    manager = ToolManager()
    manager.register_tool(mock_search_tool)
    return manager


# ============================================================================
# CLEANUP FIXTURES
# ============================================================================

@pytest.fixture(autouse=True)
def cleanup_temp_chroma():
    """
    Automatically clean up any temporary ChromaDB directories after tests.

    Runs after every test to ensure no leftover test data.
    """
    yield

    # Clean up any test_chroma_* directories in temp
    temp_dir = Path(tempfile.gettempdir())
    for chroma_dir in temp_dir.glob("test_chroma_*"):
        try:
            shutil.rmtree(chroma_dir)
        except:
            pass

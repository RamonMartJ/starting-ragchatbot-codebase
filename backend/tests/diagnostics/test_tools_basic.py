"""
Tools basic diagnostics - verify tools can execute without errors.

These tests check (< 10 seconds):
- ArticleSearchTool can execute
- PeopleSearchTool can execute
- Tool definitions have correct schema
- Tools integrate properly with VectorStore

Run with: pytest tests/diagnostics/test_tools_basic.py -v
"""

import pytest


def test_article_search_tool_can_execute():
    """Verify ArticleSearchTool executes without errors."""
    from config import config
    from search_tools import ArticleSearchTool
    from vector_store import VectorStore

    store = VectorStore(
        chroma_path=config.CHROMA_PATH,
        embedding_model=config.EMBEDDING_MODEL,
        max_results=config.MAX_RESULTS,
    )

    tool = ArticleSearchTool(store)

    try:
        # Execute a simple search
        result = tool.execute(query="test")
        assert result is not None, "Tool execute returned None"
        assert isinstance(
            result, str
        ), f"Tool result should be string, got {type(result)}"
    except Exception as e:
        pytest.fail(f"ArticleSearchTool.execute() raised exception: {e}")


def test_article_search_tool_with_filter():
    """Verify ArticleSearchTool can handle article_title filter."""
    from config import config
    from search_tools import ArticleSearchTool
    from vector_store import VectorStore

    store = VectorStore(
        chroma_path=config.CHROMA_PATH,
        embedding_model=config.EMBEDDING_MODEL,
        max_results=config.MAX_RESULTS,
    )

    tool = ArticleSearchTool(store)

    # Get an existing article title to use as filter
    titles = store.get_existing_article_titles()
    if len(titles) > 0:
        test_title = titles[0]

        try:
            result = tool.execute(query="test", article_title=test_title)
            assert result is not None, "Tool execute returned None"
            assert isinstance(
                result, str
            ), f"Tool result should be string, got {type(result)}"
        except Exception as e:
            pytest.fail(
                f"ArticleSearchTool.execute() with filter raised exception: {e}"
            )
    else:
        pytest.skip("No articles loaded, skipping filter test")


def test_people_search_tool_can_execute():
    """Verify PeopleSearchTool executes without errors."""
    from config import config
    from search_tools import PeopleSearchTool
    from vector_store import VectorStore

    store = VectorStore(
        chroma_path=config.CHROMA_PATH,
        embedding_model=config.EMBEDDING_MODEL,
        max_results=config.MAX_RESULTS,
    )

    tool = PeopleSearchTool(store)

    try:
        # Execute without parameters (should return all people by frequency)
        result = tool.execute()
        assert result is not None, "Tool execute returned None"
        assert isinstance(
            result, str
        ), f"Tool result should be string, got {type(result)}"
    except Exception as e:
        pytest.fail(f"PeopleSearchTool.execute() raised exception: {e}")


def test_people_search_tool_by_article():
    """Verify PeopleSearchTool can search by article_title."""
    from config import config
    from search_tools import PeopleSearchTool
    from vector_store import VectorStore

    store = VectorStore(
        chroma_path=config.CHROMA_PATH,
        embedding_model=config.EMBEDDING_MODEL,
        max_results=config.MAX_RESULTS,
    )

    tool = PeopleSearchTool(store)

    # Get an existing article title
    titles = store.get_existing_article_titles()
    if len(titles) > 0:
        test_title = titles[0]

        try:
            result = tool.execute(article_title=test_title)
            assert result is not None, "Tool execute returned None"
            assert isinstance(
                result, str
            ), f"Tool result should be string, got {type(result)}"
        except Exception as e:
            pytest.fail(f"PeopleSearchTool.execute() by article raised exception: {e}")
    else:
        pytest.skip("No articles loaded, skipping article search test")


def test_article_search_tool_definition_valid():
    """Verify ArticleSearchTool has valid tool definition schema."""
    from config import config
    from search_tools import ArticleSearchTool
    from vector_store import VectorStore

    store = VectorStore(
        chroma_path=config.CHROMA_PATH,
        embedding_model=config.EMBEDDING_MODEL,
        max_results=config.MAX_RESULTS,
    )

    tool = ArticleSearchTool(store)
    definition = tool.get_tool_definition()

    # Check required fields
    assert "name" in definition, "Tool definition missing 'name'"
    assert "description" in definition, "Tool definition missing 'description'"
    assert "input_schema" in definition, "Tool definition missing 'input_schema'"

    # Check name
    assert (
        definition["name"] == "search_news_content"
    ), f"Expected tool name 'search_news_content', got '{definition['name']}'"

    # Check input schema structure
    schema = definition["input_schema"]
    assert "type" in schema, "Input schema missing 'type'"
    assert schema["type"] == "object", "Input schema type should be 'object'"
    assert "properties" in schema, "Input schema missing 'properties'"
    assert "required" in schema, "Input schema missing 'required'"

    # Check required field
    assert "query" in schema["required"], "Input schema should require 'query'"


def test_people_search_tool_definition_valid():
    """Verify PeopleSearchTool has valid tool definition schema."""
    from config import config
    from search_tools import PeopleSearchTool
    from vector_store import VectorStore

    store = VectorStore(
        chroma_path=config.CHROMA_PATH,
        embedding_model=config.EMBEDDING_MODEL,
        max_results=config.MAX_RESULTS,
    )

    tool = PeopleSearchTool(store)
    definition = tool.get_tool_definition()

    # Check required fields
    assert "name" in definition, "Tool definition missing 'name'"
    assert "description" in definition, "Tool definition missing 'description'"
    assert "input_schema" in definition, "Tool definition missing 'input_schema'"

    # Check name
    assert (
        definition["name"] == "search_people_in_articles"
    ), f"Expected tool name 'search_people_in_articles', got '{definition['name']}'"

    # Check input schema structure
    schema = definition["input_schema"]
    assert "type" in schema, "Input schema missing 'type'"
    assert schema["type"] == "object", "Input schema type should be 'object'"
    assert "properties" in schema, "Input schema missing 'properties'"
    assert "required" in schema, "Input schema missing 'required'"

    # This tool should have no required fields (all parameters optional)
    assert (
        len(schema["required"]) == 0
    ), f"PeopleSearchTool should have no required fields, found: {schema['required']}"


def test_tool_manager_can_register_tools():
    """Verify ToolManager can register and manage tools."""
    from config import config
    from search_tools import ArticleSearchTool, PeopleSearchTool, ToolManager
    from vector_store import VectorStore

    store = VectorStore(
        chroma_path=config.CHROMA_PATH,
        embedding_model=config.EMBEDDING_MODEL,
        max_results=config.MAX_RESULTS,
    )

    manager = ToolManager()

    # Register article search tool
    article_tool = ArticleSearchTool(store)
    manager.register_tool(article_tool)

    # Register people search tool
    people_tool = PeopleSearchTool(store)
    manager.register_tool(people_tool)

    # Get tool definitions
    definitions = manager.get_tool_definitions()
    assert len(definitions) == 2, f"Expected 2 tools, got {len(definitions)}"

    # Check tool names
    tool_names = [d["name"] for d in definitions]
    assert "search_news_content" in tool_names, "ArticleSearchTool not registered"
    assert "search_people_in_articles" in tool_names, "PeopleSearchTool not registered"


def test_tool_manager_can_execute_tools():
    """Verify ToolManager can execute registered tools."""
    from config import config
    from search_tools import ArticleSearchTool, PeopleSearchTool, ToolManager
    from vector_store import VectorStore

    store = VectorStore(
        chroma_path=config.CHROMA_PATH,
        embedding_model=config.EMBEDDING_MODEL,
        max_results=config.MAX_RESULTS,
    )

    manager = ToolManager()
    article_tool = ArticleSearchTool(store)
    people_tool = PeopleSearchTool(store)

    manager.register_tool(article_tool)
    manager.register_tool(people_tool)

    # Try executing article search tool
    try:
        result = manager.execute_tool("search_news_content", query="test")
        assert result is not None, "Tool execution returned None"
        assert isinstance(
            result, str
        ), f"Tool result should be string, got {type(result)}"
    except Exception as e:
        pytest.fail(f"ToolManager.execute_tool() raised exception: {e}")

    # Try executing people search tool
    try:
        result = manager.execute_tool("search_people_in_articles")
        assert result is not None, "Tool execution returned None"
        assert isinstance(
            result, str
        ), f"Tool result should be string, got {type(result)}"
    except Exception as e:
        pytest.fail(
            f"ToolManager.execute_tool() for people search raised exception: {e}"
        )


def test_tools_track_sources():
    """Verify tools properly track sources for UI display."""
    from config import config
    from search_tools import ArticleSearchTool, PeopleSearchTool
    from vector_store import VectorStore

    store = VectorStore(
        chroma_path=config.CHROMA_PATH,
        embedding_model=config.EMBEDDING_MODEL,
        max_results=config.MAX_RESULTS,
    )

    # Test ArticleSearchTool
    article_tool = ArticleSearchTool(store)
    article_tool.execute(query="test")

    assert hasattr(
        article_tool, "last_sources"
    ), "ArticleSearchTool missing last_sources attribute"
    assert isinstance(article_tool.last_sources, list), "last_sources should be a list"

    # Test PeopleSearchTool
    people_tool = PeopleSearchTool(store)
    people_tool.execute()

    assert hasattr(
        people_tool, "last_sources"
    ), "PeopleSearchTool missing last_sources attribute"
    assert isinstance(people_tool.last_sources, list), "last_sources should be a list"


if __name__ == "__main__":
    # Allow running tests directly with: python test_tools_basic.py
    pytest.main([__file__, "-v"])
